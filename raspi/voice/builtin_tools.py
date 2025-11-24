"""
Built-in tools for the agent executor.

These are pre-defined tools that Claude can use without defining them.
They provide common functionality like fetching data from URLs.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any


# Built-in tool definitions
BUILTIN_TOOLS = {
    "fetch_json": {
        "name": "fetch_json",
        "description": "Fetch JSON data from a URL",
        "params": {"url": {"type": "string", "required": True}},
        "code": """
import requests
response = requests.get(args['url'], timeout=10)
response.raise_for_status()
return response.json()
""",
        "returns": {"type": "object"}
    },

    "fetch_text": {
        "name": "fetch_text",
        "description": "Fetch text content from a URL",
        "params": {"url": {"type": "string", "required": True}},
        "code": """
import requests
response = requests.get(args['url'], timeout=10)
response.raise_for_status()
return {"text": response.text}
""",
        "returns": {"text": "string"}
    },

    "get_weather": {
        "name": "get_weather",
        "description": "Get current weather for a location using wttr.in",
        "params": {"location": {"type": "string", "required": False}},
        "code": """
import requests
location = args.get('location', '')
url = f"https://wttr.in/{location}?format=j1"
response = requests.get(url, timeout=10)
response.raise_for_status()
data = response.json()
current = data['current_condition'][0]
return {
    'temp_f': int(current['temp_F']),
    'temp_c': int(current['temp_C']),
    'humidity': int(current['humidity']),
    'condition': current['weatherDesc'][0]['value'],
    'wind_mph': int(current['windspeedMiles']),
    'feels_like_f': int(current['FeelsLikeF']),
    'uv_index': int(current['uvIndex'])
}
""",
        "returns": {
            "temp_f": "number",
            "temp_c": "number",
            "humidity": "number",
            "condition": "string",
            "wind_mph": "number",
            "feels_like_f": "number",
            "uv_index": "number"
        }
    },

    "get_time": {
        "name": "get_time",
        "description": "Get current date and time information",
        "params": {},
        "code": """
now = datetime.datetime.now()
weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
return {
    'hour': now.hour,
    'minute': now.minute,
    'second': now.second,
    'day': now.day,
    'month': now.month,
    'year': now.year,
    'weekday': now.weekday(),
    'weekday_name': weekdays[now.weekday()],
    'is_weekend': now.weekday() >= 5,
    'timestamp': now.timestamp()
}
""",
        "returns": {
            "hour": "number",
            "minute": "number",
            "second": "number",
            "day": "number",
            "month": "number",
            "year": "number",
            "weekday": "number",
            "weekday_name": "string",
            "is_weekend": "boolean",
            "timestamp": "number"
        }
    },

    "random_number": {
        "name": "random_number",
        "description": "Generate a random number in a range",
        "params": {
            "min": {"type": "number", "required": False},
            "max": {"type": "number", "required": False}
        },
        "code": """
min_val = args.get('min', 0)
max_val = args.get('max', 100)
return {'value': random.randint(min_val, max_val)}
""",
        "returns": {"value": "number"}
    },

    "delay": {
        "name": "delay",
        "description": "Wait for a specified number of milliseconds",
        "params": {"ms": {"type": "number", "required": True}},
        "code": """
ms = args['ms']
time.sleep(ms / 1000.0)
return {'waited_ms': ms}
""",
        "returns": {"waited_ms": "number"}
    }
}


def register_builtin_tools(executor):
    """
    Register all built-in tools with a CustomToolExecutor.

    Args:
        executor: CustomToolExecutor instance
    """
    for name, tool in BUILTIN_TOOLS.items():
        executor.register_tool(
            name=tool["name"],
            code=tool["code"],
            description=tool.get("description", ""),
            params=tool.get("params", {}),
            returns=tool.get("returns", {})
        )


def get_builtin_tool_descriptions() -> str:
    """
    Get formatted descriptions of built-in tools for prompts.

    Returns:
        Formatted string describing available built-in tools
    """
    lines = ["Built-in tools (pre-defined, ready to use):"]
    for name, tool in BUILTIN_TOOLS.items():
        desc = tool.get("description", "No description")
        params = tool.get("params", {})
        param_str = ", ".join(f"{k}" for k in params.keys()) if params else "none"
        lines.append(f"  - {name}({param_str}): {desc}")
    return "\n".join(lines)
