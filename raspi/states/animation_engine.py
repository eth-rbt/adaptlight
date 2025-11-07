"""
Animation engine for AdaptLight.

Provides animation utilities and preset animations.
"""

import math


class AnimationEngine:
    """Animation engine for LED patterns."""

    @staticmethod
    def pulse_animation(t, speed=1.0):
        """
        Generate pulse animation value.

        Args:
            t: Time in milliseconds
            speed: Animation speed multiplier

        Returns:
            Brightness value 0-255
        """
        return int((math.sin(t / 1000.0 * speed) + 1) * 127.5)

    @staticmethod
    def rainbow_animation(t, speed=1.0):
        """
        Generate rainbow animation RGB values.

        Args:
            t: Time in milliseconds
            speed: Animation speed multiplier

        Returns:
            (r, g, b) tuple
        """
        hue = (t / 1000.0 * speed * 60) % 360
        from .color_utils import hsv_to_rgb
        return hsv_to_rgb(hue, 1.0, 1.0)

    @staticmethod
    def breathe_animation(t, speed=1.0):
        """
        Generate breathing animation value.

        Args:
            t: Time in milliseconds
            speed: Animation speed multiplier

        Returns:
            Brightness value 0-255
        """
        # Smooth sine wave
        phase = (t / 1000.0 * speed) * math.pi * 2
        value = (math.sin(phase) + 1) / 2
        # Apply easing for more natural breathing
        value = value ** 2
        return int(value * 255)
