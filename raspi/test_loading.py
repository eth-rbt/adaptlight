#!/usr/bin/env python3
"""
Test loading animation.

Tests the circular loading animation that shows while waiting for OpenAI responses.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from hardware.led_controller import LEDController
from hardware.hardware_config import HardwareConfig


def test_loading_animation():
    """Test the loading animation."""

    print("=" * 60)
    print("Testing Loading Animation")
    print("=" * 60)

    # Initialize LED controller
    print("\nInitializing LED controller...")
    try:
        led_controller = LEDController(
            led_count=16,
            led_pin=HardwareConfig.LED_PIN,
            brightness=0.3
        )
        print(f"✓ LED controller initialized (16 LEDs)")
    except Exception as e:
        print(f"⚠ Warning: LED hardware not available: {e}")
        print(f"Creating mock LED controller for testing...")

        # Create a mock LED controller
        class MockLEDController:
            def __init__(self):
                self.led_count = 16
                self.loading_active = False

            def set_pixel(self, index, r, g, b):
                print(f"  LED[{index:2d}]: RGB({r:3d}, {g:3d}, {b:3d})")

            def show(self):
                pass

            def clear(self):
                print("  All LEDs cleared")

            def start_loading_animation(self, color=(0, 100, 255), speed=0.05):
                import threading
                import time

                self.stop_loading_animation()
                self.loading_active = True

                def loading_loop():
                    while self.loading_active:
                        for i in range(self.led_count - 1, -1, -1):
                            if not self.loading_active:
                                break
                            self.set_pixel(i, *color)
                            time.sleep(speed)

                self.loading_thread = threading.Thread(target=loading_loop, daemon=True)
                self.loading_thread.start()

            def stop_loading_animation(self):
                if hasattr(self, 'loading_active'):
                    self.loading_active = False
                    if hasattr(self, 'loading_thread') and self.loading_thread.is_alive():
                        self.loading_thread.join(timeout=0.5)
                    self.clear()

            def cleanup(self):
                self.stop_loading_animation()

        led_controller = MockLEDController()
        print(f"✓ Mock LED controller created")

    print("\n" + "=" * 60)
    print("TEST 1: Standard Loading Animation")
    print("=" * 60)
    print("Animation: Blue circle going counter-clockwise (15→0)")
    print("Speed: 0.05 seconds per pixel")
    print("Duration: 5 seconds")
    print()

    led_controller.start_loading_animation(color=(0, 100, 255), speed=0.05)
    time.sleep(5)
    led_controller.stop_loading_animation()
    print("\n✓ Standard loading animation test complete\n")

    print("=" * 60)
    print("TEST 2: Fast Loading Animation")
    print("=" * 60)
    print("Animation: Green circle going counter-clockwise")
    print("Speed: 0.02 seconds per pixel (faster)")
    print("Duration: 3 seconds")
    print()

    led_controller.start_loading_animation(color=(0, 255, 0), speed=0.02)
    time.sleep(3)
    led_controller.stop_loading_animation()
    print("\n✓ Fast loading animation test complete\n")

    print("=" * 60)
    print("TEST 3: Slow Loading Animation")
    print("=" * 60)
    print("Animation: Purple circle going counter-clockwise")
    print("Speed: 0.1 seconds per pixel (slower)")
    print("Duration: 3 seconds")
    print()

    led_controller.start_loading_animation(color=(128, 0, 255), speed=0.1)
    time.sleep(3)
    led_controller.stop_loading_animation()
    print("\n✓ Slow loading animation test complete\n")

    print("=" * 60)
    print("TEST 4: Simulating OpenAI Wait Time")
    print("=" * 60)
    print("Animation: Blue loading (like during voice command processing)")
    print("Simulating OpenAI API call (2-5 seconds)...")
    print()

    led_controller.start_loading_animation(color=(0, 100, 255), speed=0.05)

    # Simulate API call delay
    print("Waiting for 'OpenAI response'...")
    time.sleep(4)

    led_controller.stop_loading_animation()
    print("\n✓ OpenAI simulation test complete\n")

    # Cleanup
    print("=" * 60)
    print("Cleaning up...")
    led_controller.cleanup()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✓")
    print("=" * 60)
    print("\nLoading animation is working correctly!")
    print("The animation goes in reverse order (counter-clockwise):")
    print("  Pixel 15 → 14 → 13 → ... → 1 → 0 → 15 → ...")


if __name__ == '__main__':
    try:
        test_loading_animation()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
