#!/usr/bin/env python3
"""
Test script for voice reactive lights.

Tests the random bubble pattern with microphone input.

Run with: python apps/raspi/hardware/test_voice_reactive.py
"""

import sys
import time
from pathlib import Path

# Add parent directories to path
ROOT_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Configuration
LED_COUNT = 32
BRIGHTNESS = 0.5
TEST_DURATION = 30  # seconds


def main():
    print("=" * 50)
    print("Voice Reactive Light Test")
    print("=" * 50)

    # Initialize LED controller
    print("\n1. Initializing NeoPixel LED strip...")
    try:
        from apps.raspi.hardware.led_controller import LEDController
        led = LEDController(led_count=LED_COUNT, brightness=BRIGHTNESS)
        print(f"   [OK] LEDController initialized ({LED_COUNT} LEDs)")
    except Exception as e:
        print(f"   [FAIL] LED init failed: {e}")
        sys.exit(1)

    # Initialize voice reactive
    print("\n2. Initializing voice reactive controller...")
    try:
        from apps.raspi.voice.reactive import VoiceReactiveLight
        reactive = VoiceReactiveLight(
            led,
            color=(255, 255, 255),  # White
            smoothing_alpha=0.25,
            debug=True
        )
        print(f"   [OK] VoiceReactiveLight initialized")
        print(f"        Color: white")
        print(f"        Smoothing: 0.25")
        if reactive.selected_device is not None:
            print(f"        Audio device: {reactive.selected_device}")
        else:
            print(f"        Audio device: default")
    except Exception as e:
        print(f"   [FAIL] Voice reactive init failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Start voice reactive
    print(f"\n3. Starting voice reactive (standalone mode)...")
    print(f"   Speak into the microphone!")
    print(f"   Test will run for {TEST_DURATION} seconds...")
    print("=" * 50)

    try:
        reactive.start(standalone=True)

        start_time = time.time()
        while time.time() - start_time < TEST_DURATION:
            remaining = TEST_DURATION - (time.time() - start_time)
            print(f"\r   Time remaining: {remaining:.0f}s  ", end="", flush=True)
            time.sleep(0.5)

        print("\n")

    except KeyboardInterrupt:
        print("\n\n   Interrupted by user")

    finally:
        print("4. Stopping...")
        reactive.stop()
        led.off()
        print("   Done!")


if __name__ == "__main__":
    main()
