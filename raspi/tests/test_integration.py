"""
Integration tests for the agent architecture.

These tests verify end-to-end flows without making actual API calls.
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.state_machine import StateMachine
from voice.tool_registry import ToolRegistry
from voice.agent_executor import MockAgentExecutor
from patterns.library import PatternLibrary


class TestBuiltinToolsRegistration:
    """Test that built-in tools are registered correctly."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)

    def test_builtin_tools_available(self):
        """Test built-in fetch tools are registered."""
        builtin_tools = [
            "fetch_json", "fetch_text", "get_weather",
            "get_time", "random_number", "delay"
        ]

        for tool_name in builtin_tools:
            assert tool_name in self.registry.custom_tool_executor.tools, \
                f"Built-in tool '{tool_name}' not registered"

    def test_get_time_works(self):
        """Test get_time built-in tool."""
        result = self.registry.custom_tool_executor.execute_sync("get_time", {})

        assert result["success"] is True
        assert "hour" in result["result"]
        assert "minute" in result["result"]
        assert "weekday_name" in result["result"]

    def test_random_number_works(self):
        """Test random_number built-in tool."""
        result = self.registry.custom_tool_executor.execute_sync(
            "random_number",
            {"min": 1, "max": 10}
        )

        assert result["success"] is True
        assert 1 <= result["result"]["value"] <= 10


class TestCounterPatternFlow:
    """Test counter pattern implementation flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)
        self.executor = MockAgentExecutor(self.sm)

    @pytest.mark.asyncio
    async def test_counter_pattern_setup(self):
        """Test setting up a counter pattern via tools."""
        # 1. Look up the counter pattern
        pattern_result = await self.registry.execute("getPattern", {"name": "counter"})
        assert pattern_result["success"] is True
        assert "template" in pattern_result["pattern"]

        # 2. Create a random color state
        state_result = await self.registry.execute("createState", {
            "name": "random_color",
            "r": "random()",
            "g": "random()",
            "b": "random()"
        })
        assert state_result["success"] is True

        # 3. Add counter rules
        rules_result = await self.registry.execute("appendRules", {
            "rules": [
                {
                    "from": "*",
                    "on": "button_click",
                    "to": "random_color",
                    "condition": "getData('counter') == None",
                    "action": "setData('counter', 4)"
                },
                {
                    "from": "random_color",
                    "on": "button_click",
                    "to": "random_color",
                    "condition": "getData('counter') > 0",
                    "action": "setData('counter', getData('counter') - 1)"
                },
                {
                    "from": "random_color",
                    "on": "button_click",
                    "to": "off",
                    "condition": "getData('counter') == 0",
                    "action": "setData('counter', None)"
                }
            ]
        })
        assert rules_result["success"] is True
        assert rules_result["rules_added"] == 3

        # Verify rules were created
        assert len(self.sm.rules) == 3


class TestTogglePatternFlow:
    """Test toggle pattern implementation flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)

    @pytest.mark.asyncio
    async def test_toggle_setup(self):
        """Test setting up a simple toggle via tools."""
        # 1. Create a red state
        await self.registry.execute("createState", {
            "name": "red",
            "r": 255,
            "g": 0,
            "b": 0
        })

        # 2. Add toggle rules
        await self.registry.execute("appendRules", {
            "rules": [
                {"from": "off", "on": "button_click", "to": "red"},
                {"from": "red", "on": "button_click", "to": "off"}
            ]
        })

        # 3. Simulate clicks
        self.sm.set_state("off")
        self.sm.execute_transition("button_click")
        assert self.sm.current_state == "red"

        self.sm.execute_transition("button_click")
        assert self.sm.current_state == "off"


