"""
GPT Realtime API executor for low-latency voice command processing.

Audio streams to GPT's persistent WebSocket during recording so processing
starts before the user finishes speaking.  Text-only responses (no audio
output from GPT) -- the existing TTS pipeline speaks the result.

Flow:
1. Button held → mic captures PCM chunks → stream_audio_chunk() resamples
   and sends to WebSocket
2. Button released → commit audio buffer → response.create
3. GPT processes → tool call loop → text response
4. Existing TTS speaks the response
"""

import asyncio
import base64
import json
import threading
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import numpy as np

from brain.tools.registry import ToolRegistry
from brain.prompts.agent.agent_prompt_realtime import get_realtime_system_prompt


@dataclass
class AgentStep:
    """A single step in agent execution (matches AgentExecutor format)."""
    turn: int
    step_type: str
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None


class RealtimeAgentExecutor:
    """
    GPT Realtime API executor.

    Maintains a persistent WebSocket connection.  Audio is streamed in
    real-time during recording, then committed and processed with tool
    calls before returning a text response.
    """

    def __init__(
        self,
        state_machine=None,
        openai_api_key: str = None,
        model: str = "gpt-4o-realtime-preview",
        verbose: bool = False,
        speech_instructions: str = None,
        representation_version: str = "stdlib",
        on_message_ready: callable = None,
        vision_config: dict = None,
        control_mode: str = "default",
        num_pixels: int = 0,
        mic_sample_rate: int = 44100,
    ):
        self.state_machine = state_machine
        self.openai_api_key = openai_api_key
        self.model = model
        self.verbose = verbose
        self.speech_instructions = speech_instructions
        self.representation_version = representation_version
        self.on_message_ready = on_message_ready
        self.vision_config = vision_config
        self.control_mode = control_mode
        self.num_pixels = num_pixels
        self.mic_sample_rate = mic_sample_rate

        # Tool registry
        self.tools = ToolRegistry(state_machine, api_key=None, vision_config=vision_config)

        # Step collection (verbose/logging)
        self.steps: List[AgentStep] = []

        # WebSocket connection (lazy)
        self._conn = None
        self._conn_lock = threading.Lock()

        # Background asyncio loop for thread-safe WebSocket sends
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()

        print(f"RealtimeAgentExecutor initialized (model={model}, mic={mic_sample_rate}Hz)")

    # ------------------------------------------------------------------
    # Background event loop
    # ------------------------------------------------------------------

    def _start_event_loop(self):
        """Start a background asyncio event loop for WebSocket operations."""
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever, daemon=True
        )
        self._loop_thread.start()

    def _run_coro(self, coro):
        """Run a coroutine on the background event loop and return result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_connected(self):
        """Ensure the WebSocket is connected, reconnecting if needed."""
        with self._conn_lock:
            if self._conn is not None:
                return
            self._connect()

    def _connect(self):
        """Open a new WebSocket connection and configure the session."""
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_api_key)

        if self.verbose:
            print(f"[Realtime] Connecting to {self.model}...")

        mgr = client.beta.realtime.connect(model=self.model)
        self._conn = mgr.enter()

        # Build system prompt
        system_state = self._get_system_state()
        instructions = get_realtime_system_prompt(
            system_state=system_state,
            representation_version=self.representation_version,
            vision_config=self.vision_config,
            control_mode=self.control_mode,
            num_pixels=self.num_pixels,
        )
        if self.speech_instructions:
            instructions += f"\n\n## Speech Output\n{self.speech_instructions}"

        # Configure session: text-only output, tools, no VAD (manual commit)
        tool_defs = self.tools.get_openai_tool_definitions()
        self._conn.session.update(session={
            "modalities": ["text"],
            "instructions": instructions,
            "tools": tool_defs,
            "turn_detection": None,  # manual mode
            "input_audio_format": "pcm16",
        })

        # Drain the session.updated confirmation event
        for event in self._conn:
            if event.type == "session.updated":
                break

        if self.verbose:
            print(f"[Realtime] Connected, {len(tool_defs)} tools registered")

    def _disconnect(self):
        """Close the WebSocket connection."""
        with self._conn_lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
                if self.verbose:
                    print("[Realtime] Disconnected")

    # ------------------------------------------------------------------
    # Audio streaming
    # ------------------------------------------------------------------

    def stream_audio_chunk(self, pcm_data: bytes):
        """
        Stream a PCM16 audio chunk to the Realtime API.

        Called from the PyAudio callback thread via the mic controller.
        Resamples from mic_sample_rate to 24kHz, base64-encodes, and sends.

        Args:
            pcm_data: Raw 16-bit mono PCM audio bytes at mic_sample_rate
        """
        try:
            self._ensure_connected()
            resampled = resample_pcm16(pcm_data, self.mic_sample_rate, 24000)
            encoded = base64.b64encode(resampled).decode("ascii")
            self._conn.input_audio_buffer.append(audio=encoded)
        except Exception as e:
            if self.verbose:
                print(f"[Realtime] stream_audio_chunk error: {e}")
            # Mark connection as dead so next call reconnects
            self._conn = None

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def run(self, user_input: str = None) -> str:
        """
        Process a text command via the Realtime API.

        Matches the AgentExecutor.run() interface (async, takes text).
        For audio, use process_audio() instead.

        Args:
            user_input: Text command (sent as a text conversation item)

        Returns:
            Final message string for TTS
        """
        self.steps = []

        try:
            self._ensure_connected()
            self.update_session()

            if user_input:
                self._conn.conversation.item.create(item={
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_input}],
                })
            else:
                self._conn.input_audio_buffer.commit()

            self._conn.response.create()
            message = self._process_response_loop(0)
            self._run_safety_check()
            return message

        except Exception as e:
            if self.verbose:
                print(f"[Realtime] run error: {e}")
            self._conn = None
            return f"Error: {str(e)}"

    def process_audio(self) -> str:
        """
        Commit streamed audio and process response synchronously.

        Called from main.py after recording stops.
        Returns the agent's text response message.
        """
        self.steps = []
        turn = 0

        try:
            self._ensure_connected()
            self._conn.input_audio_buffer.commit()
            self._conn.response.create()
            message = self._process_response_loop(turn)

            # Fire message ready callback for early TTS
            if self.on_message_ready and message:
                self.on_message_ready(message)

            # Safety check
            self._run_safety_check()
            return message

        except Exception as e:
            if self.verbose:
                print(f"[Realtime] process_audio error: {e}")
            self._conn = None
            return f"Error: {str(e)}"

    def _process_response_loop(self, turn: int) -> str:
        """
        Read events from the WebSocket, handle tool calls, return final text.

        The loop continues until a response.done event with no pending
        function_call items, or until done() is called.
        """
        max_rounds = 10
        for round_num in range(max_rounds):
            response_event = self._wait_for_response_done()
            if response_event is None:
                return "Error: no response from GPT Realtime"

            turn += 1
            response = response_event.response

            self.steps.append(AgentStep(
                turn=turn,
                step_type="api_timing",
                content=f"Response round {round_num + 1} (status={response.status})",
            ))

            if self.verbose:
                print(f"[Realtime] Response round {round_num + 1}, "
                      f"status={response.status}, "
                      f"output_items={len(response.output or [])}")

            # Separate function_call items from message items
            function_calls = []
            text_message = ""

            for item in (response.output or []):
                if item.type == "function_call":
                    function_calls.append(item)
                elif item.type == "message":
                    for content in (item.content or []):
                        if hasattr(content, "text") and content.text:
                            text_message = content.text

            if not function_calls:
                # No tool calls — we're done
                if self.verbose and text_message:
                    print(f"[Realtime] Final message: {text_message[:100]}")
                return text_message or "Done"

            # Execute tool calls
            for fc in function_calls:
                tool_name = fc.name
                try:
                    tool_input = json.loads(fc.arguments) if fc.arguments else {}
                except json.JSONDecodeError:
                    tool_input = {}

                self.steps.append(AgentStep(
                    turn=turn,
                    step_type="tool_call",
                    tool_name=tool_name,
                    tool_input=tool_input,
                ))

                if self.verbose:
                    input_str = json.dumps(tool_input)
                    if len(input_str) > 200:
                        input_str = input_str[:200] + "..."
                    print(f"[Realtime] Tool: {tool_name} | Input: {input_str}")

                # Execute tool (tools.execute is async)
                tool_start = time.time()
                result = asyncio.run(self.tools.execute(tool_name, tool_input))
                tool_ms = (time.time() - tool_start) * 1000

                self.steps.append(AgentStep(
                    turn=turn,
                    step_type="tool_result",
                    tool_name=tool_name,
                    tool_result=result,
                    duration_ms=tool_ms,
                ))

                if self.verbose:
                    result_str = json.dumps(result)
                    if len(result_str) > 200:
                        result_str = result_str[:200] + "..."
                    print(f"[Realtime]   Result: {result_str} ({tool_ms:.0f}ms)")

                # Check if done() was called
                if result.get("done"):
                    message = result.get("message", "Done")
                    self.steps.append(AgentStep(
                        turn=turn, step_type="done", content=message
                    ))
                    if self.verbose:
                        print(f"[Realtime] Agent finished: {message[:100]}")
                    return message

                # Send function call output back
                self._conn.conversation.item.create(item={
                    "type": "function_call_output",
                    "call_id": fc.call_id,
                    "output": json.dumps(result),
                })

            # Ask for another response (model may want to call more tools)
            self._conn.response.create()

        return "Max tool call rounds reached."

    def _wait_for_response_done(self):
        """Block until a response.done event is received."""
        for event in self._conn:
            if self.verbose and event.type not in (
                "response.output_item.added",
                "response.content_part.added",
                "response.text.delta",
                "response.text.done",
                "response.content_part.done",
                "response.output_item.done",
                "response.function_call_arguments.delta",
                "response.function_call_arguments.done",
            ):
                print(f"[Realtime] Event: {event.type}")
            if event.type == "response.done":
                return event
            if event.type == "error":
                error_msg = getattr(event, "error", {})
                if self.verbose:
                    print(f"[Realtime] Error event: {error_msg}")
                return None
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_system_state(self) -> str:
        """Get current system state for the prompt."""
        if not self.state_machine:
            return "No state machine configured."

        states = self.state_machine.get_state_list()
        rules = [r.to_dict() for r in self.state_machine.get_rules()]
        variables = dict(self.state_machine.state_data)
        current = self.state_machine.current_state

        return (
            f"Current state: {current}\n"
            f"States: {json.dumps(states, indent=2)}\n"
            f"Rules ({len(rules)} total):\n{json.dumps(rules, indent=2)}\n"
            f"Variables: {json.dumps(variables, indent=2)}"
        )

    def _run_safety_check(self):
        """Run safety check to ensure all states have exit rules."""
        result = self.tools.run_safety_check()
        if self.verbose and result.get("rules_added", 0) > 0:
            print(f"[Realtime] Safety check: Added {result['rules_added']} exit rule(s)")

    def get_steps(self) -> List[Dict[str, Any]]:
        """Get steps as dicts for JSON serialization."""
        return [asdict(step) for step in self.steps]

    def update_session(self):
        """
        Update the session instructions with current state.

        Call this before each interaction to ensure the model has fresh state.
        """
        if self._conn is None:
            return

        system_state = self._get_system_state()
        instructions = get_realtime_system_prompt(
            system_state=system_state,
            representation_version=self.representation_version,
            vision_config=self.vision_config,
            control_mode=self.control_mode,
            num_pixels=self.num_pixels,
        )
        if self.speech_instructions:
            instructions += f"\n\n## Speech Output\n{self.speech_instructions}"

        tool_defs = self.tools.get_openai_tool_definitions()
        self._conn.session.update(session={
            "instructions": instructions,
            "tools": tool_defs,
        })

        # Drain the session.updated event
        for event in self._conn:
            if event.type == "session.updated":
                break


# ======================================================================
# Audio resampling
# ======================================================================

def resample_pcm16(pcm_data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """
    Resample 16-bit mono PCM audio from src_rate to dst_rate.

    Uses numpy linear interpolation for speed.

    Args:
        pcm_data: Raw 16-bit LE PCM bytes
        src_rate: Source sample rate (e.g. 44100)
        dst_rate: Destination sample rate (e.g. 24000)

    Returns:
        Resampled 16-bit LE PCM bytes
    """
    if src_rate == dst_rate:
        return pcm_data

    samples = np.frombuffer(pcm_data, dtype=np.int16)
    if len(samples) == 0:
        return pcm_data

    # Calculate output length
    duration = len(samples) / src_rate
    out_len = int(duration * dst_rate)
    if out_len == 0:
        return b""

    # Linear interpolation
    src_indices = np.linspace(0, len(samples) - 1, out_len)
    resampled = np.interp(src_indices, np.arange(len(samples)), samples.astype(np.float64))

    return resampled.astype(np.int16).tobytes()
