"""
AdaptLight Brain - Shared state machine and AI processing library.

The brain module provides:
- State machine core (StateMachine, State, Rule)
- Tool registry for AI agent
- Processing modes (Agent, Parser)
- Unified SMgenerator interface

Example usage:
    from brain import SMgenerator

    smgen = SMgenerator({
        'mode': 'agent',
        'model': 'claude-haiku-4-5',
        'anthropic_api_key': 'sk-ant-...',
    })

    result = smgen.process("turn the light red")
    print(result.state)
"""

from .smgenerator import SMgenerator, SMResult
from .core import (
    StateMachine,
    State,
    States,
    Rule,
    Memory,
    get_memory,
    PipelineExecutor,
    PipelineRegistry,
    get_pipeline_registry,
)
from .tools import ToolRegistry
from .processing import AgentExecutor, CommandParser

__version__ = '0.1.0'

__all__ = [
    # Main interface
    'SMgenerator',
    'SMResult',

    # Core
    'StateMachine',
    'State',
    'States',
    'Rule',
    'Memory',
    'get_memory',
    'PipelineExecutor',
    'PipelineRegistry',
    'get_pipeline_registry',

    # Tools
    'ToolRegistry',

    # Processing
    'AgentExecutor',
    'CommandParser',
]
