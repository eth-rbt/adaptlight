#!/usr/bin/env python3
"""
Test script for voice-reactive light using VoiceReactiveLight class.

This script:
1. Uses the VoiceReactiveLight class with COB LEDs
2. Captures audio from microphone in real-time
3. Maps loudness to LED brightness using class settings
4. Updates LEDs continuously to react to voice volume

Press Ctrl+C to exit.
"""

import sys
import time

from cobled import CobLed
from voice.voice_reactive_light import VoiceReactiveLight


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("VOICE-REACTIVE LIGHT TEST (using VoiceReactiveLight class)")
    print("=" * 60)

    # Initialize COB LED controller with correct pins from config
    print("\nInitializing COB LEDs...")
    led = CobLed(
        red_pin=12,
        green_pin=13,
        blue_pin=19,
        max_duty_cycle=2.0,
        frequency=1000
    )

    # Initialize voice reactive light with green color
    print("Initializing VoiceReactiveLight...")
    vrl = VoiceReactiveLight(
        led_controller=led,
        color=(0, 255, 0),  # Green
        smoothing_alpha=0.2,
        debug=True  # Show FPS timing
    )

    print(f"\nAmplitude settings:")
    print(f"  min_amplitude: {vrl.min_amplitude}")
    print(f"  max_amplitude: {vrl.max_amplitude}")
    print(f"  smoothing_alpha: {vrl.smoothing_alpha}")

    print("\nSpeak into the microphone to see the light react!")
    print("Press Ctrl+C to exit\n")
    print("=" * 60 + "\n")

    try:
        # Start voice reactive mode (standalone = uses its own audio stream)
        vrl.start(standalone=True)

        # Keep running and print current values
        while True:
            time.sleep(0.5)
            print(f"RMS: {vrl.current_rms:6.0f} | Brightness: {vrl.current_brightness:3d}/255")

    except KeyboardInterrupt:
        print("\n\nStopping test...")

    finally:
        # Cleanup
        vrl.stop()
        led.cleanup()
        print("Test complete!")


if __name__ == "__main__":
    main()
