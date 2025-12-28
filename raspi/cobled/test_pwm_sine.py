#!/usr/bin/env python3
"""
Sine-wave PWM test for COB RGB LEDs.

Tests each channel individually at 1Hz for 3 seconds each:
Red -> Green -> Blue
"""

import math
import time

try:
    from gpiozero import PWMLED
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: gpiozero not available. Running in simulation mode.")

# PWM Pin configuration (Hardware PWM pins)
RED_PIN = 12    # Hardware PWM0
GREEN_PIN = 13  # Hardware PWM1
BLUE_PIN = 19   # Software PWM (PWM1 used by GPIO 13)

# Test settings
MAX_DUTY = 0.5          # Max duty cycle (0.0-1.0)
FREQUENCY = 0.5         # Sine wave frequency in Hz
DURATION = 3.0          # Duration per channel in seconds
STEP_SLEEP = 0.01       # Update interval (100 Hz update rate)
PWM_FREQUENCY = 1000    # PWM carrier frequency in Hz


class SimulatedPWMLED:
    """Simulated PWM LED for testing without hardware."""

    def __init__(self, pin, frequency=100):
        self.pin = pin
        self.frequency = frequency
        self._value = 0.0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val

    def close(self):
        pass


def create_led(pin, frequency=1000):
    """Create a PWM LED, real or simulated."""
    if GPIO_AVAILABLE:
        led = PWMLED(pin, frequency=frequency)
        print(f"  GPIO {pin}: PWM @ {led.frequency} Hz")
        return led
    return SimulatedPWMLED(pin, frequency)


def run_sine_test(led, name, frequency, duration, max_duty, step_sleep):
    """Run a sine wave test on a single LED channel."""
    print(f"\n  Testing {name} at {frequency} Hz for {duration}s...")

    start = time.time()
    cycles = 0
    last_cycle = -1

    while True:
        elapsed = time.time() - start
        if elapsed >= duration:
            break

        # Calculate sine wave value (0 to 1)
        phase = (elapsed * frequency) % 1.0
        wave = (math.sin(2 * math.pi * phase) + 1) / 2

        led.value = wave * max_duty

        # Count cycles
        current_cycle = int(elapsed * frequency)
        if current_cycle > last_cycle:
            last_cycle = current_cycle
            cycles += 1

        time.sleep(step_sleep)

    led.value = 0
    print(f"  {name} complete: {cycles} cycles")


def main():
    print("=" * 60)
    print("COB PWM Sine Test - Individual Channel Test")
    print("=" * 60)
    print(f"Pins: R={RED_PIN}, G={GREEN_PIN}, B={BLUE_PIN}")
    print(f"PWM frequency: {PWM_FREQUENCY} Hz")
    print(f"Sine frequency: {FREQUENCY} Hz")
    print(f"Max duty: {MAX_DUTY * 100:.0f}%")
    print(f"Duration per channel: {DURATION}s")
    print()

    print("Initializing LEDs...")
    red = create_led(RED_PIN, PWM_FREQUENCY)
    green = create_led(GREEN_PIN, PWM_FREQUENCY)
    blue = create_led(BLUE_PIN, PWM_FREQUENCY)

    try:
        # Test each channel sequentially
        run_sine_test(red, "RED", FREQUENCY, DURATION, MAX_DUTY, STEP_SLEEP)
        run_sine_test(green, "GREEN", FREQUENCY, DURATION, MAX_DUTY, STEP_SLEEP)
        run_sine_test(blue, "BLUE", FREQUENCY, DURATION, MAX_DUTY, STEP_SLEEP)

        # Test all channels together (white)
        print(f"\n  Testing WHITE (all channels) at {FREQUENCY} Hz for {DURATION}s...")
        start = time.time()
        cycles = 0
        last_cycle = -1

        while True:
            elapsed = time.time() - start
            if elapsed >= DURATION:
                break

            phase = (elapsed * FREQUENCY) % 1.0
            wave = (math.sin(2 * math.pi * phase) + 1) / 2
            duty = wave * MAX_DUTY

            red.value = duty
            green.value = duty
            blue.value = duty

            current_cycle = int(elapsed * FREQUENCY)
            if current_cycle > last_cycle:
                last_cycle = current_cycle
                cycles += 1

            time.sleep(STEP_SLEEP)

        red.value = 0
        green.value = 0
        blue.value = 0
        print(f"  WHITE complete: {cycles} cycles")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        red.value = 0
        green.value = 0
        blue.value = 0
        red.close()
        green.close()
        blue.close()
        print("\nTest complete. LEDs off.")
        print("=" * 60)


if __name__ == "__main__":
    main()
