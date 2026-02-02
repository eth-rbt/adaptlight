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
    'random',
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
