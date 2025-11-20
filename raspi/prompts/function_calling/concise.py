"""
Function calling prompt for OpenAI command parsing (concise version).

This uses OpenAI's native function calling API with streamlined instructions.
Uses unified state system with dynamic states.
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

## UNIFIED STATE SYSTEM

All states use r, g, b, speed parameters:
- **Default states**: "on" (255,255,255) and "off" (0,0,0)
- **Custom states**: Create with create_state, reference by name in rules
- **Static states**: speed=null
- **Animated states**: speed=number (expressions with t, frame)

Rules reference states by name only. State parameters are stored in the state definition.

**CRITICAL EXIT RULES:** When adding ANY transition TO a state, ALWAYS add an exit rule FROM that state (unless one exists). Examples:
- "Turn red now" → create_state + set_state + append_rules for red→off
- "In 10 sec turn red" → create_state + append_rules for timer→red AND red→off
- "Click for blue" → create_state + append_rules for click→blue AND blue→off
Safety net exists but be explicit!

## RULES

**When to DELETE vs ADD:**
- DELETE: User wants PERMANENT change ("make click do X from now on")
- ADD with conditions: TEMPORARY behavior ("next 5 clicks") or new transitions

**Rule Matching:**
- New rules are prepended (checked first)
- First matching rule wins (state1 + transition + condition passes)
- Use conditions to layer temporary behavior on top of defaults

**Common patterns:**
- Create state with random: create_state(name="random_color", r="random()", g="random()", b="random()", speed=null)
- Counter conditions: getData('counter') === undefined
- Counter actions: setData('counter', 5)

Call the appropriate functions based on the user's request."""

    return base_prompt.replace('{dynamic_content}', dynamic_content)


def get_tools():
    """
    Get the tool/function definitions for OpenAI function calling.

    Returns:
        List of tool definitions for unified state system
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "create_state",
                "description": "Create a new custom state with r, g, b, speed parameters.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the state (e.g., 'reading', 'purple_pulse')"
                        },
                        "r": {
                            "type": ["number", "string"],
                            "description": "Red value (0-255) or expression"
                        },
                        "g": {
                            "type": ["number", "string"],
                            "description": "Green value (0-255) or expression"
                        },
                        "b": {
                            "type": ["number", "string"],
                            "description": "Blue value (0-255) or expression"
                        },
                        "speed": {
                            "type": ["number", "null"],
                            "description": "Animation speed in ms (null for static)"
                        },
                        "description": {
                            "type": ["string", "null"],
                            "description": "Optional description"
                        }
                    },
                    "required": ["name", "r", "g", "b", "speed", "description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_state",
                "description": "Delete a custom state (cannot delete 'on' or 'off').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the state to delete"
                        }
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "append_rules",
                "description": "Add new state transition rules to the state machine. Rules reference states by name only.",
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
                                        "description": "Starting state name"
                                    },
                                    "transition": {
                                        "type": "string",
                                        "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"]
                                    },
                                    "state2": {
                                        "type": "string",
                                        "description": "Destination state name"
                                    },
                                    "condition": {
                                        "type": ["string", "null"],
                                        "description": "Optional condition expression"
                                    },
                                    "action": {
                                        "type": ["string", "null"],
                                        "description": "Optional action expression"
                                    }
                                },
                                "required": ["state1", "transition", "state2", "condition", "action"]
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
                            "items": {"type": "number"},
                            "description": "Specific rule indices to delete"
                        },
                        "state1": {
                            "type": "string",
                            "description": "Filter by starting state"
                        },
                        "transition": {
                            "type": "string",
                            "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"],
                            "description": "Filter by transition type"
                        },
                        "state2": {
                            "type": "string",
                            "description": "Filter by destination state"
                        },
                        "delete_all": {
                            "type": "boolean",
                            "description": "Delete all matching rules"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_state",
                "description": "Change the current state immediately. Can override state params.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "State name to transition to"
                        },
                        "params": {
                            "type": "object",
                            "description": "Optional parameters to override (r, g, b, speed)",
                            "properties": {
                                "r": {"type": ["number", "string"]},
                                "g": {"type": ["number", "string"]},
                                "b": {"type": ["number", "string"]},
                                "speed": {"type": ["number", "null"]}
                            }
                        }
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
