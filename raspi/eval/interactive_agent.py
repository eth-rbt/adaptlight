#!/usr/bin/env python3
"""
Interactive evaluation tool for AgentExecutor (multi-turn agentic mode).

Provides a REPL interface to test the new agent architecture:
- Shows current states, rules, and variables
- Accepts user commands
- Runs multi-turn agent loop
- Displays resulting changes
"""

import sys
import json
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.agent_executor import AgentExecutor
from voice.tool_registry import ToolRegistry
from core.state import State
from core.state_machine import StateMachine


class InteractiveAgentEvaluator:
    """Interactive REPL for testing the agent executor."""

    def __init__(self, api_key, model='claude-sonnet-4-20250514', verbose=False):
        """Initialize the interactive evaluator."""
        # Initialize state machine
        self.state_machine = StateMachine()
        self._initialize_default_states()
        self._initialize_default_rules()

        # Initialize agent executor
        self.executor = AgentExecutor(
            state_machine=self.state_machine,
            api_key=api_key,
            model=model,
            max_turns=10,
            verbose=verbose
        )

        self.verbose = verbose

    def _initialize_default_states(self):
        """Initialize with default states."""
        self.state_machine.states.add_state(State('off', r=0, g=0, b=0, description='LEDs off'))
        self.state_machine.states.add_state(State('on', r=255, g=255, b=255, description='White light'))

    def _initialize_default_rules(self):
        """Add default on/off toggle rules."""
        self.state_machine.add_rule({
            "from": "off",
            "on": "button_click",
            "to": "on"
        })
        self.state_machine.add_rule({
            "from": "on",
            "on": "button_click",
            "to": "off"
        })

    def _print_separator(self, char='=', length=70):
        """Print a separator line."""
        print(char * length)

    def _print_current_state(self):
        """Print the current state machine state."""
        print(f"\n📍 CURRENT STATE: {self.state_machine.current_state}")

    def _print_states(self):
        """Print all registered states."""
        states = self.state_machine.states.get_states()
        print(f"\n🎨 REGISTERED STATES ({len(states)} states):")
        for state in states:
            params = []
            if state.r is not None:
                params.append(f"r={state.r}")
            if state.g is not None:
                params.append(f"g={state.g}")
            if state.b is not None:
                params.append(f"b={state.b}")
            if state.speed is not None:
                params.append(f"speed={state.speed}ms")

            param_str = ", ".join(params) if params else "no params"
            print(f"  • {state.name}: {param_str}")
            if state.description:
                print(f"    └─ {state.description}")

    def _print_rules(self):
        """Print current rules."""
        rules = self.state_machine.get_rules()
        print(f"\n📋 RULES ({len(rules)} rules):")
        if not rules:
            print("  (no rules)")
            return

        for idx, rule in enumerate(rules):
            state1 = rule.state1
            transition = rule.transition
            state2 = rule.state2
            condition = rule.condition
            action = rule.action
            priority = rule.priority

            rule_str = f"  [{idx}] {state1} --[{transition}]--> {state2}"

            if priority != 0:
                rule_str += f" (priority: {priority})"
            if condition:
                rule_str += f"\n      └─ if: {condition}"
            if action:
                rule_str += f"\n      └─ action: {action}"

            print(rule_str)

    def _print_variables(self):
        """Print current variables."""
        variables = self.state_machine.state_data
        print(f"\n💾 VARIABLES ({len(variables)} variables):")
        if not variables:
            print("  (no variables)")
            return

        for key, value in variables.items():
            print(f"  • {key}: {value}")

    def _print_custom_tools(self):
        """Print registered custom tools."""
        tools = self.executor.tools.custom_tool_executor.list_tools()
        # Filter out built-in tools
        builtin = {'fetch_json', 'fetch_text', 'get_weather', 'get_time', 'random_number', 'delay'}
        custom = [t for t in tools if t not in builtin]

        if custom:
            print(f"\n🔧 CUSTOM TOOLS ({len(custom)} tools):")
            for name in custom:
                tool = self.executor.tools.custom_tool_executor.get_tool(name)
                desc = tool.get('description', 'No description')
                print(f"  • {name}: {desc}")

    def _print_data_sources(self):
        """Print registered data sources."""
        sources = self.executor.tools.data_source_manager.list_sources()
        if sources:
            print(f"\n📡 DATA SOURCES ({len(sources)} sources):")
            for name in sources:
                source = self.executor.tools.data_source_manager.get_source(name)
                interval = source.get('interval_ms', 0)
                fires = source.get('fires_transition', '')
                print(f"  • {name}: every {interval}ms → fires '{fires}'")

    def _print_status(self):
        """Print complete current status."""
        self._print_separator()
        self._print_current_state()
        self._print_states()
        self._print_rules()
        self._print_variables()
        self._print_custom_tools()
        self._print_data_sources()
        self._print_separator()

    def _reset(self):
        """Reset to default state."""
        # Clear everything
        self.state_machine.clear_rules()
        self.state_machine.clear_data()
        self.state_machine.states.clear_states()

        # Re-initialize defaults
        self._initialize_default_states()
        self._initialize_default_rules()
        self.state_machine.set_state('off')

        # Re-initialize executor with fresh tool registry
        self.executor.tools = ToolRegistry(self.state_machine)

    def _simulate_transition(self, transition):
        """Simulate a button/transition event."""
        old_state = self.state_machine.current_state
        result = self.state_machine.execute_transition(transition)
        new_state = self.state_machine.current_state

        if result:
            print(f"  ✓ Transition '{transition}': {old_state} → {new_state}")
        else:
            print(f"  ✗ Transition '{transition}': no matching rule from '{old_state}'")

        return result

    async def _run_agent(self, user_input):
        """Run the agent loop for a user input."""
        print("\n🤖 Running agent...")
        print("-" * 40)

        result = await self.executor.run(user_input)

        print("-" * 40)
        print(f"\n💬 Agent response: {result}")

        return result

    def run(self):
        """Run the interactive REPL."""
        print("\n" + "=" * 70)
        print("  AdaptLight Agent Evaluator (Multi-turn Agentic Mode)")
        print("=" * 70)
        print("\nThis uses the new AgentExecutor with multi-turn tool calling.")
        print("\nCommands:")
        print("  - Type any natural language command")
        print("  - 'click', 'hold', 'release', 'double' - Simulate button events")
        print("  - 'status' - Show current status")
        print("  - 'reset' - Reset to default state")
        print("  - 'verbose' - Toggle verbose mode")
        print("  - 'quit', 'exit', 'q' - Exit the program")

        # Show initial status
        self._print_status()

        while True:
            try:
                # Get user input
                print("\n" + "-" * 70)
                user_input = input("➤ ").strip()

                if not user_input:
                    continue

                # Check for special commands
                lower_input = user_input.lower()

                if lower_input in ['quit', 'exit', 'q']:
                    print("\nGoodbye!")
                    break

                if lower_input == 'reset':
                    print("\nResetting to default state...")
                    self._reset()
                    self._print_status()
                    continue

                if lower_input == 'status':
                    self._print_status()
                    continue

                if lower_input == 'verbose':
                    self.verbose = not self.verbose
                    self.executor.verbose = self.verbose
                    print(f"\nVerbose mode: {'ON' if self.verbose else 'OFF'}")
                    continue

                if lower_input == 'help':
                    print("\nCommands:")
                    print("  - Type any natural language command to modify the state machine")
                    print("  - 'click' - Simulate button_click")
                    print("  - 'hold' - Simulate button_hold")
                    print("  - 'release' - Simulate button_release")
                    print("  - 'double' - Simulate button_double_click")
                    print("  - 'status' - Show current status")
                    print("  - 'reset' - Reset to default state")
                    print("  - 'verbose' - Toggle verbose mode")
                    print("  - 'quit', 'exit', 'q' - Exit the program")
                    continue

                # Simulate button events
                if lower_input == 'click':
                    self._simulate_transition('button_click')
                    self._print_current_state()
                    continue

                if lower_input == 'hold':
                    self._simulate_transition('button_hold')
                    self._print_current_state()
                    continue

                if lower_input == 'release':
                    self._simulate_transition('button_release')
                    self._print_current_state()
                    continue

                if lower_input == 'double':
                    self._simulate_transition('button_double_click')
                    self._print_current_state()
                    continue

                # Run the agent
                asyncio.run(self._run_agent(user_input))

                # Show updated status
                print("\n" + "=" * 70)
                print("  UPDATED STATUS")
                self._print_status()

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'quit' to exit.")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue


def main():
    """Main entry point."""
    import yaml
    import argparse

    parser = argparse.ArgumentParser(description='Interactive Agent Evaluator')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose mode')
    parser.add_argument('--model', '-m', default='claude-sonnet-4-20250514', help='Model to use')
    args = parser.parse_args()

    # Load API key from config
    config_file = Path(__file__).parent.parent / 'config.yaml'

    if not config_file.exists():
        print(f"Error: config.yaml not found at {config_file}")
        print("Please create config.yaml with claude.api_key")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Get Claude API key
    api_key = config.get('claude', {}).get('api_key')

    if not api_key:
        print("Error: claude.api_key not found in config.yaml")
        print("The agent executor requires a Claude API key.")
        sys.exit(1)

    print(f"\nConfiguration:")
    print(f"  Model: {args.model}")
    print(f"  Verbose: {args.verbose}")

    # Run interactive evaluator
    evaluator = InteractiveAgentEvaluator(
        api_key=api_key,
        model=args.model,
        verbose=args.verbose
    )
    evaluator.run()


if __name__ == '__main__':
    main()
