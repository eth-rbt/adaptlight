#!/usr/bin/env python3
"""
Evaluation script for AdaptLight command parser.

Runs test cases by executing transitions and checking resulting states.
"""

import sys
import json
import copy
import random
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.command_parser import CommandParser
from eval.examples import ALL_EXAMPLES


class RuleExecutor:
    """Executes state machine rules to simulate transitions."""

    def __init__(self, rules, initial_state, initial_params, initial_variables):
        """Initialize with rules and state."""
        self.rules = copy.deepcopy(rules)
        self.current_state = initial_state
        self.state_params = initial_params
        self.variables = copy.deepcopy(initial_variables)
        self.pending_rule_deletions = []  # Indices to delete after transition

    def execute_transition(self, transition):
        """
        Execute a transition and update state.

        Args:
            transition: Transition name (e.g., "button_click") or None to skip

        Returns:
            (new_state, new_params) tuple
        """
        if transition is None:
            # No transition, just return current state
            return self.current_state, self.state_params

        # Find matching rule (checks in order, first match wins)
        matching_rule = None
        for rule in self.rules:
            if rule.get("state1") == self.current_state and rule.get("transition") == transition:
                # Check condition if present
                condition = rule.get("condition")
                if condition:
                    # Simple condition evaluation for counter tests
                    if not self._evaluate_condition(condition):
                        # Condition failed, try next rule
                        continue

                # Found matching rule with passing condition (or no condition)
                matching_rule = rule
                break

        if not matching_rule:
            # No rule found, state doesn't change
            return self.current_state, self.state_params

        # Execute action if present
        if matching_rule.get("action"):
            self._execute_action(matching_rule.get("action"))

        # Get new state and params
        new_state = matching_rule.get("state2")
        new_params = matching_rule.get("state2Param")

        # Evaluate params if they're expressions
        if isinstance(new_params, dict):
            evaluated_params = {}
            for key, value in new_params.items():
                if isinstance(value, str):
                    # Simple evaluation for common cases
                    if value == "random()":
                        evaluated_params[key] = random.randint(0, 255)
                    else:
                        # Keep as string expression
                        evaluated_params[key] = value
                else:
                    evaluated_params[key] = value
            new_params = evaluated_params

        # Update state
        self.current_state = new_state
        self.state_params = new_params

        # Apply pending rule deletions (deferred deletion)
        self._apply_pending_deletions()

        return self.current_state, self.state_params

    def _evaluate_condition(self, condition):
        """
        Evaluate a condition expression.

        Handles:
        - getData('key') comparisons
        - Arithmetic with ||  operator for defaults
        - Comparison operators: <, >, <=, >=, ===, !==
        """
        import re

        if not condition:
            return True

        # Replace getData calls with actual values
        getdata_pattern = r'getData\([\'"](\w+)[\'"]\)'

        def replace_getdata(match):
            key = match.group(1)
            value = self.variables.get(key)
            if value is None:
                return 'None'
            return str(value)

        condition = re.sub(getdata_pattern, replace_getdata, condition)

        # Handle || operator for default values: (None || 0) becomes 0
        condition = re.sub(r'\(\s*None\s*\|\|\s*(\d+)\s*\)', r'\1', condition)

        # Convert JavaScript comparison operators to Python
        condition = condition.replace('===', '==')
        condition = condition.replace('!==', '!=')
        condition = condition.replace(' undefined', ' None')

        # Try to evaluate the condition
        try:
            result = eval(condition, {"__builtins__": {}}, {})
            return bool(result)
        except:
            # If evaluation fails, assume condition passes
            print(f"  ⚠️  Could not evaluate condition: {condition}")
            return True

    def _execute_action(self, action):
        """
        Execute an action string.

        Supports:
        - setData('key', value)
        - getData('key')
        - deleteRulesByIndex([0, 1, 2])
        """
        import re

        # Parse deleteRulesByIndex calls
        delete_pattern = r'deleteRulesByIndex\(\[([\d,\s]+)\]\)'
        delete_matches = re.findall(delete_pattern, action)
        for match in delete_matches:
            indices = [int(x.strip()) for x in match.split(',') if x.strip()]
            self.pending_rule_deletions.extend(indices)

        # Parse setData calls
        # Match patterns like: setData('key', value) or setData("key", value)
        # Use a more complex pattern to handle nested parentheses
        setdata_pattern = r'setData\([\'"](\w+)[\'"]\s*,\s*([^;]+?)\)(?:;|$)'
        setdata_matches = re.findall(setdata_pattern, action)
        for key, value_expr in setdata_matches:
            # Evaluate the value expression
            evaluated_value = self._evaluate_expression(value_expr)
            self.variables[key] = evaluated_value

    def _evaluate_expression(self, expr):
        """
        Evaluate a simple expression.

        Handles:
        - Numbers: 5, 0
        - getData calls: getData('key')
        - Arithmetic: getData('key') + 1
        - undefined/null
        """
        import re

        expr = expr.strip()

        # Handle undefined/null
        if expr in ['undefined', 'null']:
            return None

        # Handle plain numbers
        try:
            return int(expr)
        except ValueError:
            pass

        # Handle getData calls
        getdata_pattern = r'getData\([\'"](\w+)[\'"]\)'
        expr = re.sub(getdata_pattern, lambda m: str(self.variables.get(m.group(1), 0)), expr)

        # Handle || operator for default values: (getData('key') || 0)
        expr = re.sub(r'\(\s*0\s*\|\|\s*0\s*\)', '0', expr)  # Simplified

        # Try to evaluate as arithmetic
        try:
            # Very simple eval for testing (only safe in test environment!)
            return eval(expr, {"__builtins__": {}}, {})
        except:
            return 0

    def _apply_pending_deletions(self):
        """Apply pending rule deletions in reverse order to avoid index shifting."""
        if not self.pending_rule_deletions:
            return

        # Sort in reverse order to delete from end to start
        indices_to_delete = sorted(set(self.pending_rule_deletions), reverse=True)

        for idx in indices_to_delete:
            if 0 <= idx < len(self.rules):
                del self.rules[idx]
                print(f"  🗑️  Deleted rule at index {idx}")
            else:
                print(f"  ⚠️  Rule index {idx} out of bounds, skipping")

        # Clear pending deletions
        self.pending_rule_deletions = []

    def get_state(self):
        """Get current state as dict."""
        return {
            "state": self.current_state,
            "params": self.state_params,
            "variables": self.variables
        }


