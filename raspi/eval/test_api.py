#!/usr/bin/env python3
"""
Test script for API-related features:
- Preset APIs (weather, stock, crypto, etc.)
- Memory (persistent storage)
- Pipelines (button-triggered API checks)
- askUser (user interaction)

Run: python -m eval.test_api
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from voice.agent_executor import AgentExecutor
from voice.tool_registry import ToolRegistry
from core.state_machine import StateMachine
from core.state import State
from core.memory import get_memory
from core.pipeline_registry import get_pipeline_registry


def setup_state_machine():
    """Initialize state machine with defaults."""
    sm = StateMachine()
    sm.states.add_state(State('off', r=0, g=0, b=0, description='LEDs off'))
    sm.states.add_state(State('on', r=255, g=255, b=255, description='White light'))
    sm.add_rule({"from": "off", "on": "button_click", "to": "on"})
    sm.add_rule({"from": "on", "on": "button_click", "to": "off"})
    return sm


def print_separator(char='=', length=60):
    print(char * length)


def print_result(test_name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    icon = "✓" if passed else "✗"
    print(f"  {icon} [{status}] {test_name}")
    if details and not passed:
        print(f"      {details}")


class APITestRunner:
    """Test runner for API-related features."""

    def __init__(self, api_key, model='claude-sonnet-4-20250514'):
        self.api_key = api_key
        self.model = model
        self.passed = 0
        self.failed = 0

    def reset(self):
        """Reset state machine and related components."""
        self.sm = setup_state_machine()
        self.tools = ToolRegistry(self.sm, api_key=self.api_key)

        # Clear memory for clean tests
        memory = get_memory()
        memory.clear()

        # Clear pipelines for clean tests
        registry = get_pipeline_registry()
        registry.clear()

    async def run_all_tests(self):
        """Run all API-related tests."""
        print_separator()
        print("  AdaptLight API Feature Tests")
        print_separator()

        # Test categories
        await self.test_preset_apis()
        await self.test_memory()
        await self.test_pipelines()
        await self.test_agent_api_commands()

        # Summary
        print_separator()
        total = self.passed + self.failed
        print(f"  RESULTS: {self.passed}/{total} passed")
        print_separator()

        return self.failed == 0

    async def test_preset_apis(self):
        """Test preset API functionality."""
        print("\n[Preset APIs]")
        self.reset()

        # Test listAPIs
        result = await self.tools.execute("listAPIs", {})
        passed = result.get("success") and result.get("count", 0) > 0
        print_result("listAPIs returns available APIs", passed,
                    f"Got {result.get('count', 0)} APIs")
        self._record(passed)

        # Test fetchAPI - time (doesn't need external network)
        result = await self.tools.execute("fetchAPI", {"api": "time"})
        passed = result.get("success") and "hour" in result.get("data", {})
        print_result("fetchAPI(time) returns current time", passed,
                    f"Data: {result.get('data', {})}")
        self._record(passed)

        # Test fetchAPI - random
        result = await self.tools.execute("fetchAPI", {"api": "random", "params": {"min": 1, "max": 100}})
        passed = result.get("success") and "value" in result.get("data", {})
        value = result.get("data", {}).get("value", 0)
        passed = passed and 1 <= value <= 100
        print_result("fetchAPI(random) returns value in range", passed,
                    f"Value: {value}")
        self._record(passed)

        # Test fetchAPI - invalid API
        result = await self.tools.execute("fetchAPI", {"api": "invalid_api"})
        passed = not result.get("success") and "error" in result
        print_result("fetchAPI rejects invalid API name", passed)
        self._record(passed)

    async def test_memory(self):
        """Test memory (persistent storage) functionality."""
        print("\n[Memory]")
        self.reset()

        # Test remember
        result = await self.tools.execute("remember", {"key": "location", "value": "San Francisco"})
        passed = result.get("success")
        print_result("remember stores value", passed)
        self._record(passed)

        # Test recall
        result = await self.tools.execute("recall", {"key": "location"})
        passed = result.get("success") and result.get("value") == "San Francisco"
        print_result("recall retrieves stored value", passed,
                    f"Got: {result.get('value')}")
        self._record(passed)

        # Test recall non-existent
        result = await self.tools.execute("recall", {"key": "nonexistent"})
        passed = result.get("success") and result.get("value") is None
        print_result("recall returns null for missing key", passed)
        self._record(passed)

        # Test listMemory
        await self.tools.execute("remember", {"key": "favorite_stock", "value": "TSLA"})
        result = await self.tools.execute("listMemory", {})
        passed = result.get("success") and result.get("count", 0) >= 2
        memories = result.get("memories", {})
        passed = passed and "location" in memories and "favorite_stock" in memories
        print_result("listMemory lists all memories", passed,
                    f"Count: {result.get('count')}")
        self._record(passed)

        # Test forgetMemory
        result = await self.tools.execute("forgetMemory", {"key": "location"})
        passed = result.get("success")

        # Verify it's gone
        result = await self.tools.execute("recall", {"key": "location"})
        passed = passed and result.get("value") is None
        print_result("forgetMemory deletes value", passed)
        self._record(passed)

    async def test_pipelines(self):
        """Test pipeline functionality."""
        print("\n[Pipelines]")
        self.reset()

        # Create test states
        await self.tools.execute("createState", {"name": "green", "r": 0, "g": 255, "b": 0})
        await self.tools.execute("createState", {"name": "red", "r": 255, "g": 0, "b": 0})

        # Test definePipeline - simple pipeline without LLM
        pipeline_def = {
            "name": "test_random",
            "steps": [
                {"do": "fetch", "api": "random", "params": {"min": 1, "max": 100}, "as": "rand"},
                {"do": "setVar", "key": "last_random", "value": "{{rand}}"}
            ],
            "description": "Test pipeline"
        }
        result = await self.tools.execute("definePipeline", pipeline_def)
        passed = result.get("success")
        print_result("definePipeline creates pipeline", passed)
        self._record(passed)

        # Test listPipelines
        result = await self.tools.execute("listPipelines", {})
        passed = result.get("success") and result.get("count", 0) >= 1
        pipelines = result.get("pipelines", [])
        passed = passed and any(p.get("name") == "test_random" for p in pipelines)
        print_result("listPipelines shows defined pipelines", passed,
                    f"Found: {[p.get('name') for p in pipelines]}")
        self._record(passed)

        # Test runPipeline
        result = await self.tools.execute("runPipeline", {"name": "test_random"})
        passed = result.get("success")
        print_result("runPipeline executes pipeline", passed)
        self._record(passed)

        # Test deletePipeline
        result = await self.tools.execute("deletePipeline", {"name": "test_random"})
        passed = result.get("success")

        # Verify it's gone
        result = await self.tools.execute("listPipelines", {})
        passed = passed and not any(p.get("name") == "test_random" for p in result.get("pipelines", []))
        print_result("deletePipeline removes pipeline", passed)
        self._record(passed)

        # Test pipeline with setState mapping (requires states to exist)
        pipeline_with_map = {
            "name": "test_map",
            "steps": [
                {"do": "setVar", "key": "direction", "value": "up"},
                {"do": "setState", "from": "direction", "map": {"up": "green", "down": "red"}}
            ]
        }
        result = await self.tools.execute("definePipeline", pipeline_with_map)
        passed = result.get("success")

        result = await self.tools.execute("runPipeline", {"name": "test_map"})
        passed = passed and result.get("success")
        passed = passed and self.sm.current_state == "green"
        print_result("Pipeline setState with map works", passed,
                    f"Current state: {self.sm.current_state}")
        self._record(passed)

    async def test_agent_api_commands(self):
        """Test agent handling of API-related voice commands."""
        print("\n[Agent API Commands]")
        self.reset()

        # Initialize agent executor
        executor = AgentExecutor(
            state_machine=self.sm,
            api_key=self.api_key,
            model=self.model,
            max_turns=10,
            verbose=False
        )

        # Test: "Remember my location"
        result = await executor.run("Remember that my location is New York")
        memory = get_memory()
        stored = memory.get("location")
        passed = stored is not None and "new york" in stored.lower()
        print_result("Agent handles 'remember location' command", passed,
                    f"Stored: {stored}")
        self._record(passed)

        # Test: "What do you remember?"
        result = await executor.run("What do you remember about me?")
        passed = "location" in result.lower() or "new york" in result.lower()
        print_result("Agent reports stored memories", passed,
                    f"Response: {result[:100]}...")
        self._record(passed)

        # Test: "Create a pipeline for stock check"
        self.reset()
        executor = AgentExecutor(
            state_machine=self.sm,
            api_key=self.api_key,
            model=self.model,
            max_turns=15,
            verbose=False
        )

        result = await executor.run(
            "Set up so when I click, it checks if a random number is above or below 50. "
            "Green if above, red if below. Use a pipeline."
        )

        # Check pipeline was created
        registry = get_pipeline_registry()
        pipelines = registry.list()
        passed = len(pipelines) > 0
        print_result("Agent creates pipeline from voice command", passed,
                    f"Pipelines: {[p.get('name') for p in pipelines]}")
        self._record(passed)

        # Check states were created
        states = [s.name for s in self.sm.states.get_states()]
        has_green = any("green" in s.lower() for s in states)
        has_red = any("red" in s.lower() for s in states)
        passed = has_green and has_red
        print_result("Agent creates required states", passed,
                    f"States: {states}")
        self._record(passed)

    def _record(self, passed):
        """Record test result."""
        if passed:
            self.passed += 1
        else:
            self.failed += 1


async def main():
    """Main entry point."""
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

    # Run tests
    runner = APITestRunner(api_key=api_key, model=model)
    success = await runner.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
