"""
Function calling prompt for OpenAI command parsing (full version).

This uses OpenAI's native function calling API with detailed tool definitions.
"""


def get_system_prompt(dynamic_content=""):
    """
    Get the system prompt for function calling mode.

    Args:
        dynamic_content: Dynamic content to insert (states, transitions, history, rules, variables)

    Returns:
        Complete system prompt string
    """
    base_prompt = """You are a state machine configuration assistant. Parse user commands and call the appropriate functions to modify the state machine.

## YOUR TASK

Read the user's request and current system state. Call the appropriate functions to make the requested changes.

## CURRENT SYSTEM STATE

The following lists show what is currently available in the system, past user inputs, and what rules already exist.

{dynamic_content}

## RULE BEHAVIOR

**CRITICAL: Understanding When to Delete vs Add Rules**

**IMPORTANT**: Think carefully before deleting! Prefer using conditions to layer behavior on top of existing rules.

### When to DELETE then ADD (Replace behavior PERMANENTLY):
- User wants to PERMANENTLY change what a transition does (no going back)
- User says "click to turn on blue light" with NO mention of reverting → DELETE old, ADD new
- User says "change X to Y **from now on**" → DELETE old, ADD new

### When to ADD with CONDITIONS (Preferred for temporary behavior):
- **User wants TEMPORARY behavior** (e.g., "next 5 clicks", "for a while") → ADD with conditions, DON'T delete
- User says "then it goes back to..." or "after that, normal" → ADD with conditions
- User says "ADD a rule" or "also make double click do X" → Just ADD
- User specifies a NEW transition that isn't currently used → Just ADD

**CRITICAL: How Rule Matching Works**
- When you append rules, they are added to the TOP of the list (prepended)
- The state machine evaluates rules in order from top to bottom
- The FIRST rule that matches (state1 + transition + condition is true) is executed
- This allows new conditional rules to "override" existing defaults without deleting them
- If conditional rules fail, execution falls through to default rules below

### Common Colors:
- red: {r:255, g:0, b:0}
- green: {r:0, g:255, b:0}
- blue: {r:0, g:0, b:255}
- yellow: {r:255, g:255, b:0}
- purple: {r:128, g:0, b:128}
- white: {r:255, g:255, b:255}

### Color Expressions:
Available in expressions: r, g, b (current values), random() (0-255)
- Random color: {r: "random()", g: "random()", b: "random()"}
- Brighten: {r: "min(r + 30, 255)", g: "min(g + 30, 255)", b: "min(b + 30, 255)"}

### Animation Parameters:
Available in animations: r, g, b, t (time in ms), frame (counter)
- Pulse: {r: "abs(sin(frame * 0.05)) * 255", g: "abs(sin(frame * 0.05)) * 255", b: "abs(sin(frame * 0.05)) * 255", speed: 50}

### Conditions and Actions:
- Use getData('key') and setData('key', value) for counters
- Example: condition: "getData('counter') === undefined", action: "setData('counter', 4)"

Remember to call the appropriate functions based on what the user wants to accomplish."""

    return base_prompt.replace('{dynamic_content}', dynamic_content)


def get_tools():
    """
    Get the tool/function definitions for OpenAI function calling.

    Returns:
        List of tool definitions
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "append_rules",
                "description": "Add new state transition rules to the state machine. Use this to create new behaviors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rules": {
                            "type": "array",
                            "description": "Array of rule objects to add",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "state1": {
                                        "type": "string",
                                        "enum": ["off", "on", "color", "animation"],
                                        "description": "Starting state name"
                                    },
                                    "transition": {
                                        "type": "string",
                                        "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"],
                                        "description": "Transition/event that triggers this rule"
                                    },
                                    "state2": {
                                        "type": "string",
                                        "enum": ["off", "on", "color", "animation"],
                                        "description": "Destination state name"
                                    },
                                    "state2Param": {
                                        "description": "Parameters for state2 (object with r,g,b for color/animation, null for on/off)"
                                    },
                                    "condition": {
                                        "type": ["string", "null"],
                                        "description": "Optional condition expression"
                                    },
                                    "action": {
                                        "type": ["string", "null"],
                                        "description": "Optional action to execute"
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
                "description": "Delete existing rules from the state machine. Can delete by index, by criteria, or all rules.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "indices": {
                            "type": "array",
                            "description": "Array of rule indices to delete (0-based)",
                            "items": {"type": "number"}
                        },
                        "state1": {
                            "type": "string",
                            "enum": ["off", "on", "color", "animation"],
                            "description": "Delete rules matching this starting state"
                        },
                        "transition": {
                            "type": "string",
                            "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"],
                            "description": "Delete rules matching this transition"
                        },
                        "state2": {
                            "type": "string",
                            "enum": ["off", "on", "color", "animation"],
                            "description": "Delete rules matching this destination state"
                        },
                        "delete_all": {"type": "boolean", "description": "If true, delete all rules"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_state",
                "description": "Change the current state of the system immediately.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["off", "on", "color", "animation"],
                            "description": "The state to switch to"
                        },
                        "params": {
                            "description": "Optional parameters to pass to the state (e.g., color values)"
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
                "description": "Manage global variables in the state machine data store.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["set", "delete", "clear_all"],
                            "description": "Action to perform"
                        },
                        "variables": {
                            "type": "object",
                            "description": "Key-value pairs to set (used with action: 'set')"
                        },
                        "keys": {
                            "type": "array",
                            "description": "Array of keys to delete (used with action: 'delete')",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "reset_rules",
                "description": "Reset all rules back to the default state (simple on/off toggle with button click).",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ]
