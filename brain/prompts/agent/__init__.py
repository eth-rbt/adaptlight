"""Agent prompts for multi-turn tool-calling mode."""

from .agent_prompt import get_agent_system_prompt
from .agent_prompt_with_examples import get_agent_system_prompt_with_examples
from .agent_prompt_all_leds import get_agent_system_prompt_all_leds
from .agent_prompt_realtime import get_realtime_system_prompt

__all__ = ['get_agent_system_prompt', 'get_agent_system_prompt_with_examples', 'get_agent_system_prompt_all_leds', 'get_realtime_system_prompt']
