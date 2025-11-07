"""
LED controller for NeoPixel WS2812B strips.

This module replaces the DOM-based visual display from the JavaScript version
with actual NeoPixel LED control via GPIO.

Key functions:
- set_color(r, g, b): Set all LEDs to a specific RGB color
- set_brightness(brightness): Set overall brightness
- fill(color): Fill all LEDs with a color
- clear(): Turn off all LEDs
"""

# Try neopixel_spi library (Pi 5 compatible via SPI)
USE_NEOPIXEL_SPI = False

try:
    import board
    import neopixel_spi as neopixel
    USE_NEOPIXEL_SPI = True
except ImportError:
    print("Warning: neopixel_spi library not available. LED control will be simulated.")
    print("Install with: pip install adafruit-circuitpython-neopixel-spi adafruit-blinka")


class LEDController:
    """Controls NeoPixel LED strip for visual output."""

    def __init__(self, led_count=16, led_pin=18, brightness=0.3):
        """
        Initialize LED controller.

        Args:
            led_count: Number of LEDs in the strip
            led_pin: GPIO pin number (ignored for SPI, kept for compatibility)
            brightness: Initial brightness (0.0 to 1.0)
        """
        self.led_count = led_count
        self.brightness = brightness
        self.current_color = (0, 0, 0)
        self.pixels = None

        if USE_NEOPIXEL_SPI:
            # Use neopixel_spi library (Pi 5 compatible via SPI)
            # Note: Uses SPI, so pin parameter is ignored
            import board
            import neopixel_spi as neopixel
            spi_bus = board.SPI()
            self.pixels = neopixel.NeoPixel_SPI(
                spi_bus,
                led_count,
                brightness=brightness,
                auto_write=False,
                pixel_order=neopixel.GRB
            )
            print(f"NeoPixel_SPI initialized: {led_count} LEDs via SPI")
        else:
            print(f"LED simulation mode: {led_count} LEDs")

    def set_color(self, r: int, g: int, b: int):
        """
        Set all LEDs to a specific RGB color.

        Args:
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
        """
        # Clamp values to 0-255
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        self.current_color = (r, g, b)

        if self.pixels:
            if USE_NEOPIXEL_SPI:
                # neopixel_spi uses fill and show like standard neopixel
                self.pixels.fill((r, g, b))
                self.pixels.show()
        else:
            # Simulation mode
            print(f"LED Color: RGB({r}, {g}, {b})")

    def set_brightness(self, brightness: float):
        """
        Set overall brightness.

        Args:
            brightness: Brightness level (0.0 to 1.0)
        """
        brightness = max(0.0, min(1.0, brightness))
        self.brightness = brightness

        if self.pixels:
            if USE_NEOPIXEL_SPI:
                self.pixels.brightness = brightness
                self.pixels.show()
        else:
            print(f"LED Brightness: {brightness * 100}%")

    def fill(self, color: tuple):
        """
        Fill all LEDs with a color.

        Args:
            color: RGB tuple (r, g, b)
        """
        self.set_color(*color)

    def clear(self):
        """Turn off all LEDs."""
        self.set_color(0, 0, 0)

    def get_current_color(self):
        """Get the current LED color."""
        return self.current_color

    def cleanup(self):
        """Cleanup resources and turn off LEDs."""
        self.clear()
        print("LED controller cleanup complete")
