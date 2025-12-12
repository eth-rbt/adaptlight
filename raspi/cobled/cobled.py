#!/usr/bin/env python3
"""
PWM driver for COB RGB LEDs.

Maps 0-255 RGB values to capped PWM duty cycles with a max-duty clamp
to protect the LEDs and power supply. Provides the same interface the
rest of the app expects (set_color, animations, cleanup).
"""

import time
import threading

try:
    from gpiozero import PWMLED
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: gpiozero not available. Running COB LED in simulation mode.")


class SimulatedPWMLED:
    """Simulated PWM LED for development without hardware."""

    def __init__(self, pin):
        self.pin = pin
        self._value = 0.0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        print(f"  GPIO {self.pin}: {val * 100:.1f}% duty cycle")

    def close(self):
        pass


def _create_led(pin):
    """Create a PWM LED (real or simulated)."""
    if GPIO_AVAILABLE:
        return PWMLED(pin)
    return SimulatedPWMLED(pin)


class CobLed:
    """COB RGB LED controller backed by PWM."""

    def __init__(self, red_pin=23, green_pin=27, blue_pin=22, max_duty_cycle=1.0, brightness=1.0):
        """
        Args:
            red_pin, green_pin, blue_pin: GPIO pins for each channel.
            max_duty_cycle: Clamp for duty cycle (0.0-1.0).
            brightness: Global brightness multiplier (0.0-1.0).
        """
        self.red = _create_led(red_pin)
        self.green = _create_led(green_pin)
        self.blue = _create_led(blue_pin)

        self.max_duty = self._clamp_unit(max_duty_cycle)
        self.brightness = self._clamp_unit(brightness)
        self.current_color = (0, 0, 0)

        # Animation flags
        self.loading_active = False
        self.recording_active = False
        self.loading_thread = None
        self.recording_thread = None

    def _clamp_unit(self, value):
        return max(0.0, min(1.0, float(value)))

    def _rgb_to_duty(self, value):
        # Map 0-255 -> 0-max_duty with brightness scaling
        duty = (max(0, min(255, int(value))) / 255.0) * self.brightness
        return max(0.0, min(self.max_duty, duty))

    def set_color(self, r: int, g: int, b: int):
        """Set all channels to an RGB color (0-255 per channel)."""
        self.current_color = (max(0, min(255, int(r))),
                              max(0, min(255, int(g))),
                              max(0, min(255, int(b))))

        self.red.value = self._rgb_to_duty(self.current_color[0])
        self.green.value = self._rgb_to_duty(self.current_color[1])
        self.blue.value = self._rgb_to_duty(self.current_color[2])

    def get_current_color(self):
        """Return the last requested RGB tuple."""
        return self.current_color

    def set_brightness(self, brightness: float):
        """Adjust global brightness and reapply the current color."""
        self.brightness = self._clamp_unit(brightness)
        self.set_color(*self.current_color)

    def clear(self):
        """Turn off all channels."""
        self.set_color(0, 0, 0)

    def _stop_loading_animation(self):
        self.loading_active = False
        if self.loading_thread and self.loading_thread.is_alive():
            self.loading_thread.join(timeout=0.5)
        self.loading_thread = None

    def _stop_recording_animation(self):
        self.recording_active = False
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=0.5)
        self.recording_thread = None

    def start_loading_animation(self, color=(255, 255, 255), speed=0.05, period=5.0):
        """Soft breathing (sine) loading animation."""
        import math

        self.stop_loading_animation()
        self.loading_active = True

        def loading_loop():
            start = time.time()
            while self.loading_active:
                elapsed = time.time() - start
                phase = (elapsed % period) / period
                brightness_factor = 0.2 + 0.8 * (math.sin(2 * math.pi * phase) + 1) / 2
                r = int(color[0] * brightness_factor)
                g = int(color[1] * brightness_factor)
                b = int(color[2] * brightness_factor)
                self.set_color(r, g, b)
                time.sleep(speed)

        self.loading_thread = threading.Thread(target=loading_loop, daemon=True)
        self.loading_thread.start()

    def stop_loading_animation(self):
        """Stop loading animation."""
        self._stop_loading_animation()
        self.clear()

    def start_recording_animation(self, base_color=(0, 255, 0), speed=0.05):
        """Breathing animation for recording state."""
        import math

        self.stop_recording_animation()
        self.recording_active = True

        def recording_loop():
            step = 0
            while self.recording_active:
                brightness_factor = 0.2 + 0.8 * (math.sin(step * 0.1) + 1) / 2
                r = int(base_color[0] * brightness_factor)
                g = int(base_color[1] * brightness_factor)
                b = int(base_color[2] * brightness_factor)
                self.set_color(r, g, b)
                step += 1
                time.sleep(speed)

        self.recording_thread = threading.Thread(target=recording_loop, daemon=True)
        self.recording_thread.start()

    def stop_recording_animation(self):
        """Stop recording animation."""
        self._stop_recording_animation()
        self.clear()

    def flash_success(self, flashes=3, duration=0.2):
        """Flash green to indicate success."""
        for _ in range(flashes):
            self.set_color(0, 255, 0)
            time.sleep(duration)
            self.clear()
            time.sleep(duration)

    def flash_error(self, flashes=3, duration=0.3):
        """Flash red to indicate error."""
        for _ in range(flashes):
            self.set_color(255, 0, 0)
            time.sleep(duration)
            self.clear()
            time.sleep(duration)

    def cleanup(self):
        """Cleanup resources and turn off LEDs."""
        self._stop_loading_animation()
        self._stop_recording_animation()
        self.clear()
        self.red.close()
        self.green.close()
        self.blue.close()
        print("COB LED controller cleanup complete")
