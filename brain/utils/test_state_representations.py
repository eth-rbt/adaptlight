"""
Tests for the three state representation versions.
"""
import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from brain.utils.state_representations import (
    OriginalRenderer, PurePythonRenderer, StdlibRenderer
)


class TestOriginalRenderer(unittest.TestCase):
    def test_static_color(self):
        """Static color returns correct RGB and next_ms=speed."""
        renderer = OriginalRenderer(r_expr=255, g_expr=0, b_expr=0, speed=None)
        rgb, next_ms = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 0, 0))
        self.assertIsNone(next_ms)

    def test_animation(self):
        """Animation returns next_ms=speed."""
        renderer = OriginalRenderer(
            r_expr="sin(frame * 0.1) * 127 + 128",
            g_expr=0, b_expr=0, speed=30
        )
        rgb, next_ms = renderer.render((0, 0, 0), 0)
        self.assertEqual(next_ms, 30)

    def test_uses_prev_value(self):
        """Expression can access previous r/g/b values."""
        renderer = OriginalRenderer(r_expr="r + 10", g_expr="g", b_expr="b", speed=None)
        rgb, _ = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (110, 50, 25))

    def test_random_function(self):
        """random() function is available."""
        renderer = OriginalRenderer(r_expr="random()", g_expr=0, b_expr=0, speed=None)
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertGreaterEqual(rgb[0], 0)
        self.assertLessEqual(rgb[0], 255)

    def test_math_functions(self):
        """Math functions are available."""
        renderer = OriginalRenderer(
            r_expr="abs(-128)",
            g_expr="min(255, 300)",
            b_expr="max(0, -50)",
            speed=None
        )
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (128, 255, 0))


class TestPurePythonRenderer(unittest.TestCase):
    def test_basic_function(self):
        """Basic render function works."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    return (255, 128, 64), None
''')
        rgb, next_ms = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 128, 64))
        self.assertIsNone(next_ms)

    def test_uses_prev(self):
        """Can use prev parameter."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    r, g, b = prev
    return (min(255, r + 50), g, b), None
''')
        rgb, _ = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (150, 50, 25))

    def test_uses_time(self):
        """Can use t parameter."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    return (int(t * 100) % 256, 0, 0), 30
''')
        rgb, _ = renderer.render((0, 0, 0), 2.5)
        self.assertEqual(rgb[0], 250)

    def test_state_complete_signal(self):
        """Returns next_ms=0 to signal completion."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    if t > 1.0:
        return (255, 255, 255), 0  # Done!
    return (0, 0, 0), 30
''')
        _, next_ms = renderer.render((0, 0, 0), 0.5)
        self.assertEqual(next_ms, 30)
        _, next_ms = renderer.render((0, 0, 0), 1.5)
        self.assertEqual(next_ms, 0)  # Completion signal

    def test_math_module_available(self):
        """math module is pre-injected and available."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    # math is pre-injected, no import needed
    v = int(math.sin(math.pi / 2) * 255)
    return (v, 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 255)


class TestStdlibRenderer(unittest.TestCase):
    def test_hsv_function(self):
        """hsv() helper works."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return hsv(0, 1, 1), None  # Red
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 0, 0))

    def test_hsv_rainbow(self):
        """hsv() produces correct colors across hue range."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return hsv(t, 1, 1), None
''')
        # h=0 -> red
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 0, 0))
        # h=0.333 -> green
        rgb, _ = renderer.render((0, 0, 0), 1/3)
        self.assertEqual(rgb[1], 255)  # Green is dominant
        # h=0.666 -> blue
        rgb, _ = renderer.render((0, 0, 0), 2/3)
        self.assertEqual(rgb[2], 255)  # Blue is dominant

    def test_rgb_clamp(self):
        """rgb() clamps values to 0-255."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return rgb(300, -50, 128), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 0, 128))

    def test_lerp(self):
        """lerp() interpolation works."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = lerp(0, 100, 0.5)
    return (int(v), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 50)

    def test_lerp_color(self):
        """lerp_color() interpolates between colors."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return lerp_color((0, 0, 0), (100, 200, 50), 0.5), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (50, 100, 25))

    def test_clamp(self):
        """clamp() works correctly."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v1 = clamp(150, 0, 100)  # Should be 100
    v2 = clamp(-50, 0, 100)  # Should be 0
    v3 = clamp(50, 0, 100)   # Should be 50
    return (int(v1), int(v2), int(v3)), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (100, 0, 50))

    def test_easing_functions(self):
        """Easing functions work."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = ease_in(0.5)
    return (int(v * 255), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 63)  # 0.25 * 255

    def test_ease_out(self):
        """ease_out works correctly."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = ease_out(0.5)
    return (int(v * 255), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 191)  # 0.75 * 255

    def test_math_functions(self):
        """Math functions available."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = sin(PI / 2) * 255
    return (int(v), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 255)

    def test_random_functions(self):
        """Random functions available."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = randint(100, 100)  # Always 100
    return (v, 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 100)

    def test_map_range(self):
        """map_range works correctly."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = map_range(50, 0, 100, 0, 255)
    return (int(v), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 127)  # 50% of 255


class TestErrorHandling(unittest.TestCase):
    def test_syntax_error_fallback(self):
        """Syntax error returns prev color."""
        renderer = StdlibRenderer('''
def render(prev, t)
    return (255, 0, 0), None  # Missing colon
''')
        rgb, next_ms = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (100, 50, 25))
        self.assertIsNone(next_ms)

    def test_runtime_error_fallback(self):
        """Runtime error returns prev color."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return (1/0, 0, 0), None  # Division by zero
''')
        rgb, _ = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (100, 50, 25))

    def test_undefined_function_fallback(self):
        """Undefined function returns prev color."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return (undefined_func(), 0, 0), None
''')
        rgb, _ = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (100, 50, 25))


class TestEquivalentOutput(unittest.TestCase):
    def test_all_versions_static_red(self):
        """All three versions produce same output for static red."""
        orig = OriginalRenderer(r_expr=255, g_expr=0, b_expr=0, speed=None)
        pure = PurePythonRenderer('''
def render(prev, t):
    return (255, 0, 0), None
''')
        stdlib = StdlibRenderer('''
def render(prev, t):
    return (255, 0, 0), None
''')

        prev = (0, 0, 0)
        t = 0

        self.assertEqual(orig.render(prev, t)[0], (255, 0, 0))
        self.assertEqual(pure.render(prev, t)[0], (255, 0, 0))
        self.assertEqual(stdlib.render(prev, t)[0], (255, 0, 0))

    def test_stdlib_hsv_vs_pure_python(self):
        """Stdlib hsv() matches manual calculation."""
        stdlib = StdlibRenderer('''
def render(prev, t):
    return hsv(0.5, 1, 1), None  # Cyan
''')

        # Manual HSV to RGB for h=0.5, s=1, v=1 -> cyan (0, 255, 255)
        rgb, _ = stdlib.render((0, 0, 0), 0)
        self.assertEqual(rgb, (0, 255, 255))


if __name__ == '__main__':
    unittest.main()
