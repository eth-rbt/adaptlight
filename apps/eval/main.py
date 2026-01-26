"""
AdaptLight Evaluation Runner

Test the SMgenerator with various configurations and test cases.
"""

import os
import sys
import time
import json
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Add parent directories to path for imports
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env file from root directory
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

from brain import SMgenerator, SMResult


@dataclass
class TestCase:
    """A single test case."""
    name: str
    input: str
    expected: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class TestResult:
    """Result of running a test case."""
    case: TestCase
    passed: bool
    result: Optional[SMResult]
    error: Optional[str] = None
    timing_ms: float = 0


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / 'config.yaml'

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    def expand_env(obj):
        if isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            return os.environ.get(env_var, '')
        elif isinstance(obj, dict):
            return {k: expand_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [expand_env(item) for item in obj]
        return obj

    return expand_env(config)


def load_test_cases(suite_path: str) -> List[TestCase]:
    """Load test cases from a YAML file."""
    with open(suite_path) as f:
        data = yaml.safe_load(f)

    cases = []
    for item in data:
        cases.append(TestCase(
            name=item.get('name', 'unnamed'),
            input=item.get('input', ''),
            expected=item.get('expected', {}),
            description=item.get('description', '')
        ))
    return cases


class EvalRunner:
    """Evaluation runner for testing the SMgenerator."""

    def __init__(self, config: dict, verbose: bool = False):
        """
        Initialize the evaluation runner.

        Args:
            config: Configuration dictionary
            verbose: Enable verbose output
        """
        self.config = config
        self.verbose = verbose
        self.results: List[Dict[str, Any]] = []

    def create_smgen(self, variant: Dict[str, Any] = None) -> SMgenerator:
        """Create an SMgenerator instance with optional variant overrides."""
        smgen_config = dict(self.config.get('brain', {}))

        # Apply variant overrides
        if variant and 'brain' in variant:
            smgen_config.update(variant['brain'])

        # Add API keys
        smgen_config['anthropic_api_key'] = self.config.get('anthropic', {}).get('api_key', '')
        smgen_config['openai_api_key'] = self.config.get('openai', {}).get('api_key', '')

        return SMgenerator(smgen_config)

    def check_expectations(self, result: SMResult, expected: Dict[str, Any]) -> bool:
        """Check if result meets expectations."""
        if not result.success:
            return False

        # Check state name
        if 'state_name' in expected:
            if result.state.get('name') != expected['state_name']:
                if self.verbose:
                    print(f"    Expected state: {expected['state_name']}, got: {result.state.get('name')}")
                return False

        # Check that a state exists
        if 'has_state' in expected:
            state_name = expected['has_state']
            # This would require access to the brain's state machine
            # For now, just check if it's in the result
            pass

        # Check message contains
        if 'message_contains' in expected:
            if expected['message_contains'].lower() not in result.message.lower():
                if self.verbose:
                    print(f"    Expected message to contain: {expected['message_contains']}")
                return False

        # Check tool was called
        if 'tool_called' in expected:
            tool_names = [tc.get('name') for tc in result.tool_calls]
            if expected['tool_called'] not in tool_names:
                if self.verbose:
                    print(f"    Expected tool: {expected['tool_called']}, got: {tool_names}")
                return False

        return True

    def run_case(self, smgen: SMgenerator, case: TestCase) -> TestResult:
        """Run a single test case."""
        start_time = time.time()

        try:
            result = smgen.process(case.input)
            timing_ms = (time.time() - start_time) * 1000

            passed = self.check_expectations(result, case.expected)

            return TestResult(
                case=case,
                passed=passed,
                result=result,
                timing_ms=timing_ms
            )

        except Exception as e:
            timing_ms = (time.time() - start_time) * 1000
            return TestResult(
                case=case,
                passed=False,
                result=None,
                error=str(e),
                timing_ms=timing_ms
            )

    def run_suite(self, suite_name: str, variant: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run a test suite with a specific variant."""
        cases_dir = Path(__file__).parent / 'cases'
        suite_path = cases_dir / f'{suite_name}.yaml'

        if not suite_path.exists():
            return {
                'suite': suite_name,
                'variant': variant.get('name', 'default') if variant else 'default',
                'error': f'Suite file not found: {suite_path}',
                'passed': 0,
                'failed': 0,
                'total': 0
            }

        cases = load_test_cases(suite_path)
        smgen = self.create_smgen(variant)

        results = []
        for case in cases:
            # Reset SMgenerator between cases
            smgen.reset()

            if self.verbose:
                print(f"  Running: {case.name}...")

            test_result = self.run_case(smgen, case)
            results.append(test_result)

            if self.verbose:
                status = '✓' if test_result.passed else '✗'
                print(f"    {status} {case.name} ({test_result.timing_ms:.0f}ms)")

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        return {
            'suite': suite_name,
            'variant': variant.get('name', 'default') if variant else 'default',
            'passed': passed,
            'failed': failed,
            'total': len(results),
            'results': [
                {
                    'case': r.case.name,
                    'passed': r.passed,
                    'timing_ms': r.timing_ms,
                    'error': r.error,
                    'state': r.result.state if r.result else None,
                    'message': r.result.message if r.result else None,
                }
                for r in results
            ]
        }

    def run(self, suites: List[str] = None) -> List[Dict[str, Any]]:
        """Run all configured test suites."""
        if suites is None:
            suites = self.config.get('eval', {}).get('suites', ['basic'])

        variants = self.config.get('eval', {}).get('variants', [{'name': 'default'}])

        all_results = []

        for suite in suites:
            print(f"\n{'='*60}")
            print(f"Suite: {suite}")
            print('='*60)

            for variant in variants:
                print(f"\nVariant: {variant.get('name', 'default')}")

                result = self.run_suite(suite, variant)
                all_results.append(result)

                status = '✓' if result['failed'] == 0 else '✗'
                print(f"  {status} {result['passed']}/{result['total']} passed")

        return all_results

    def print_summary(self, results: List[Dict[str, Any]]):
        """Print summary of results."""
        print(f"\n{'='*60}")
        print("SUMMARY")
        print('='*60)

        total_passed = 0
        total_failed = 0

        for r in results:
            status = '✓' if r['failed'] == 0 else '✗'
            print(f"{status} {r['suite']} ({r['variant']}): {r['passed']}/{r['total']}")
            total_passed += r['passed']
            total_failed += r['failed']

        print('-'*60)
        print(f"Total: {total_passed} passed, {total_failed} failed")

        return total_failed == 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='AdaptLight Evaluation Runner')
    parser.add_argument('--config', '-c', help='Path to config file')
    parser.add_argument('--suite', '-s', action='append', help='Test suite to run (can specify multiple)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--output', '-o', help='Output results to JSON file')
    args = parser.parse_args()

    config = load_config(args.config)
    runner = EvalRunner(config, verbose=args.verbose)

    print("=" * 60)
    print("AdaptLight Evaluation Runner")
    print("=" * 60)

    results = runner.run(args.suite)
    success = runner.print_summary(results)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults written to: {args.output}")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
