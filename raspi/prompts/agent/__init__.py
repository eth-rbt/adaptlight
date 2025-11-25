"""Agent prompts for multi-turn tool-calling mode."""

from .agent_prompt import get_agent_system_prompt
from .agent_prompt_with_examples import get_agent_system_prompt_with_examples

__all__ = ['get_agent_system_prompt', 'get_agent_system_prompt_with_examples']
