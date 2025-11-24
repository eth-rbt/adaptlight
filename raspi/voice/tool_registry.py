"""
Tool registry for the agent executor.

Manages all tools available to the Claude agent, including:
- State management tools (createState, deleteState, setState)
- Rule management tools (appendRules, deleteRules, getRules)
- Information tools (getPattern, getStates)
- External data tools (defineTool, createDataSource)
- Completion tool (done)
"""

import json
from typing import Dict, Any, Callable, List, Optional

from .custom_tools import CustomToolExecutor, DataSourceManager


class ToolRegistry:
    """Registry of tools available to the agent."""

    def __init__(self, state_machine=None):
        """
        Initialize tool registry.

        Args:
            state_machine: StateMachine instance to operate on
        """
        self.state_machine = state_machine
        self.tools: Dict[str, Dict[str, Any]] = {}

        # Custom tools executor for Claude-defined API integrations
        self.custom_tool_executor = CustomToolExecutor(timeout=30.0)

        # Data source manager for periodic fetching
        self.data_source_manager = DataSourceManager(
            self.custom_tool_executor,
            state_machine
        )

        # Aliases for backward compatibility
        self.custom_tools = self.custom_tool_executor.tools
        self.data_sources = self.data_source_manager.sources

        # Register built-in tools
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register all built-in tools."""

        # Information gathering tools
        self.register_tool(
            name="getPattern",
            description="Look up a pattern template. Available patterns: counter, toggle, cycle, hold_release, timer, schedule, data_reactive",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": ["counter", "toggle", "cycle", "hold_release", "timer", "schedule", "data_reactive"],
                        "description": "Name of the pattern to look up"
                    }
                },
                "required": ["name"]
            },
            handler=self._handle_get_pattern
        )

        self.register_tool(
            name="getStates",
            description="List all existing states with their definitions",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._handle_get_states
        )

        self.register_tool(
            name="getRules",
            description="List all current rules",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._handle_get_rules
        )

        # State management tools
        self.register_tool(
            name="createState",
            description="Create a named light state. Use expressions like 'random()' or 'sin(frame * 0.1) * 255' for dynamic colors.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "State name"},
                    "r": {"type": ["number", "string"], "description": "Red value (0-255) or expression"},
                    "g": {"type": ["number", "string"], "description": "Green value (0-255) or expression"},
                    "b": {"type": ["number", "string"], "description": "Blue value (0-255) or expression"},
                    "speed": {"type": ["number", "null"], "description": "Animation speed in ms (null for static)"},
                    "description": {"type": ["string", "null"], "description": "Human-readable description"}
                },
                "required": ["name", "r", "g", "b"]
            },
            handler=self._handle_create_state
        )

        self.register_tool(
            name="deleteState",
            description="Delete a state by name. Cannot delete 'on' or 'off'.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "State name to delete"}
                },
                "required": ["name"]
            },
            handler=self._handle_delete_state
        )

        self.register_tool(
            name="setState",
            description="Immediately change to a state",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "State name to switch to"}
                },
                "required": ["name"]
            },
            handler=self._handle_set_state
        )

        # Rule management tools
        self.register_tool(
            name="appendRules",
            description="Add transition rules. Rules are evaluated by priority (highest first). Use '*' for wildcard state matching.",
            input_schema={
                "type": "object",
                "properties": {
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string", "description": "Source state ('*' for any)"},
                                "on": {"type": "string", "description": "Transition trigger"},
                                "to": {"type": "string", "description": "Destination state"},
                                "condition": {"type": ["string", "null"], "description": "Condition expression"},
                                "action": {"type": ["string", "null"], "description": "Action expression"},
                                "priority": {"type": "number", "description": "Priority (higher = first)"}
                            },
                            "required": ["from", "on", "to"]
                        },
                        "description": "Array of rules to add"
                    }
                },
                "required": ["rules"]
            },
            handler=self._handle_append_rules
        )

        self.register_tool(
            name="deleteRules",
            description="Delete rules matching criteria",
            input_schema={
                "type": "object",
                "properties": {
                    "indices": {"type": "array", "items": {"type": "number"}, "description": "Rule indices to delete"},
                    "transition": {"type": ["string", "null"], "description": "Delete rules with this transition"},
                    "from_state": {"type": ["string", "null"], "description": "Delete rules from this state"},
                    "to_state": {"type": ["string", "null"], "description": "Delete rules to this state"},
                    "all": {"type": "boolean", "description": "Delete all rules"}
                },
                "required": []
            },
            handler=self._handle_delete_rules
        )

        # Variable management
        self.register_tool(
            name="setVariable",
            description="Set a variable in state_data",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Variable name"},
                    "value": {"description": "Value to set (any type)"}
                },
                "required": ["key", "value"]
            },
            handler=self._handle_set_variable
        )

        self.register_tool(
            name="getVariables",
            description="Get all variables in state_data",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._handle_get_variables
        )

        # External data tools
        self.register_tool(
            name="defineTool",
            description="Define a custom tool for fetching external data. The code should return a dict. Use 'return {...}' at the end.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tool name"},
                    "description": {"type": "string", "description": "What this tool does"},
                    "params": {"type": "object", "description": "Parameter definitions"},
                    "code": {"type": "string", "description": "Python code that returns a dict"},
                    "returns": {"type": "object", "description": "Return value schema"}
                },
                "required": ["name", "code"]
            },
            handler=self._handle_define_tool
        )

        self.register_tool(
            name="callTool",
            description="Execute a custom tool and return its result. Use this to test tools after defining them.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the custom tool to call"},
                    "args": {"type": "object", "description": "Arguments to pass to the tool"}
                },
                "required": ["name"]
            },
            handler=self._handle_call_tool
        )

        self.register_tool(
            name="createDataSource",
            description="Set up periodic data fetching that stores results and fires transitions",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Data source name"},
                    "interval_ms": {"type": "number", "description": "Polling interval in milliseconds"},
                    "fetch": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string", "description": "Tool name to call"},
                            "args": {"type": "object", "description": "Arguments to pass"}
                        },
                        "required": ["tool"]
                    },
                    "store": {"type": "object", "description": "Mapping of variable names to result paths"},
                    "fires": {"type": "string", "description": "Transition to fire after fetch"}
                },
                "required": ["name", "fetch", "fires"]
            },
            handler=self._handle_create_data_source
        )

        self.register_tool(
            name="triggerDataSource",
            description="Trigger an immediate fetch from a data source. Useful for testing.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Data source name to trigger"}
                },
                "required": ["name"]
            },
            handler=self._handle_trigger_data_source
        )

        # Completion tool
        self.register_tool(
            name="done",
            description="Signal completion and provide final message to user",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to show the user"}
                },
                "required": ["message"]
            },
            handler=self._handle_done
        )

    def register_tool(self, name: str, description: str, input_schema: Dict, handler: Callable):
        """Register a tool."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "handler": handler
        }

    def get_tool_definitions(self) -> List[Dict]:
        """Get tool definitions in Claude API format."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"]
            }
            for tool in self.tools.values()
        ]

    async def execute(self, tool_name: str, tool_input: Dict) -> Dict[str, Any]:
        """Execute a tool and return result."""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            handler = self.tools[tool_name]["handler"]
            result = handler(tool_input)
            return result
        except Exception as e:
            return {"error": str(e)}

    # Tool handlers

    def _handle_get_pattern(self, input: Dict) -> Dict:
        """Handle getPattern tool call."""
        from patterns.library import PatternLibrary
        library = PatternLibrary()
        pattern = library.get(input["name"])
        if pattern:
            return {"success": True, "pattern": pattern}
        return {"success": False, "error": f"Pattern '{input['name']}' not found"}

    def _handle_get_states(self, input: Dict) -> Dict:
        """Handle getStates tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}
        states = self.state_machine.get_state_list()
        return {"success": True, "states": states, "current_state": self.state_machine.current_state}

    def _handle_get_rules(self, input: Dict) -> Dict:
        """Handle getRules tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}
        rules = [r.to_dict() for r in self.state_machine.get_rules()]
        return {"success": True, "rules": rules}

    def _handle_create_state(self, input: Dict) -> Dict:
        """Handle createState tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}

        name = input["name"]
        r = input["r"]
        g = input["g"]
        b = input["b"]
        speed = input.get("speed")
        description = input.get("description", "")

        # Register the state
        self.state_machine.register_state(name, description)

        # Store state parameters (used by light_states.py)
        if not hasattr(self.state_machine, 'state_params'):
            self.state_machine.state_params = {}
        self.state_machine.state_params[name] = {
            "r": r, "g": g, "b": b, "speed": speed, "description": description
        }

        return {"success": True, "state": name}

    def _handle_delete_state(self, input: Dict) -> Dict:
        """Handle deleteState tool call."""
        name = input["name"]
        if name in ["on", "off"]:
            return {"error": "Cannot delete built-in states 'on' or 'off'"}

        if not self.state_machine:
            return {"error": "No state machine configured"}

        # Remove from states
        if hasattr(self.state_machine, 'states'):
            self.state_machine.states.remove_state(name)

        # Remove state params
        if hasattr(self.state_machine, 'state_params') and name in self.state_machine.state_params:
            del self.state_machine.state_params[name]

        return {"success": True, "deleted": name}

    def _handle_set_state(self, input: Dict) -> Dict:
        """Handle setState tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}

        name = input["name"]
        self.state_machine.set_state(name)
        return {"success": True, "current_state": name}

    def _handle_append_rules(self, input: Dict) -> Dict:
        """Handle appendRules tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}

        rules = input["rules"]
        added = []
        for rule in rules:
            self.state_machine.add_rule(rule)
            added.append(f"{rule.get('from', rule.get('state1'))} --[{rule.get('on', rule.get('transition'))}]--> {rule.get('to', rule.get('state2'))}")

        return {"success": True, "rules_added": len(rules), "rules": added}

    def _handle_delete_rules(self, input: Dict) -> Dict:
        """Handle deleteRules tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}

        deleted = 0

        if input.get("all"):
            deleted = len(self.state_machine.rules)
            self.state_machine.clear_rules()
        elif input.get("indices"):
            # Delete in reverse order to preserve indices
            for idx in sorted(input["indices"], reverse=True):
                if 0 <= idx < len(self.state_machine.rules):
                    self.state_machine.remove_rule(idx)
                    deleted += 1
        else:
            # Filter by criteria
            to_delete = []
            for i, rule in enumerate(self.state_machine.rules):
                match = True
                if input.get("transition") and rule.transition != input["transition"]:
                    match = False
                if input.get("from_state") and rule.state1 != input["from_state"]:
                    match = False
                if input.get("to_state") and rule.state2 != input["to_state"]:
                    match = False
                if match:
                    to_delete.append(i)

            for idx in sorted(to_delete, reverse=True):
                self.state_machine.remove_rule(idx)
                deleted += 1

        return {"success": True, "deleted": deleted}

    def _handle_set_variable(self, input: Dict) -> Dict:
        """Handle setVariable tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}

        key = input["key"]
        value = input["value"]
        self.state_machine.set_data(key, value)
        return {"success": True, "key": key, "value": value}

    def _handle_get_variables(self, input: Dict) -> Dict:
        """Handle getVariables tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}

        return {"success": True, "variables": dict(self.state_machine.state_data)}

    def _handle_define_tool(self, input: Dict) -> Dict:
        """Handle defineTool tool call."""
        name = input["name"]
        code = input["code"]
        description = input.get("description", "")
        params = input.get("params", {})
        returns = input.get("returns", {})

        # Register with the custom tool executor
        self.custom_tool_executor.register_tool(
            name=name,
            code=code,
            description=description,
            params=params,
            returns=returns
        )

        return {"success": True, "tool": name, "message": f"Tool '{name}' defined"}

    def _handle_create_data_source(self, input: Dict) -> Dict:
        """Handle createDataSource tool call."""
        name = input["name"]
        interval_ms = input.get("interval_ms", 60000)
        fetch = input["fetch"]
        store = input.get("store", {})
        fires = input["fires"]

        # Register with the data source manager
        self.data_source_manager.register_source(
            name=name,
            interval_ms=interval_ms,
            fetch_tool=fetch.get("tool"),
            fetch_args=fetch.get("args", {}),
            store_mapping=store,
            fires_transition=fires
        )

        return {
            "success": True,
            "data_source": name,
            "message": f"Data source '{name}' created (polling every {interval_ms}ms, fires '{fires}')"
        }

    def _handle_call_tool(self, input: Dict) -> Dict:
        """Handle callTool tool call - execute a custom tool."""
        import asyncio
        name = input["name"]
        args = input.get("args", {})

        if name not in self.custom_tool_executor.tools:
            return {"success": False, "error": f"Custom tool '{name}' not found"}

        # Run async executor synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Create a new loop in a thread
            result = self.custom_tool_executor.execute_sync(name, args)
        else:
            result = loop.run_until_complete(
                self.custom_tool_executor.execute(name, args)
            )

        return result

    def _handle_trigger_data_source(self, input: Dict) -> Dict:
        """Handle triggerDataSource tool call - trigger immediate fetch."""
        import asyncio
        name = input["name"]

        if name not in self.data_source_manager.sources:
            return {"success": False, "error": f"Data source '{name}' not found"}

        # Run async trigger synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # For running loops, schedule and wait
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.data_source_manager.trigger_now(name)
                )
                result = future.result()
        else:
            result = loop.run_until_complete(
                self.data_source_manager.trigger_now(name)
            )

        return result

    def _handle_done(self, input: Dict) -> Dict:
        """Handle done tool call."""
        return {"done": True, "message": input["message"]}
