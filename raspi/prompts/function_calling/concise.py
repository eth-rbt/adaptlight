"""
Function calling prompt for OpenAI command parsing (concise version).

This uses OpenAI's native function calling API with streamlined instructions.
"""


def get_system_prompt(dynamic_content=""):
    """
    Get the concise system prompt for function calling mode.

    Args:
        dynamic_content: Dynamic content to insert (states, transitions, history, rules, variables)

    Returns:
        Complete system prompt string
    """
    base_prompt = """You are a state machine configuration assistant. Parse user commands and call functions to modify the state machine.

## CURRENT SYSTEM STATE

{dynamic_content}

## RULES

**When to DELETE vs ADD:**
- DELETE: User wants PERMANENT change ("make click do X from now on")
- ADD with conditions: TEMPORARY behavior ("next 5 clicks") or new transitions

**Rule Matching:**
- New rules are prepended (checked first)
- First matching rule wins (state1 + transition + condition passes)
- Use conditions to layer temporary behavior on top of defaults

**Common patterns:**
- Random color: {r: "random()", g: "random()", b: "random()"}
- Counter conditions: getData('counter') === undefined
- Counter actions: setData('counter', 5)

Call the appropriate functions based on the user's request."""

    return base_prompt.replace('{dynamic_content}', dynamic_content)


def get_tools():
    """
    Get the tool/function definitions for OpenAI function calling.

    Returns:
        List of tool definitions (same as full version)
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "append_rules",
                "description": "Add new state transition rules to the state machine.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rules": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "state1": {
                                        "type": "string",
                                        "enum": ["off", "on", "color", "animation"]
                                    },
                                    "transition": {
                                        "type": "string",
                                        "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"]
                                    },
                                    "state2": {
                                        "type": "string",
                                        "enum": ["off", "on", "color", "animation"]
                                    },
                                    "state2Param": {
                                        "description": "Parameters for state2 (null or object with r,g,b)"
                                    },
                                    "condition": {
                                        "type": ["string", "null"]
                                    },
                                    "action": {
                                        "type": ["string", "null"]
                                    }
                                },
                                "required": ["state1", "transition", "state2", "state2Param"]
                            }
                        }
                    },
                    "required": ["rules"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_rules",
                "description": "Delete existing rules from the state machine.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "indices": {
                            "type": "array",
                            "items": {"type": "number"}
                        },
                        "state1": {"type": "string", "enum": ["off", "on", "color", "animation"]},
                        "transition": {"type": "string", "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"]},
                        "state2": {"type": "string", "enum": ["off", "on", "color", "animation"]},
                        "delete_all": {"type": "boolean"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_state",
                "description": "Change the current state immediately.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string", "enum": ["off", "on", "color", "animation"]},
                        "params": {"description": "Optional parameters (e.g., color values)"}
                    },
                    "required": ["state"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "manage_variables",
                "description": "Manage global variables.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["set", "delete", "clear_all"]},
                        "variables": {"type": "object"},
                        "keys": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "reset_rules",
                "description": "Reset to default on/off toggle.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]
