#!/usr/bin/env python3
"""
Evaluation script for AdaptLight command parser.

Runs example test cases and compares parser output against expected results.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.command_parser import CommandParser
from eval.examples import ALL_EXAMPLES


class ParserEvaluator:
    """Evaluates command parser against test examples."""

    def __init__(self, api_key=None):
        """Initialize evaluator with command parser."""
        self.parser = CommandParser(api_key=api_key)
        self.results = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "details": []
        }

    def evaluate_example(self, example):
        """
        Evaluate a single example.

        Args:
            example: Example dict with user_input, expected_tools, etc.

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
                current_state
            )

            # Check if parsing succeeded
            if not result.get('success'):
                print("❌ FAILED: Parser returned success=False")
                return {
                    "passed": False,
                    "reason": "Parser failed",
                    "expected": example['expected_tools'],
                    "actual": None
                }

            # Extract tool calls
            actual_tools = result.get('toolCalls', [])
            expected_tools = example.get('expected_tools', [])

            print(f"\nExpected {len(expected_tools)} tool call(s)")
            print(f"Received {len(actual_tools)} tool call(s)")

            # Compare tool calls
            if self.compare_tool_calls(expected_tools, actual_tools):
                print("✅ PASSED")
                return {
                    "passed": True,
                    "expected": expected_tools,
                    "actual": actual_tools
                }
            else:
                print("❌ FAILED: Tool calls don't match")
                print(f"\nExpected:")
                print(json.dumps(expected_tools, indent=2))
                print(f"\nActual:")
                print(json.dumps(actual_tools, indent=2))
                return {
                    "passed": False,
                    "reason": "Tool calls mismatch",
                    "expected": expected_tools,
                    "actual": actual_tools
                }

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {
                "passed": False,
                "reason": f"Exception: {e}",
                "expected": example['expected_tools'],
                "actual": None
            }

    def compare_tool_calls(self, expected, actual):
        """
        Compare expected and actual tool calls.

        Args:
            expected: List of expected tool call dicts
            actual: List of actual tool call dicts from parser

        Returns:
            True if they match, False otherwise
        """
        # Check count
        if len(expected) != len(actual):
            return False

        # Compare each tool call
        for exp_tool, act_tool in zip(expected, actual):
            # Check tool name
            if exp_tool['name'] != act_tool['name']:
                return False

            # Compare arguments (loosely - just check structure)
            exp_args = exp_tool.get('arguments', {})
            act_args = act_tool.get('arguments', {})

            # For now, just check that major keys are present
            # More sophisticated comparison can be added later
            if set(exp_args.keys()) != set(act_args.keys()):
                return False

        return True

    def evaluate_category(self, category_name, examples):
        """
        Evaluate all examples in a category.

        Args:
            category_name: Name of the category
            examples: List of example dicts

        Returns:
            Summary dict
        """
        print(f"\n{'#'*60}")
        print(f"# Category: {category_name.upper()}")
        print(f"# {len(examples)} test(s)")
        print(f"{'#'*60}")

        passed = 0
        failed = 0

        for example in examples:
            result = self.evaluate_example(example)

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

        return {
            "passed": passed,
            "failed": failed,
            "total": len(examples)
        }

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
        print(f"Total Tests: {total}")
        print(f"Passed: {self.results['passed']} ({self.results['passed']/total*100:.1f}%)")
        print(f"Failed: {self.results['failed']} ({self.results['failed']/total*100:.1f}%)")
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

    api_key = config.get('openai', {}).get('api_key')
    if not api_key:
        print("Error: openai.api_key not found in config.yaml")
        sys.exit(1)

    # Run evaluation
    evaluator = ParserEvaluator(api_key=api_key)
    results = evaluator.evaluate_all()

    # Exit with error code if any tests failed
    if results['failed'] > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
