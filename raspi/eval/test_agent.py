#!/usr/bin/env python3
"""
Non-interactive test script for AgentExecutor.
Runs predefined test commands and reports results.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from voice.agent_executor import AgentExecutor
from core.state_machine import StateMachine
from core.state import State


def setup_state_machine():
    """Initialize state machine with defaults."""
    sm = StateMachine()
    sm.states.add_state(State('off', r=0, g=0, b=0, description='LEDs off'))
    sm.states.add_state(State('on', r=255, g=255, b=255, description='White light'))
    sm.add_rule({"from": "off", "on": "button_click", "to": "on"})
    sm.add_rule({"from": "on", "on": "button_click", "to": "off"})
    return sm


def print_status(sm):
    """Print current state machine status."""
    print(f"\n  Current state: {sm.current_state}")
    print(f"  States: {[s.name for s in sm.states.get_states()]}")
    print(f"  Rules: {len(sm.get_rules())}")
    for i, r in enumerate(sm.get_rules()):
        print(f"    [{i}] {r.state1} --[{r.transition}]--> {r.state2}")
    print(f"  Variables: {sm.state_data}")


async def run_test(executor, sm, command, description):
    """Run a single test command."""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"Command: \"{command}\"")
    print("="*60)

    try:
        result = await executor.run(command)
        print(f"\nAgent Response: {result}")
        print_status(sm)
        return True
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    # Load API key
    config_file = Path(__file__).parent.parent / 'config.yaml'
    if not config_file.exists():
        print(f"Error: config.yaml not found")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    api_key = config.get('claude', {}).get('api_key')
    if not api_key:
        print("Error: claude.api_key not found in config.yaml")
        sys.exit(1)

    model = config.get('claude', {}).get('model', 'claude-sonnet-4-20250514')
    print(f"Using model: {model}")

    # Test cases
    tests = [
        ("make a red state", "Create simple state"),
        ("set up a toggle between red and blue on click", "Toggle pattern"),
        ("click", "Simulate click (should trigger toggle)"),
        ("click", "Simulate click again"),
        ("reset everything and restore the default on/off toggle", "Reset to defaults"),
        ("click", "Click after reset (should toggle on/off)"),
    ]

    # Single state machine for all tests (persistent)
    sm = setup_state_machine()
    executor = AgentExecutor(
        state_machine=sm,
        api_key=api_key,
        model=model,
        max_turns=10,
        verbose=True
    )

    # Run tests
    passed = 0
    failed = 0

    for command, description in tests:
        if command == "click":
            # Simulate button click
            print(f"\n{'='*60}")
            print(f"TEST: {description}")
            print(f"Simulating: button_click")
            print("="*60)
            old = sm.current_state
            result = sm.execute_transition("button_click")
            new = sm.current_state
            print(f"  {old} -> {new} (transition: {result})")
            print_status(sm)
            passed += 1
        else:
            success = await run_test(executor, sm, command, description)
            if success:
                passed += 1
            else:
                failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(main())
