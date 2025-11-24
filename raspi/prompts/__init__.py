# Prompts package for AdaptLight
from .agent_prompt import get_agent_system_prompt
from .parsing_prompt import get_system_prompt as get_parsing_prompt
from .parsing_prompt_concise import get_system_prompt as get_concise_prompt

__all__ = ['get_agent_system_prompt', 'get_parsing_prompt', 'get_concise_prompt']
