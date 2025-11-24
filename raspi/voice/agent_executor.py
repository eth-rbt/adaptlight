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
from typing import Dict, Any, List, Optional

from .tool_registry import ToolRegistry
from prompts.agent_prompt import get_agent_system_prompt


class AgentExecutor:
    """Multi-turn agent executor for voice commands."""

    def __init__(self, state_machine=None, api_key: str = None, model: str = "claude-sonnet-4-20250514",
                 max_turns: int = 10, verbose: bool = False):
        """
        Initialize agent executor.

        Args:
            state_machine: StateMachine instance to operate on
            api_key: Anthropic API key
            model: Claude model to use
            max_turns: Maximum turns before stopping (safety limit)
            verbose: Print debug information
        """
        self.state_machine = state_machine
        self.api_key = api_key
        self.model = model
        self.max_turns = max_turns
        self.verbose = verbose

        # Initialize tool registry
        self.tools = ToolRegistry(state_machine)

        # Initialize Claude client
        self.client = None
        if api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=api_key)
                print(f"AgentExecutor initialized with model: {model}")
            except ImportError:
                print("Warning: Anthropic library not available. Install with: pip install anthropic")

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
        return get_agent_system_prompt(system_state)

    async def run(self, user_input: str) -> str:
        """
        Run the agent loop for a user input.

        Args:
            user_input: Natural language command from user

        Returns:
            Final message to show user
        """
        if not self.client:
            return "Error: Claude client not initialized. Check API key."

        messages = [
            {"role": "user", "content": user_input}
        ]

        system_prompt = self._build_system_prompt()

        for turn in range(self.max_turns):
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"Turn {turn + 1}/{self.max_turns}")
                print(f"{'='*60}")

            try:
                # Call Claude with tools
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    tools=self.tools.get_tool_definitions()
                )

                if self.verbose:
                    print(f"Stop reason: {response.stop_reason}")

                # Process response content
                assistant_content = []
                tool_results = []

                for block in response.content:
                    if block.type == "text":
                        if self.verbose:
                            print(f"Claude: {block.text}")
                        assistant_content.append(block)

                    elif block.type == "tool_use":
                        if self.verbose:
                            print(f"Tool call: {block.name}({json.dumps(block.input)})")

                        # Execute the tool
                        result = await self.tools.execute(block.name, block.input)

                        if self.verbose:
                            print(f"Result: {json.dumps(result)}")

                        assistant_content.append(block)

                        # Check if done
                        if result.get("done"):
                            return result.get("message", "Done")

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
                        for block in response.content:
                            if block.type == "text":
                                return block.text
                        return "Completed (no message)"

            except Exception as e:
                if self.verbose:
                    print(f"Error: {e}")
                return f"Error: {str(e)}"

        return f"Max turns ({self.max_turns}) reached. The request may be too complex."

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
