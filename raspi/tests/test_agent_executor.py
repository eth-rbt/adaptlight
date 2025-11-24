"""
Tests for the agent executor and tool registry.
"""
import pytest
import sys
import os
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.state_machine import StateMachine
from voice.tool_registry import ToolRegistry
from voice.agent_executor import AgentExecutor, MockAgentExecutor


class TestToolRegistry:
    """Test the tool registry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)

    def test_builtin_tools_registered(self):
        """Check all built-in tools are registered."""
        tools = self.registry.get_tool_definitions()
        tool_names = [t["name"] for t in tools]

        expected = [
            "getPattern", "getStates", "getRules",
            "createState", "deleteState", "setState",
            "appendRules", "deleteRules",
            "setVariable", "getVariables",
            "defineTool", "createDataSource",
            "done"
        ]

        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_tool_definitions_format(self):
        """Check tool definitions have correct format."""
        tools = self.registry.get_tool_definitions()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"


class TestToolExecution:
    """Test tool execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.registry = ToolRegistry(self.sm)

    @pytest.mark.asyncio
    async def test_create_state(self):
        """Test createState tool."""
        result = await self.registry.execute("createState", {
            "name": "red",
            "r": 255,
            "g": 0,
            "b": 0
        })

        assert result["success"] is True
        assert result["state"] == "red"
        assert "red" in [s["name"] for s in self.sm.get_state_list()]

    @pytest.mark.asyncio
    async def test_set_state(self):
        """Test setState tool."""
        # First create the state
        await self.registry.execute("createState", {
            "name": "blue",
            "r": 0,
            "g": 0,
            "b": 255
        })

        result = await self.registry.execute("setState", {"name": "blue"})

        assert result["success"] is True
        assert self.sm.current_state == "blue"

    @pytest.mark.asyncio
    async def test_append_rules(self):
        """Test appendRules tool."""
        result = await self.registry.execute("appendRules", {
            "rules": [
                {"from": "off", "on": "button_click", "to": "on"},
                {"from": "on", "on": "button_click", "to": "off"}
            ]
        })

        assert result["success"] is True
        assert result["rules_added"] == 2
        assert len(self.sm.rules) == 2

    @pytest.mark.asyncio
    async def test_append_rules_with_priority(self):
        """Test appendRules with priority."""
        await self.registry.execute("appendRules", {
            "rules": [
                {"from": "off", "on": "button_click", "to": "on", "priority": 0},
                {"from": "*", "on": "button_hold", "to": "off", "priority": 100}
            ]
        })

        # Find the wildcard rule
        wildcard_rule = None
        for rule in self.sm.rules:
            if rule.state1 == "*":
                wildcard_rule = rule
                break

        assert wildcard_rule is not None
        assert wildcard_rule.priority == 100

    @pytest.mark.asyncio
    async def test_delete_rules_all(self):
        """Test deleteRules with all=True."""
        # Add some rules first
        await self.registry.execute("appendRules", {
            "rules": [
                {"from": "off", "on": "button_click", "to": "on"},
                {"from": "on", "on": "button_click", "to": "off"}
            ]
        })

        assert len(self.sm.rules) == 2

        result = await self.registry.execute("deleteRules", {"all": True})

        assert result["success"] is True
        assert result["deleted"] == 2
        assert len(self.sm.rules) == 0

    @pytest.mark.asyncio
    async def test_set_variable(self):
        """Test setVariable tool."""
        result = await self.registry.execute("setVariable", {
            "key": "counter",
            "value": 5
        })

        assert result["success"] is True
        assert self.sm.get_data("counter") == 5

    @pytest.mark.asyncio
    async def test_get_variables(self):
        """Test getVariables tool."""
        self.sm.set_data("x", 10)
        self.sm.set_data("y", "hello")

        result = await self.registry.execute("getVariables", {})

        assert result["success"] is True
        assert result["variables"]["x"] == 10
        assert result["variables"]["y"] == "hello"

    @pytest.mark.asyncio
    async def test_done(self):
        """Test done tool."""
        result = await self.registry.execute("done", {
            "message": "All set up!"
        })

        assert result["done"] is True
        assert result["message"] == "All set up!"

    @pytest.mark.asyncio
    async def test_define_tool(self):
        """Test defineTool tool."""
        result = await self.registry.execute("defineTool", {
            "name": "get_number",
            "code": "return 42",
            "description": "Returns the number 42"
        })

        assert result["success"] is True
        assert "get_number" in self.registry.custom_tools

    @pytest.mark.asyncio
    async def test_create_data_source(self):
        """Test createDataSource tool."""
        result = await self.registry.execute("createDataSource", {
            "name": "weather",
            "interval_ms": 3600000,
            "fetch": {"tool": "get_weather", "args": {}},
            "store": {"temperature": "result.temp"},
            "fires": "weather_updated"
        })

        assert result["success"] is True
        assert "weather" in self.registry.data_sources

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Test executing unknown tool."""
        result = await self.registry.execute("nonexistent", {})

        assert "error" in result
        assert "Unknown tool" in result["error"]


class TestMockAgentExecutor:
    """Test the mock agent executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.executor = MockAgentExecutor(self.sm)

    @pytest.mark.asyncio
    async def test_execute_logs_calls(self):
        """Test that tool calls are logged."""
        await self.executor.execute_tool("createState", {
            "name": "red",
            "r": 255,
            "g": 0,
            "b": 0
        })

        assert len(self.executor.call_log) == 1
        assert self.executor.call_log[0]["tool"] == "createState"

    @pytest.mark.asyncio
    async def test_reset_log(self):
        """Test resetting the call log."""
        await self.executor.execute_tool("createState", {
            "name": "red",
            "r": 255,
            "g": 0,
            "b": 0
        })

        self.executor.reset_log()

        assert len(self.executor.call_log) == 0


class TestAgentExecutorInit:
    """Test agent executor initialization."""

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        executor = AgentExecutor()
        assert executor.client is None

    def test_init_with_state_machine(self):
        """Test initialization with state machine."""
        sm = StateMachine()
        executor = AgentExecutor(state_machine=sm)
        assert executor.state_machine == sm
        assert executor.tools.state_machine == sm
