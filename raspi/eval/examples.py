"""
Example test cases for command parser evaluation.

These examples are extracted from the main parsing prompt and organized
for systematic testing and evaluation.
"""

# Basic rule examples
BASIC_RULE_EXAMPLES = [
    {
        "name": "Simple on/off toggle",
        "description": "Basic button click to toggle on/off",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "When button is clicked in off state, go to on state",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": None},
                        {"state1": "on", "transition": "button_click", "state2": "off", "state2Param": None}
                    ]
                }
            }
        ]
    },
    {
        "name": "Click for blue light",
        "description": "Button click to turn on specific color",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Click button to turn on blue light",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "off", "transition": "button_click", "state2": "color", "state2Param": {"r": 0, "g": 0, "b": 255}},
                        {"state1": "color", "transition": "button_click", "state2": "off", "state2Param": None}
                    ]
                }
            }
        ]
    },
    {
        "name": "Double click for red light",
        "description": "Double click to toggle red light",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Double click to toggle red light",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "off", "transition": "button_double_click", "state2": "color", "state2Param": {"r": 255, "g": 0, "b": 0}},
                        {"state1": "color", "transition": "button_double_click", "state2": "off", "state2Param": None}
                    ]
                }
            }
        ]
    },
    {
        "name": "Hold for random color",
        "description": "Hold button for random color",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Hold button for random color",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "off", "transition": "button_hold", "state2": "color", "state2Param": {"r": "random()", "g": "random()", "b": "random()"}}
                    ]
                }
            }
        ]
    }
]

# Color manipulation examples
COLOR_MANIPULATION_EXAMPLES = [
    {
        "name": "Cycle through colors",
        "description": "Click to cycle RGB values",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": None}
            ],
            "current_state": "color"
        },
        "user_input": "Click to cycle through colors",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "color", "transition": "button_click", "state2": "color", "state2Param": {"r": "b", "g": "r", "b": "g"}}
                    ]
                }
            }
        ]
    },
    {
        "name": "Make it brighter",
        "description": "Double click to increase brightness",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "color", "state2Param": {"r": 0, "g": 0, "b": 255}}
            ],
            "current_state": "color"
        },
        "user_input": "Double click to make it brighter",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "color", "transition": "button_double_click", "state2": "color",
                         "state2Param": {"r": "min(r + 30, 255)", "g": "min(g + 30, 255)", "b": "min(b + 30, 255)"}}
                    ]
                }
            }
        ]
    }
]

# Animation examples
ANIMATION_EXAMPLES = [
    {
        "name": "Rainbow animation",
        "description": "Hold for rainbow animation",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Hold button for rainbow animation",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {
                            "state1": "off",
                            "transition": "button_hold",
                            "state2": "animation",
                            "state2Param": {
                                "r": "(frame * 2) % 256",
                                "g": "abs(sin(frame * 0.1)) * 255",
                                "b": "abs(cos(frame * 0.1)) * 255",
                                "speed": 50
                            }
                        },
                        {"state1": "animation", "transition": "button_release", "state2": "off", "state2Param": None}
                    ]
                }
            }
        ]
    },
    {
        "name": "Pulsing animation",
        "description": "Click for pulsing white animation",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Click for pulsing animation",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {
                            "state1": "off",
                            "transition": "button_click",
                            "state2": "animation",
                            "state2Param": {
                                "r": "abs(sin(frame * 0.05)) * 255",
                                "g": "abs(sin(frame * 0.05)) * 255",
                                "b": "abs(sin(frame * 0.05)) * 255",
                                "speed": 50
                            }
                        }
                    ]
                }
            }
        ]
    }
]