class TestDataSourceFlow:
    """Test data source setup and execution flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)

    @pytest.mark.asyncio
    async def test_data_source_with_builtin_tool(self):
        """Test creating a data source that uses a built-in tool."""
        # 1. Create a data source using get_time
        result = await self.registry.execute("createDataSource", {
            "name": "time_checker",
            "interval_ms": 60000,
            "fetch": {"tool": "get_time", "args": {}},
            "store": {"current_hour": "result.hour"},
            "fires": "time_updated"
        })

        assert result["success"] is True
        assert "time_checker" in self.registry.data_sources

    @pytest.mark.asyncio
    async def test_custom_tool_then_data_source(self):
        """Test defining a custom tool then using it in a data source."""
        # 1. Define a custom tool
        tool_result = await self.registry.execute("defineTool", {
            "name": "get_mock_data",
            "code": "return {'value': 42, 'status': 'ok'}",
            "description": "Mock data fetcher"
        })
        assert tool_result["success"] is True

        # 2. Test the tool
        call_result = await self.registry.execute("callTool", {
            "name": "get_mock_data",
            "args": {}
        })
        assert call_result["success"] is True
        assert call_result["result"]["value"] == 42

        # 3. Create a data source using the custom tool
        ds_result = await self.registry.execute("createDataSource", {
            "name": "mock_source",
            "interval_ms": 5000,
            "fetch": {"tool": "get_mock_data", "args": {}},
            "store": {"mock_value": "result.value"},
            "fires": "mock_updated"
        })
        assert ds_result["success"] is True


class TestPriorityAndWildcards:
    """Test priority and wildcard features in integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)

    @pytest.mark.asyncio
    async def test_safety_rule_pattern(self):
        """Test safety rule pattern with wildcards and priority."""
        # Create states
        await self.registry.execute("createState", {
            "name": "active",
            "r": 0,
            "g": 255,
            "b": 0
        })

        # Add rules with different priorities
        await self.registry.execute("appendRules", {
            "rules": [
                # Safety rule - highest priority, any state → off
                {
                    "from": "*",
                    "on": "button_hold",
                    "to": "off",
                    "priority": 100
                },
                # Normal rule - lower priority
                {
                    "from": "off",
                    "on": "button_click",
                    "to": "active",
                    "priority": 0
                },
                # Normal toggle back
                {
                    "from": "active",
                    "on": "button_click",
                    "to": "off",
                    "priority": 0
                }
            ]
        })

        # Test normal flow
        self.sm.set_state("off")
        self.sm.execute_transition("button_click")
        assert self.sm.current_state == "active"

        # Test safety rule from any state
        self.sm.execute_transition("button_hold")
        assert self.sm.current_state == "off"

        # Even from off, hold should keep us at off
        self.sm.execute_transition("button_hold")
        assert self.sm.current_state == "off"


class TestPatternLibraryIntegration:
    """Test pattern library integration with tool registry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)
        self.library = PatternLibrary()

    @pytest.mark.asyncio
    async def test_all_patterns_retrievable(self):
        """Test all patterns can be retrieved via getPattern tool."""
        pattern_names = self.library.list()

        for name in pattern_names:
            result = await self.registry.execute("getPattern", {"name": name})
            assert result["success"] is True, f"Failed to get pattern '{name}'"
            assert "pattern" in result
            assert result["pattern"]["name"] == name

    @pytest.mark.asyncio
    async def test_pattern_has_usable_example(self):
        """Test that pattern examples have valid structure."""
        # Get the toggle pattern
        result = await self.registry.execute("getPattern", {"name": "toggle"})
        pattern = result["pattern"]

        # Check example has required fields
        example = pattern["example"]
        assert "user_request" in example
        assert "output" in example

        # The output should have appendRules
        output = example["output"]
        assert "appendRules" in output


class TestCompleteFlow:
    """Test complete user flows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)

    @pytest.mark.asyncio
    async def test_create_state_add_rules_execute(self):
        """Test full flow: create state, add rules, execute transitions."""
        # 1. Create a custom state
        await self.registry.execute("createState", {
            "name": "blue",
            "r": 0,
            "g": 0,
            "b": 255,
            "description": "Blue light"
        })

        # 2. Check states
        states_result = await self.registry.execute("getStates", {})
        state_names = [s["name"] for s in states_result["states"]]
        assert "blue" in state_names

        # 3. Add rules
        await self.registry.execute("appendRules", {
            "rules": [
                {"from": "off", "on": "button_click", "to": "blue"},
                {"from": "blue", "on": "button_click", "to": "off"}
            ]
        })

        # 4. Check rules
        rules_result = await self.registry.execute("getRules", {})
        assert len(rules_result["rules"]) == 2

        # 5. Set initial state and execute
        await self.registry.execute("setState", {"name": "off"})
        assert self.sm.current_state == "off"

        # 6. Simulate transition
        self.sm.execute_transition("button_click")
        assert self.sm.current_state == "blue"

        # 7. Call done
        done_result = await self.registry.execute("done", {
            "message": "Blue light toggle set up!"
        })
        assert done_result["done"] is True

    @pytest.mark.asyncio
    async def test_variable_based_rules(self):
        """Test rules with conditions using variables."""
        # Set up a counter variable
        await self.registry.execute("setVariable", {
            "key": "click_count",
            "value": 0
        })

        # Create states
        await self.registry.execute("createState", {
            "name": "counting",
            "r": 100,
            "g": 100,
            "b": 255
        })

        # Get variables to verify
        vars_result = await self.registry.execute("getVariables", {})
        assert vars_result["variables"]["click_count"] == 0

        # Update variable
        await self.registry.execute("setVariable", {
            "key": "click_count",
            "value": 5
        })

        vars_result = await self.registry.execute("getVariables", {})
        assert vars_result["variables"]["click_count"] == 5
