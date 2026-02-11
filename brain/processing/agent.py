"""
Agent executor for multi-turn agentic voice command processing.

Replaces single-shot parsing with a multi-turn agent loop where Claude
iterates until the task is complete, calling tools as needed.

Flow:
1. User speaks command
2. Agent loop:
   - Claude thinks about next step
   - Claude calls tool(s)
   - Execute tool(s), return results
   - Repeat until done() is called
3. Return final message to user
"""

import json
import asyncio
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional

from brain.tools.registry import ToolRegistry


@dataclass
class AgentStep:
    """A single step in agent execution."""
    turn: int
    step_type: str  # "thinking", "tool_call", "tool_result", "api_timing", "done"
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
from brain.prompts.agent import get_agent_system_prompt, get_agent_system_prompt_with_examples


class AgentExecutor:
    """Multi-turn agent executor for voice commands."""

    def __init__(self, state_machine=None, api_key: str = None, model: str = "claude-sonnet-4-20250514",
                 max_turns: int = 10, verbose: bool = False, prompt_variant: str = "examples",
                 speech_instructions: str = None, representation_version: str = "stdlib",
                 on_message_ready: callable = None):
        """
        Initialize agent executor.

        Args:
            state_machine: StateMachine instance to operate on
            api_key: Anthropic API key
            model: Claude model to use
            max_turns: Maximum turns before stopping (safety limit)
            verbose: Print debug information
            prompt_variant: 'concise' or 'examples' (default: examples)
            speech_instructions: Extra instructions for speech output (e.g., "Keep responses under 2 sentences")
            representation_version: State representation ('original', 'pure_python', 'stdlib')
            on_message_ready: Callback when message is ready (before safety check completes)
        """
        self.state_machine = state_machine
        self.api_key = api_key
        self.model = model
        self.max_turns = max_turns
        self.verbose = verbose
        self.prompt_variant = prompt_variant
        self.speech_instructions = speech_instructions
        self.representation_version = representation_version
        self.on_message_ready = on_message_ready

        # Initialize tool registry
        self.tools = ToolRegistry(state_machine, api_key=api_key)

        # Step collection for verbose output
        self.steps: List[AgentStep] = []

        # Initialize Claude client
        self.client = None
        if api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=api_key)
                print(f"AgentExecutor initialized with model: {model}")
            except ImportError:
                print("ERROR: Anthropic library not available. Install with: pip install anthropic")
            except Exception as e:
                print(f"ERROR: Failed to initialize Anthropic client: {e}")
        else:
            print("ERROR: No Claude API key provided. Check config.yaml claude.api_key")

    def _get_system_state(self) -> str:
        """Get current system state for prompt injection."""
        if not self.state_machine:
            return "No state machine configured."

        states = self.state_machine.get_state_list()
        rules = [r.to_dict() for r in self.state_machine.get_rules()]
        variables = dict(self.state_machine.state_data)
        current = self.state_machine.current_state

        return f"""Current state: {current}

States: {json.dumps(states, indent=2)}

Rules ({len(rules)} total):
{json.dumps(rules, indent=2)}

Variables: {json.dumps(variables, indent=2)}"""

    def _build_system_prompt(self) -> str:
        """Build the full system prompt with current state."""
        system_state = self._get_system_state()
        if self.prompt_variant == "examples":
            prompt = get_agent_system_prompt_with_examples(system_state, self.representation_version)
        else:
            prompt = get_agent_system_prompt(system_state)

        # Append speech instructions if speech mode is enabled
        if self.speech_instructions:
            prompt += f"\n\n## Speech Output Instructions\n{self.speech_instructions}"

        return prompt

    async def run(self, user_input: str) -> str:
        """
        Run the agent loop for a user input.

        Args:
            user_input: Natural language command from user

        Returns:
            Final message to show user
        """
        if self.client is None:
            return "Error: Claude client not initialized. Check API key."

        # Reset steps for this run
        self.steps = []

        messages = [
            {"role": "user", "content": user_input}
        ]

        system_prompt = self._build_system_prompt()

        import time

        for turn in range(self.max_turns):
            if self.verbose:
                print(f"\n{'─'*60}")
                print(f"🔄 Turn {turn + 1}/{self.max_turns}")
                print(f"{'─'*60}")

            try:
                # Call Claude with tools
                turn_start = time.time()
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    tools=self.tools.get_tool_definitions()
                )
                api_time = time.time() - turn_start
                api_time_ms = api_time * 1000

                # Record API timing step
                self.steps.append(AgentStep(
                    turn=turn + 1,
                    step_type="api_timing",
                    content=f"API call completed (stop_reason: {response.stop_reason})",
                    duration_ms=api_time_ms
                ))

                if self.verbose:
                    print(f"⏱️  API call: {api_time:.2f}s | Stop: {response.stop_reason}")

                # Process response content
                assistant_content = []
                tool_results = []

                for block in response.content:
                    if block.type == "text":
                        # Record thinking step
                        self.steps.append(AgentStep(
                            turn=turn + 1,
                            step_type="thinking",
                            content=block.text
                        ))
                        if self.verbose:
                            print(f"💭 Thinking: {block.text}")
                        assistant_content.append(block)

                    elif block.type == "tool_use":
                        # Record tool call step
                        self.steps.append(AgentStep(
                            turn=turn + 1,
                            step_type="tool_call",
                            tool_name=block.name,
                            tool_input=block.input
                        ))

                        if self.verbose:
                            # Pretty print tool call
                            input_str = json.dumps(block.input, indent=2)
                            if len(input_str) > 200:
                                input_str = input_str[:200] + "..."
                            print(f"🔧 Tool: {block.name}")
                            print(f"   Input: {input_str}")

                        # Execute the tool
                        tool_start = time.time()
                        result = await self.tools.execute(block.name, block.input)
                        tool_time = time.time() - tool_start
                        tool_time_ms = tool_time * 1000

                        # Record tool result step
                        self.steps.append(AgentStep(
                            turn=turn + 1,
                            step_type="tool_result",
                            tool_name=block.name,
                            tool_result=result,
                            duration_ms=tool_time_ms
                        ))

                        if self.verbose:
                            result_str = json.dumps(result)
                            if len(result_str) > 200:
                                result_str = result_str[:200] + "..."
                            print(f"   Result: {result_str}")
                            print(f"   ⏱️  Tool exec: {tool_time:.3f}s")

                        assistant_content.append(block)

                        # Check if done
                        if result.get("done"):
                            message = result.get("message", "Done")
                            # Record done step
                            self.steps.append(AgentStep(
                                turn=turn + 1,
                                step_type="done",
                                content=message
                            ))
                            if self.verbose:
                                print(f"✅ Agent finished")
                            # Fire message ready callback BEFORE safety check
                            # This allows TTS to start generating while we finish up
                            if self.on_message_ready:
                                self.on_message_ready(message)
                            # Run safety check before returning
                            self._run_safety_check()
                            return message

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })

                # Add assistant message
                messages.append({"role": "assistant", "content": assistant_content})

                # If there were tool calls, add results and continue
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                else:
                    # No tool calls and stop_reason is end_turn - extract message
                    if response.stop_reason == "end_turn":
                        # Run safety check before returning
                        self._run_safety_check()
                        for block in response.content:
                            if block.type == "text":
                                return block.text
                        return "Completed (no message)"

            except Exception as e:
                if self.verbose:
                    print(f"Error: {e}")
                return f"Error: {str(e)}"

        # Run safety check even on max turns
        self._run_safety_check()
        return f"Max turns ({self.max_turns}) reached. The request may be too complex."

    def _run_safety_check(self):
        """Run safety check to ensure all states have exit rules."""
        result = self.tools.run_safety_check()
        if self.verbose and result.get("rules_added", 0) > 0:
            print(f"🛡️  Safety check: Added {result['rules_added']} exit rule(s)")
            for rule in result.get("auto_added_rules", []):
                print(f"   → {rule}")

    def get_steps(self) -> List[Dict[str, Any]]:
        """Get steps as dicts for JSON serialization."""
        return [asdict(step) for step in self.steps]

    def run_sync(self, user_input: str) -> str:
        """
        Synchronous wrapper for run().

        Args:
            user_input: Natural language command from user

        Returns:
            Final message to show user
        """
        return asyncio.run(self.run(user_input))


class MockAgentExecutor:
    """Mock agent executor for testing without API calls."""

    def __init__(self, state_machine=None):
        self.state_machine = state_machine
        self.tools = ToolRegistry(state_machine)
        self.call_log = []

    async def execute_tool(self, name: str, input: Dict) -> Dict:
        """Execute a tool and log the call."""
        self.call_log.append({"tool": name, "input": input})
        return await self.tools.execute(name, input)

    def reset_log(self):
        """Clear the call log."""
        self.call_log = []