# Conditional rule examples
CONDITIONAL_EXAMPLES = [
    {
        "name": "Counter-based behavior",
        "description": "Next 5 clicks should be random colors",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Next 5 clicks should be random colors",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {
                            "state1": "off",
                            "transition": "button_click",
                            "condition": "getData('counter') === undefined",
                            "action": "setData('counter', 4)",
                            "state2": "color",
                            "state2Param": {"r": "random()", "g": "random()", "b": "random()"}
                        },
                        {
                            "state1": "color",
                            "transition": "button_click",
                            "condition": "getData('counter') > 0",
                            "action": "setData('counter', getData('counter') - 1)",
                            "state2": "color",
                            "state2Param": {"r": "random()", "g": "random()", "b": "random()"}
                        },
                        {
                            "state1": "color",
                            "transition": "button_click",
                            "condition": "getData('counter') === 0",
                            "state2": "off",
                            "state2Param": None
                        }
                    ]
                }
            }
        ]
    },
    {
        "name": "Time-based rule",
        "description": "Blue light only after 8pm",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Click for blue light, but only after 8pm",
        "expected_tools": [
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {
                            "state1": "off",
                            "transition": "button_click",
                            "condition": "time.hour >= 20",
                            "state2": "color",
                            "state2Param": {"r": 0, "g": 0, "b": 255}
                        }
                    ]
                }
            }
        ]
    }
]

# Immediate state change examples
IMMEDIATE_STATE_EXAMPLES = [
    {
        "name": "Turn red now",
        "description": "Immediate state change to red",
        "previous_state": {"rules": [], "current_state": "off"},
        "user_input": "Turn the light red now",
        "expected_tools": [
            {
                "name": "set_state",
                "arguments": {
                    "state": "color",
                    "params": {"r": 255, "g": 0, "b": 0}
                }
            }
        ]
    }
]

# Rule modification examples
RULE_MODIFICATION_EXAMPLES = [
    {
        "name": "Change color from blue to red",
        "description": "Modify existing rule to use different color",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "color", "state2Param": {"r": 0, "g": 0, "b": 255}},
                {"state1": "color", "transition": "button_click", "state2": "off", "state2Param": None}
            ],
            "current_state": "off"
        },
        "user_input": "Change the click color to red",
        "expected_tools": [
            {
                "name": "delete_rules",
                "arguments": {"indices": [0]}
            },
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "off", "transition": "button_click", "state2": "color", "state2Param": {"r": 255, "g": 0, "b": 0}}
                    ]
                }
            }
        ]
    },
    {
        "name": "Change from click to double click",
        "description": "Change the transition type",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "color", "state2Param": {"r": 0, "g": 255, "b": 0}},
                {"state1": "color", "transition": "button_click", "state2": "off", "state2Param": None}
            ],
            "current_state": "off"
        },
        "user_input": "Change it to double click instead",
        "expected_tools": [
            {
                "name": "delete_rules",
                "arguments": {"indices": [0, 1]}
            },
            {
                "name": "append_rules",
                "arguments": {
                    "rules": [
                        {"state1": "off", "transition": "button_double_click", "state2": "color", "state2Param": {"r": 0, "g": 255, "b": 0}},
                        {"state1": "color", "transition": "button_double_click", "state2": "off", "state2Param": None}
                    ]
                }
            }
        ]
    }
]

# Reset examples
RESET_EXAMPLES = [
    {
        "name": "Reset to default",
        "description": "Reset everything back to basics",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "animation", "state2Param": {"r": "random()", "g": "random()", "b": "random()", "speed": 100}},
                {"state1": "animation", "transition": "button_release", "state2": "off", "state2Param": None}
            ],
            "current_state": "off"
        },
        "user_input": "Reset everything back to default",
        "expected_tools": [
            {
                "name": "reset_rules",
                "arguments": {}
            }
        ]
    }
]

# All example categories
ALL_EXAMPLES = {
    "basic_rules": BASIC_RULE_EXAMPLES,
    "color_manipulation": COLOR_MANIPULATION_EXAMPLES,
    "animations": ANIMATION_EXAMPLES,
    "conditionals": CONDITIONAL_EXAMPLES,
    "immediate_state": IMMEDIATE_STATE_EXAMPLES,
    "rule_modifications": RULE_MODIFICATION_EXAMPLES,
    "resets": RESET_EXAMPLES
}
