"""
State Machine Generator for AdaptLight.

The SMgenerator class provides a single entry point for:
- Processing user input (voice commands, text)
- Managing state machine
- Emitting events via hooks for app-specific feedback

Supports two processing modes:
- agent: Multi-turn Claude conversation with tool calls
- parser: Single-shot OpenAI parsing to tool calls
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import inspect


@dataclass
class SMResult:
    """Result from SMgenerator processing."""
    success: bool
    state: Dict[str, Any]
    message: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_steps: List[Dict[str, Any]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.success

    @classmethod
    def from_error(cls, error: Exception, state: Dict[str, Any], run_id: str = None) -> 'SMResult':
        """Create an SMResult from an exception."""
        return cls(
            success=False,
            state=state,
            message=str(error),
            error=str(error),
            run_id=run_id or str(uuid.uuid4())[:8]
        )


class SMgenerator:
    """
    State Machine Generator - unified interface to the AdaptLight state machine.

    Supports two processing modes:
    - agent: Multi-turn Claude conversation with tool calls
    - parser: Single-shot OpenAI parsing to tool calls

    Emits events via hooks for app-specific feedback.

    Example usage:
        smgen = SMgenerator({
            'mode': 'agent',
            'model': 'claude-haiku-4-5',
            'anthropic_api_key': 'sk-ant-...',
        })

        # Register hooks
        smgen.on('processing_start', lambda d: print(f"Starting: {d['input']}"))
        smgen.on('processing_end', lambda d: print(f"Done in {d['total_ms']:.0f}ms"))

        # Process input
        result = smgen.process("turn the light red")
        print(result.state)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SMgenerator with configuration.

        Args:
            config: Configuration dictionary with keys:
                - mode: 'agent' or 'parser' (default: 'agent')
                - model: Model name (default: 'claude-haiku-4-5')
                - prompt_variant: 'examples' or 'concise' (default: 'examples')
                - max_turns: Max agent turns (default: 10)
                - verbose: Enable verbose output (default: False)
                - anthropic_api_key: API key for Claude (required for agent mode)
                - openai_api_key: API key for OpenAI (required for parser mode)
                - storage_dir: Directory for memory/pipeline storage (optional)
                - representation_version: State representation ('original', 'pure_python', 'stdlib')
        """
        self.config = config
        self.hooks: Dict[str, List[Callable]] = {}
        self._last_tool_calls: List[Dict] = []

        # Get representation version
        self.representation_version = config.get('representation_version', 'stdlib')

        # Configure storage if provided
        storage_dir = config.get('storage_dir')
        if storage_dir:
            from brain.core.memory import set_memory_storage_dir
            from brain.core.pipeline_registry import set_pipeline_storage_dir
            set_memory_storage_dir(storage_dir)
            set_pipeline_storage_dir(storage_dir)

        # Initialize core state machine with representation version
        from brain.core.state_machine import StateMachine
        self.state_machine = StateMachine(
            debug=config.get('verbose', False),
            representation_version=self.representation_version
        )

        # Initialize tool registry with vision capabilities
        from brain.tools.registry import ToolRegistry
        self.tools = ToolRegistry(
            state_machine=self.state_machine,
            api_key=config.get('anthropic_api_key'),
            vision_config=config.get('vision_config')
        )

        # Initialize processor based on mode
        mode = config.get('mode', 'agent')
        speech_mode = config.get('speech_mode', 'default')
        self.mode = mode
        self.speech_mode = speech_mode

        if mode == 'agent':
            # Check if parallel speech mode is enabled
            if speech_mode == 'parallel':
                from brain.processing.parallel_agent import ParallelAgentExecutor
                self.processor = ParallelAgentExecutor(
                    state_machine=self.state_machine,
                    api_key=config.get('anthropic_api_key'),
                    model=config.get('model', 'claude-haiku-4-5'),
                    verbose=config.get('verbose', False),
                    prompt_variant=config.get('prompt_variant', 'examples'),
                    speech_instructions=config.get('speech_instructions'),
                    representation_version=self.representation_version,
                    on_message_ready=lambda msg: self._emit('message_ready', {'message': msg})
                )
            else:
                from brain.processing.agent import AgentExecutor
                self.processor = AgentExecutor(
                    state_machine=self.state_machine,
                    api_key=config.get('anthropic_api_key'),
                    model=config.get('model', 'claude-haiku-4-5'),
                    max_turns=config.get('max_turns', 10),
                    verbose=config.get('verbose', False),
                    prompt_variant=config.get('prompt_variant', 'examples'),
                    speech_instructions=config.get('speech_instructions'),
                    representation_version=self.representation_version,
                    on_message_ready=lambda msg: self._emit('message_ready', {'message': msg})
                )
        else:
            from brain.processing.parser import CommandParser
            self.processor = CommandParser(
                api_key=config.get('openai_api_key'),
                model=config.get('model', 'gpt-4o'),
                prompt_variant=config.get('prompt_variant', 'full')
            )

    # ─────────────────────────────────────────────────────────────
    # Hook System
    # ─────────────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable) -> None:
        """
        Register a callback for an event.

        Events:
        - processing_start: {input: str, run_id: str}
        - processing_end: {result: SMResult, total_ms: float, run_id: str}
        - tool_start: {tool: str, input: dict, run_id: str}
        - tool_end: {tool: str, result: dict, duration_ms: float, run_id: str}
        - llm_call_start: {run_id: str}
        - llm_call_end: {duration_ms: float, run_id: str}
        - error: {error: str, run_id: str}
        """
        self.hooks.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """Unregister a callback."""
        if event in self.hooks and callback in self.hooks[event]:
            self.hooks[event].remove(callback)

    def _emit(self, event: str, data: Dict[str, Any] = None) -> None:
        """
        Emit an event to all registered callbacks.

        Supports both sync and async callbacks.
        Hook errors are caught and logged, not propagated.
        """
        for callback in self.hooks.get(event, []):
            try:
                result = callback(data or {})
                # If callback is async, run it
                if inspect.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception as e:
                print(f"Hook error ({event}): {e}")

    # ─────────────────────────────────────────────────────────────
    # Main Interface
    # ─────────────────────────────────────────────────────────────

    def process(self, text: str) -> SMResult:
        """
        Process user input and return result.

        This is a synchronous method that internally handles async processing.

        Args:
            text: User input text

        Returns:
            SMResult with state, message, tool_calls, timing
        """
        run_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        timing = {}
        self._last_tool_calls = []

        self._emit('processing_start', {'input': text, 'run_id': run_id})

        try:
            # Run the processor
            agent_steps = []
            if self.mode == 'agent':
                # Agent mode is async
                message, agent_steps = asyncio.run(self._run_agent(text, run_id, timing))
            else:
                # Parser mode is sync
                message = self._run_parser(text, run_id, timing)

            total_ms = (time.time() - start_time) * 1000
            timing['total_ms'] = total_ms

            result = SMResult(
                success=True,
                state=self._get_state_dict(),
                message=message,
                tool_calls=self._last_tool_calls,
                timing=timing,
                run_id=run_id,
                agent_steps=agent_steps
            )

            self._emit('processing_end', {
                'result': result,
                'total_ms': total_ms,
                'run_id': run_id
            })

            return result

        except Exception as e:
            self._emit('error', {'error': str(e), 'run_id': run_id})

            total_ms = (time.time() - start_time) * 1000
            timing['total_ms'] = total_ms

            result = SMResult.from_error(e, self._get_state_dict(), run_id)
            result.timing = timing

            self._emit('processing_end', {
                'result': result,
                'total_ms': total_ms,
                'run_id': run_id
            })

            raise

    async def _run_agent(self, text: str, run_id: str, timing: Dict) -> tuple:
        """Run agent processor with hook emissions.

        Returns:
            tuple: (message, agent_steps)
        """
        agent_start = time.time()
        result = await self.processor.run(text)
        timing['agent_ms'] = (time.time() - agent_start) * 1000

        # Get agent steps for verbose output
        steps = self.processor.get_steps() if hasattr(self.processor, 'get_steps') else []
        return result, steps

    def _run_parser(self, text: str, run_id: str, timing: Dict) -> str:
        """Run parser processor with hook emissions."""
        # Parser mode - single API call
        parser_start = time.time()

        # Get current state info for parser
        current_state = self.state_machine.get_state()
        available_states = self.state_machine.states.get_states_for_prompt()
        current_rules = [str(r) for r in self.state_machine.get_rules()]

        result = self.processor.parse(
            text,
            current_state=current_state,
            available_states=available_states,
            current_rules=current_rules
        )

        timing['parser_ms'] = (time.time() - parser_start) * 1000

        # Execute the tool calls from parser result
        if result and 'tool_calls' in result:
            for tool_call in result['tool_calls']:
                tool_name = tool_call.get('name')
                tool_input = tool_call.get('input', {})

                self._emit('tool_start', {
                    'tool': tool_name,
                    'input': tool_input,
                    'run_id': run_id
                })

                tool_start = time.time()
                tool_result = asyncio.run(self.tools.execute(tool_name, tool_input))
                tool_ms = (time.time() - tool_start) * 1000

                self._last_tool_calls.append({
                    'name': tool_name,
                    'input': tool_input,
                    'result': tool_result,
                    'duration_ms': tool_ms
                })

                self._emit('tool_end', {
                    'tool': tool_name,
                    'result': tool_result,
                    'duration_ms': tool_ms,
                    'run_id': run_id
                })

        return result.get('message', '') if result else ''

    def trigger(self, event: str) -> Dict[str, Any]:
        """
        Trigger a state machine event (button_click, etc.).

        Args:
            event: Event name (button_click, button_hold, etc.)

        Returns:
            Current state dict after transition
        """
        self.state_machine.execute_transition(event)
        return self._get_state_dict()

    def get_state(self) -> Dict[str, Any]:
        """Get current state for rendering."""
        return self._get_state_dict()

    def _get_state_dict(self) -> Dict[str, Any]:
        """Get current state as a dictionary."""
        state_name = self.state_machine.get_state()
        state_obj = self.state_machine.get_state_object(state_name)
        current_rgb = self.state_machine.get_current_rgb()

        if state_obj:
            return {
                'name': state_name,
                'r': state_obj.r,
                'g': state_obj.g,
                'b': state_obj.b,
                'speed': state_obj.speed,
                'code': state_obj.code,
                'audio_reactive': state_obj.audio_reactive,
                'volume_reactive': state_obj.volume_reactive,
                'vision_reactive': state_obj.vision_reactive,
                'api_reactive': state_obj.api_reactive,
                'current_rgb': current_rgb,
            }
        else:
            # Built-in state without object
            return {
                'name': state_name,
                'r': 255 if state_name == 'on' else 0,
                'g': 255 if state_name == 'on' else 0,
                'b': 255 if state_name == 'on' else 0,
                'speed': None,
                'code': None,
                'audio_reactive': {},
                'volume_reactive': {},
                'vision_reactive': {},
                'api_reactive': {},
                'current_rgb': current_rgb,
            }

    def reset(self) -> None:
        """Reset state machine to initial state."""
        self.state_machine.reset()

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the state machine generator state."""
        return {
            'mode': self.mode,
            'current_state': self.state_machine.get_state(),
            'rules_count': len(self.state_machine.rules),
            'states_count': len(self.state_machine.states.get_states()),
            'tools_count': len(self.tools.tools),
        }

    def get_details(self) -> Dict[str, Any]:
        """Get detailed state machine info including all states and rules."""
        # Built-in default states
        states = [
            {
                'name': 'off',
                'r': 0,
                'g': 0,
                'b': 0,
                'speed': None,
                'code': None,
                'description': 'Light off (built-in)',
            },
            {
                'name': 'on',
                'r': 255,
                'g': 255,
                'b': 255,
                'speed': None,
                'code': None,
                'description': 'Light on (built-in)',
            },
        ]

        # Add user-created states
        for state in self.state_machine.states.get_states():
            # Skip if it overwrites a built-in
            states = [s for s in states if s['name'] != state.name]
            states.append({
                'name': state.name,
                'r': state.r,
                'g': state.g,
                'b': state.b,
                'speed': state.speed,
                'code': state.code,
                'audio_reactive': state.audio_reactive,
                'volume_reactive': state.volume_reactive,
                'vision_reactive': state.vision_reactive,
                'api_reactive': state.api_reactive,
                'description': state.description,
            })

        # Get all rules
        rules = []
        for rule in self.state_machine.rules:
            rules.append({
                'from': rule.state1,
                'on': rule.transition,
                'to': rule.state2,
                'condition': rule.condition,
                'action': rule.action,
                'priority': rule.priority,
                'enabled': rule.enabled,
                'pipeline': rule.pipeline,
                'trigger_config': rule.trigger_config,
            })

        return {
            'current_state': self.state_machine.get_state(),
            'states': states,
            'rules': rules,
        }
