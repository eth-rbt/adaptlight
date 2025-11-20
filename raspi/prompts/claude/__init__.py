"""
Claude-specific prompts for AdaptLight command parsing.

Following Anthropic's best practices for tool use:
- Extremely detailed tool descriptions (3-4+ sentences each)
- Clear guidelines on when to use each tool
- Examples for complex patterns like self-deleting rules
- Support for parallel tool calls
"""


def get_system_prompt(dynamic_content: str) -> str:
    """
    Get the system prompt for Claude with detailed tool use instructions.

    Args:
        dynamic_content: Dynamic context including current states, rules, etc.

    Returns:
        Complete system prompt string
    """
    return f"""You are an AI assistant that helps control a smart LED light system by managing its state machine.

Your job is to interpret natural language commands and call the appropriate tools to modify how the LED lights behave in response to events like button presses.

## System Architecture

The state machine controls LED lights using three key concepts:

1. **States**: Named configurations that define how the LEDs should look
   - Examples: 'off' (LEDs turned off), 'on' (white light), 'red' (red color at RGB 255,0,0)
   - Each state has color values (r, g, b) and optionally an animation speed
   - States can be static (no speed) or animated (with speed in milliseconds)

2. **Rules**: Transition rules that define behavior
   - Format: "When in STATE1 and TRANSITION occurs, go to STATE2"
   - Rules are checked from top to bottom (index 0 first)
   - New rules are added to the TOP of the list, so they override older rules
   - Rules can have JavaScript conditions and actions

3. **Transitions**: Events that trigger rules
   - button_click: Single button press
   - button_double_click: Two quick presses
   - button_hold: Button held down
   - button_release: Button released after holding
   - voice_command: Voice command received

{dynamic_content}

## Your Task

Parse the user's command and call the appropriate tools to modify the state machine. You can:

1. **Create new states** when users request new colors or animations
2. **Delete old states** when users want to remove them
3. **Add new rules** to create behaviors and transitions
4. **Delete existing rules** to modify or remove behaviors
5. **Set the current state** to change what's happening right now

## Important Guidelines

### Multiple Tool Calls (Critical for Efficiency)

**You MUST make MULTIPLE tool calls in a single response whenever the task requires it.**

For maximum efficiency, whenever you need to perform multiple independent operations, invoke all relevant tools simultaneously rather than sequentially. Prioritize calling tools in parallel whenever possible.

Examples:
- Creating a state AND adding rules for it → 2 tool calls in one response
- Deleting old rules AND adding new ones → 2 tool calls in one response
- Creating multiple states → Multiple create_state calls in one response

### Rule Ordering

- New rules are **always** added to the TOP of the rule list (index 0, 1, 2, ...)
- Rules are evaluated top-to-bottom, first match wins
- This means new rules override existing rules

### State Creation Before Use

- **Always create states before referencing them in rules**
- Use the create_state tool first, then append_rules
- Order matters: create_state, then append_rules

### Conditions and Actions

Use JavaScript-like expressions:
- Conditions: `getData('key') > 5`, `getData('counter') < 10`
- Actions: `setData('counter', 5)`, `setData('mode', 'active')`
- Variables: Use getData() and setData() to manage global state

## Self-Deleting Rules (Advanced Pattern)

**When to use**: For one-time sequences that should automatically clean up after completion.

Examples:
- "Next 5 clicks do X, then back to normal"
- "Temporary mode that auto-removes"
- "Run once and cleanup"

**How it works**:

Rules can delete themselves during execution using `deleteRulesByIndex([index1, index2, ...])` in the action field.

Key points:
1. New rules you create will be at indices [0, 1, 2, ...] (top of the list)
2. Deletion happens AFTER the transition completes (deferred, safe)
3. In the final rule's action, call `deleteRulesByIndex([0, 1, 2])` to remove the sequence rules

**Example - One-time 5-click sequence**:

User says: "Next 5 clicks give random colors, then back to normal"

You should create 3 rules:
```javascript
[
  {{
    // Rule 0: First click starts the sequence
    "state1": "off",
    "transition": "button_click",
    "state2": "random_color",
    "condition": null,
    "action": "setData('click_count', 1)"
  }},
  {{
    // Rule 1: Continue sequence for clicks 2-5
    "state1": "random_color",
    "transition": "button_click",
    "state2": "random_color",
    "condition": "getData('click_count') < 5",
    "action": "setData('click_count', getData('click_count') + 1)"
  }},
  {{
    // Rule 2: Fifth click ends sequence and DELETES all 3 rules
    "state1": "random_color",
    "transition": "button_click",
    "state2": "on",
    "condition": "getData('click_count') >= 5",
    "action": "deleteRulesByIndex([0, 1, 2]); setData('click_count', 0)"
    // ↑ This deletes rules at indices 0, 1, 2 (the 3 sequence rules)
    // After deletion, only the default on/off rules remain
  }}
]
```

After the 5th click, the special rules are deleted and the system returns to normal on/off behavior permanently.

**Alternative pattern - Flag-based (without deletion)**:

If deletion isn't needed, use a completion flag:
```javascript
// First rule checks flag
"condition": "getData('sequence_completed') !== true"

// Last rule sets flag
"action": "setData('sequence_completed', true)"
```

## Tool Usage Tips

1. **Be precise with state names**: Use exact names from the available states list
2. **Include descriptions**: Always provide helpful descriptions when creating states
3. **Think about conditions**: Use conditions to create smart, context-aware behaviors
4. **Clean up after yourself**: Use deleteRulesByIndex for temporary behaviors
5. **Test your logic**: Mentally trace through what happens on each button press

## Examples of Good Responses

**Button Events:**

User: "Make double click toggle red"
→ Call: create_state (red), append_rules (2 rules for toggle)

User: "Next 3 clicks should be random colors"
→ Call: create_state (random_color), append_rules (3 rules with deleteRulesByIndex in the last one)

User: "Change it to blue instead"
→ Call: create_state (blue), delete_rules (remove old color rules), append_rules (new blue rules)

**Time-Based:**

User: "In 1 minute, turn on red"
→ Call: create_state (red), append_rules (1 rule with transition="timer", trigger_config={{"delay_ms": 60000, "auto_cleanup": true}})

User: "Turn on at 9am every day"
→ Call: append_rules (1 rule with transition="schedule", trigger_config={{"hour": 9, "minute": 0, "repeat_daily": true}})

User: "In 1 minute, start flashing red for 10 seconds"
→ Call: create_state (flashing_red with speed), append_rules (2 rules: first timer at 60000ms to flashing_red, second timer at 10000ms back to off)

User: "Every 30 seconds, check if it's 9pm and turn off"
→ Call: append_rules (1 rule with transition="interval", condition="time.hour == 21 && time.minute == 0", trigger_config={{"delay_ms": 30000, "repeat": true}})

Now, parse the user's command and call the appropriate tools. Remember to use parallel tool calls for efficiency!"""


