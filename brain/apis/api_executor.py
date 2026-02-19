"""
API Executor for AdaptLight preset APIs.

Executes preset API calls and returns raw data.
The agent decides what to do with the data (colors, states, etc.)
"""

import requests
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from .preset_apis import PRESET_APIS, get_api_info


class APIExecutor:
    """Executes preset API calls and returns raw data."""

    def __init__(self, timeout: float = 15.0):
        """
        Initialize the API executor.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    def execute(self, api_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a preset API call.

        Args:
            api_name: Name of the preset API
            params: Parameters for the API call

        Returns:
            Dict with 'success', 'data', and optionally 'error'
        """
        params = params or {}

        if api_name not in PRESET_APIS:
            return {"success": False, "error": f"Unknown API: {api_name}. Use listAPIs() to see available APIs."}

        api_info = PRESET_APIS[api_name]

        # Validate required params
        for param_name, param_def in api_info.get("params", {}).items():
            if param_def.get("required", False) and param_name not in params:
                return {"success": False, "error": f"Missing required parameter: {param_name}"}

        # Apply defaults
        for param_name, param_def in api_info.get("params", {}).items():
            if param_name not in params and "default" in param_def:
                params[param_name] = param_def["default"]

        # Execute the appropriate handler
        try:
            handler = getattr(self, f"_fetch_{api_name}", None)
            if handler is None:
                return {"success": False, "error": f"No implementation for API: {api_name}"}

            data = handler(params)
            return {"success": True, "data": data}

        except requests.exceptions.Timeout:
            return {"success": False, "error": f"API timeout after {self.timeout}s"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"API error: {str(e)}"}

    # =========================================================================
    # API Implementations - Each returns raw data
    # =========================================================================

    def _fetch_weather(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch weather data from wttr.in."""
        location = params["location"]

        url = f"https://wttr.in/{location}?format=j1"
        response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "AdaptLight/1.0"})
        response.raise_for_status()

        data = response.json()
        print(data) #Defaults to sunny, even at night (Might be API issue)
        current = data["current_condition"][0]

        # Determine if it's day or night
        try:
            obs_time = current.get("localObsDateTime", "12:00 PM") #Changing to localObsDateTime because its more accurate
            hour = int(obs_time.split(" ")[1][:2])
            print("did we get here okay?")
            if "PM" in obs_time and hour != 12:
                hour += 12
            is_day = 6 <= hour <= 18
        except:
            print("Error detected, nuking system")
            is_day = True
        # Map weather codes to conditions
        weather_code = int(current.get("weatherCode", 0))
        condition = self._weather_code_to_condition(weather_code)

        return {
            "temp_f": int(current["temp_F"]),
            "temp_c": int(current["temp_C"]),
            "condition": condition,
            "humidity": int(current["humidity"]),
            "wind_mph": int(current["windspeedMiles"]),
            "is_day": is_day,
            "description": current.get("weatherDesc", [{}])[0].get("value", "Unknown")
        }

    def _weather_code_to_condition(self, code: int) -> str:
        """Convert wttr.in weather code to simple condition string."""
        if code in [113]:
            return "sunny"
        elif code in [116, 119, 122]:
            return "cloudy"
        elif code in [143, 248, 260]:
            return "foggy"
        elif code in [176, 263, 266, 281, 284, 293, 296, 299, 302, 305, 308, 311, 314, 353, 356, 359]:
            return "rainy"
        elif code in [179, 182, 185, 227, 230, 317, 320, 323, 326, 329, 332, 335, 338, 350, 362, 365, 368, 371, 374, 377]:
            return "snowy"
        elif code in [200, 386, 389, 392, 395]:
            return "stormy"
        else:
            return "cloudy"

    def _fetch_stock(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch stock data using Yahoo Finance."""
        symbol = params["symbol"].upper()

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        headers = {"User-Agent": "AdaptLight/1.0"}
        response = requests.get(url, timeout=self.timeout, headers=headers)
        response.raise_for_status()

        data = response.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        quote = result.get("indicators", {}).get("quote", [{}])[0]

        current_price = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("previousClose", current_price)

        change_absolute = current_price - prev_close
        change_percent = (change_absolute / prev_close * 100) if prev_close else 0

        market_state = meta.get("marketState", "CLOSED")
        market_open = market_state in ["REGULAR", "PRE", "POST"]

        return {
            "price": round(current_price, 2),
            "change_percent": round(change_percent, 2),
            "change_absolute": round(change_absolute, 2),
            "volume": int(quote.get("volume", [0])[-1]) if quote.get("volume") else 0,
            "market_open": market_open,
            "symbol": symbol
        }

    def _fetch_crypto(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch cryptocurrency data from CoinGecko."""
        coin = params["coin"].lower()

        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true&include_24hr_vol=true"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()

        if coin not in data:
            raise ValueError(f"Cryptocurrency '{coin}' not found. Try: bitcoin, ethereum, solana, dogecoin")

        coin_data = data[coin]

        return {
            "price_usd": coin_data.get("usd", 0),
            "change_24h": round(coin_data.get("usd_24h_change", 0), 2),
            "market_cap": coin_data.get("usd_market_cap", 0),
            "volume_24h": coin_data.get("usd_24h_vol", 0),
            "coin": coin
        }

    def _fetch_sun(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch sunrise/sunset data."""
        location = params["location"]
        lat, lon = self._location_to_coords(location)

        url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()["results"]

        sunrise = datetime.fromisoformat(data["sunrise"].replace("Z", "+00:00"))
        sunset = datetime.fromisoformat(data["sunset"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)

        is_daytime = sunrise <= now <= sunset
        day_length = (sunset - sunrise).total_seconds() / 3600

        minutes_until_sunset = (sunset - now).total_seconds() / 60
        minutes_until_sunrise = (sunrise - now).total_seconds() / 60

        return {
            "sunrise": sunrise.strftime("%H:%M"),
            "sunset": sunset.strftime("%H:%M"),
            "is_daytime": is_daytime,
            "day_length_hours": round(day_length, 2),
            "minutes_until_sunset": round(minutes_until_sunset),
            "minutes_until_sunrise": round(minutes_until_sunrise)
        }

    def _location_to_coords(self, location: str) -> tuple:
        """Convert location string to lat/lon coordinates."""
        if "," in location:
            parts = location.split(",")
            if len(parts) == 2:
                try:
                    return (float(parts[0].strip()), float(parts[1].strip()))
                except ValueError:
                    pass

        # Use wttr.in for geocoding
        url = f"https://wttr.in/{location}?format=j1"
        response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "AdaptLight/1.0"})
        response.raise_for_status()

        data = response.json()
        nearest = data.get("nearest_area", [{}])[0]

        return (float(nearest.get("latitude", "0")), float(nearest.get("longitude", "0")))

    def _fetch_air_quality(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch air quality data from World Air Quality Index."""
        location = params["location"]

        url = f"https://api.waqi.info/feed/{location}/?token=demo"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()

        if data.get("status") != "ok":
            raise ValueError(f"Air quality data not found for '{location}'")

        aqi_data = data["data"]
        aqi = aqi_data.get("aqi", 0)

        if aqi <= 50:
            level = "good"
        elif aqi <= 100:
            level = "moderate"
        elif aqi <= 150:
            level = "unhealthy_sensitive"
        elif aqi <= 200:
            level = "unhealthy"
        elif aqi <= 300:
            level = "very_unhealthy"
        else:
            level = "hazardous"

        iaqi = aqi_data.get("iaqi", {})

        return {
            "aqi": aqi,
            "level": level,
            "pm25": iaqi.get("pm25", {}).get("v", 0),
            "pm10": iaqi.get("pm10", {}).get("v", 0),
            "dominant_pollutant": aqi_data.get("dominentpol", "unknown")
        }

    def _fetch_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current time information."""
        now = datetime.now(ZoneInfo(params.get('timezone', "Asia/Tokyo"))) #MUST SPECIFY TIMEZONE
        print("Your date and time is this =", now) #Checking if issue is with Datetime class

        weekday = now.weekday() + 1
        print("The weekday is ", weekday)
        is_weekend = weekday >= 5
        is_business = not is_weekend and 9 <= now.hour < 17

        return {
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "weekday": weekday,
            "is_weekend": is_weekend,
            "is_business_hours": is_business
        }

    def _fetch_fear_greed(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch Bitcoin Fear & Greed Index."""
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()["data"][0]

        return {
            "value": int(data["value"]),
            "classification": data["value_classification"].lower().replace(" ", "_")
        }

    def _fetch_github_repo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch GitHub repository statistics."""
        repo = params["repo"]

        url = f"https://api.github.com/repos/{repo}"
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "AdaptLight/1.0"}
        response = requests.get(url, timeout=self.timeout, headers=headers)
        response.raise_for_status()

        data = response.json()

        return {
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "watchers": data.get("watchers_count", 0)
        }

    def _fetch_random(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate random value."""
        min_val = int(params.get("min", 0))
        max_val = int(params.get("max", 100))

        return {
            "value": random.randint(min_val, max_val)
        }
