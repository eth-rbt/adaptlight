#!/usr/bin/env python3
"""
Interactive evaluation tool for AdaptLight command parser.

Provides a REPL interface to test state management:
- Shows current states, rules, and variables
- Accept user commands
- Display resulting changes
- Repeat in a loop
"""

import sys
import json
import copy
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.command_parser import CommandParser
from core.state import State, States


class InteractiveEvaluator:
    """Interactive REPL for testing the state management system."""

    def __init__(self, api_key, parsing_method='json_output', prompt_variant='full',
                 model='gpt-4o', reasoning_effort='medium', verbosity=0, claude_api_key=None):
        """Initialize the interactive evaluator."""
        self.parser = CommandParser(
            api_key=api_key,
            parsing_method=parsing_method,
            prompt_variant=prompt_variant,
            model=model,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            claude_api_key=claude_api_key
        )

        # Initialize state collection
        self.states = States()
        self._initialize_default_states()

        # Initialize state machine state
        self.rules = self._get_default_rules()
        self.current_state = 'off'
        self.state_params = None
        self.variables = {}

        # Available transitions
        self.available_transitions = [
            {"name": "button_click", "description": "Single click"},
            {"name": "button_double_click", "description": "Double click"},
            {"name": "button_hold", "description": "Hold button"},
            {"name": "button_release", "description": "Release after hold"},
            {"name": "voice_command", "description": "Voice command"}
        ]

    def _initialize_default_states(self):
        """Initialize with default states."""
        # Basic states
        self.states.add_state(State('off', r=0, g=0, b=0, description='LEDs off'))
        self.states.add_state(State('on', r=255, g=255, b=255, description='White light'))

    def _get_default_rules(self):
        """Get default on/off toggle rules."""
        return [
            {
                "state1": "off",
                "transition": "button_click",
                "state2": "on",
                "state2Param": None,
                "condition": None,
                "action": None
            },
            {
                "state1": "on",
                "transition": "button_click",
                "state2": "off",
                "state2Param": None,
                "condition": None,
                "action": None
            }
        ]

    def _print_separator(self, char='=', length=70):
        """Print a separator line."""
        print(char * length)

    def _print_current_state(self):
        """Print the current state machine state."""
        print(f"\n📍 CURRENT STATE: {self.current_state}")
        if self.state_params:
            print(f"   Parameters: {self.state_params}")

    def _print_states(self):
        """Print all registered states."""
        print(f"\n🎨 REGISTERED STATES ({len(self.states.get_states())} states):")
        for state in self.states.get_states():
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
        print(f"\n📋 RULES ({len(self.rules)} rules):")
        if not self.rules:
            print("  (no rules)")
            return

        for idx, rule in enumerate(self.rules):
            state1 = rule.get('state1', '?')
            transition = rule.get('transition', '?')
            state2 = rule.get('state2', '?')
            condition = rule.get('condition')
            action = rule.get('action')

            rule_str = f"  [{idx}] {state1} --[{transition}]--> {state2}"

            if condition:
                rule_str += f"\n      └─ if: {condition}"
            if action:
                rule_str += f"\n      └─ action: {action}"

            print(rule_str)

    def _print_variables(self):
        """Print current variables."""
        print(f"\n💾 VARIABLES ({len(self.variables)} variables):")
        if not self.variables:
            print("  (no variables)")
            return

        for key, value in self.variables.items():
            print(f"  • {key}: {value}")

    def _print_status(self):
        """Print complete current status."""
        self._print_separator()
        self._print_current_state()
        self._print_states()
        self._print_rules()
        self._print_variables()
        self._print_separator()

    def _execute_tool_calls(self, tool_calls):
        """Execute tool calls and update state."""
        if not tool_calls:
            print("\n⚙️  No tool calls to execute")
            return

        print(f"\n⚙️  EXECUTING {len(tool_calls)} TOOL CALL(S):")

        for i, tool_call in enumerate(tool_calls, 1):
            tool_name = tool_call['name']
            tool_args = tool_call['arguments']

            print(f"\n  [{i}] {tool_name}")
            print(f"      Arguments: {json.dumps(tool_args, indent=8)}")

            self._execute_tool(tool_name, tool_args)

    def _execute_tool(self, tool_name, args):
        """Execute a single tool call."""
        if tool_name == 'append_rules':
            # Add rules to the TOP of the list (prepend)
            new_rules = args.get('rules', [])
            self.rules = new_rules + self.rules
            print(f"      ✓ Added {len(new_rules)} rule(s) to the top")

        elif tool_name == 'delete_rules':
            # Delete rules based on criteria
            if args.get('reset_rules'):
                self.rules = self._get_default_rules()
                print(f"      ✓ Reset to default rules")
            elif args.get('delete_all'):
                self.rules = []
                print(f"      ✓ Deleted all rules")
            elif args.get('indices'):
                # Delete by indices (reverse order to avoid index shifting)
                for idx in sorted(args['indices'], reverse=True):
                    if 0 <= idx < len(self.rules):
                        del self.rules[idx]
                print(f"      ✓ Deleted rules at indices: {args['indices']}")
            else:
                # Delete by criteria
                original_count = len(self.rules)
                indices_to_delete = []

                for i in range(len(self.rules) - 1, -1, -1):
                    rule = self.rules[i]
                    should_delete = False

                    if args.get('state1') and rule.get('state1') == args['state1']:
                        should_delete = True
                    if args.get('transition') and rule.get('transition') == args['transition']:
                        should_delete = True
                    if args.get('state2') and rule.get('state2') == args['state2']:
                        should_delete = True

                    if should_delete:
                        indices_to_delete.append(i)

                for idx in indices_to_delete:
                    del self.rules[idx]

                deleted_count = original_count - len(self.rules)
                print(f"      ✓ Deleted {deleted_count} rule(s)")

        elif tool_name == 'set_state':
            # Change current state immediately
            self.current_state = args.get('state')
            self.state_params = None  # setState no longer takes params
            print(f"      ✓ Set current state to: {self.current_state}")

        elif tool_name == 'create_state':
            # Create a new state
            state = State(
                name=args['name'],
                r=args.get('r'),
                g=args.get('g'),
                b=args.get('b'),
                speed=args.get('speed'),
                description=args.get('description', '')
            )
            self.states.add_state(state)
            print(f"      ✓ Created state: {args['name']}")

        elif tool_name == 'delete_state':
            # Delete a state
            name = args.get('name')
            if self.states.delete_state(name):
                print(f"      ✓ Deleted state: {name}")
            else:
                print(f"      ⚠ State not found: {name}")

        elif tool_name == 'manage_variables':
            # Manage variables
            action = args.get('action')
            if action == 'set':
                variables = args.get('variables', {})
                self.variables.update(variables)
                print(f"      ✓ Set {len(variables)} variable(s)")
            elif action == 'delete':
                keys = args.get('keys', [])
                for key in keys:
                    self.variables.pop(key, None)
                print(f"      ✓ Deleted {len(keys)} variable(s)")
            elif action == 'clear_all':
                self.variables = {}
                print(f"      ✓ Cleared all variables")

        elif tool_name == 'manage_states':
            # Manage states in the collection
            action = args.get('action')
            if action == 'add':
                states_to_add = args.get('states', [])
                for state_data in states_to_add:
                    state = State(
                        name=state_data['name'],
                        r=state_data.get('r'),
                        g=state_data.get('g'),
                        b=state_data.get('b'),
                        speed=state_data.get('speed'),
                        description=state_data.get('description', '')
                    )
                    self.states.add_state(state)
                print(f"      ✓ Added/updated {len(states_to_add)} state(s)")

            elif action == 'delete':
                names = args.get('names', [])
                deleted = 0
                for name in names:
                    if self.states.delete_state(name):
                        deleted += 1
                print(f"      ✓ Deleted {deleted} state(s)")

            elif action == 'clear_all':
                self.states.clear_states()
                print(f"      ✓ Cleared all states")

        else:
            print(f"      ⚠ Unknown tool: {tool_name}")

    def run(self):
        """Run the interactive REPL."""
        print("\n" + "="*70)
        print("  AdaptLight Interactive Evaluator")
        print("="*70)
        print("\nType commands to modify the state machine.")
        print("Type 'quit' or 'exit' to quit.")
        print("Type 'reset' to reset to default state.")
        print("Type 'help' for help.")

        # Show initial status
        self._print_status()

        while True:
            try:
                # Get user input
                print("\n" + "-"*70)
                user_input = input("➤ ").strip()

                if not user_input:
                    continue

                # Check for special commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye!")
                    break

                if user_input.lower() == 'reset':
                    print("\nResetting to default state...")
                    self.rules = self._get_default_rules()
                    self.current_state = 'off'
                    self.state_params = None
                    self.variables = {}
                    self.states = States()
                    self._initialize_default_states()
                    self._print_status()
                    continue

                if user_input.lower() == 'help':
                    print("\nAvailable commands:")
                    print("  - Type any natural language command to modify the state machine")
                    print("  - 'reset' - Reset to default state")
                    print("  - 'status' - Show current status")
                    print("  - 'quit', 'exit', 'q' - Exit the program")
                    continue

                if user_input.lower() == 'status':
                    self._print_status()
                    continue

                # Parse the command
                print("\n🔄 Parsing command...")

                available_states = self.states.get_states_for_prompt()

                result = self.parser.parse_command(
                    user_input,
                    available_states,
                    self.available_transitions,
                    self.rules,
                    self.current_state,
                    self.variables
                )

                # Check if parsing succeeded
                if not result.get('success'):
                    print("❌ Parser failed")
                    if result.get('error'):
                        print(f"   Error: {result['error']}")
                    continue

                # Execute tool calls
                tool_calls = result.get('toolCalls', [])
                self._execute_tool_calls(tool_calls)

                # Show updated status
                print("\n" + "="*70)
                print("  UPDATED STATUS")
                print("="*70)
                self._print_current_state()
                self._print_states()
                self._print_rules()
                self._print_variables()

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

    # Load API key from config
    config_file = Path(__file__).parent.parent / 'config.yaml'

    if not config_file.exists():
        print(f"Error: config.yaml not found at {config_file}")
        print("Please create config.yaml with OpenAI API key")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Get API keys
    api_key = config.get('openai', {}).get('api_key')
    claude_api_key = config.get('claude', {}).get('api_key')

    # Get parsing configuration
    parsing_method = config.get('openai', {}).get('parsing_method', 'json_output')
    prompt_variant = config.get('openai', {}).get('prompt_variant', 'full')
    model = config.get('openai', {}).get('model', 'gpt-4o')
    reasoning_effort = config.get('openai', {}).get('reasoning_effort', 'medium')
    verbosity = config.get('openai', {}).get('verbosity', 0)

    # If using Claude, override model
    if parsing_method == 'claude':
        model = config.get('claude', {}).get('model', 'claude-3-7-sonnet-20250219')
        if not claude_api_key:
            print("Error: claude.api_key not found in config.yaml but parsing_method is 'claude'")
            sys.exit(1)

    print(f"\nConfiguration:")
    print(f"  Parsing method: {parsing_method}")
    print(f"  Prompt variant: {prompt_variant}")
    print(f"  Model: {model}")
    print(f"  Reasoning effort: {reasoning_effort}")
    print(f"  Verbosity: {verbosity}")

    # Run interactive evaluator
    evaluator = InteractiveEvaluator(
        api_key=api_key,
        parsing_method=parsing_method,
        prompt_variant=prompt_variant,
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        claude_api_key=claude_api_key
    )
    evaluator.run()


if __name__ == '__main__':
    main()