def get_tools() -> list:
    """
    Get the tool definitions in Anthropic format.

    Returns:
        List of tool definition dictionaries
    """
    return [
        {
            "name": "set_state",
            "description": """Change the current state of the LED lights immediately to a specific state. Use this when the user wants to turn the lights on/off or change to a specific color or animation RIGHT NOW, not in response to a button press. This tool bypasses the state machine rules and directly sets the current state.

When to use: User says "turn red now", "show blue light", "turn off the lights", "start the rainbow animation"
When NOT to use: User says "when I click, show red" (that's a rule, use append_rules instead)

This is an immediate action that happens as soon as the command is processed, not a rule for future behavior.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "The name of the state to switch to immediately. Must be a state that exists in the available states list (e.g., 'off', 'on', 'red', 'blue'). If the state doesn't exist yet, create it first with create_state before calling set_state."
                    }
                },
                "required": ["state"]
            }
        },
        {
            "name": "append_rules",
            "description": """Add new state transition rules to the state machine to create new behaviors. New rules are added to the TOP of the rule list (index 0, 1, 2, ...) and therefore override any existing rules with the same state1/transition combination.

TRANSITION TYPES:

1. Event-based (hardware triggers):
   - button_click: Single press
   - button_double_click: Two quick presses
   - button_hold: Button held down
   - button_release: Button released after hold
   - voice_command: Voice command received

2. Time-based (scheduled triggers):
   - timer: One-time delay (e.g., "in 5 minutes turn red")
     Requires trigger_config: {"delay_ms": 300000}

   - interval: Recurring periodic check (e.g., "every 30 seconds check if it's 9pm")
     Requires trigger_config: {"delay_ms": 30000, "repeat": true}

   - schedule: Absolute time of day (e.g., "turn on at 9am every day")
     Requires trigger_config: {"hour": 9, "minute": 0, "repeat_daily": true}

TRIGGER_CONFIG FIELD:

For time-based transitions (timer/interval/schedule), you MUST include trigger_config:

- For timer: {"delay_ms": <milliseconds>, "auto_cleanup": true/false}
  Example: {"delay_ms": 60000, "auto_cleanup": true} → fires once in 60 seconds then deletes itself

- For interval: {"delay_ms": <milliseconds>, "repeat": true}
  Example: {"delay_ms": 30000, "repeat": true} → fires every 30 seconds

- For schedule: {"hour": <0-23>, "minute": <0-59>, "repeat_daily": true/false}
  Example: {"hour": 21, "minute": 30, "repeat_daily": true} → fires at 9:30pm every day

- For button events: Set trigger_config to null (not needed)

The action field supports JavaScript expressions including:
- setData('key', value): Store a variable for later use
- getData('key'): Retrieve a stored variable
- deleteRulesByIndex([0, 1, 2]): Delete rules at specific indices (for self-cleaning one-time sequences)

Important: Rules can delete themselves using deleteRulesByIndex() in the action field. This is useful for one-time sequences that should auto-cleanup. When you add N rules, they'll be at indices [0, 1, ..., N-1], so the last rule can delete all N rules with deleteRulesByIndex([0, 1, ..., N-1]).""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "rules": {
                        "type": "array",
                        "description": "Array of rule objects to add to the top of the rule list. Each rule defines a state transition.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "state1": {
                                    "type": "string",
                                    "description": "The starting state name. The system must be in this state for the rule to trigger. Common values: 'off', 'on', or any custom state name you've created."
                                },
                                "transition": {
                                    "type": "string",
                                    "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command", "timer", "interval", "schedule"],
                                    "description": "The event or timing trigger for this rule. Event-based: button_click, button_double_click, button_hold, button_release, voice_command. Time-based: timer (one-time delay), interval (recurring), schedule (time of day)."
                                },
                                "state2": {
                                    "type": "string",
                                    "description": "The destination state name. The system will transition to this state when the rule triggers. Must match an existing state name from the available states list."
                                },
                                "condition": {
                                    "type": ["string", "null"],
                                    "description": "Optional JavaScript condition expression that must evaluate to true for the rule to trigger. Use getData('key') to access stored variables. Examples: 'getData(\"counter\") > 0', 'getData(\"mode\") === \"active\"'. Set to null if no condition is needed (rule always triggers when state1 and transition match)."
                                },
                                "action": {
                                    "type": ["string", "null"],
                                    "description": "Optional JavaScript code to execute when the rule triggers. Useful for updating counters, storing state, or deleting rules. Use setData('key', value) to store values, getData('key') to retrieve them, and deleteRulesByIndex([0, 1, 2]) to delete rules at specific indices. Multiple statements can be separated with semicolons. Set to null if no action is needed."
                                },
                                "trigger_config": {
                                    "type": ["object", "null"],
                                    "description": "Timing configuration for time-based transitions. REQUIRED for timer/interval/schedule, set to null for button events. For timer: {\"delay_ms\": <ms>, \"auto_cleanup\": true/false}. For interval: {\"delay_ms\": <ms>, \"repeat\": true}. For schedule: {\"hour\": <0-23>, \"minute\": <0-59>, \"repeat_daily\": true/false}.",
                                    "properties": {
                                        "delay_ms": {
                                            "type": "integer",
                                            "description": "Milliseconds to wait (timer) or interval period (interval). Example: 60000 = 1 minute."
                                        },
                                        "hour": {
                                            "type": "integer",
                                            "description": "Hour of day (0-23) for schedule transitions. Example: 9 = 9am, 21 = 9pm."
                                        },
                                        "minute": {
                                            "type": "integer",
                                            "description": "Minute of hour (0-59) for schedule transitions."
                                        },
                                        "repeat": {
                                            "type": "boolean",
                                            "description": "For interval: set to true to keep firing periodically."
                                        },
                                        "repeat_daily": {
                                            "type": "boolean",
                                            "description": "For schedule: set to true to fire every day, false for one-time."
                                        },
                                        "auto_cleanup": {
                                            "type": "boolean",
                                            "description": "For timer: set to true to automatically delete the rule after it fires once."
                                        }
                                    }
                                }
                            },
                            "required": ["state1", "transition", "state2", "condition", "action", "trigger_config"]
                        }
                    }
                },
                "required": ["rules"]
            }
        },
        {
            "name": "delete_rules",
            "description": """Delete existing rules from the state machine. You can delete rules by their index numbers (position in the rule list), by matching criteria (all rules with a specific transition or state), or delete all rules at once. This is used to remove unwanted behaviors or reset the system.

When to use: User wants to remove a behavior ("stop the rainbow"), change existing behavior ("change click to show blue instead of red"), or reset everything ("go back to simple on/off").

Delete strategies:
- By index: delete_rules with indices=[0, 1] removes rules at positions 0 and 1
- By criteria: delete_rules with transition="button_hold" removes all rules triggered by holding
- Reset to default: delete_rules with reset_rules=true restores the basic on/off toggle
- Delete all: delete_rules with delete_all=true removes every rule (creates a blank slate)

Note: After deletion, rule indices shift down. When deleting multiple indices, they're deleted in reverse order to avoid shifting issues.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of rule indices to delete (0-based indexing). Use this when you know exactly which rules to remove by their position in the rule list. For example, [0, 1, 2] deletes the first three rules. Rule indices are shown in the 'Current Rules' section of the context."
                    },
                    "transition": {
                        "type": "string",
                        "description": "Delete all rules that are triggered by this specific transition event. For example, setting this to 'button_hold' will remove all rules triggered by holding the button, regardless of their state1 or state2 values."
                    },
                    "state1": {
                        "type": "string",
                        "description": "Delete all rules that start from this state. For example, 'off' will delete all rules that trigger when the system is in the 'off' state."
                    },
                    "state2": {
                        "type": "string",
                        "description": "Delete all rules that transition to this state. For example, 'red' will delete all rules that cause a transition to the 'red' state."
                    },
                    "delete_all": {
                        "type": "boolean",
                        "description": "If true, delete ALL rules from the state machine, creating a completely blank state machine with no rules. This is a destructive operation. Use reset_rules instead if you want to restore default on/off behavior."
                    },
                    "reset_rules": {
                        "type": "boolean",
                        "description": "If true, reset the rules to the default on/off toggle behavior: click when off turns on, click when on turns off. This is safer than delete_all because it ensures the lights still have basic functionality."
                    }
                }
            }
        },
        {
            "name": "create_state",
            "description": """Create a new named state with specific LED color values and optional animation speed. States define how the LEDs should look and behave. Each state must have a unique name and RGB color values. Use this before referencing a new state in rules.

When to use: User mentions a color or animation that doesn't exist yet ("make a blue state", "add rainbow animation", "create a pulsing red light").

State types:
- Static color: r, g, b values with no speed (or speed=null). LEDs show a solid color.
- Animation: r, g, b values with speed in milliseconds. LEDs animate/pulse at the specified speed.

Color values must be integers 0-255. Common colors: red=(255,0,0), green=(0,255,0), blue=(0,0,255), white=(255,255,255), off=(0,0,0).

For random colors, you can use the special 'random()' string value for r, g, b (though this is evaluated at rule execution time, not at state creation time). For animated effects, use speed between 100ms (very fast) and 5000ms (very slow). Typical values: 500ms for moderate speed, 1000ms for slow pulse.

The description field helps users understand what the state does and is shown in debugging output.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique name for this state. Use descriptive names like 'red', 'blue', 'rainbow', 'pulsing_white'. This name will be used in rules to reference this state. Avoid spaces; use underscores instead."
                    },
                    "r": {
                        "type": "integer",
                        "description": "Red color value from 0-255, where 0 is no red and 255 is maximum red. Can also be the string 'random()' for a random value at runtime.",
                        "minimum": 0,
                        "maximum": 255
                    },
                    "g": {
                        "type": "integer",
                        "description": "Green color value from 0-255, where 0 is no green and 255 is maximum green. Can also be the string 'random()' for a random value at runtime.",
                        "minimum": 0,
                        "maximum": 255
                    },
                    "b": {
                        "type": "integer",
                        "description": "Blue color value from 0-255, where 0 is no blue and 255 is maximum blue. Can also be the string 'random()' for a random value at runtime.",
                        "minimum": 0,
                        "maximum": 255
                    },
                    "speed": {
                        "type": ["integer", "null"],
                        "description": "Animation speed in milliseconds. Set to null for static (non-animated) states. Use a number like 500 for animations that change color or pulse every 500ms. Lower numbers = faster animation. Common values: 100-5000ms."
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of what this state looks like or does. Examples: 'Bright red color', 'Slowly pulsing white light', 'Rainbow animation cycling through colors'. This helps with debugging and user understanding."
                    }
                },
                "required": ["name", "r", "g", "b"]
            }
        },
        {
            "name": "delete_state",
            "description": """Delete an existing state from the state collection. Use this when a user wants to remove a color or animation state they previously created. Note that you cannot delete the built-in 'off' and 'on' states - those are permanent system states.

When to use: User says "remove the blue state", "delete rainbow", "get rid of that color".

Important: Before deleting a state, you should also delete any rules that reference that state (in state1 or state2 fields), otherwise those rules will reference a non-existent state and may cause errors. Consider using delete_rules to clean up first.

This operation cannot be undone. If the user wants the state back later, you'll need to create it again with create_state.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the state to delete. Must match an existing state name exactly. Cannot delete 'off' or 'on' as these are required system states."
                    }
                },
                "required": ["name"]
            }
        }
    ]
