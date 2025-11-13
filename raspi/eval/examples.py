"""
Example test cases for command parser evaluation.

Tests execute transitions and check resulting states (deterministic)
or check that properties changed correctly (non-deterministic).

All examples start with default rules (on/off toggle).
"""

# Default rules that all examples start with
DEFAULT_RULES = [
    {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": None},
    {"state1": "on", "transition": "button_click", "state2": "off", "state2Param": None}
]

# Deterministic tests - execute transitions and check exact state
DETERMINISTIC_TESTS = [
    {
        "name": "Replace with blue light toggle",
        "description": "Click should toggle blue light instead of plain on",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Click button to turn on blue light",
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "color",
                "expected_params": {"r": 0, "g": 0, "b": 255}
            },
            {
                "transition": "button_click",
                "expected_state": "off",
                "expected_params": None
            },
            {
                "transition": "button_double_click",
                "expected_state": "off",  # No rule for double click, stay in off
                "expected_params": None
            }
        ]
    },
    {
        "name": "Add double click for red light",
        "description": "Double click should add red light, keep click for on/off",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Double click to toggle red light",
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "on",
                "expected_params": None
            },
            {
                "transition": "button_click",
                "expected_state": "off",
                "expected_params": None
            },
            {
                "transition": "button_double_click",
                "expected_state": "color",
                "expected_params": {"r": 255, "g": 0, "b": 0}
            },
            {
                "transition": "button_double_click",
                "expected_state": "off",
                "expected_params": None
            }
        ]
    },
    {
        "name": "Hold for random color animation",
        "description": "Hold to cycle through random colors, release to freeze on current color",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Hold to cycle through random colors, release to freeze on current color",
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "on",  # Default click rule should still work
                "expected_params": None
            },
            {
                "transition": "button_click",
                "expected_state": "off",
                "expected_params": None
            },
            {
                "transition": "button_hold",
                "expected_state": "animation",
                "expected_params": "any"  # Animation with random colors
            },
            {
                "transition": "button_release",
                "expected_state": "color",
                "expected_params": "any"  # Freezes to current color
            }
        ]
    },
    {
        "name": "Animation with hold and release",
        "description": "Hold for animation, release to turn off",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Hold button for rainbow animation, release to turn off",
        "test_sequence": [
            {
                "transition": "button_hold",
                "expected_state": "animation",
                "expected_params": "any"
            },
            {
                "transition": "button_release",
                "expected_state": "off",
                "expected_params": None
            },
            {
                "transition": "button_click",
                "expected_state": "on",  # Default rule still works
                "expected_params": None
            }
        ]
    },
    {
        "name": "Replace click with animation",
        "description": "Click should start animation instead of turning on",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Click for pulsing animation instead",
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "animation",
                "expected_params": "any"
            },
            {
                "transition": "button_click",
                "expected_state": "off",
                "expected_params": None
            },
            {
                "transition": "button_double_click",
                "expected_state": "off",  # No rule, stays off
                "expected_params": None
            }
        ]
    },
    {
        "name": "Counter-based clicks",
        "description": "the next 5 clicks should give me random colors, then it goes back to normal on and off",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "the next 5 clicks should give me random colors, then it goes back to normal on and off",
        "test_sequence": [
            {"transition": "button_click", "expected_state": "color", "expected_params": "any"},  # Click 1
            {"transition": "button_click", "expected_state": "color", "expected_params": "any"},  # Click 2
            {"transition": "button_click", "expected_state": "color", "expected_params": "any"},  # Click 3
            {"transition": "button_click", "expected_state": "color", "expected_params": "any"},  # Click 4
            {"transition": "button_click", "expected_state": "color", "expected_params": "any"},  # Click 5
            {"transition": "button_click", "expected_state": "on", "expected_params": None}, 
            {"transition": "button_click", "expected_state": "off", "expected_params": None}    # Click 6 - should turn off
        ]
    },
    {
        "name": "Immediate state change",
        "description": "Turn red now should change state immediately",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Turn the light red now",
        "test_sequence": [
            {
                "transition": None,  # No transition, just check current state
                "expected_state": "color",
                "expected_params": {"r": 255, "g": 0, "b": 0}
            },
            {
                "transition": "button_click",
                "expected_state": "off",  # Default rules should still work
                "expected_params": None
            }
        ]
    },
    {
        "name": "Reset to default",
        "description": "Reset should restore simple on/off",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "animation", "state2Param": {"r": "random()", "g": "random()", "b": "random()", "speed": 100}},
                {"state1": "animation", "transition": "button_click", "state2": "off", "state2Param": None}
            ],
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Reset everything",
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "on",  # Should be on, not animation
                "expected_params": None
            },
            {
                "transition": "button_click",
                "expected_state": "off",
                "expected_params": None
            }
        ]
    }
]

