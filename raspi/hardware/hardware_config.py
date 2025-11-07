"""
Hardware pin configuration for AdaptLight.

Centralizes all GPIO pin assignments and hardware settings.
"""

try:
    import board
    BOARD_AVAILABLE = True
except ImportError:
    BOARD_AVAILABLE = False


class HardwareConfig:
    """Hardware pin and settings configuration."""

    # GPIO Pins
    BUTTON_PIN = 2  # GPIO 2 for button input
    LED_PIN = board.D18 if BOARD_AVAILABLE else 18  # GPIO 18 for LED data

    # LED Settings
    LED_COUNT = 16  # Number of LEDs in strip
    LED_BRIGHTNESS = 0.3  # Default brightness (0.0 to 1.0)
    LED_DEFAULT_COLOR = (255, 255, 255)  # White

    # Button Settings
    BUTTON_BOUNCE_TIME = 0.05  # 50ms debounce
    BUTTON_DOUBLE_CLICK_THRESHOLD = 0.2  # 200ms
    BUTTON_HOLD_THRESHOLD = 0.5  # 500ms

    @classmethod
    def get_config_dict(cls):
        """Get configuration as a dictionary."""
        return {
            'button_pin': cls.BUTTON_PIN,
            'led_pin': cls.LED_PIN,
            'led_count': cls.LED_COUNT,
            'led_brightness': cls.LED_BRIGHTNESS,
            'led_default_color': cls.LED_DEFAULT_COLOR,
            'button_bounce_time': cls.BUTTON_BOUNCE_TIME,
            'button_double_click_threshold': cls.BUTTON_DOUBLE_CLICK_THRESHOLD,
            'button_hold_threshold': cls.BUTTON_HOLD_THRESHOLD
        }
