"""
State behavior implementations for AdaptLight.

This package contains the actual behavior for each state (on, off, color, animation)
and utilities for color/animation processing.
"""

from .light_states import initialize_default_states

__all__ = ['initialize_default_states']
