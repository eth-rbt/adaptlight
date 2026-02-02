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

    def __init__(self, led_count=16, led_pin=18, brightness=0.3, spi_bus_id=1):
        """
        Initialize LED controller.

        Args:
            led_count: Number of LEDs in the strip
            led_pin: GPIO pin number (ignored for SPI, kept for compatibility)
            brightness: Initial brightness (0.0 to 1.0)
            spi_bus_id: SPI bus to use (0 = SPI0/GPIO10, 1 = SPI1/GPIO20)
        """
        self.led_count = led_count
        self.brightness = brightness
        self.current_color = (0, 0, 0)
        self.pixels = None

        if USE_NEOPIXEL_SPI:
            # Use neopixel_spi library (Pi 5 compatible via SPI)
            import board
            import busio
            import neopixel_spi as neopixel

            # Select SPI bus (SPI0 = GPIO10, SPI1 = GPIO20)
            if spi_bus_id == 1:
                # Manually create SPI1 bus using GPIO 20 (MOSI) and GPIO 21 (SCLK)
                # SPI1 pins: MOSI=GPIO20, MISO=GPIO19, SCLK=GPIO21
                spi_bus = busio.SPI(clock=board.D21, MOSI=board.D20)
                spi_name = "SPI1 (GPIO20)"
            else:
                spi_bus = board.SPI()
                spi_name = "SPI0 (GPIO10)"

            self.pixels = neopixel.NeoPixel_SPI(
                spi_bus,
                led_count,
                brightness=brightness,
                auto_write=False,
                pixel_order=neopixel.GRB
            )
            print(f"NeoPixel_SPI initialized: {led_count} LEDs via {spi_name}")
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

    def off(self):
        """Turn off all LEDs (alias for clear)."""
        self.clear()

    def get_current_color(self):
        """Get the current LED color."""
        return self.current_color

    def set_pixel(self, index: int, r: int, g: int, b: int):
        """
        Set a specific pixel to an RGB color.

        Args:
            index: Pixel index (0 to led_count-1)
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
        """
        if index < 0 or index >= self.led_count:
            return

        # Clamp values to 0-255
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        if self.pixels:
            if USE_NEOPIXEL_SPI:
                self.pixels[index] = (r, g, b)
        else:
            # Simulation mode - show which pixel changed
            print(f"LED[{index}]: RGB({r}, {g}, {b})")

    def show(self):
        """Update the LED display with current pixel values."""
        if self.pixels:
            if USE_NEOPIXEL_SPI:
                self.pixels.show()

    def start_loading_animation(self, color=(255, 255, 255), speed=0.03, tail_length=8):
        """
        Start a circular chase loading animation.

        Args:
            color: Base RGB tuple (default white)
            speed: Time in seconds between updates
            tail_length: Number of LEDs in the fading tail
        """
        import threading
        import time

        # Stop any existing animation
        self.stop_loading_animation()

        self.loading_active = True

        def loading_loop():
            """Circular chase animation."""
            position = 0
            while self.loading_active:
                # Clear all pixels
                if self.pixels:
                    self.pixels.fill((0, 0, 0))

                # Draw the tail with fading brightness
                for i in range(tail_length):
                    # Calculate pixel index (wrapping around)
                    pixel_idx = (position - i) % self.led_count

                    # Brightness fades from 1.0 to 0.1 along the tail
                    brightness = 1.0 - (i / tail_length) * 0.9

                    r = int(color[0] * brightness)
                    g = int(color[1] * brightness)
                    b = int(color[2] * brightness)

                    self.set_pixel(pixel_idx, r, g, b)

                self.show()

                # Move to next position
                position = (position + 1) % self.led_count

                time.sleep(speed)

        # Start the loading thread
        self.loading_thread = threading.Thread(target=loading_loop, daemon=True)
        self.loading_thread.start()

    def stop_loading_animation(self):
        """Stop the loading animation."""
        if hasattr(self, 'loading_active'):
            self.loading_active = False
            if hasattr(self, 'loading_thread') and self.loading_thread.is_alive():
                self.loading_thread.join(timeout=0.5)
            # Clear all pixels after stopping
            self.clear()

    def start_recording_animation(self, base_color=(0, 255, 0), speed=0.02):
        """
        Start a recording animation with breathing/pulsing effect.
        Uses varying brightness of green to indicate voice recording.

        Args:
            base_color: RGB tuple for the recording color (default green)
            speed: Time in seconds between brightness updates
        """
        import threading
        import time
        import math

        # Stop any existing animation
        self.stop_recording_animation()

        self.recording_active = True

        def recording_loop():
            """Run the recording animation with breathing effect."""
            step = 0
            while self.recording_active:
                # Use sine wave for smooth breathing effect
                # Brightness oscillates between 0.2 and 1.0
                brightness_factor = 0.2 + 0.8 * (math.sin(step * 0.1) + 1) / 2

                # Calculate color with brightness factor
                r = int(base_color[0] * brightness_factor)
                g = int(base_color[1] * brightness_factor)
                b = int(base_color[2] * brightness_factor)

                # Set all pixels to the pulsing color
                if self.pixels:
                    for i in range(self.led_count):
                        self.set_pixel(i, r, g, b)
                    self.show()
                else:
                    # Simulation mode
                    print(f"Recording LED: RGB({r}, {g}, {b}) - brightness: {brightness_factor:.2f}")

                step += 1
                time.sleep(speed)

        # Start the recording thread
        self.recording_thread = threading.Thread(target=recording_loop, daemon=True)
        self.recording_thread.start()

    def stop_recording_animation(self):
        """Stop the recording animation."""
        if hasattr(self, 'recording_active'):
            self.recording_active = False
            if hasattr(self, 'recording_thread') and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=0.5)
            # Clear all pixels after stopping
            self.clear()

    def flash_success(self, flashes=3, duration=0.2):
        """
        Flash green to indicate successful operation (e.g., rules changed).

        Args:
            flashes: Number of times to flash
            duration: Duration of each flash in seconds
        """
        import time

        print(f"  ✅ Flashing green (success)")

        for _ in range(flashes):
            # Flash bright green
            self.set_color(0, 255, 0)
            time.sleep(duration)

            # Turn off
            self.set_color(0, 0, 0)
            time.sleep(duration)

    def flash_error(self, flashes=3, duration=0.3):
        """
        Flash red to indicate error or no changes made.

        Args:
            flashes: Number of times to flash
            duration: Duration of each flash in seconds
        """
        import time

        print(f"  ❌ Flashing red (error/no changes)")

        for _ in range(flashes):
            # Flash bright red
            self.set_color(255, 0, 0)
            time.sleep(duration)

            # Turn off
            self.set_color(0, 0, 0)
            time.sleep(duration)

    def cleanup(self):
        """Cleanup resources and turn off LEDs."""
        self.stop_loading_animation()
        self.stop_recording_animation()
        self.clear()
        print("LED controller cleanup complete")
