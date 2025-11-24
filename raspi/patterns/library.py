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
        "description": "React to external data source updates",
        "when_to_use": [
            "check the weather",
            "based on temperature",
            "when stock",
            "if the API"
        ],
        "template": {
            "variables": ["data_source_name", "transition_name", "conditions"],
            "steps": [
                "1. Define a custom tool to fetch the data (defineTool)",
                "2. Create a data source that uses the tool (createDataSource)",
                "3. Create states for each condition",
                "4. Create rules that react to the data source transition"
            ],
            "rules": [
                {
                    "description": "React to data update with condition",
                    "from": "*",
                    "on": "{transition_name}",
                    "to": "{conditional_state}",
                    "condition": "{condition_expression}"
                }
            ]
        },
        "example": {
            "user_request": "Check the weather - blue if cold, red if hot",
            "variables": {
                "data_source_name": "weather",
                "transition_name": "weather_updated"
            },
            "output": {
                "defineTool": {
                    "name": "get_weather",
                    "description": "Fetch current temperature",
                    "code": "import requests\\nresponse = requests.get('https://wttr.in/?format=j1')\\ndata = response.json()\\nreturn {'temp': int(data['current_condition'][0]['temp_F'])}"
                },
                "createDataSource": {
                    "name": "weather",
                    "interval_ms": 3600000,
                    "fetch": {"tool": "get_weather", "args": {}},
                    "store": {"temperature": "result.temp"},
                    "fires": "weather_updated"
                },
                "createState": [
                    {"name": "cold_blue", "r": 0, "g": 100, "b": 255, "speed": None},
                    {"name": "hot_red", "r": 255, "g": 50, "b": 0, "speed": None}
                ],
                "appendRules": [
                    {
                        "from": "*",
                        "on": "weather_updated",
                        "to": "cold_blue",
                        "condition": "getData('temperature') < 60"
                    },
                    {
                        "from": "*",
                        "on": "weather_updated",
                        "to": "hot_red",
                        "condition": "getData('temperature') >= 60"
                    }
                ]
            }
        }
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
