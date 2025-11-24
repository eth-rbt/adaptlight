"""
Tests for the custom tools system.
"""
import pytest
import sys
import os
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from voice.custom_tools import CustomToolExecutor, DataSourceManager
from core.state_machine import StateMachine


class TestCustomToolExecutor:
    """Test the custom tool executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = CustomToolExecutor(timeout=5.0)

    def test_register_tool(self):
        """Test registering a custom tool."""
        self.executor.register_tool(
            name="get_number",
            code="return 42",
            description="Returns 42"
        )

        assert "get_number" in self.executor.tools
        assert self.executor.tools["get_number"]["code"] == "return 42"

    def test_get_tool(self):
        """Test getting a registered tool."""
        self.executor.register_tool(
            name="test_tool",
            code="return {'status': 'ok'}",
            description="Test tool"
        )

        tool = self.executor.get_tool("test_tool")
        assert tool is not None
        assert tool["name"] == "test_tool"

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        tool = self.executor.get_tool("nonexistent")
        assert tool is None

    def test_list_tools(self):
        """Test listing all tools."""
        self.executor.register_tool("tool1", "return 1", "Tool 1")
        self.executor.register_tool("tool2", "return 2", "Tool 2")

        tools = self.executor.list_tools()
        assert "tool1" in tools
        assert "tool2" in tools

    def test_execute_sync_simple(self):
        """Test synchronous execution of a simple tool."""
        self.executor.register_tool(
            name="add",
            code="return args['a'] + args['b']"
        )

        result = self.executor.execute_sync("add", {"a": 2, "b": 3})

        assert result["success"] is True
        assert result["result"] == 5

    def test_execute_sync_dict_return(self):
        """Test tool that returns a dict."""
        self.executor.register_tool(
            name="get_data",
            code="return {'temp': 72, 'humidity': 45}"
        )

        result = self.executor.execute_sync("get_data", {})

        assert result["success"] is True
        assert result["result"]["temp"] == 72
        assert result["result"]["humidity"] == 45

    def test_execute_sync_with_math(self):
        """Test tool using math module."""
        self.executor.register_tool(
            name="calc_sqrt",
            code="return math.sqrt(args['n'])"
        )

        result = self.executor.execute_sync("calc_sqrt", {"n": 16})

        assert result["success"] is True
        assert result["result"] == 4.0

    def test_execute_sync_unknown_tool(self):
        """Test executing an unknown tool."""
        result = self.executor.execute_sync("nonexistent", {})

        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_execute_sync_error_handling(self):
        """Test that errors are caught and returned."""
        self.executor.register_tool(
            name="broken",
            code="return 1/0"
        )

        result = self.executor.execute_sync("broken", {})

        assert result["success"] is False
        assert "division by zero" in result["error"]

    def test_execute_sync_multiline_code(self):
        """Test multiline code execution."""
        self.executor.register_tool(
            name="multiline",
            code="""
