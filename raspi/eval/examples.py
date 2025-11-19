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
        "user_input": "Click button to turn on blue light (state name: blue)",
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "blue",
                "expected_params": None
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
        "user_input": "Double click to toggle red light (state name: red)",
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
                "expected_state": "red",
                "expected_params": None
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
        "user_input": "Hold to cycle through random colors (state name: random_colors), release to freeze on current color (state name: frozen_color)",
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
                "expected_state": "random_colors",
                "expected_params": None
            },
            {
                "transition": "button_release",
                "expected_state": "frozen_color",
                "expected_params": None
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
        "user_input": "Hold button for rainbow animation (state name: rainbow), release to turn off",
        "test_sequence": [
            {
                "transition": "button_hold",
                "expected_state": "rainbow",
                "expected_params": None
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
        "user_input": "Click for pulsing animation instead (state name: pulsing)",
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "pulsing",
                "expected_params": None
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
        "user_input": "the next 5 clicks should give me random colors (state name: random_color), then it goes back to normal on and off",
        "test_sequence": [
            {"transition": "button_click", "expected_state": "random_color", "expected_params": None},  # Click 1
            {"transition": "button_click", "expected_state": "random_color", "expected_params": None},  # Click 2
            {"transition": "button_click", "expected_state": "random_color", "expected_params": None},  # Click 3
            {"transition": "button_click", "expected_state": "random_color", "expected_params": None},  # Click 4
            {"transition": "button_click", "expected_state": "random_color", "expected_params": None},  # Click 5
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
        "user_input": "Turn the light red now (state name: red)",
        "test_sequence": [
            {
                "transition": None,  # No transition, just check current state
                "expected_state": "red",  # Unified system creates named state "red"
                "expected_params": None  # setState no longer passes params
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
                {"state1": "off", "transition": "button_click", "state2": "blue", "state2Param": None},
                {"state1": "blue", "transition": "button_click", "state2": "off", "state2Param": None}
            ],
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None},
                "blue": {"r": 0, "g": 0, "b": 255, "speed": None}
            }
        },
        "user_input": "Change the click color to red (state name: red), it was another color before",
        "property_checks": [
            {
                "name": "Click now gives red state",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Find the off->red rule after modification
                    any(r.get("state1") == "off" and
                        r.get("transition") == "button_click" and
                        r.get("state2") == "red"
                        for r in after_rules) and
                    # Check that red state was created in states dict
                    "red" in after_state.get("states", {})
                )
            }
        ],
        "test_sequence": [
            {
                "transition": "button_click",
                "expected_state": "red",
                "expected_params": None
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
                    "state2": "rainbow",
                    "state2Param": None
                }
            ],
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None},
                "rainbow": {"r": "(frame * 2) % 256", "g": "abs(sin(frame * 0.1)) * 255", "b": "abs(cos(frame * 0.1)) * 255", "speed": 100}
            }
        },
        "user_input": "Make the last animation faster (state name: rainbow)",
        "property_checks": [
            {
                "name": "Animation speed decreased",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Find rainbow state speed before and after
                    (before_speed := before_state.get("states", {}).get("rainbow", {}).get("speed", 100)) is not None and
                    (after_speed := after_state.get("states", {}).get("rainbow", {}).get("speed")) is not None and
                    # Speed should be lower (faster)
                    after_speed < before_speed
                )
            }
        ],
        "test_sequence": [
            {
                "transition": "button_hold",
                "expected_state": "rainbow",
                "expected_params": None
            }
        ]
    },
    {
        "name": "Change transition type",
        "description": "Change from click to double click",
        "previous_state": {
            "rules": [
                {"state1": "off", "transition": "button_click", "state2": "green", "state2Param": None},
                {"state1": "green", "transition": "button_click", "state2": "off", "state2Param": None}
            ],
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None},
                "green": {"r": 0, "g": 255, "b": 0, "speed": None}
            }
        },
        "user_input": "Change it to double click instead (state name: green)",
        "property_checks": [
            {
                "name": "Rules use double_click now",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Should have double_click rules
                    any(r.get("transition") == "button_double_click" for r in after_rules) and
                    # Should not have old single click to green rules (might keep or remove)
                    not any(r.get("state1") == "off" and
                           r.get("transition") == "button_click" and
                           r.get("state2") == "green"
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
                "expected_state": "green",  # Double click should work now
                "expected_params": None
            }
        ]
    }
]

# All example categories
ALL_EXAMPLES = {
    "deterministic": DETERMINISTIC_TESTS,
    "non_deterministic": NON_DETERMINISTIC_TESTS
}
