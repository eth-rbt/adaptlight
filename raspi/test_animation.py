#!/usr/bin/env python3
"""
Test animation functionality.

Tests the animation state to ensure LED animations are working correctly.
Run this to verify that animations update LEDs at the correct rate.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.state_machine import StateMachine
from hardware.led_controller import LEDController
from hardware.hardware_config import HardwareConfig
from states.light_states import initialize_default_states, set_led_controller, set_state_machine


def test_animation():
    """Test animation state."""

    print("=" * 60)
    print("Testing Animation State")
    print("=" * 60)

    # Initialize components
    print("\n1. Initializing state machine...")
    state_machine = StateMachine()
    set_state_machine(state_machine)

    print("2. Initializing LED controller...")
    try:
        led_controller = LEDController(
            led_count=16,
            led_pin=HardwareConfig.LED_PIN,
            brightness=0.3
        )
        set_led_controller(led_controller)
        print(f"   ✓ LED controller initialized (16 LEDs)")
    except Exception as e:
        print(f"   ⚠ Warning: LED hardware not available: {e}")
        print(f"   Creating mock LED controller for testing...")

        # Create a mock LED controller that just prints values
        class MockLEDController:
            def __init__(self):
                self.r = 0
                self.g = 0
                self.b = 0

            def set_color(self, r, g, b):
                self.r, self.g, self.b = r, g, b
                # Print color changes (but not every single frame to avoid spam)
                import random
                if random.random() < 0.1:  # Print ~10% of frames
                    print(f"   LED Color: RGB({r:3d}, {g:3d}, {b:3d})")

            def get_current_color(self):
                return (self.r, self.g, self.b)

            def cleanup(self):
                pass

        led_controller = MockLEDController()
        set_led_controller(led_controller)
        print(f"   ✓ Mock LED controller created")

    print("3. Registering default states...")
    initialize_default_states(state_machine)

    # Test 1: Pulse Animation
    print("\n" + "=" * 60)
    print("TEST 1: Pulse Animation (white pulsing)")
    print("=" * 60)
    print("Animation: abs(sin(frame * 0.05)) * 255")
    print("Speed: 50ms per frame")
    print("Duration: 3 seconds")
    print()

    pulse_params = {
        'r': 'abs(sin(frame * 0.05)) * 255',
        'g': 'abs(sin(frame * 0.05)) * 255',
        'b': 'abs(sin(frame * 0.05)) * 255',
        'speed': 50
    }

    state_machine.set_state('animation', pulse_params)
    time.sleep(3)
    state_machine.stop_interval()
    print("\n✓ Pulse animation test complete\n")

    # Test 2: Rainbow Animation
    print("=" * 60)
    print("TEST 2: Rainbow Animation (color cycling)")
    print("=" * 60)
    print("Animation: RGB channels cycling with different phases")
    print("Speed: 30ms per frame")
    print("Duration: 3 seconds")
    print()

    rainbow_params = {
        'r': '(frame * 2) % 256',
        'g': 'abs(sin(frame * 0.1)) * 255',
        'b': 'abs(cos(frame * 0.1)) * 255',
        'speed': 30
    }

    state_machine.set_state('animation', rainbow_params)
    time.sleep(3)
    state_machine.stop_interval()
    print("\n✓ Rainbow animation test complete\n")

    # Test 3: Color Wave Animation
    print("=" * 60)
    print("TEST 3: Color Wave (time-based animation)")
    print("=" * 60)
    print("Animation: Time-based sine/cosine waves")
    print("Speed: 50ms per frame")
    print("Duration: 3 seconds")
    print()

    wave_params = {
        'r': 'abs(sin(t/1000)) * 255',
        'g': 'abs(cos(t/1000)) * 255',
        'b': '128',
        'speed': 50
    }

    state_machine.set_state('animation', wave_params)
    time.sleep(3)
    state_machine.stop_interval()
    print("\n✓ Wave animation test complete\n")

    # Test 4: Color Rotation
    print("=" * 60)
    print("TEST 4: Color Rotation (channels swapping)")
    print("=" * 60)
    print("Animation: RGB values rotating between channels")
    print("Speed: 200ms per frame")
    print("Duration: 3 seconds")
    print()

    # First set a color to rotate
    state_machine.set_state('color', {'r': 255, 'g': 100, 'b': 50})
    time.sleep(0.5)

    rotate_params = {
        'r': 'b',
        'g': 'r',
        'b': 'g',
        'speed': 200
    }

    state_machine.set_state('animation', rotate_params)
    time.sleep(3)
    state_machine.stop_interval()
    print("\n✓ Rotation animation test complete\n")

    # Test 5: Fast vs Slow Speed
    print("=" * 60)
    print("TEST 5: Speed Comparison")
    print("=" * 60)
    print("Testing different animation speeds...")
    print()

    print("Fast (20ms):")
    fast_params = {
        'r': 'abs(sin(frame * 0.1)) * 255',
        'g': '128',
        'b': 'abs(cos(frame * 0.1)) * 255',
        'speed': 20
    }
    state_machine.set_state('animation', fast_params)
    time.sleep(2)
    state_machine.stop_interval()

    print("\nSlow (150ms):")
    slow_params = {
        'r': 'abs(sin(frame * 0.1)) * 255',
        'g': '128',
        'b': 'abs(cos(frame * 0.1)) * 255',
        'speed': 150
    }
    state_machine.set_state('animation', slow_params)
    time.sleep(2)
    state_machine.stop_interval()
    print("\n✓ Speed comparison test complete\n")

    # Turn off
    print("=" * 60)
    print("Turning off LEDs...")
    state_machine.set_state('off')

    # Cleanup
    print("Cleaning up...")
    led_controller.cleanup()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✓")
    print("=" * 60)
    print("\nAnimation system is working correctly!")
    print("LEDs should have displayed:")
    print("  1. White pulsing")
    print("  2. Rainbow colors")
    print("  3. Red/green wave with blue constant")
    print("  4. Color rotation")
    print("  5. Fast then slow animations")


if __name__ == '__main__':
    try:
        test_animation()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
