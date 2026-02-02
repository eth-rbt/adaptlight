"""
APIs module for AdaptLight.

This module provides:
- Preset API library with curated, ready-to-use integrations
- API executor for calling preset APIs and returning raw data

The agent decides what colors to use based on the data!
"""

from .preset_apis import PRESET_APIS, get_api_info, list_apis
from .api_executor import APIExecutor
