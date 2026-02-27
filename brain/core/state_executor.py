"""
StateExecutor - manages state rendering across representation versions.

Handles:
- Compiling state code into renderers
- Calling render(prev, t) and tracking timing
- Signaling state_complete when next_ms=0

Return values for render(prev, t):
- ((r, g, b), next_ms > 0)  → call again in next_ms milliseconds
- ((r, g, b), None)         → static, no more updates needed
- ((r, g, b), 0)            → STATE COMPLETE, trigger state_complete transition
"""

import time
from brain.utils.state_representations import (
    OriginalRenderer, PurePythonRenderer, StdlibRenderer
)


class StateExecutor:
    """Manages state rendering for all three representation versions."""

    def __init__(self, representation_version: str = "stdlib", num_pixels: int = 0):
        """
        Initialize the state executor.

        Args:
            representation_version: "original", "pure_python", or "stdlib"
            num_pixels: Number of ring LED pixels (0 = no ring)
        """
        self.version = representation_version
        self.num_pixels = num_pixels
        self.current_renderer = None
        self.current_state = None
        self.state_start_time = None
        self.prev_rgb = (0, 0, 0)
        self.on_state_complete = None  # Callback when next_ms=0
        self.on_rgb_update = None  # Callback when RGB changes
        self._get_data_fn = None  # Function to get data from state machine
        self._set_data_fn = None  # Function to set data in state machine

    def set_data_accessors(self, get_fn, set_fn):
        """
        Set the data accessor functions for getData/setData in render code.

        Args:
            get_fn: Function(key, default=None) -> value
            set_fn: Function(key, value) -> value
        """
        self._get_data_fn = get_fn
        self._set_data_fn = set_fn

    def set_on_state_complete(self, callback):
        """
        Set callback for when renderer signals completion (next_ms=0).

        Args:
            callback: Function to call when state completes (no args)
        """
        self.on_state_complete = callback

    def set_on_rgb_update(self, callback):
        """
        Set callback for when RGB values update.

        Args:
            callback: Function that takes (r, g, b) tuple
        """
        self.on_rgb_update = callback

    def compile_state(self, state) -> bool:
        """
        Compile a state into a renderer.

        For original mode: uses r/g/b/speed fields
        For pure_python/stdlib mode: uses code field

        Args:
            state: State object to compile

        Returns:
            True if successful, False otherwise
        """
        try:
            if state.code is not None:
                # Code-based state (pure_python or stdlib)
                if self.version == "pure_python":
                    self.current_renderer = PurePythonRenderer(
                        state.code,
                        get_data_fn=self._get_data_fn,
                        set_data_fn=self._set_data_fn,
                        num_pixels=self.num_pixels
                    )
                else:
                    # Default to stdlib for code-based states
                    self.current_renderer = StdlibRenderer(
                        state.code,
                        get_data_fn=self._get_data_fn,
                        set_data_fn=self._set_data_fn,
                        num_pixels=self.num_pixels
                    )
            else:
                # Original r/g/b expression state
                self.current_renderer = OriginalRenderer(
                    r_expr=state.r,
                    g_expr=state.g,
                    b_expr=state.b,
                    speed=state.speed
                )
            return True
        except Exception as e:
            print(f"Failed to compile state '{state.name}': {e}")
            self.current_renderer = None
            return False

    def enter_state(self, state, initial_rgb=None):
        """
        Called when entering a new state.
        Compiles the state and resets timing.

        Args:
            state: State object to enter
            initial_rgb: Initial RGB values (defaults to current prev_rgb)
        """
        self.current_state = state
        self.compile_state(state)
        self.state_start_time = time.time()
        if initial_rgb is not None:
            self.prev_rgb = initial_rgb

    def render(self) -> tuple:
        """
        Render current frame.

        Returns:
            ((r, g, b), next_ms) or None if no renderer
            For dict returns from 'all' mode: ({"cobbled": (r,g,b), "ring": [...], "next_ms": N}, next_ms)

        If next_ms == 0, calls on_state_complete callback.
        If RGB changes, calls on_rgb_update callback.
        """
        if not self.current_renderer:
            return None

        t = time.time() - self.state_start_time
        result = self.current_renderer.render(self.prev_rgb, t)

        # Handle dict return from 'all' mode render functions
        if isinstance(result, dict):
            rgb = result.get("cobbled", self.prev_rgb)
            next_ms = result.get("next_ms")
            ring_pixels = result.get("ring")

            old_rgb = self.prev_rgb
            self.prev_rgb = rgb

            if self.on_rgb_update and rgb != old_rgb:
                self.on_rgb_update(rgb)

            if next_ms == 0 and self.on_state_complete:
                self.on_state_complete()

            # Return the full dict so light_states can dispatch ring pixels
            return result, next_ms

        # Standard tuple return: ((r,g,b), next_ms)
        rgb, next_ms = result

        # Update prev_rgb for next render
        old_rgb = self.prev_rgb
        self.prev_rgb = rgb

        # Notify RGB update if changed
        if self.on_rgb_update and rgb != old_rgb:
            self.on_rgb_update(rgb)

        # Check for state completion
        if next_ms == 0 and self.on_state_complete:
            self.on_state_complete()

        return rgb, next_ms

    def get_current_rgb(self) -> tuple:
        """Get the current RGB values."""
        return self.prev_rgb

    def get_elapsed_time(self) -> float:
        """Get time elapsed since state entry in seconds."""
        if self.state_start_time is None:
            return 0.0
        return time.time() - self.state_start_time
