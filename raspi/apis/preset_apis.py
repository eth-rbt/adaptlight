"""
Preset API library for AdaptLight.

This module contains curated, ready-to-use API integrations that the agent
can use without writing custom code. Each API returns raw data that the
agent can then use to decide what colors/states to create.

APIs just return data - the agent decides the colors!
"""

from typing import Dict, List, Optional, Any


PRESET_APIS = {
    "weather": {
        "name": "weather",
        "description": "Get current weather conditions for a location",
        "params": {
            "location": {
                "type": "string",
                "description": "City name, zip code, or 'lat,lon' coordinates",
                "required": True,
                "examples": ["San Francisco", "10001", "37.7749,-122.4194"]
            }
        },
        "returns": {
            "temp_f": "Temperature in Fahrenheit",
            "temp_c": "Temperature in Celsius",
            "condition": "Weather condition (sunny, cloudy, rainy, snowy, stormy, foggy)",
            "humidity": "Humidity percentage (0-100)",
            "wind_mph": "Wind speed in MPH",
            "is_day": "True if daytime, False if night",
            "description": "Human-readable weather description"
        },
        "example_response": {
            "temp_f": 65,
            "temp_c": 18,
            "condition": "cloudy",
            "humidity": 72,
            "wind_mph": 8,
            "is_day": True,
            "description": "Partly cloudy"
        }
    },

    "stock": {
        "name": "stock",
        "description": "Get stock price and daily change percentage",
        "params": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol",
                "required": True,
                "examples": ["AAPL", "GOOGL", "SPY", "TSLA"]
            }
        },
        "returns": {
            "price": "Current price in USD",
            "change_percent": "Daily change percentage (can be negative)",
            "change_absolute": "Absolute price change in USD",
            "volume": "Trading volume",
            "market_open": "True if market is currently open",
            "symbol": "The stock symbol"
        },
        "example_response": {
            "price": 178.52,
            "change_percent": 1.23,
            "change_absolute": 2.17,
            "volume": 52341000,
            "market_open": True,
            "symbol": "AAPL"
        }
    },

    "crypto": {
        "name": "crypto",
        "description": "Get cryptocurrency price and 24-hour change",
        "params": {
            "coin": {
                "type": "string",
                "description": "Cryptocurrency ID (use lowercase)",
                "required": True,
                "examples": ["bitcoin", "ethereum", "solana", "dogecoin"]
            }
        },
        "returns": {
            "price_usd": "Current price in USD",
            "change_24h": "24-hour change percentage (can be negative)",
            "market_cap": "Market capitalization in USD",
            "volume_24h": "24-hour trading volume",
            "coin": "The coin ID"
        },
        "example_response": {
            "price_usd": 43250.00,
            "change_24h": -2.5,
            "market_cap": 847000000000,
            "volume_24h": 28000000000,
            "coin": "bitcoin"
        }
    },

    "sun": {
        "name": "sun",
        "description": "Get sunrise/sunset times and daylight status",
        "params": {
            "location": {
                "type": "string",
                "description": "City name or 'lat,lon' coordinates",
                "required": True,
                "examples": ["New York", "51.5074,-0.1278"]
            }
        },
        "returns": {
            "sunrise": "Sunrise time (HH:MM)",
            "sunset": "Sunset time (HH:MM)",
            "is_daytime": "True if currently between sunrise and sunset",
            "day_length_hours": "Length of day in hours",
            "minutes_until_sunset": "Minutes until sunset (negative if past)",
            "minutes_until_sunrise": "Minutes until sunrise (negative if past)"
        },
        "example_response": {
            "sunrise": "06:45",
            "sunset": "17:30",
            "is_daytime": True,
            "day_length_hours": 10.75,
            "minutes_until_sunset": 180,
            "minutes_until_sunrise": -420
        }
    },

    "air_quality": {
        "name": "air_quality",
        "description": "Get air quality index and pollution levels",
        "params": {
            "location": {
                "type": "string",
                "description": "City name",
                "required": True,
                "examples": ["Los Angeles", "Beijing", "London"]
            }
        },
        "returns": {
            "aqi": "Air Quality Index (0-500, lower is better)",
            "level": "AQI level (good, moderate, unhealthy_sensitive, unhealthy, very_unhealthy, hazardous)",
            "pm25": "PM2.5 concentration",
            "pm10": "PM10 concentration",
            "dominant_pollutant": "Main pollutant"
        },
        "example_response": {
            "aqi": 42,
            "level": "good",
            "pm25": 12,
            "pm10": 25,
            "dominant_pollutant": "pm25"
        }
    },

    "time": {
        "name": "time",
        "description": "Get current time information",
        "params": {
            "timezone": {
                "type": "string",
                "description": "Timezone (optional, defaults to local)",
                "required": False,
                "default": "local",
                "examples": ["America/New_York", "Europe/London", "Asia/Tokyo"]
            }
        },
        "returns": {
            "hour": "Current hour (0-23)",
            "minute": "Current minute (0-59)",
            "second": "Current second (0-59)",
            "weekday": "Day of week (0=Monday, 6=Sunday)",
            "is_weekend": "True if Saturday or Sunday",
            "is_business_hours": "True if 9am-5pm on weekday"
        },
        "example_response": {
            "hour": 14,
            "minute": 30,
            "second": 45,
            "weekday": 2,
            "is_weekend": False,
            "is_business_hours": True
        }
    },

    "fear_greed": {
        "name": "fear_greed",
        "description": "Get the Bitcoin/Crypto Fear & Greed Index",
        "params": {},
        "returns": {
            "value": "Fear/Greed index (0-100, 0=extreme fear, 100=extreme greed)",
            "classification": "Category: extreme_fear, fear, neutral, greed, extreme_greed"
        },
        "example_response": {
            "value": 35,
            "classification": "fear"
        }
    },

    "github_repo": {
        "name": "github_repo",
        "description": "Get GitHub repository statistics",
        "params": {
            "repo": {
                "type": "string",
                "description": "Repository in 'owner/repo' format",
                "required": True,
                "examples": ["facebook/react", "microsoft/vscode", "torvalds/linux"]
            }
        },
        "returns": {
            "stars": "Number of stars",
            "forks": "Number of forks",
            "open_issues": "Number of open issues",
            "watchers": "Number of watchers"
        },
        "example_response": {
            "stars": 215000,
            "forks": 45000,
            "open_issues": 1200,
            "watchers": 6500
        }
    },

    "random": {
        "name": "random",
        "description": "Get random values (useful for testing or random effects)",
        "params": {
            "min": {
                "type": "number",
                "description": "Minimum value",
                "required": False,
                "default": 0
            },
            "max": {
                "type": "number",
                "description": "Maximum value",
                "required": False,
                "default": 100
            }
        },
        "returns": {
            "value": "Random value between min and max"
        },
        "example_response": {
            "value": 42
        }
    }
}


def get_api_info(name: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a preset API.

    Args:
        name: API name

    Returns:
        API definition dict or None if not found
    """
    return PRESET_APIS.get(name)


def list_apis() -> List[Dict[str, Any]]:
    """
    List all available preset APIs.

    Returns:
        List of API summaries
    """
    apis = []
    for name, api in PRESET_APIS.items():
        apis.append({
            "name": name,
            "description": api["description"],
            "params": {k: v["description"] for k, v in api.get("params", {}).items()},
            "returns": list(api.get("returns", {}).keys()),
            "example_response": api.get("example_response")
        })
    return apis
