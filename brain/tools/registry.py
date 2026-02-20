"""
Tool registry for the agent executor.

Manages all tools available to the Claude agent, including:
- State management tools (createState, deleteState, setState)
- Rule management tools (appendRules, deleteRules, getRules)
- Information tools (getPattern, getStates, getDocs)
- Preset API tools (listAPIs, fetchAPI)
- Memory tools (remember, recall, forgetMemory, listMemory)
- Pipeline tools (definePipeline, runPipeline, deletePipeline, listPipelines)
- Custom tools (defineTool, callTool)
- User interaction tools (askUser)
- Completion tool (done)
"""

import json
import re
from typing import Dict, Any, Callable, List, Optional

from .custom import CustomToolExecutor
from brain.apis.api_executor import APIExecutor
from brain.apis.preset_apis import PRESET_APIS, list_apis, get_api_info
from brain.core.memory import get_memory
from brain.core.pipeline_registry import get_pipeline_registry
from brain.core.pipeline import PipelineExecutor


class ToolRegistry:
    """Registry of tools available to the agent."""

    def __init__(self, state_machine=None, api_key: str = None):
        """
        Initialize tool registry.

        Args:
            state_machine: StateMachine instance to operate on
            api_key: Anthropic API key for LLM parsing in pipelines
        """
        self.state_machine = state_machine
        self.api_key = api_key
        self.tools: Dict[str, Dict[str, Any]] = {}

        # Custom tools executor for Claude-defined API integrations
        self.custom_tool_executor = CustomToolExecutor(timeout=30.0)

        # Preset API executor for curated APIs
        self.api_executor = APIExecutor(timeout=15.0)

        # Memory for persistent storage
        self.memory = get_memory()

        # Pipeline registry and executor
        self.pipeline_registry = get_pipeline_registry()
        self.pipeline_executor = PipelineExecutor(
            api_executor=self.api_executor,
            llm_parser=self._get_llm_parser(),
            state_machine=state_machine,
            memory=self.memory
        )

        # Wire up pipeline executor to state machine for rule-triggered pipelines
        if state_machine:
            state_machine.pipeline_executor = self.pipeline_executor

        # Pending question for askUser (set by handler, read by agent loop)
        self.pending_question: Optional[str] = None

        # Aliases for backward compatibility
        self.custom_tools = self.custom_tool_executor.tools

        # Register agent tools
        self._register_agent_tools()

    def _get_llm_parser(self):
        """Get LLM parser instance for pipeline steps."""
        if self.api_key:
            from brain.llm.llm_parser import LLMParser
            return LLMParser(api_key=self.api_key)
        return None

    @staticmethod
    def _coerce_inline_value(raw: str):
        value = str(raw or '').strip()
        if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
            value = value[1:-1]

        lowered = value.lower()
        if lowered in ('true', 'false'):
            return lowered == 'true'

        if re.match(r'^-?\d+$', value):
            try:
                return int(value)
            except Exception:
                return value

        if re.match(r'^-?\d+\.\d+$', value):
            try:
                return float(value)
            except Exception:
                return value

        return value

    @classmethod
    def _extract_vision_reactive_from_code(cls, code: str) -> Optional[Dict[str, Any]]:
        if not isinstance(code, str) or not code.strip():
            return None

        inline = {}
        allowed = {
            'enabled', 'prompt', 'model', 'engine', 'cv_detector', 'interval_ms',
            'event', 'cooldown_ms'
        }

        for line in code.splitlines():
            match = re.match(r'^\s*(?:#|//)\s*vision\.(\w+)\s*[:=]\s*(.+?)\s*$', line)
            if not match:
                continue

            key = match.group(1)
            if key not in allowed:
                continue

            inline[key] = cls._coerce_inline_value(match.group(2))

        if not inline:
            return None

        inline.setdefault('enabled', True)
        return inline

    def _register_agent_tools(self):
        """Register all agent tools."""

        # Information gathering tools
        self.register_tool(
            name="getPattern",
            description="Look up a pattern template. Available patterns: counter, toggle, cycle, hold_release, timer, schedule, data_reactive, timed, sunrise, api_reactive, pipeline",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": ["counter", "toggle", "cycle", "hold_release", "timer", "schedule", "data_reactive", "timed", "sunrise", "api_reactive", "pipeline"],
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

        self.register_tool(
            name="getDocs",
            description="Look up detailed documentation on a topic. Use when you need syntax details, examples, or parameter info. Topics: states, animations, voice_reactive, rules, timer, interval, schedule, pipelines, fetch, llm, apis, memory, variables, expressions, complete_examples",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": ["states", "animations", "voice_reactive", "rules", "timer", "interval", "schedule", "pipelines", "fetch", "llm", "apis", "memory", "variables", "expressions", "complete_examples"],
                        "description": "Topic to look up"
                    }
                },
                "required": ["topic"]
            },
            handler=self._handle_get_docs
        )

        # State management tools
        self.register_tool(
            name="createState",
            description="""Create a named light state. Two formats supported:

1. Original format (r/g/b): Use expressions like 'sin(frame * 0.1) * 255' for animations.
2. Code format: Define render(prev, t) function that returns ((r,g,b), next_ms).
   - next_ms > 0: animation continues
   - next_ms = None: static state
   - next_ms = 0: state complete (triggers state_complete transition)

Use voice_reactive for mic-reactive brightness.
Use vision_reactive for camera-reactive behavior:
   - All vision output writes to getData('vision')
   - CV: fast (100ms+), outputs raw data (person_count, hand_positions, etc.)
   - VLM: slow (2000ms+), can emit events via _event field
Use api_reactive for API-reactive behavior:
   - Polls preset APIs or custom URLs at interval_ms
   - Writes results to getData(key)
   - Can emit events for rule transitions""",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "State name"},
                    "r": {"type": ["number", "string", "null"], "description": "Red value (0-255) or expression (original format)"},
                    "g": {"type": ["number", "string", "null"], "description": "Green value (0-255) or expression (original format)"},
                    "b": {"type": ["number", "string", "null"], "description": "Blue value (0-255) or expression (original format)"},
                    "speed": {"type": ["number", "null"], "description": "Animation speed in ms (null for static, original format)"},
                    "code": {"type": ["string", "null"], "description": "Python code defining render(prev, t) function (code format)"},
                    "description": {"type": ["string", "null"], "description": "Human-readable description"},
                    "voice_reactive": {
                        "type": ["object", "null"],
                        "description": "Enable mic-reactive brightness. LED brightness follows audio input volume.",
                        "properties": {
                            "enabled": {"type": "boolean", "description": "Enable voice-reactive mode"},
                            "color": {"type": "array", "items": {"type": "number"}, "description": "Optional [r,g,b] override color"},
                            "smoothing_alpha": {"type": "number", "description": "Smoothing factor 0-1 (lower=smoother, default 0.6)"},
                            "min_amplitude": {"type": "number", "description": "Noise floor threshold (default 100)"},
                            "max_amplitude": {"type": "number", "description": "Full brightness threshold (default 5000)"}
                        }
                    },
                    "vision_reactive": {
                        "type": ["object", "null"],
                        "description": "Enable camera-reactive behavior. Output writes to getData('vision'). CV outputs raw data, VLM can emit events.",
                        "properties": {
                            "enabled": {"type": "boolean", "description": "Enable vision-reactive mode"},
                            "prompt": {"type": "string", "description": "What to observe (required for VLM, optional for CV)"},
                            "model": {"type": "string", "description": "OpenAI vision model (default gpt-4o-mini)"},
                            "engine": {"type": "string", "description": "cv | vlm | hybrid. CV is fast (100ms+), VLM is slow (2000ms+)"},
                            "cv_detector": {"type": "string", "description": "opencv_hog | opencv_face | opencv_motion"},
                            "interval_ms": {"type": "number", "description": "Analyze interval: CV >=100ms, VLM >=2000ms"},
                            "event": {"type": "string", "description": "Event name for VLM to emit (VLM only, CV doesn't emit events)"},
                            "cooldown_ms": {"type": "number", "description": "Minimum time between event emissions"}
                        }
                    },
                    "api_reactive": {
                        "type": ["object", "null"],
                        "description": "Enable API-reactive behavior. Polls APIs and writes results to getData(key). Can emit events for rule transitions.",
                        "properties": {
                            "enabled": {"type": "boolean", "description": "Enable API-reactive mode"},
                            "api": {"type": "string", "description": "Preset API name (weather, stock, crypto, etc.)"},
                            "url": {"type": "string", "description": "Custom URL (overrides api if provided)"},
                            "method": {"type": "string", "description": "HTTP method for custom URL (GET, POST, etc.)"},
                            "headers": {"type": "object", "description": "Custom headers for URL requests"},
                            "params": {"type": "object", "description": "API parameters or request body"},
                            "interval_ms": {"type": "number", "description": "Polling interval in ms (min 1000ms)"},
                            "key": {"type": "string", "description": "Key to write results to in state_data"},
                            "event": {"type": "string", "description": "Event to emit when data updates (for rule transitions)"},
                            "cooldown_ms": {"type": "number", "description": "Minimum time between event emissions"}
                        }
                    }
                },
                "required": ["name"]
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
            description="Add transition rules. Rules are evaluated by priority (highest first). Use '*' for wildcard state matching. Supports pipelines, time-based triggers, and vision watchers via trigger_config.vision. Use 'state_complete' trigger for auto-transitions when a state's animation finishes.",
            input_schema={
                "type": "object",
                "properties": {
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string", "description": "Source state ('*' for any, 'prefix/*' for prefix match)"},
                                "on": {"type": "string", "description": "Trigger: button_click, button_hold, button_release, button_double_click, timer, interval, schedule, state_complete, or vision_* custom events"},
                                "to": {"type": "string", "description": "Destination state"},
                                "condition": {"type": ["string", "null"], "description": "Condition expression e.g. \"getData('x') > 0\""},
                                "action": {"type": ["string", "null"], "description": "Action expression e.g. \"setData('x', getData('x') - 1)\""},
                                "priority": {"type": "number", "description": "Priority (higher = checked first, default 0)"},
                                "pipeline": {"type": ["string", "null"], "description": "Pipeline name to execute when rule fires"},
                                "enabled": {"type": "boolean", "description": "Whether rule is active (default true)"},
                                "trigger_config": {
                                    "type": ["object", "null"],
                                    "description": "Config for time-based triggers (timer/interval/schedule) or vision watcher config",
                                    "properties": {
                                        "delay_ms": {"type": "number", "description": "Delay in ms (for timer/interval)"},
                                        "repeat": {"type": "boolean", "description": "Repeat interval (for interval)"},
                                        "auto_cleanup": {"type": "boolean", "description": "Remove rule after firing (for timer)"},
                                        "hour": {"type": "number", "description": "Hour 0-23 (for schedule)"},
                                        "minute": {"type": "number", "description": "Minute 0-59 (for schedule)"},
                                        "repeat_daily": {"type": "boolean", "description": "Repeat daily (for schedule)"},
                                        "vision": {
                                            "type": "object",
                                            "description": "Rule-level vision watcher. Output writes to getData('vision'). VLM can emit events to trigger this rule.",
                                            "properties": {
                                                "enabled": {"type": "boolean", "description": "Enable this watcher"},
                                                "prompt": {"type": "string", "description": "What to observe (required for VLM)"},
                                                "event": {"type": "string", "description": "Event to emit (VLM only, should start with vision_)"},
                                                "model": {"type": "string", "description": "OpenAI vision model"},
                                                "engine": {"type": "string", "description": "cv | vlm | hybrid"},
                                                "cv_detector": {"type": "string", "description": "opencv_hog | opencv_face | opencv_motion"},
                                                "interval_ms": {"type": "number", "description": "Analyze interval: CV >=100ms, VLM >=2000ms"},
                                                "cooldown_ms": {"type": "number", "description": "Cooldown for repeated events"}
                                            }
                                        }
                                    }
                                }
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

        # Preset API tools
        self.register_tool(
            name="listAPIs",
            description="List available preset APIs. Returns API names, descriptions, parameters, and example responses.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._handle_list_apis
        )

        self.register_tool(
            name="fetchAPI",
            description="Call a preset API to get raw data. Use listAPIs() to see available APIs. You decide what colors to use based on the data.",
            input_schema={
                "type": "object",
                "properties": {
                    "api": {
                        "type": "string",
                        "enum": list(PRESET_APIS.keys()),
                        "description": "Name of the preset API"
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the API call (e.g., {location: 'NYC'} for weather)"
                    }
                },
                "required": ["api"]
            },
            handler=self._handle_fetch_api
        )

        # Memory tools
        self.register_tool(
            name="remember",
            description="Store something in memory (persists across sessions). Use for user preferences like location, favorite colors, stock symbols, etc.",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key (e.g., 'location', 'favorite_stock')"},
                    "value": {"description": "Value to store (any type)"}
                },
                "required": ["key", "value"]
            },
            handler=self._handle_remember
        )

        self.register_tool(
            name="recall",
            description="Retrieve something from memory. Returns null if not found.",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key to retrieve"}
                },
                "required": ["key"]
            },
            handler=self._handle_recall
        )

        self.register_tool(
            name="forgetMemory",
            description="Delete something from memory.",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key to delete"}
                },
                "required": ["key"]
            },
            handler=self._handle_forget_memory
        )

        self.register_tool(
            name="listMemory",
            description="List all stored memories.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._handle_list_memory
        )

        # Pipeline tools
        self.register_tool(
            name="definePipeline",
            description="Define a pipeline for button-triggered actions. Pipelines can fetch APIs, parse with LLM, and set states.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Pipeline name"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "do": {
                                    "type": "string",
                                    "enum": ["fetch", "llm", "setState", "setVar", "wait", "run"],
                                    "description": "Step type"
                                },
                                "api": {"type": "string", "description": "For fetch: API name"},
                                "params": {"type": "object", "description": "For fetch: API parameters"},
                                "input": {"type": "string", "description": "For llm: input data (use {{var}})"},
                                "prompt": {"type": "string", "description": "For llm: prompt text"},
                                "state": {"type": "string", "description": "For setState: state name"},
                                "from": {"type": "string", "description": "For setState: variable to map from"},
                                "map": {"type": "object", "description": "For setState: value->state mapping"},
                                "key": {"type": "string", "description": "For setVar: variable name"},
                                "value": {"description": "For setVar: variable value"},
                                "ms": {"type": "number", "description": "For wait: milliseconds"},
                                "pipeline": {"type": "string", "description": "For run: pipeline name"},
                                "as": {"type": "string", "description": "Store result in variable"},
                                "if": {"type": "string", "description": "Condition for step execution"}
                            },
                            "required": ["do"]
                        },
                        "description": "Pipeline steps"
                    },
                    "description": {"type": "string", "description": "Human-readable description"}
                },
                "required": ["name", "steps"]
            },
            handler=self._handle_define_pipeline
        )

        self.register_tool(
            name="runPipeline",
            description="Execute a pipeline immediately.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Pipeline name to execute"}
                },
                "required": ["name"]
            },
            handler=self._handle_run_pipeline
        )

        self.register_tool(
            name="deletePipeline",
            description="Delete a pipeline.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Pipeline name to delete"}
                },
                "required": ["name"]
            },
            handler=self._handle_delete_pipeline
        )

        self.register_tool(
            name="listPipelines",
            description="List all defined pipelines.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._handle_list_pipelines
        )

        # User interaction tools
        self.register_tool(
            name="askUser",
            description="Ask the user a question and wait for their response. Use when you need information like location, preferences, etc.",
            input_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to ask the user"}
                },
                "required": ["question"]
            },
            handler=self._handle_ask_user
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
        from brain.patterns.library import PatternLibrary
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

    def _handle_get_docs(self, input: Dict) -> Dict:
        """Handle getDocs tool call - return documentation section."""
        import os
        import re

        topic = input.get("topic", "").lower()

        # Path to docs file
        docs_path = os.path.join(os.path.dirname(__file__), "..", "docs", "AGENT_REFERENCE.md")

        try:
            with open(docs_path, "r") as f:
                content = f.read()

            # Find the section for this topic
            # Sections are marked with "# SECTION: topic_name"
            section_pattern = rf"# SECTION: {topic}\n(.*?)(?=# SECTION:|$)"
            match = re.search(section_pattern, content, re.DOTALL | re.IGNORECASE)

            if match:
                section_content = match.group(1).strip()
                # Limit to reasonable size (first ~3000 chars)
                if len(section_content) > 3000:
                    section_content = section_content[:3000] + "\n\n... (truncated, use specific sub-topics for more detail)"

                return {
                    "success": True,
                    "topic": topic,
                    "content": section_content
                }
            else:
                # List available topics
                available = re.findall(r"# SECTION: (\w+)", content)
                return {
                    "success": False,
                    "error": f"Topic '{topic}' not found",
                    "available_topics": available
                }

        except FileNotFoundError:
            return {"success": False, "error": "Documentation file not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_create_state(self, input: Dict) -> Dict:
        """Handle createState tool call."""
        if not self.state_machine:
            return {"error": "No state machine configured"}

        from brain.core.state import State

        name = input["name"]
        code = input.get("code")
        r = input.get("r")
        g = input.get("g")
        b = input.get("b")
        speed = input.get("speed")
        description = input.get("description", "")
        voice_reactive = input.get("voice_reactive")
        vision_reactive = input.get("vision_reactive")
        api_reactive = input.get("api_reactive")

        inline_vision_reactive = self._extract_vision_reactive_from_code(code) if code is not None else None
        if inline_vision_reactive:
            explicit_vision = vision_reactive if isinstance(vision_reactive, dict) else {}
            vision_reactive = {**inline_vision_reactive, **explicit_vision}

        # Validate: either code or r/g/b must be provided
        if code is None and (r is None or g is None or b is None):
            return {"error": "Either 'code' or 'r', 'g', 'b' must be provided"}

        # Create a proper State object
        if code is not None:
            # Code-based state (pure_python or stdlib mode)
            state = State(
                name=name,
                code=code,
                description=description,
                voice_reactive=voice_reactive,
                vision_reactive=vision_reactive,
                api_reactive=api_reactive
            )
        else:
            # Original r/g/b mode
            state = State(
                name=name,
                r=r,
                g=g,
                b=b,
                speed=speed,
                description=description,
                voice_reactive=voice_reactive,
                vision_reactive=vision_reactive,
                api_reactive=api_reactive
            )

        # Add to state machine's state collection
        self.state_machine.states.add_state(state)
        print(f"State registered: {name}")

        return {"success": True, "state": name, "mode": "code" if code else "original"}

    def _handle_delete_state(self, input: Dict) -> Dict:
        """Handle deleteState tool call."""
        name = input["name"]
        if name in ["on", "off"]:
            return {"error": "Cannot delete built-in states 'on' or 'off'"}

        if not self.state_machine:
            return {"error": "No state machine configured"}

        # Remove from states
        if hasattr(self.state_machine, 'states'):
            self.state_machine.states.delete_state(name)

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

    def _handle_list_apis(self, input: Dict) -> Dict:
        """Handle listAPIs tool call - list available preset APIs."""
        apis = list_apis()
        return {
            "success": True,
            "apis": apis,
            "count": len(apis)
        }

    def _handle_fetch_api(self, input: Dict) -> Dict:
        """Handle fetchAPI tool call - execute a preset API and return raw data."""
        api_name = input["api"]
        params = input.get("params", {})

        return self.api_executor.execute(api_name, params)

    def _handle_done(self, input: Dict) -> Dict:
        """Handle done tool call."""
        return {"done": True, "message": input["message"]}

    # Memory tool handlers

    def _handle_remember(self, input: Dict) -> Dict:
        """Handle remember tool call - store in memory."""
        key = input["key"]
        value = input["value"]
        self.memory.set(key, value)
        return {"success": True, "key": key, "value": value}

    def _handle_recall(self, input: Dict) -> Dict:
        """Handle recall tool call - retrieve from memory."""
        key = input["key"]
        value = self.memory.get(key)
        if value is not None:
            return {"success": True, "key": key, "value": value}
        return {"success": True, "key": key, "value": None, "message": "Not found"}

    def _handle_forget_memory(self, input: Dict) -> Dict:
        """Handle forgetMemory tool call - delete from memory."""
        key = input["key"]
        deleted = self.memory.delete(key)
        return {"success": True, "deleted": deleted, "key": key}

    def _handle_list_memory(self, input: Dict) -> Dict:
        """Handle listMemory tool call - list all memories."""
        memories = self.memory.list()
        return {"success": True, "memories": memories, "count": len(memories)}

    # Pipeline tool handlers

    def _handle_define_pipeline(self, input: Dict) -> Dict:
        """Handle definePipeline tool call - create a pipeline."""
        name = input["name"]
        steps = input["steps"]
        description = input.get("description", "")

        self.pipeline_registry.register(name, steps, description)
        return {
            "success": True,
            "pipeline": name,
            "steps": len(steps),
            "message": f"Pipeline '{name}' defined with {len(steps)} steps"
        }

    def _handle_run_pipeline(self, input: Dict) -> Dict:
        """Handle runPipeline tool call - execute a pipeline."""
        name = input["name"]
        pipeline = self.pipeline_registry.get(name)

        if not pipeline:
            return {"success": False, "error": f"Pipeline '{name}' not found"}

        result = self.pipeline_executor.execute(pipeline)
        return result

    def _handle_delete_pipeline(self, input: Dict) -> Dict:
        """Handle deletePipeline tool call - delete a pipeline."""
        name = input["name"]
        deleted = self.pipeline_registry.delete(name)
        return {"success": deleted, "pipeline": name}

    def _handle_list_pipelines(self, input: Dict) -> Dict:
        """Handle listPipelines tool call - list all pipelines."""
        pipelines = self.pipeline_registry.list()
        return {"success": True, "pipelines": pipelines, "count": len(pipelines)}

    # User interaction tool handlers

    def _handle_ask_user(self, input: Dict) -> Dict:
        """Handle askUser tool call - ask user a question."""
        question = input["question"]
        self.pending_question = question
        return {
            "waiting_for_user": True,
            "question": question,
            "message": f"Asking user: {question}"
        }

    # Safety check - runs at the end of the agent loop

    def run_safety_check(self) -> Dict:
        """
        Run safety checks after agent completes.

        Ensures all states have exit rules so users don't get stuck.
        Auto-adds button_click → off rules where needed.

        Returns:
            Dict with safety check results and any auto-added rules
        """
        if not self.state_machine:
            return {"success": True, "message": "No state machine configured"}

        # Get all states and rules
        all_states = self.state_machine.states.get_states()
        all_rules = self.state_machine.get_rules()

        # Find states that have no exit rules
        states_with_exits = set()
        for rule in all_rules:
            states_with_exits.add(rule.state1)

        # Check each state (except 'off' which doesn't need an exit)
        auto_added_rules = []
        for state in all_states:
            if state.name == "off":
                continue

            if state.name not in states_with_exits:
                # Auto-add button_click → off as safety net
                self.state_machine.add_rule({
                    "from": state.name,
                    "on": "button_click",
                    "to": "off"
                })
                auto_added_rules.append(f"{state.name} --[button_click]--> off")
                print(f"⚠️  Safety: Auto-added exit rule: {state.name} --[button_click]--> off")

        return {
            "success": True,
            "auto_added_rules": auto_added_rules,
            "rules_added": len(auto_added_rules)
        }
