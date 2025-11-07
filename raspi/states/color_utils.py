"""
Color utility functions for AdaptLight.

Provides helper functions for color manipulation:
- Color space conversions (RGB, HSV, HSL)
- Color interpolation
- Color validation
"""

import math


def rgb_to_hsv(r: int, g: int, b: int):
    """
    Convert RGB to HSV.

    Args:
        r, g, b: RGB values (0-255)

    Returns:
        Tuple of (h, s, v) where h is 0-360, s and v are 0-1
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    delta = max_c - min_c

    # Hue
    if delta == 0:
        h = 0
    elif max_c == r:
        h = 60 * (((g - b) / delta) % 6)
    elif max_c == g:
        h = 60 * (((b - r) / delta) + 2)
    else:
        h = 60 * (((r - g) / delta) + 4)

    # Saturation
    s = 0 if max_c == 0 else delta / max_c

    # Value
    v = max_c

    return h, s, v


def hsv_to_rgb(h: float, s: float, v: float):
    """
    Convert HSV to RGB.

    Args:
        h: Hue (0-360)
        s: Saturation (0-1)
        v: Value (0-1)

    Returns:
        Tuple of (r, g, b) where values are 0-255
    """
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


def interpolate_color(color1, color2, t):
    """
    Interpolate between two colors.

    Args:
        color1: First RGB tuple (r, g, b)
        color2: Second RGB tuple (r, g, b)
        t: Interpolation factor (0-1)

    Returns:
        Interpolated RGB tuple
    """
    r = int(color1[0] + (color2[0] - color1[0]) * t)
    g = int(color1[1] + (color2[1] - color1[1]) * t)
    b = int(color1[2] + (color2[2] - color1[2]) * t)

    return r, g, b


def clamp_rgb(r, g, b):
    """
    Clamp RGB values to valid range.

    Args:
        r, g, b: RGB values

    Returns:
        Clamped (r, g, b) tuple
    """
    return (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b)))
    )
