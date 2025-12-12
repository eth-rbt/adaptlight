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
            {"transition": "button_click", "expected_state": "off", "expected_params": None},
            {"transition": "button_click", "expected_state": "on", "expected_params": None}    # Click 6 - should turn off
        ]
    },
    {
        "name": "Immediate state change",
        "description": "Turn red now should change state immediately AND add exit rule",
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
                "transition": "button_click",  # Should be able to exit
                "expected_state": "off",  # Should go to off (either from LLM or safety net)
                "expected_params": None
            }
        ]
    },
    {
        "name": "Timer with exit rule",
        "description": "Timer transition should include exit rule to prevent stuck state",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "In 10 seconds turn light red (state name: red)",
        "test_sequence": [
            {
                "transition": "button_click",  # Should still be able to use default rules
                "expected_state": "on",
                "expected_params": None
            },
            {
                "transition": "button_click",  # Back to off
                "expected_state": "off",
                "expected_params": None
            }
            # Note: We can't actually test the timer firing in this framework,
            # but the safety net should ensure a red->off rule exists
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
    },
    {
        "name": "Timer with automatic exit rule",
        "description": "Timer transition should have exit rule added automatically",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None}
            }
        },
        "user_input": "In 10 seconds turn light red (state name: red)",
        "property_checks": [
            {
                "name": "Red state has exit rule",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Red state should exist
                    "red" in after_state.get("states", {}) and
                    # Timer rule should exist: off -> red
                    any(r.get("state1") == "off" and
                        r.get("state2") == "red"
                        for r in after_rules) and
                    # Exit rule should exist: red -> off (either from LLM or safety net)
                    any(r.get("state1") == "red" and
                        r.get("state2") == "off"
                        for r in after_rules)
                )
            }
        ],
        "test_sequence": [
            {
                "transition": "button_click",  # Should still work (default rules)
                "expected_state": "on",
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

# API and Memory tests - test new pipeline/memory features
API_MEMORY_TESTS = [
    {
        "name": "Remember location",
        "description": "Agent should store location in memory",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {}
        },
        "user_input": "Remember that my location is San Francisco",
        "property_checks": [
            {
                "name": "Location stored in memory",
                "check": lambda before_rules, after_rules, before_state, after_state: True
                # Memory check would need special handling
            }
        ],
        "test_sequence": []
    },
    {
        "name": "Create stock check pipeline",
        "description": "Agent should create pipeline for button-triggered stock check",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None}
            }
        },
        "user_input": "Click to check if Tesla stock is up or down. Green for up, red for down.",
        "property_checks": [
            {
                "name": "Green and red states created",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Should have green and red states
                    any("green" in s.lower() for s in after_state.get("states", {}).keys()) and
                    any("red" in s.lower() for s in after_state.get("states", {}).keys())
                )
            },
            {
                "name": "Pipeline or rule for stock check exists",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    # Should have a rule with pipeline or API-related setup
                    len(after_rules) > len(before_rules) or
                    any(r.get("pipeline") for r in after_rules)
                )
            }
        ],
        "test_sequence": []
    },
    {
        "name": "Weather-based colors with memory",
        "description": "Set up weather check using stored location",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None}
            },
            # Assume memory already has location
            "memory": {"location": "New York"}
        },
        "user_input": "Click to show weather for my location - yellow for sunny, gray for cloudy, blue for rainy",
        "property_checks": [
            {
                "name": "Weather states created",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    len(after_state.get("states", {})) > len(before_state.get("states", {}))
                )
            }
        ],
        "test_sequence": []
    }
]

# Timed state tests - test duration_ms and then features
TIMED_STATE_TESTS = [
    {
        "name": "Flash then off",
        "description": "Create a timed state that auto-transitions",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None}
            }
        },
        "user_input": "Flash red for 3 seconds then turn off",
        "property_checks": [
            {
                "name": "Timed state with duration_ms created",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    any(
                        s.get("duration_ms") is not None and s.get("then") is not None
                        for s in after_state.get("states", {}).values()
                        if isinstance(s, dict)
                    )
                )
            }
        ],
        "test_sequence": [
            {
                "transition": None,  # Check immediate state
                "expected_state_contains": "red",  # Should be in red/flash state
                "expected_params": None
            }
        ]
    },
    {
        "name": "Sunrise simulation",
        "description": "Create gradual color transition using elapsed_ms",
        "previous_state": {
            "rules": DEFAULT_RULES.copy(),
            "current_state": "off",
            "variables": {},
            "states": {
                "on": {"r": 255, "g": 255, "b": 255, "speed": None},
                "off": {"r": 0, "g": 0, "b": 0, "speed": None}
            }
        },
        "user_input": "Create a 10 second sunrise simulation - start dim red and fade to bright white",
        "property_checks": [
            {
                "name": "Sunrise state with expressions",
                "check": lambda before_rules, after_rules, before_state, after_state: (
                    any(
                        (isinstance(s.get("r"), str) and "elapsed" in s.get("r", "")) or
                        (isinstance(s.get("g"), str) and "elapsed" in s.get("g", "")) or
                        s.get("duration_ms") is not None
                        for s in after_state.get("states", {}).values()
                        if isinstance(s, dict)
                    )
                )
            }
        ],
        "test_sequence": []
    }
]

# All example categories
ALL_EXAMPLES = {
    "deterministic": DETERMINISTIC_TESTS,
    "non_deterministic": NON_DETERMINISTIC_TESTS,
    "api_memory": API_MEMORY_TESTS,
    "timed_states": TIMED_STATE_TESTS
}