class MockStateMachine:
    """Mock state machine to execute tool calls and track state."""

    def __init__(self, initial_rules, initial_state, initial_variables, initial_states=None):
        """Initialize with starting conditions."""
        self.rules = copy.deepcopy(initial_rules)
        self.current_state = initial_state
        self.state_params = None
        self.variables = copy.deepcopy(initial_variables)
        # Track created states (unified state system)
        if initial_states:
            self.states = copy.deepcopy(initial_states)
        else:
            self.states = {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None}
            }

    def execute_tool(self, tool_name, args):
        """Execute a tool call and update state."""
        if tool_name == 'append_rules':
            # Add rules to the TOP of the list (prepend)
            # New rules are checked first, allowing them to override/layer on defaults
            new_rules = args.get('rules', [])
            self.rules = new_rules + self.rules

        elif tool_name == 'delete_rules':
            # Delete rules based on criteria
            if args.get('reset_rules'):
                # Reset to default on/off toggle rules
                self.rules = [
                    {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": None, "condition": None, "action": None},
                    {"state1": "on", "transition": "button_click", "state2": "off", "state2Param": None, "condition": None, "action": None}
                ]
            elif args.get('delete_all'):
                self.rules = []
            elif args.get('indices'):
                # Delete by indices (reverse order to avoid index shifting)
                for idx in sorted(args['indices'], reverse=True):
                    if 0 <= idx < len(self.rules):
                        del self.rules[idx]
            else:
                # Delete by criteria (state1, transition, state2)
                rules_to_delete = []
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
                        rules_to_delete.append(i)

                for idx in rules_to_delete:
                    del self.rules[idx]

        elif tool_name == 'set_state':
            # Change current state immediately
            self.current_state = args.get('state')
            # Note: setState no longer takes params, only state name
            self.state_params = None

        elif tool_name == 'manage_variables':
            # Manage variables
            action = args.get('action')
            if action == 'set':
                variables = args.get('variables', {})
                self.variables.update(variables)
            elif action == 'delete':
                keys = args.get('keys', [])
                for key in keys:
                    self.variables.pop(key, None)
            elif action == 'clear_all':
                self.variables = {}

        elif tool_name == 'reset_rules':
            # Reset to default rules
            self.rules = [
                {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": None},
                {"state1": "on", "transition": "button_click", "state2": "off", "state2Param": None}
            ]

        elif tool_name == 'create_state':
            # Create a new state with r, g, b, speed parameters
            name = args.get('name')
            if name:
                self.states[name] = {
                    "r": args.get('r'),
                    "g": args.get('g'),
                    "b": args.get('b'),
                    "speed": args.get('speed'),
                    "description": args.get('description')
                }

        elif tool_name == 'delete_state':
            # Delete a state by name
            name = args.get('name')
            if name and name in self.states:
                del self.states[name]

    def get_state(self):
        """Get current state as dict."""
        return {
            "rules": self.rules,
            "current_state": self.current_state,
            "state_params": self.state_params,
            "variables": self.variables,
            "states": self.states
        }


class ParserEvaluator:
    """Evaluates command parser against test examples."""

    def __init__(self, api_key=None, parsing_method='json_output', prompt_variant='full', model='gpt-4o',
                 reasoning_effort='medium', verbosity=0, claude_api_key=None):
        """Initialize evaluator with command parser."""
        self.parser = CommandParser(
            api_key=api_key,
            parsing_method=parsing_method,
            prompt_variant=prompt_variant,
            model=model,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            claude_api_key=claude_api_key
        )
        self.results = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "details": []
        }

    def evaluate_deterministic(self, example):
        """
        Evaluate a deterministic test by executing transitions.

        Args:
            example: Example dict with test_sequence

        Returns:
            Dict with evaluation result
        """
        print(f"\n{'='*60}")
        print(f"Test: {example['name']}")
        print(f"Description: {example['description']}")
        print(f"User Input: \"{example['user_input']}\"")
        print(f"{'='*60}")

        try:
            # Extract previous state
            prev_state = example.get('previous_state', {})
            current_rules = prev_state.get('rules', [])
            current_state = prev_state.get('current_state', 'off')
            variables = prev_state.get('variables', {})
            initial_states = prev_state.get('states', None)

            # Build available states (simplified for testing)
            available_states = "off, on, color, animation"

            # Available transitions
            available_transitions = [
                {"name": "button_click", "description": "Single click"},
                {"name": "button_double_click", "description": "Double click"},
                {"name": "button_hold", "description": "Hold button"},
                {"name": "button_release", "description": "Release after hold"},
                {"name": "voice_command", "description": "Voice command"}
            ]

            # Parse the command
            result = self.parser.parse_command(
                example['user_input'],
                available_states,
                available_transitions,
                current_rules,
                current_state,
                variables
            )

            # Check if parsing succeeded
            if not result.get('success'):
                print("❌ FAILED: Parser returned success=False")
                return {"passed": False, "reason": "Parser failed"}

            # Execute tool calls to get final rules
            mock_sm = MockStateMachine(current_rules, current_state, variables, initial_states)

            tool_calls = result.get('toolCalls', [])
            print(f"\n⚙️  TOOL CALLS: {len(tool_calls)} call(s)")
            for tool_call in tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['arguments']
                print(f"  - {tool_name}({json.dumps(tool_args)})")
                mock_sm.execute_tool(tool_name, tool_args)

            final_state = mock_sm.get_state()

            # Print final rules
            print(f"\n📋 RULES AFTER TOOL CALLS ({len(final_state['rules'])} rules):")
            for idx, rule in enumerate(final_state['rules']):
                cond = f" [if {rule['condition']}]" if rule.get('condition') else ""
                print(f"  [{idx}] {rule['state1']} --[{rule['transition']}]--> {rule['state2']}{cond}")

            executor = RuleExecutor(
                final_state['rules'],
                final_state['current_state'],
                final_state.get('state_params'),
                final_state['variables']
            )

            for i, step in enumerate(example['test_sequence'], 1):
                transition = step.get('transition')
                expected_state = step.get('expected_state')
                expected_params = step.get('expected_params')

                # Execute transition
                actual_state, actual_params = executor.execute_transition(transition)

                # Check state
                if actual_state != expected_state:
                    print(f"\n❌ Step {i} FAILED: expected state '{expected_state}', got '{actual_state}'")
                    return {
                        "passed": False,
                        "reason": f"Step {i}: State mismatch (expected {expected_state}, got {actual_state})"
                    }

                # Check params
                if expected_params != "any":
                    if expected_params != actual_params:
                        print(f"\n❌ Step {i} FAILED: params mismatch")
                        return {
                            "passed": False,
                            "reason": f"Step {i}: Params mismatch"
                        }

            print("\n✅ PASSED")
            return {"passed": True}

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"passed": False, "reason": f"Exception: {e}"}

    def evaluate_non_deterministic(self, example):
        """
        Evaluate a non-deterministic test with property checks.

        Args:
            example: Example dict with property_checks

        Returns:
            Dict with evaluation result
        """
        print(f"\n{'='*60}")
        print(f"Test: {example['name']}")
        print(f"Description: {example['description']}")
        print(f"User Input: \"{example['user_input']}\"")
        print(f"{'='*60}")

        try:
            # Extract previous state
            prev_state = example.get('previous_state', {})
            current_rules = prev_state.get('rules', [])
            current_state = prev_state.get('current_state', 'off')
            variables = prev_state.get('variables', {})
            initial_states = prev_state.get('states', None)

            before_rules = copy.deepcopy(current_rules)
            before_state = {
                "state": current_state,
                "variables": variables,
                "states": copy.deepcopy(initial_states) if initial_states else {}
            }

            # Build available states
            available_states = "off, on, color, animation"
            available_transitions = [
                {"name": "button_click", "description": "Single click"},
                {"name": "button_double_click", "description": "Double click"},
                {"name": "button_hold", "description": "Hold button"},
                {"name": "button_release", "description": "Release after hold"},
                {"name": "voice_command", "description": "Voice command"}
            ]

            # Parse the command
            result = self.parser.parse_command(
                example['user_input'],
                available_states,
                available_transitions,
                current_rules,
                current_state,
                variables
            )

            if not result.get('success'):
                print("❌ FAILED: Parser returned success=False")
                return {"passed": False, "reason": "Parser failed"}

            # Execute tool calls
            mock_sm = MockStateMachine(current_rules, current_state, variables, initial_states)
            tool_calls = result.get('toolCalls', [])
            print(f"\n⚙️  TOOL CALLS: {len(tool_calls)} call(s)")
            for tool_call in tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['arguments']
                print(f"  - {tool_name}({json.dumps(tool_args)})")
                mock_sm.execute_tool(tool_name, tool_args)

            final_state = mock_sm.get_state()
            after_rules = final_state['rules']
            after_state = {
                "state": final_state['current_state'],
                "params": final_state.get('state_params'),
                "variables": final_state['variables'],
                "states": final_state.get('states', {})
            }

            # Print final rules
            print(f"\n📋 RULES AFTER TOOL CALLS ({len(after_rules)} rules):")
            for idx, rule in enumerate(after_rules):
                cond = f" [if {rule['condition']}]" if rule.get('condition') else ""
                print(f"  [{idx}] {rule['state1']} --[{rule['transition']}]--> {rule['state2']}{cond}")

            # Run property checks
            for prop_check in example['property_checks']:
                check_name = prop_check['name']
                check_func = prop_check['check']

                try:
                    passed = check_func(before_rules, after_rules, before_state, after_state)
                    if not passed:
                        print(f"\n❌ Property check FAILED: {check_name}")
                        return {
                            "passed": False,
                            "reason": f"Property check failed: {check_name}"
                        }
                except Exception as e:
                    print(f"\n❌ Property check ERROR: {check_name} - {e}")
                    return {
                        "passed": False,
                        "reason": f"Property check error: {check_name} - {e}"
                    }

            # Execute test sequence if present
            if example.get('test_sequence'):
                executor = RuleExecutor(
                    after_rules,
                    after_state['state'],
                    after_state.get('params'),
                    after_state['variables']
                )

                for i, step in enumerate(example['test_sequence'], 1):
                    transition = step.get('transition')
                    expected_state = step.get('expected_state')
                    expected_params = step.get('expected_params')

                    actual_state, actual_params = executor.execute_transition(transition)

                    if actual_state != expected_state:
                        print(f"\n❌ Step {i} FAILED: expected state '{expected_state}', got '{actual_state}'")
                        return {
                            "passed": False,
                            "reason": f"Step {i}: State mismatch"
                        }

                    if expected_params != "any" and expected_params != actual_params:
                        print(f"\n❌ Step {i} FAILED: params mismatch")
                        return {
                            "passed": False,
                            "reason": f"Step {i}: Params mismatch"
                        }

            print("\n✅ PASSED")
            return {"passed": True}

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"passed": False, "reason": f"Exception: {e}"}

    def evaluate_category(self, category_name, examples):
        """Evaluate all examples in a category."""
        print(f"\n{'#'*60}")
        print(f"# Category: {category_name.upper()}")
        print(f"# {len(examples)} test(s)")
        print(f"{'#'*60}")

        passed = 0
        failed = 0

        for example in examples:
            # Choose evaluation method based on category
            if category_name == "deterministic":
                result = self.evaluate_deterministic(example)
            else:
                result = self.evaluate_non_deterministic(example)

            detail = {
                "category": category_name,
                "name": example['name'],
                "result": result
            }
            self.results['details'].append(detail)

            if result['passed']:
                passed += 1
                self.results['passed'] += 1
            else:
                failed += 1
                self.results['failed'] += 1

        print(f"\nCategory Summary: {passed}/{len(examples)} passed")

        return {"passed": passed, "failed": failed, "total": len(examples)}

    def evaluate_all(self):
        """Evaluate all example categories."""
        print("\n" + "="*60)
        print("ADAPTLIGHT COMMAND PARSER EVALUATION")
        print("="*60)

        for category_name, examples in ALL_EXAMPLES.items():
            self.evaluate_category(category_name, examples)

        # Print final summary
        print("\n" + "="*60)
        print("FINAL RESULTS")
        print("="*60)
        total = self.results['passed'] + self.results['failed']
        if total > 0:
            print(f"Total Tests: {total}")
            print(f"Passed: {self.results['passed']} ({self.results['passed']/total*100:.1f}%)")
            print(f"Failed: {self.results['failed']} ({self.results['failed']/total*100:.1f}%)")
        else:
            print("No tests run")
        print("="*60)

        return self.results


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

    # If using Claude, override model and check for API key
    if parsing_method == 'claude':
        model = config.get('claude', {}).get('model', 'claude-3-7-sonnet-20250219')
        if not claude_api_key:
            print("Error: claude.api_key not found in config.yaml but parsing_method is 'claude'")
            sys.exit(1)
    else:
        if not api_key:
            print("Error: openai.api_key not found in config.yaml")
            sys.exit(1)

    print(f"Using parsing method: {parsing_method}, variant: {prompt_variant}, model: {model}")
    print(f"Reasoning effort: {reasoning_effort}, verbosity: {verbosity}")

    # Run evaluation
    evaluator = ParserEvaluator(
        api_key=api_key,
        parsing_method=parsing_method,
        prompt_variant=prompt_variant,
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        claude_api_key=claude_api_key
    )
    results = evaluator.evaluate_all()

    # Exit with error code if any tests failed
    if results['failed'] > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
