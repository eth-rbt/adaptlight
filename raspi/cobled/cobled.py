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


def _create_led(pin, frequency=1000):
    """
    Create a PWM LED (real or simulated).

    gpiozero.PWMLED automatically uses hardware PWM on supported pins:
    - Hardware PWM pins: GPIO 12, 13, 18, 19
    - Note: GPIO 12 and 18 share PWM0, GPIO 13 and 19 share PWM1
      Only one pin per channel can use hardware PWM at a time

    Args:
        pin: GPIO pin number (BCM numbering)
        frequency: PWM frequency in Hz (default 1000 Hz, gpiozero default is 100 Hz)
    """
    if GPIO_AVAILABLE:
        hardware_pwm_pins = [12, 13, 18, 19]

        # gpiozero automatically uses hardware PWM on supported pins
        # No special configuration needed - it detects hardware PWM capability
        led = PWMLED(pin, frequency=frequency)

        if pin in hardware_pwm_pins:
            print(f"  GPIO {pin}: Hardware PWM @ {led.frequency} Hz")
        else:
            print(f"  GPIO {pin}: Software PWM @ {led.frequency} Hz")

        return led
    return SimulatedPWMLED(pin)


class CobLed:
    """COB RGB LED controller backed by PWM."""

    def __init__(self, red_pin=23, green_pin=27, blue_pin=22, max_duty_cycle=1.0, brightness=1.0, frequency=1000):
        """
        Args:
            red_pin, green_pin, blue_pin: GPIO pins for each channel.
                                         Recommended: 12, 13, 18, 19 for hardware PWM
            max_duty_cycle: Max TOTAL duty cycle across all channels (0.0-3.0).
                           RGB values are scaled proportionally to stay within this limit.
                           E.g., 1.5 means full white (255,255,255) results in 0.5 duty per channel.
            brightness: Global brightness multiplier (0.0-1.0).
            frequency: PWM frequency in Hz (default 1000 Hz, gpiozero default is 100 Hz).
                      Higher = smoother, but software PWM may struggle above ~1000 Hz.
        """
        print(f"Initializing COB LEDs on GPIO pins: R={red_pin}, G={green_pin}, B={blue_pin}")
        print(f"PWM frequency: {frequency} Hz")

        # Check for PWM channel conflicts
        hardware_pwm_pins = {12: 'PWM0', 18: 'PWM0', 13: 'PWM1', 19: 'PWM1'}
        pins_used = [red_pin, green_pin, blue_pin]
        channels_used = {}
        for pin in pins_used:
            if pin in hardware_pwm_pins:
                channel = hardware_pwm_pins[pin]
                if channel in channels_used:
                    print(f"  WARNING: GPIO {pin} and GPIO {channels_used[channel]} both use {channel}")
                    print(f"  Only one can use hardware PWM at a time!")
                else:
                    channels_used[channel] = pin

        self.red = _create_led(red_pin, frequency)
        self.green = _create_led(green_pin, frequency)
        self.blue = _create_led(blue_pin, frequency)

        self.max_total_duty = max(0.0, min(3.0, float(max_duty_cycle)))
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
        # Map 0-255 -> 0-1 with brightness scaling (no clamping here, scaling done in set_color)
        return (max(0, min(255, int(value))) / 255.0) * self.brightness

    def set_color(self, r: int, g: int, b: int):
        """Set all channels to an RGB color (0-255 per channel)."""
        self.current_color = (max(0, min(255, int(r))),
                              max(0, min(255, int(g))),
                              max(0, min(255, int(b))))

        # Calculate raw duty cycles (0-1 each, total can be 0-3)
        r_duty = self._rgb_to_duty(self.current_color[0])
        g_duty = self._rgb_to_duty(self.current_color[1])
        b_duty = self._rgb_to_duty(self.current_color[2])

        # Scale proportionally if total exceeds max_total_duty
        total = r_duty + g_duty + b_duty
        if total > self.max_total_duty and total > 0:
            scale = self.max_total_duty / total
            r_duty *= scale
            g_duty *= scale
            b_duty *= scale

        # Update all channels as quickly as possible to minimize timing differences
        # This helps reduce flicker when all channels are active (white light)
        self.red.value = r_duty
        self.green.value = g_duty
        self.blue.value = b_duty

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

    def start_loading_animation(self, color=(255, 255, 255), speed=0.01, period=5.0, debug=False):
        """Soft breathing (sine) loading animation."""
        import math

        self.stop_loading_animation()
        self.loading_active = True

        def loading_loop():
            start = time.time()
            last_update = start
            update_count = 0
            while self.loading_active:
                loop_start = time.time()
                elapsed = loop_start - start
                phase = (elapsed % period) / period
                brightness_factor = 0.2 + 0.8 * (math.sin(2 * math.pi * phase) + 1) / 2
                r = int(color[0] * brightness_factor)
                g = int(color[1] * brightness_factor)
                b = int(color[2] * brightness_factor)
                self.set_color(r, g, b)

                update_count += 1
                if debug and update_count % 50 == 0:
                    avg_interval = (loop_start - start) / update_count
                    print(f"[LOADING] Updates: {update_count}, Avg interval: {avg_interval*1000:.1f}ms, Target: {speed*1000:.1f}ms")

                time.sleep(speed)

        self.loading_thread = threading.Thread(target=loading_loop, daemon=True)
        self.loading_thread.start()

    def stop_loading_animation(self):
        """Stop loading animation."""
        self._stop_loading_animation()
        self.clear()

    def start_recording_animation(self, base_color=(0, 255, 0), speed=0.01, debug=False):
        """Breathing animation for recording state."""
        import math

        self.stop_recording_animation()
        self.recording_active = True

        def recording_loop():
            step = 0
            start = time.time()
            while self.recording_active:
                brightness_factor = 0.2 + 0.8 * (math.sin(step * 0.1) + 1) / 2
                r = int(base_color[0] * brightness_factor)
                g = int(base_color[1] * brightness_factor)
                b = int(base_color[2] * brightness_factor)
                self.set_color(r, g, b)
                step += 1

                if debug and step % 50 == 0:
                    elapsed = time.time() - start
                    avg_interval = elapsed / step
                    print(f"[RECORDING] Steps: {step}, Avg interval: {avg_interval*1000:.1f}ms, Target: {speed*1000:.1f}ms")

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
