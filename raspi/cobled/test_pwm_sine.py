#!/usr/bin/env python3
"""
Sine-wave PWM test for COB RGB LEDs.

Gradually sweeps each channel from 0 to max_duty (default 0.1)
using a sine wave. Great for validating power/heat with gentle ramps.
"""

import math
import time

try:
    from gpiozero import PWMLED
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: gpiozero not available. Running in simulation mode.")
    print("Install with: pip install gpiozero")


# PWM Pin configuration
RED_PIN = 23
GREEN_PIN = 27
BLUE_PIN = 22

# Max duty cycle (0.0-1.0) to protect COB LEDs
MAX_DUTY = 0.1

# Timing
PERIOD_SECONDS = 6.0      # One full sine cycle
STEP_SLEEP = 0.05         # Update interval
RUN_DURATION = 30.0       # Total run time (seconds)


class SimulatedPWMLED:
    """Simulated PWM LED for testing without hardware."""

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


def create_led(pin):
    """Create a PWM LED, real or simulated."""
    if GPIO_AVAILABLE:
        return PWMLED(pin)
    return SimulatedPWMLED(pin)


def main():
    print("=" * 60)
    print("COB PWM Sine Test")
    print("=" * 60)
    print(f"Pins (R/G/B): {RED_PIN}/{GREEN_PIN}/{BLUE_PIN}")
    print(f"Max duty: {MAX_DUTY * 100:.1f}%")
    print(f"Period: {PERIOD_SECONDS}s, step: {STEP_SLEEP}s, duration: {RUN_DURATION}s")
    print()

    red = create_led(RED_PIN)
    green = create_led(GREEN_PIN)
    blue = create_led(BLUE_PIN)

    start = time.time()
    try:
        while True:
            elapsed = time.time() - start
            if elapsed > RUN_DURATION:
                break

            phase = (elapsed % PERIOD_SECONDS) / PERIOD_SECONDS

            # Offset each channel for visual separation
            r_phase = phase
            g_phase = (phase + 1 / 3) % 1.0
            b_phase = (phase + 2 / 3) % 1.0

            def wave(p):
                return (math.sin(2 * math.pi * p) + 1) / 2  # 0..1

            red.value = wave(r_phase) * MAX_DUTY
            green.value = wave(g_phase) * MAX_DUTY
            blue.value = wave(b_phase) * MAX_DUTY

            time.sleep(STEP_SLEEP)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        red.value = 0
        green.value = 0
        blue.value = 0
        red.close()
        green.close()
        blue.close()
        print("Test complete. LEDs off.")
        print("=" * 60)


if __name__ == "__main__":
    main()