# Non-deterministic tests - check properties changed correctly
NON_DETERMINISTIC_TESTS = [
    {
        "name": "Change color blue to red",
        "description": "Modify existing click rule to use red instead of blue",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "color", "state2Param": {"r": 0, "g": 0, "b": 255}},
                {"state1": "color", "transition": "button_click", "state2": "off", "state2Param": None}
            ],
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Change the click color to red, it was another color before",
        "property_checks": [
            {
                "name": "Click now gives red color",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Find the off->color rule after modification
                    any(r.get("state1") == "off" and
                        r.get("transition") == "button_click" and
                        r.get("state2") == "color" and
                        r.get("state2Param", {}).get("r") == 255 and
                        r.get("state2Param", {}).get("g") == 0 and
                        r.get("state2Param", {}).get("b") == 0
                        for r in after_rules)
                )
            }
        ],
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "color",
                "expected_params": {"r": 255, "g": 0, "b": 0}  # Should be red now
            }
        ]
    },
    {
        "name": "Make animation faster",
        "description": "Reduce speed value to make animation faster",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": None},
                {"state1": "on", "transition": "button_click", "state2": "off", "state2Param": None},
                {
                    "state1": "off",
                    "transition": "button_hold",
                    "state2": "animation",
                    "state2Param": {"r": "(frame * 2) % 256", "g": "abs(sin(frame * 0.1)) * 255", "b": "abs(cos(frame * 0.1)) * 255", "speed": 100}
                }
            ],
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Make the last animation faster",
        "property_checks": [
            {
                "name": "Animation speed decreased",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Find animation rule before
                    (before_speed := next((r.get("state2Param", {}).get("speed")
                                          for r in before_rules
                                          if r.get("state2") == "animation"), None)) is not None and
                    # Find animation rule after
                    (after_speed := next((r.get("state2Param", {}).get("speed")
                                         for r in after_rules
                                         if r.get("state2") == "animation"), None)) is not None and
                    # Speed should be lower (faster)
                    after_speed < before_speed
                )
            }
        ],
        "test_sequence": [
            {
                "transition": "button_hold",
                "expected_state": "animation",
                "expected_params": "any"  # Don't check exact params, property check handles it
            }
        ]
    },
    {
        "name": "Change transition type",
        "description": "Change from click to double click",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "color", "state2Param": {"r": 0, "g": 255, "b": 0}},
                {"state1": "color", "transition": "button_click", "state2": "off", "state2Param": None}
            ],
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Change it to double click instead",
        "property_checks": [
            {
                "name": "Rules use double_click now",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Should have double_click rules
                    any(r.get("transition") == "button_double_click" for r in after_rules) and
                    # Should not have old single click to color rules (might keep or remove)
                    not any(r.get("state1") == "off" and
                           r.get("transition") == "button_click" and
                           r.get("state2") == "color"
                           for r in after_rules)
                )
            }
        ],
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "off",  # Click should no longer work
                "expected_params": None
            },
            {
                "transition": "button_double_click",
                "expected_state": "color",  # Double click should work now
                "expected_params": {"r": 0, "g": 255, "b": 0}
            }
        ]
    }
]

# All example categories
ALL_EXAMPLES = {
    "deterministic": DETERMINISTIC_TESTS,
    "non_deterministic": NON_DETERMINISTIC_TESTS
}