x = args.get('x', 0)
y = args.get('y', 0)
total = x + y
return {'sum': total, 'doubled': total * 2}
"""
        )

        result = self.executor.execute_sync("multiline", {"x": 5, "y": 3})

        assert result["success"] is True
        assert result["result"]["sum"] == 8
        assert result["result"]["doubled"] == 16

    @pytest.mark.asyncio
    async def test_execute_async(self):
        """Test async execution."""
        self.executor.register_tool(
            name="async_test",
            code="return args['value'] * 2"
        )

        result = await self.executor.execute("async_test", {"value": 21})

        assert result["success"] is True
        assert result["result"] == 42


class TestDataSourceManager:
    """Test the data source manager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = CustomToolExecutor()
        self.sm = StateMachine()
        self.manager = DataSourceManager(self.executor, self.sm)

        # Register a test tool
        self.executor.register_tool(
            name="get_temp",
            code="return {'temp': 75, 'humidity': 50}"
        )

    def test_register_source(self):
        """Test registering a data source."""
        self.manager.register_source(
            name="weather",
            interval_ms=60000,
            fetch_tool="get_temp",
            fetch_args={},
            store_mapping={"temperature": "result.temp"},
            fires_transition="weather_updated"
        )

        assert "weather" in self.manager.sources

    def test_get_source(self):
        """Test getting a registered source."""
        self.manager.register_source(
            name="test",
            interval_ms=1000,
            fetch_tool="get_temp",
            fetch_args={},
            store_mapping={},
            fires_transition="test_updated"
        )

        source = self.manager.get_source("test")
        assert source is not None
        assert source["name"] == "test"

    def test_get_nonexistent_source(self):
        """Test getting a source that doesn't exist."""
        source = self.manager.get_source("nonexistent")
        assert source is None

    def test_list_sources(self):
        """Test listing all sources."""
        self.manager.register_source(
            name="src1",
            interval_ms=1000,
            fetch_tool="get_temp",
            fetch_args={},
            store_mapping={},
            fires_transition="updated1"
        )
        self.manager.register_source(
            name="src2",
            interval_ms=2000,
            fetch_tool="get_temp",
            fetch_args={},
            store_mapping={},
            fires_transition="updated2"
        )

        sources = self.manager.list_sources()
        assert "src1" in sources
        assert "src2" in sources

    def test_extract_value_simple(self):
        """Test simple value extraction."""
        data = {"temp": 72}
        value = self.manager._extract_value(data, "temp")
        assert value == 72

    def test_extract_value_with_result_prefix(self):
        """Test value extraction with result. prefix."""
        data = {"temp": 72}
        value = self.manager._extract_value(data, "result.temp")
        assert value == 72

    def test_extract_value_nested(self):
        """Test nested value extraction."""
        data = {"current": {"temp": 72, "conditions": {"sky": "clear"}}}
        value = self.manager._extract_value(data, "current.temp")
        assert value == 72

        value = self.manager._extract_value(data, "current.conditions.sky")
        assert value == "clear"

    @pytest.mark.asyncio
    async def test_fetch_source(self):
        """Test fetching from a data source."""
        self.manager.register_source(
            name="weather",
            interval_ms=60000,
            fetch_tool="get_temp",
            fetch_args={},
            store_mapping={"temperature": "result.temp", "humidity": "result.humidity"},
            fires_transition="weather_updated"
        )

        result = await self.manager.trigger_now("weather")

        assert result["success"] is True
        assert self.sm.get_data("temperature") == 75
        assert self.sm.get_data("humidity") == 50

    @pytest.mark.asyncio
    async def test_fetch_unknown_source(self):
        """Test fetching from an unknown source."""
        result = await self.manager.trigger_now("nonexistent")

        assert result["success"] is False
        assert "Unknown source" in result["error"]


class TestCustomToolsIntegration:
    """Integration tests for custom tools with tool registry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()

        # Import here to avoid circular imports
        from voice.tool_registry import ToolRegistry
        self.registry = ToolRegistry(self.sm)

    @pytest.mark.asyncio
    async def test_define_and_call_tool(self):
        """Test defining and calling a custom tool via registry."""
        # Define a tool
        result = await self.registry.execute("defineTool", {
            "name": "multiply",
            "code": "return args['x'] * args['y']",
            "description": "Multiplies two numbers"
        })

        assert result["success"] is True

        # Call the tool
        result = await self.registry.execute("callTool", {
            "name": "multiply",
            "args": {"x": 6, "y": 7}
        })

        assert result["success"] is True
        assert result["result"] == 42

    @pytest.mark.asyncio
    async def test_define_data_source(self):
        """Test defining a data source via registry."""
        # First define the tool
        await self.registry.execute("defineTool", {
            "name": "get_value",
            "code": "return {'value': 100}"
        })

        # Create the data source
        result = await self.registry.execute("createDataSource", {
            "name": "value_source",
            "interval_ms": 60000,
            "fetch": {"tool": "get_value", "args": {}},
            "store": {"current_value": "result.value"},
            "fires": "value_updated"
        })

        assert result["success"] is True
        assert "value_source" in self.registry.data_sources

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self):
        """Test calling a tool that doesn't exist."""
        result = await self.registry.execute("callTool", {
            "name": "nonexistent"
        })

        assert result["success"] is False
        assert "not found" in result["error"]


class TestSafeExecution:
    """Test safety restrictions in custom tool execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = CustomToolExecutor(timeout=2.0)

    def test_no_file_operations(self):
        """Test that file operations are restricted."""
        self.executor.register_tool(
            name="read_file",
            code="return open('/etc/passwd').read()"
        )

        result = self.executor.execute_sync("read_file", {})

        # Should fail - open() not in restricted builtins
        assert result["success"] is False

    def test_no_exec(self):
        """Test that exec is not available."""
        self.executor.register_tool(
            name="try_exec",
            code="exec('x = 1'); return x"
        )

        result = self.executor.execute_sync("try_exec", {})

        # Should fail - exec not in restricted builtins
        assert result["success"] is False

    def test_no_import(self):
        """Test that __import__ is restricted."""
        self.executor.register_tool(
            name="try_import",
            code="return __import__('os').system('ls')"
        )

        result = self.executor.execute_sync("try_import", {})

        # Should fail - __import__ not available
        assert result["success"] is False

    def test_allowed_json(self):
        """Test that json module is allowed."""
        self.executor.register_tool(
            name="use_json",
            code="return json.loads('{\"x\": 1}')"
        )

        result = self.executor.execute_sync("use_json", {})

        assert result["success"] is True
        assert result["result"]["x"] == 1
