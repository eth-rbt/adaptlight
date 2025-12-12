#!/usr/bin/env python3
"""
Test script for COB RGB LED control via PWM.

Tests individual R, G, B channels and combined white light.
All LEDs run at 50% duty cycle.

PWM Pin assignments:
- GPIO 23: Red LED
- GPIO 27: Green LED
- GPIO 22: Blue LED
"""

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

# Duty cycle (0.0 to 1.0)
DUTY_CYCLE = 0.1  # 50%

# Duration for each test phase (seconds)
TEST_DURATION = 2.0


class SimulatedPWMLED:
    """Simulated PWM LED for testing without hardware."""

    def __init__(self, pin):
        self.pin = pin
        self._value = 0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        print(f"  GPIO {self.pin}: {val * 100:.0f}% duty cycle")

    def close(self):
        pass


def create_led(pin):
    """Create a PWM LED, real or simulated."""
    if GPIO_AVAILABLE:
        return PWMLED(pin)
    else:
        return SimulatedPWMLED(pin)


def test_rgb_leds():
    """Run the RGB LED test sequence."""
    print("=" * 50)
    print("COB RGB LED PWM Test")
    print("=" * 50)
    print(f"Duty cycle: {DUTY_CYCLE * 100:.0f}%")
    print(f"Test duration per phase: {TEST_DURATION}s")
    print()

    # Initialize LEDs
    print("Initializing PWM LEDs...")
    red_led = create_led(RED_PIN)
    green_led = create_led(GREEN_PIN)
    blue_led = create_led(BLUE_PIN)
    print()

    try:
        # Test 1: Red LED only
        print("Test 1: RED LED")
        print("-" * 30)
        red_led.value = DUTY_CYCLE
        green_led.value = 0
        blue_led.value = 0
        time.sleep(TEST_DURATION)
        print()

        # Test 2: Green LED only
        print("Test 2: GREEN LED")
        print("-" * 30)
        red_led.value = 0
        green_led.value = DUTY_CYCLE
        blue_led.value = 0
        time.sleep(TEST_DURATION)
        print()

        # Test 3: Blue LED only
        print("Test 3: BLUE LED")
        print("-" * 30)
        red_led.value = 0
        green_led.value = 0
        blue_led.value = DUTY_CYCLE
        time.sleep(TEST_DURATION)
        print()

        # Test 4: All LEDs (White)
        print("Test 4: WHITE (all LEDs)")
        print("-" * 30)
        red_led.value = DUTY_CYCLE
        green_led.value = DUTY_CYCLE
        blue_led.value = DUTY_CYCLE
        time.sleep(TEST_DURATION)
        print()

        # Turn off all LEDs
        print("Test complete - turning off all LEDs")
        print("-" * 30)
        red_led.value = 0
        green_led.value = 0
        blue_led.value = 0

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        # Cleanup
        red_led.close()
        green_led.close()
        blue_led.close()
        print("\nCleanup complete")

    print("=" * 50)


if __name__ == "__main__":
    test_rgb_leds()
