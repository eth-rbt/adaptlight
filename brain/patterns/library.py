"""
Pattern library for common state machine configurations.

Provides templates and examples for patterns like:
- counter: Temporary behavior that reverts after N occurrences
- toggle: Simple A↔B switching
- cycle: Rotate through multiple states
- hold_release: Hold to activate, release to deactivate
- timer: Delayed state change
- schedule: Time-of-day triggers
- data_reactive: React to external data updates
"""

from typing import Dict, List, Optional


PATTERNS = {
    "counter": {
        "name": "counter",
        "description": "Temporary behavior that reverts after N occurrences",
        "when_to_use": [
            "next N clicks",
            "for N times",
            "then back to normal",
            "temporary behavior"
        ],
        "template": {
            "variables": ["N", "temp_state", "return_state", "transition"],
            "rules": [
                {
                    "description": "Entry rule - start counting",
                    "from": "*",
                    "on": "{transition}",
                    "to": "{temp_state}",
                    "condition": "getData('counter') == None",
                    "action": "setData('counter', {N} - 1)"
                },
                {
                    "description": "Continue rule - decrement counter",
                    "from": "{temp_state}",
                    "on": "{transition}",
                    "to": "{temp_state}",
                    "condition": "getData('counter') > 0",
                    "action": "setData('counter', getData('counter') - 1)"
                },
                {
                    "description": "Exit rule - return to normal",
                    "from": "{temp_state}",
                    "on": "{transition}",
                    "to": "{return_state}",
                    "condition": "getData('counter') == 0",
                    "action": "setData('counter', None)"
                }
            ]
        },
        "example": {
            "user_request": "Next 3 clicks give me random colors, then back to normal",
            "variables": {
                "N": 3,
                "temp_state": "random_color",
                "return_state": "off",
                "transition": "button_click"
            },
            "output": {
                "createState": {
                    "name": "random_color",
                    "r": "random()",
                    "g": "random()",
                    "b": "random()",
                    "speed": None,
                    "description": "Random color on each entry"
                },
                "appendRules": [
                    {
                        "from": "*",
                        "on": "button_click",
                        "to": "random_color",
                        "condition": "getData('counter') == None",
                        "action": "setData('counter', 2)"
                    },
                    {
                        "from": "random_color",
                        "on": "button_click",
                        "to": "random_color",
                        "condition": "getData('counter') > 0",
                        "action": "setData('counter', getData('counter') - 1)"
                    },
                    {
                        "from": "random_color",
                        "on": "button_click",
                        "to": "off",
                        "condition": "getData('counter') == 0",
                        "action": "setData('counter', None)"
                    }
                ]
            }
        }
    },

    "toggle": {
        "name": "toggle",
        "description": "Simple A↔B state switching",
        "when_to_use": [
            "toggle",
            "switch between",
            "on/off",
            "alternate"
        ],
        "template": {
            "variables": ["state_a", "state_b", "transition"],
            "rules": [
                {
                    "description": "A to B",
                    "from": "{state_a}",
                    "on": "{transition}",
                    "to": "{state_b}"
                },
                {
                    "description": "B to A",
                    "from": "{state_b}",
                    "on": "{transition}",
                    "to": "{state_a}"
                }
            ]
        },
        "example": {
            "user_request": "Toggle between off and red on click",
            "variables": {
                "state_a": "off",
                "state_b": "red",
                "transition": "button_click"
            },
            "output": {
                "createState": {
                    "name": "red",
                    "r": 255,
                    "g": 0,
                    "b": 0,
                    "speed": None
                },
                "appendRules": [
                    {"from": "off", "on": "button_click", "to": "red"},
                    {"from": "red", "on": "button_click", "to": "off"}
                ]
            }
        }
    },

    "cycle": {
        "name": "cycle",
        "description": "Rotate through multiple states in sequence",
        "when_to_use": [
            "cycle through",
            "rotate",
            "sequence of",
            "one after another"
        ],
        "template": {
            "variables": ["states", "transition"],
            "rules": [
                {
                    "description": "For each state[i], go to state[i+1] (wrapping around)",
                    "from": "{states[i]}",
                    "on": "{transition}",
                    "to": "{states[(i+1) % len(states)]}"
                }
            ]
        },
        "example": {
            "user_request": "Cycle through red, green, blue on click",
            "variables": {
                "states": ["off", "red", "green", "blue"],
                "transition": "button_click"
            },
            "output": {
                "createState": [
                    {"name": "red", "r": 255, "g": 0, "b": 0, "speed": None},
                    {"name": "green", "r": 0, "g": 255, "b": 0, "speed": None},
                    {"name": "blue", "r": 0, "g": 0, "b": 255, "speed": None}
                ],
                "appendRules": [
                    {"from": "off", "on": "button_click", "to": "red"},
                    {"from": "red", "on": "button_click", "to": "green"},
                    {"from": "green", "on": "button_click", "to": "blue"},
                    {"from": "blue", "on": "button_click", "to": "off"}
                ]
            }
        }
    },

    "hold_release": {
        "name": "hold_release",
        "description": "Hold to activate, release to deactivate/freeze",
        "when_to_use": [
            "hold for",
            "while holding",
            "release to",
            "hold button"
        ],
        "template": {
            "variables": ["active_state", "release_state", "from_state"],
            "rules": [
                {
                    "description": "Hold to activate",
                    "from": "{from_state}",
                    "on": "button_hold",
                    "to": "{active_state}"
                },
                {
                    "description": "Release to go to release state",
                    "from": "{active_state}",
                    "on": "button_release",
                    "to": "{release_state}"
                }
            ]
        },
        "example": {
            "user_request": "Hold for rainbow animation, release to freeze on current color",
            "variables": {
                "active_state": "rainbow",
                "release_state": "frozen",
                "from_state": "*"
            },
            "output": {
                "createState": [
                    {
                        "name": "rainbow",
                        "r": "abs(sin(frame * 0.05)) * 255",
                        "g": "abs(sin(frame * 0.05 + 2)) * 255",
                        "b": "abs(sin(frame * 0.05 + 4)) * 255",
                        "speed": 50,
                        "description": "Rainbow animation"
                    },
                    {
                        "name": "frozen",
                        "r": "r",
                        "g": "g",
                        "b": "b",
                        "speed": None,
                        "description": "Frozen at current color"
                    }
                ],
                "appendRules": [
                    {"from": "*", "on": "button_hold", "to": "rainbow"},
                    {"from": "rainbow", "on": "button_release", "to": "frozen"},
                    {"from": "frozen", "on": "button_click", "to": "off"}
                ]
            }
        }
    },

    "timer": {
        "name": "timer",
        "description": "Delayed state change after a timeout",
        "when_to_use": [
            "in N seconds",
            "after N minutes",
            "delayed",
            "wait then"
        ],
        "template": {
            "variables": ["delay_ms", "from_state", "to_state"],
            "rules": [
                {
                    "description": "Timer rule",
                    "from": "{from_state}",
                    "on": "timer",
                    "to": "{to_state}",
                    "trigger_config": {
                        "delay_ms": "{delay_ms}",
                        "auto_cleanup": True
                    }
                }
            ]
        },
        "example": {
            "user_request": "In 10 seconds, turn red",
            "variables": {
                "delay_ms": 10000,
                "from_state": "*",
                "to_state": "red"
            },
            "output": {
                "createState": {
                    "name": "red",
                    "r": 255,
                    "g": 0,
                    "b": 0,
                    "speed": None
                },
                "appendRules": [
                    {
                        "from": "*",
                        "on": "timer",
                        "to": "red",
                        "trigger_config": {"delay_ms": 10000, "auto_cleanup": True}
                    },
                    {"from": "red", "on": "button_click", "to": "off"}
                ]
            }
        }
    },

    "schedule": {
        "name": "schedule",
        "description": "Time-of-day based state changes",
        "when_to_use": [
            "at N o'clock",
            "every day at",
            "in the morning",
            "at night"
        ],
        "template": {
            "variables": ["hour", "minute", "to_state", "repeat_daily"],
            "rules": [
                {
                    "description": "Schedule rule",
                    "from": "*",
                    "on": "schedule",
                    "to": "{to_state}",
                    "trigger_config": {
                        "hour": "{hour}",
                        "minute": "{minute}",
                        "repeat_daily": "{repeat_daily}"
                    }
                }
            ]
        },
        "example": {
            "user_request": "At 8pm every day, turn on warm light",
            "variables": {
                "hour": 20,
                "minute": 0,
                "to_state": "warm",
                "repeat_daily": True
            },
            "output": {
                "createState": {
                    "name": "warm",
                    "r": 255,
                    "g": 180,
                    "b": 100,
                    "speed": None,
                    "description": "Warm evening light"
                },
                "appendRules": [
                    {
                        "from": "*",
                        "on": "schedule",
                        "to": "warm",
                        "trigger_config": {"hour": 20, "minute": 0, "repeat_daily": True}
                    },
                    {"from": "warm", "on": "button_click", "to": "off"}
                ]
            }
        }
    },

    "data_reactive": {
        "name": "data_reactive",
        "description": "React to external data by fetching APIs and setting states",
        "when_to_use": [
            "check the weather",
            "based on temperature",
            "when stock",
            "if the API"
        ],
        "template": {
            "variables": ["api_name", "params", "conditions"],
            "steps": [
                "1. Call fetchAPI() to get data",
                "2. Create states for each condition",
                "3. Based on the data, call setState() to set the appropriate state"
            ]
        },
        "example": {
            "user_request": "Check the weather - blue if cold, red if hot",
            "variables": {
                "api_name": "weather",
                "params": {"location": "San Francisco"}
            },
            "output": {
                "fetchAPI": {"api": "weather", "params": {"location": "San Francisco"}},
                "createState": [
                    {"name": "cold_blue", "r": 0, "g": 100, "b": 255, "speed": None},
                    {"name": "hot_red", "r": 255, "g": 50, "b": 0, "speed": None}
                ],
                "setState": "cold_blue or hot_red based on temp_f < 60"
            }
        }
    },

    "timed": {
        "name": "timed",
        "description": "State that auto-transitions after a duration (no rules needed)",
        "when_to_use": [
            "for N seconds",
            "flash for",
            "temporarily",
            "then go back",
            "timeout",
            "fade over"
        ],
        "template": {
            "variables": ["duration_ms", "state_name", "then_state"],
            "notes": [
                "Use duration_ms + then on createState - no rules needed!",
                "For gradual changes, use expressions with elapsed_ms",
                "elapsed_ms gives milliseconds since state started"
            ]
        },
        "example": {
            "user_request": "Flash red for 5 seconds then turn off",
            "variables": {
                "duration_ms": 5000,
                "state_name": "flash_red",
                "then_state": "off"
            },
            "output": {
                "createState": {
                    "name": "flash_red",
                    "r": 255,
                    "g": 0,
                    "b": 0,
                    "speed": None,
                    "duration_ms": 5000,
                    "then": "off",
                    "description": "Red flash for 5 seconds"
                },
                "setState": "flash_red"
            }
        }
    },

    "sunrise": {
        "name": "sunrise",
        "description": "Gradual color transition over time (sunrise/sunset simulation)",
        "when_to_use": [
            "sunrise",
            "sunset",
            "fade from",
            "gradually",
            "over N minutes",
            "wake up light"
        ],
        "template": {
            "variables": ["duration_ms", "start_color", "end_color"],
            "notes": [
                "Use elapsed_ms in expressions to calculate progress",
                "Formula: start + (elapsed_ms / duration_ms) * (end - start)",
                "Combine with duration_ms + then for auto-completion"
            ]
        },
        "example": {
            "user_request": "15-minute sunrise from dim red to bright white",
            "variables": {
                "duration_ms": 900000,
                "start_color": {"r": 50, "g": 0, "b": 0},
                "end_color": {"r": 255, "g": 255, "b": 255}
            },
            "output": {
                "createState": {
                    "name": "sunrise",
                    "r": "min(255, 50 + (elapsed_ms / 900000) * 205)",
                    "g": "min(255, (elapsed_ms / 900000) * 255)",
                    "b": "min(255, (elapsed_ms / 900000) * 255)",
                    "speed": 1000,
                    "duration_ms": 900000,
                    "then": "on",
                    "description": "15-minute sunrise simulation"
                },
                "setState": "sunrise"
            }
        }
    },

    "api_reactive": {
        "name": "api_reactive",
        "description": "Fetch data from APIs and set light colors based on the data",
        "when_to_use": [
            "weather",
            "temperature",
            "stock",
            "bitcoin",
            "crypto",
            "air quality",
            "sunset",
            "sunrise time",
            "market",
            "price"
        ],
        "template": {
            "notes": [
                "1. Call listAPIs() to see available APIs",
                "2. Call fetchAPI(api, params) to get raw data",
                "3. Create states with colors YOU choose based on the data",
                "4. Set the appropriate state based on current values",
                "5. For button-triggered checks, use the 'pipeline' pattern"
            ]
        },
        "example": {
            "user_request": "Make the light reflect the weather",
            "steps": [
                "1. fetchAPI('weather', {location: 'NYC'}) -> {temp_f: 45, condition: 'cloudy'}",
                "2. createState('cold', r=0, g=100, b=255)",
                "3. createState('warm', r=255, g=200, b=100)",
                "4. // temp_f is 45, that's cold!",
                "5. setState('cold')",
                "6. done('It's 45°F - showing blue for cold!')"
            ]
        },
        "more_examples": [
            {
                "user_request": "Check Bitcoin",
                "steps": [
                    "fetchAPI('crypto', {coin: 'bitcoin'}) -> {price_usd: 43250, change_24h: 2.5}",
                    "createState('up', r=0, g=255, b=100)",
                    "createState('down', r=255, g=100, b=100)",
                    "// change_24h is positive!",
                    "setState('up')",
                    "done('Bitcoin up 2.5% - showing green!')"
                ]
            }
        ]
    },

    "pipeline": {
        "name": "pipeline",
        "description": "Button-triggered API check with LLM parsing - fetch data, interpret with LLM, set state",
        "when_to_use": [
            "click to check",
            "button triggers",
            "show me on click",
            "check when I press",
            "click for stock",
            "click for weather"
        ],
        "template": {
            "notes": [
                "1. Create states for possible outcomes (green/red, sunny/cloudy, etc.)",
                "2. Define a pipeline with fetch, llm, and setState steps",
                "3. Add a rule that triggers the pipeline on button_click",
                "4. Use {{memory.key}} in pipelines to reference stored user data"
            ],
            "steps": [
                {"do": "fetch", "api": "<api_name>", "params": {}, "as": "data"},
                {"do": "llm", "input": "{{data}}", "prompt": "<interpretation prompt>", "as": "result"},
                {"do": "setState", "from": "result", "map": {"<value1>": "<state1>", "<value2>": "<state2>"}}
            ]
        },
        "example": {
            "user_request": "Click to check if Tesla stock is up or down",
            "variables": {
                "stock_symbol": "TSLA",
                "up_state": "green",
                "down_state": "red"
            },
            "output": {
                "createState": [
                    {"name": "green", "r": 0, "g": 255, "b": 0, "description": "Stock is up"},
                    {"name": "red", "r": 255, "g": 0, "b": 0, "description": "Stock is down"}
                ],
                "definePipeline": {
                    "name": "check_stock",
                    "steps": [
                        {"do": "fetch", "api": "stock", "params": {"symbol": "TSLA"}, "as": "stock"},
                        {"do": "llm", "input": "{{stock}}", "prompt": "Is change_percent positive or negative? Reply with just 'up' or 'down'", "as": "direction"},
                        {"do": "setState", "from": "direction", "map": {"up": "green", "down": "red"}}
                    ],
                    "description": "Check Tesla stock direction"
                },
                "appendRules": [
                    {"from": "*", "on": "button_click", "pipeline": "check_stock"}
                ]
            }
        },
        "more_examples": [
            {
                "user_request": "Click to show weather for my location",
                "notes": "Uses {{memory.location}} to get stored location",
                "output": {
                    "createState": [
                        {"name": "sunny", "r": 255, "g": 200, "b": 50},
                        {"name": "cloudy", "r": 150, "g": 150, "b": 150},
                        {"name": "rainy", "r": 0, "g": 100, "b": 200}
                    ],
                    "definePipeline": {
                        "name": "check_weather",
                        "steps": [
                            {"do": "fetch", "api": "weather", "params": {"location": "{{memory.location}}"}, "as": "weather"},
                            {"do": "llm", "input": "{{weather}}", "prompt": "Is it sunny, cloudy, or rainy? One word only.", "as": "condition"},
                            {"do": "setState", "from": "condition", "map": {"sunny": "sunny", "cloudy": "cloudy", "rainy": "rainy"}}
                        ]
                    },
                    "appendRules": [
                        {"from": "*", "on": "button_click", "pipeline": "check_weather"}
                    ]
                }
            }
        ]
    }
}


class PatternLibrary:
    """Library of common patterns for the agent to look up."""

    def __init__(self):
        """Initialize pattern library."""
        self.patterns = PATTERNS

    def get(self, name: str) -> Optional[Dict]:
        """
        Get a pattern by name.

        Args:
            name: Pattern name

        Returns:
            Pattern dict or None if not found
        """
        return self.patterns.get(name)

    def list(self) -> List[str]:
        """
        List all available pattern names.

        Returns:
            List of pattern names
        """
        return list(self.patterns.keys())

    def list_with_descriptions(self) -> List[Dict]:
        """
        List all patterns with their descriptions.

        Returns:
            List of {name, description} dicts
        """
        return [
            {"name": name, "description": p["description"]}
            for name, p in self.patterns.items()
        ]

    def search(self, keywords: List[str]) -> List[str]:
        """
        Search for patterns matching keywords.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of matching pattern names
        """
        matches = []
        for name, pattern in self.patterns.items():
            triggers = pattern.get("when_to_use", [])
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in name or any(keyword_lower in t.lower() for t in triggers):
                    if name not in matches:
                        matches.append(name)
        return matches
