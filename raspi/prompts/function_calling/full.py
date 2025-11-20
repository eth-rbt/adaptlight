"""
Function calling prompt for OpenAI command parsing (full version).

This uses OpenAI's native function calling API with detailed tool definitions.
Uses unified state system with dynamic states.
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

## UNIFIED STATE SYSTEM

All states use r, g, b, speed parameters:
- **Default states**: "on" (255,255,255) and "off" (0,0,0)
- **Custom states**: Create with create_state function, reference by name in rules
- **Static states**: speed=null (color evaluated once)
- **Animated states**: speed=number (expressions evaluated every frame with t, frame variables)

Rules reference states by name only. State parameters are stored in the state definition, not in rules.

## EXIT RULES (CRITICAL!)

**CRITICAL: Always provide an exit path when adding transitions to new states!**

When adding rules that transition TO a state, ensure there's a way OUT:
- **ALWAYS add exit rules** for the destination state (unless one already exists)
- The system has a safety net that auto-adds click-to-off rules if you forget
- But it's better to be explicit and thoughtful about exit paths

**Examples:**

Immediate state change: "Turn the light red now"
```
create_state(name="red", r=255, g=0, b=0, speed=null, description="Bright red color")
set_state(state="red")
append_rules(rules=[
    {state1: "red", transition: "button_click", state2: "off", condition: null, action: null}
])
```

Timer transition: "In 10 seconds turn light red"
```
create_state(name="red", r=255, g=0, b=0, speed=null, description="Bright red color")
append_rules(rules=[
    {state1: "off", transition: "timer", state2: "red", condition: null, action: null},
    {state1: "red", transition: "button_click", state2: "off", condition: null, action: null}  ← EXIT RULE!
])
```

Button transition: "Click to turn blue"
```
create_state(name="blue", r=0, g=0, b=255, speed=null, description="Blue color")
append_rules(rules=[
    {state1: "off", transition: "button_click", state2: "blue", condition: null, action: null},
    {state1: "blue", transition: "button_click", state2: "off", condition: null, action: null}  ← EXIT RULE!
])
```

**Why:** Without exit rules, users get stuck in states with no way to change them!

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

### Creating States:
- Create custom states using create_state function
- Example: create_state(name="reading", r=255, g=200, b=150, speed=null, description="Warm white")
- Then reference in rules: {state1: "off", transition: "button_click", state2: "reading", ...}

### Common Colors:
- red: r=255, g=0, b=0
- green: r=0, g=255, b=0
- blue: r=0, g=0, b=255
- yellow: r=255, g=255, b=0
- purple: r=128, g=0, b=128
- white: r=255, g=255, b=255

### Color Expressions:
Available in expressions: r, g, b (current values), random() (0-255)
- Random color state: create_state(name="random_color", r="random()", g="random()", b="random()", speed=null)
- Brighten: r="min(r + 30, 255)", g="min(g + 30, 255)", b="min(b + 30, 255)"

### Animation Parameters:
Available in animations: r, g, b, t (time in ms), frame (counter)
- Pulse state: create_state(name="pulse", r="abs(sin(frame * 0.05)) * 255", g="abs(sin(frame * 0.05)) * 255", b="abs(sin(frame * 0.05)) * 255", speed=50)

### Conditions and Actions:
- Use getData('key') and setData('key', value) for counters
- Example: condition="getData('counter') === undefined", action="setData('counter', 4)"

Remember to call the appropriate functions based on what the user wants to accomplish."""

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
                "description": "Create a new custom state with r, g, b, speed parameters. States can then be referenced by name in rules.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the state (e.g., 'reading', 'purple_pulse', 'random_color')"
                        },
                        "r": {
                            "type": ["number", "string"],
                            "description": "Red value (0-255) or expression like 'random()' or 'abs(sin(frame * 0.05)) * 255'"
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
                            "description": "Animation speed in milliseconds (null for static states, number for animated states)"
                        },
                        "description": {
                            "type": ["string", "null"],
                            "description": "Optional human-readable description of what this state does"
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
                "description": "Delete a custom state. Cannot delete the default 'on' or 'off' states.",
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
                "description": "Add new state transition rules to the state machine. Rules reference states by name only - state parameters are looked up from the state definition.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rules": {
                            "type": "array",
                            "description": "Array of rule objects to add. New rules are prepended (checked first).",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "state1": {
                                        "type": "string",
                                        "description": "Starting state name (e.g., 'off', 'on', or any custom state name)"
                                    },
                                    "transition": {
                                        "type": "string",
                                        "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"],
                                        "description": "Transition/event that triggers this rule"
                                    },
                                    "state2": {
                                        "type": "string",
                                        "description": "Destination state name (e.g., 'on', 'off', or any custom state name)"
                                    },
                                    "condition": {
                                        "type": ["string", "null"],
                                        "description": "Optional condition expression (e.g., \"getData('counter') > 0\")"
                                    },
                                    "action": {
                                        "type": ["string", "null"],
                                        "description": "Optional action to execute (e.g., \"setData('counter', 5)\")"
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
                            "description": "Delete rules matching this starting state name"
                        },
                        "transition": {
                            "type": "string",
                            "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"],
                            "description": "Delete rules matching this transition"
                        },
                        "state2": {
                            "type": "string",
                            "description": "Delete rules matching this destination state name"
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
                "description": "Change the current state of the system immediately. Can optionally override state parameters.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "The state name to switch to (e.g., 'on', 'off', or any custom state)"
                        },
                        "params": {
                            "type": "object",
                            "description": "Optional parameters to override state defaults (r, g, b, speed)",
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
