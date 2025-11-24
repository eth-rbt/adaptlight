"""
Custom tools system for Claude-defined API integrations.

Allows Claude to write Python code that fetches external data (weather, stocks, etc.).
The code runs in a restricted environment for safety.

Usage:
1. Claude calls defineTool() with name, code, and description
2. The code is stored in the tool registry
3. Data sources can call custom tools via fetch.tool
4. Results are stored in variables and trigger transitions
"""

import asyncio
import traceback
from typing import Dict, Any, Optional


# Allowed modules for custom tool execution
ALLOWED_IMPORTS = {
    'requests',
    'json',
    'datetime',
    'time',
    'math',
    're',
    'urllib',
    'urllib.parse',
}

# Restricted globals for safety
RESTRICTED_BUILTINS = {
    'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter', 'float',
    'format', 'frozenset', 'int', 'isinstance', 'issubclass', 'len',
    'list', 'map', 'max', 'min', 'pow', 'range', 'reversed', 'round',
    'set', 'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
    'True', 'False', 'None',
}


class CustomToolExecutor:
    """Executes Claude-defined custom tools in a restricted environment."""

    def __init__(self, timeout: float = 30.0):
        """
        Initialize custom tool executor.

        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, code: str, description: str = "",
                      params: Dict = None, returns: Dict = None):
        """
        Register a custom tool.

        Args:
            name: Tool name
            code: Python code (should use 'return' for result)
            description: What the tool does
            params: Parameter schema
            returns: Return value schema
        """
        self.tools[name] = {
            "name": name,
            "code": code,
            "description": description,
            "params": params or {},
            "returns": returns or {},
        }

    def get_tool(self, name: str) -> Optional[Dict]:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> list:
        """List all registered custom tools."""
        return list(self.tools.keys())

    def _create_safe_globals(self) -> Dict:
        """Create a restricted globals dict for code execution."""
        safe_builtins = {k: __builtins__[k] for k in RESTRICTED_BUILTINS
                        if k in __builtins__}

        # Add safe imports
        safe_globals = {
            '__builtins__': safe_builtins,
        }

        # Import allowed modules
        for module_name in ALLOWED_IMPORTS:
            try:
                parts = module_name.split('.')
                if len(parts) == 1:
                    safe_globals[module_name] = __import__(module_name)
                else:
                    parent = __import__(parts[0])
                    for part in parts[1:]:
                        parent = getattr(parent, part)
                    safe_globals[parts[-1]] = parent
            except ImportError:
                pass  # Module not available

        return safe_globals

    def execute_sync(self, name: str, args: Dict = None) -> Dict[str, Any]:
        """
        Execute a custom tool synchronously.

        Args:
            name: Tool name
            args: Arguments to pass to the tool

        Returns:
            Dict with 'success' and 'result' or 'error'
        """
        if name not in self.tools:
            return {"success": False, "error": f"Unknown tool: {name}"}

        tool = self.tools[name]
        code = tool["code"]
        args = args or {}

        try:
            # Create execution environment
            safe_globals = self._create_safe_globals()

            # Add args to globals so function can access it
            safe_globals["args"] = args
            # Also add individual args as globals
            for k, v in args.items():
                safe_globals[k] = v

            safe_locals = {}

            # Wrap code in a function if it uses 'return'
            if 'return' in code:
                wrapped_code = "def _tool_func(args):\n"
                for line in code.split('\n'):
                    if line.strip():  # Skip empty lines
                        wrapped_code += f"    {line}\n"
                wrapped_code += "_result = _tool_func(args)"
                exec(wrapped_code, safe_globals, safe_locals)
                result = safe_locals.get('_result')
            else:
                safe_locals["args"] = args
                exec(code, safe_globals, safe_locals)
                result = safe_locals.get('result')

            return {"success": True, "result": result}

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    async def execute(self, name: str, args: Dict = None) -> Dict[str, Any]:
        """
        Execute a custom tool asynchronously with timeout.

        Args:
            name: Tool name
            args: Arguments to pass to the tool

        Returns:
            Dict with 'success' and 'result' or 'error'
        """
        try:
            # Run in thread pool with timeout
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self.execute_sync, name, args),
                timeout=self.timeout
            )
            return result
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Tool '{name}' timed out after {self.timeout}s"
            }


class DataSourceManager:
    """Manages periodic data sources that fetch and store external data."""

    def __init__(self, tool_executor: CustomToolExecutor, state_machine=None):
        """
        Initialize data source manager.

        Args:
            tool_executor: CustomToolExecutor for running tools
            state_machine: StateMachine for storing data and firing transitions
        """
        self.tool_executor = tool_executor
        self.state_machine = state_machine
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    def register_source(self, name: str, interval_ms: int,
                        fetch_tool: str, fetch_args: Dict,
                        store_mapping: Dict, fires_transition: str):
        """
        Register a data source.

        Args:
            name: Data source name
            interval_ms: Polling interval in milliseconds
            fetch_tool: Name of custom tool to call
            fetch_args: Arguments to pass to the tool
            store_mapping: {variable_name: "result.path"} mapping
            fires_transition: Transition to fire after successful fetch
        """
        self.sources[name] = {
            "name": name,
            "interval_ms": interval_ms,
            "fetch_tool": fetch_tool,
            "fetch_args": fetch_args,
            "store_mapping": store_mapping,
            "fires_transition": fires_transition,
            "last_fetch": None,
            "last_error": None,
        }

    def get_source(self, name: str) -> Optional[Dict]:
        """Get a data source by name."""
        return self.sources.get(name)

    def list_sources(self) -> list:
        """List all registered data sources."""
        return list(self.sources.keys())

    def _extract_value(self, data: Any, path: str) -> Any:
        """
        Extract a value from data using dot notation.

        Args:
            data: The data to extract from
            path: Dot-separated path like "result.temp" or just "temp"

        Returns:
            The extracted value
        """
        if path.startswith("result."):
            path = path[7:]

        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

        return current

    async def _fetch_source(self, name: str) -> Dict[str, Any]:
        """
        Fetch data from a source and store results.

        Args:
            name: Data source name

        Returns:
            Dict with fetch status
        """
        if name not in self.sources:
            return {"success": False, "error": f"Unknown source: {name}"}

        source = self.sources[name]

        # Execute the fetch tool
        result = await self.tool_executor.execute(
            source["fetch_tool"],
            source["fetch_args"]
        )

        if not result["success"]:
            source["last_error"] = result.get("error")
            return result

        # Store results in state machine variables
        if self.state_machine and source["store_mapping"]:
            for var_name, path in source["store_mapping"].items():
                value = self._extract_value(result["result"], path)
                self.state_machine.set_data(var_name, value)

        # Fire the transition
        if self.state_machine and source["fires_transition"]:
            self.state_machine.execute_transition(source["fires_transition"])

        source["last_fetch"] = result
        source["last_error"] = None

        return {"success": True, "result": result["result"]}

    async def _run_source_loop(self, name: str):
        """Run the fetch loop for a data source."""
        source = self.sources[name]
        interval_s = source["interval_ms"] / 1000.0

        while self._running and name in self.sources:
            try:
                await self._fetch_source(name)
            except Exception as e:
                source["last_error"] = str(e)

            await asyncio.sleep(interval_s)

    async def start(self):
        """Start all data source loops."""
        self._running = True
        for name in self.sources:
            if name not in self.tasks:
                self.tasks[name] = asyncio.create_task(self._run_source_loop(name))

    async def stop(self):
        """Stop all data source loops."""
        self._running = False
        for name, task in self.tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.tasks.clear()

    async def trigger_now(self, name: str) -> Dict[str, Any]:
        """
        Trigger an immediate fetch for a data source.

        Args:
            name: Data source name

        Returns:
            Fetch result
        """
        return await self._fetch_source(name)
