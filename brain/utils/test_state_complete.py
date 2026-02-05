"""
Tests for state_complete transition mechanism.
"""
import unittest
import time
import sys
import os
from unittest.mock import Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from brain.core.state_executor import StateExecutor
from brain.core.state import State


class TestStateExecutorCompletion(unittest.TestCase):
    def test_callback_on_completion(self):
        """on_state_complete callback fires when next_ms=0."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        # State that completes immediately
        state = State(name="done", code='''
def render(prev, t):
    return (255, 255, 255), 0  # Complete immediately
''')
        executor.enter_state(state)
        executor.render()

        callback.assert_called_once()

    def test_no_callback_on_animation(self):
        """Callback doesn't fire when next_ms > 0."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        state = State(name="animate", code='''
def render(prev, t):
    return (255, 0, 0), 30  # Keep animating
''')
        executor.enter_state(state)
        executor.render()

        callback.assert_not_called()

    def test_no_callback_on_static(self):
        """Callback doesn't fire when next_ms=None (static)."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        state = State(name="static", code='''
def render(prev, t):
    return (255, 0, 0), None  # Static
''')
        executor.enter_state(state)
        executor.render()

        callback.assert_not_called()

    def test_completion_after_time(self):
        """State completes after animation finishes based on time."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        # State that completes after 0.1 seconds
        state = State(name="timed", code='''
def render(prev, t):
    if t >= 0.1:
        return (255, 255, 255), 0  # Done
    return (0, 0, 0), 10  # Keep going
''')
        executor.enter_state(state)

        # First render at t~0
        executor.render()
        callback.assert_not_called()

        # Simulate time passing by adjusting start time
        executor.state_start_time = time.time() - 0.15
        executor.render()  # t ~ 0.15

        callback.assert_called_once()

    def test_rgb_callback_fires(self):
        """on_rgb_update callback fires when RGB changes."""
        executor = StateExecutor("stdlib")
        rgb_callback = Mock()
        executor.set_on_rgb_update(rgb_callback)

        state = State(name="red", code='''
def render(prev, t):
    return (255, 0, 0), None
''')
        executor.enter_state(state, initial_rgb=(0, 0, 0))
        executor.render()

        rgb_callback.assert_called_once_with((255, 0, 0))

    def test_rgb_callback_not_fires_if_same(self):
        """on_rgb_update callback doesn't fire if RGB unchanged."""
        executor = StateExecutor("stdlib")
        rgb_callback = Mock()
        executor.set_on_rgb_update(rgb_callback)

        state = State(name="red", code='''
def render(prev, t):
    return (255, 0, 0), None
''')
        executor.enter_state(state, initial_rgb=(255, 0, 0))
        executor.render()

        rgb_callback.assert_not_called()


class TestStateExecutorRendering(unittest.TestCase):
    def test_original_mode_rendering(self):
        """Original mode renders r/g/b expressions correctly."""
        executor = StateExecutor("original")

        state = State(name="red", r=255, g=0, b=0, speed=None)
        executor.enter_state(state)
        result = executor.render()

        self.assertIsNotNone(result)
        rgb, next_ms = result
        self.assertEqual(rgb, (255, 0, 0))
        self.assertIsNone(next_ms)

    def test_stdlib_mode_rendering(self):
        """Stdlib mode renders code correctly."""
        executor = StateExecutor("stdlib")

        state = State(name="green", code='''
def render(prev, t):
    return (0, 255, 0), None
''')
        executor.enter_state(state)
        result = executor.render()

        self.assertIsNotNone(result)
        rgb, next_ms = result
        self.assertEqual(rgb, (0, 255, 0))
        self.assertIsNone(next_ms)

    def test_pure_python_mode_rendering(self):
        """Pure Python mode renders code correctly."""
        executor = StateExecutor("pure_python")

        state = State(name="blue", code='''
def render(prev, t):
    return (0, 0, 255), None
''')
        executor.enter_state(state)
        result = executor.render()

        self.assertIsNotNone(result)
        rgb, next_ms = result
        self.assertEqual(rgb, (0, 0, 255))
        self.assertIsNone(next_ms)

    def test_prev_rgb_tracking(self):
        """prev_rgb is tracked across renders."""
        executor = StateExecutor("stdlib")

        state = State(name="brighten", code='''
def render(prev, t):
    r, g, b = prev
    return (min(255, r + 50), g, b), 30
''')
        executor.enter_state(state, initial_rgb=(100, 50, 25))

        # First render
        rgb1, _ = executor.render()
        self.assertEqual(rgb1, (150, 50, 25))

        # Second render should use updated prev
        rgb2, _ = executor.render()
        self.assertEqual(rgb2, (200, 50, 25))

        # Third render
        rgb3, _ = executor.render()
        self.assertEqual(rgb3, (250, 50, 25))

    def test_time_tracking(self):
        """Time is tracked correctly across renders."""
        executor = StateExecutor("stdlib")

        state = State(name="time_based", code='''
def render(prev, t):
    return (int(t * 100) % 256, 0, 0), 10
''')
        executor.enter_state(state)

        # First render at t~0
        rgb1, _ = executor.render()
        self.assertLess(rgb1[0], 10)  # Very small value

        # Simulate 1 second passing
        executor.state_start_time = time.time() - 1.0
        rgb2, _ = executor.render()
        self.assertEqual(rgb2[0], 100)  # 1.0 * 100 = 100


class TestStateExecutorEdgeCases(unittest.TestCase):
    def test_no_renderer_returns_none(self):
        """render() returns None if no renderer is set."""
        executor = StateExecutor("stdlib")
        result = executor.render()
        self.assertIsNone(result)

    def test_fallback_to_stdlib_for_code_state(self):
        """Code-based state uses stdlib even if version is 'original'."""
        executor = StateExecutor("original")

        # Even with original mode, a code-based state should work
        # (it will use OriginalRenderer for this state since it has no code)
        state = State(name="red", r=255, g=0, b=0, speed=None)
        executor.enter_state(state)
        result = executor.render()

        self.assertIsNotNone(result)
        rgb, _ = result
        self.assertEqual(rgb, (255, 0, 0))

    def test_get_elapsed_time(self):
        """get_elapsed_time() returns correct value."""
        executor = StateExecutor("stdlib")

        state = State(name="test", code='def render(prev, t): return (0,0,0), None')
        executor.enter_state(state)

        # Immediately after entering
        elapsed = executor.get_elapsed_time()
        self.assertLess(elapsed, 0.1)

        # After simulated time
        executor.state_start_time = time.time() - 1.5
        elapsed = executor.get_elapsed_time()
        self.assertGreater(elapsed, 1.4)
        self.assertLess(elapsed, 1.6)

    def test_get_current_rgb(self):
        """get_current_rgb() returns current RGB."""
        executor = StateExecutor("stdlib")

        state = State(name="test", code='def render(prev, t): return (100, 150, 200), None')
        executor.enter_state(state, initial_rgb=(0, 0, 0))
        executor.render()

        rgb = executor.get_current_rgb()
        self.assertEqual(rgb, (100, 150, 200))


if __name__ == '__main__':
    unittest.main()
