#!/usr/bin/env python3
"""
Test script for Serial-based COB LED controller.

Tests communication with Arduino over UART for PWM LED control.

Usage:
    python -m raspi.hardware.cobled.test_serial_cobled
    python raspi/hardware/cobled/test_serial_cobled.py

Wiring:
    Pi GPIO 14 (TX) -> Arduino RX (pin 0 on Micro)
    Pi GND -> Arduino GND
    Arduino PWM pins -> COB LED MOSFETs
"""

import sys
import time
from pathlib import Path

# Add parent directories to path
ROOT_DIR = Path(__file__).parent.parent.parent.parent
if (ROOT_DIR / 'apps').exists():
    ROOT_DIR = ROOT_DIR.parent
sys.path.insert(0, str(ROOT_DIR))


def get_cobled_serial():
    """Import CobLedSerial from the right location."""
    try:
        from raspi.hardware.cobled.cobled_serial import CobLedSerial
    except ImportError:
        from apps.raspi.hardware.cobled.cobled_serial import CobLedSerial
    return CobLedSerial


def test_basic_colors():
    """Test basic color output."""
    print("\n" + "=" * 50)
    print("Test 1: Basic Colors")
    print("=" * 50)

    CobLedSerial = get_cobled_serial()
    led = CobLedSerial()

    colors = [
        ("Red", 255, 0, 0),
        ("Green", 0, 255, 0),
        ("Blue", 0, 0, 255),
        ("White", 255, 255, 255),
        ("Yellow", 255, 255, 0),
        ("Cyan", 0, 255, 255),
        ("Magenta", 255, 0, 255),
        ("Orange", 255, 128, 0),
        ("Off", 0, 0, 0),
    ]

    for name, r, g, b in colors:
        print(f"  {name}: RGB({r}, {g}, {b})")
        led.set_color(r, g, b)
        time.sleep(0.5)

    led.cleanup()
    print("  [OK] Basic colors test complete")


def test_brightness():
    """Test brightness control."""
    print("\n" + "=" * 50)
    print("Test 2: Brightness Control")
    print("=" * 50)

    CobLedSerial = get_cobled_serial()
    led = CobLedSerial()

    led.set_color(255, 255, 255)

    for brightness in [0.1, 0.25, 0.5, 0.75, 1.0]:
        print(f"  Brightness: {brightness * 100:.0f}%")
        led.set_brightness(brightness)
        time.sleep(0.5)

    led.cleanup()
    print("  [OK] Brightness test complete")


def test_smooth_fade():
    """Test smooth color fading."""
    print("\n" + "=" * 50)
    print("Test 3: Smooth Fade")
    print("=" * 50)

    CobLedSerial = get_cobled_serial()
    led = CobLedSerial()

    print("  Fading red...")
    for i in range(0, 255, 5):
        led.set_color(i, 0, 0)
        time.sleep(0.02)
    for i in range(255, 0, -5):
        led.set_color(i, 0, 0)
        time.sleep(0.02)

    print("  Fading green...")
    for i in range(0, 255, 5):
        led.set_color(0, i, 0)
        time.sleep(0.02)
    for i in range(255, 0, -5):
        led.set_color(0, i, 0)
        time.sleep(0.02)

    print("  Fading blue...")
    for i in range(0, 255, 5):
        led.set_color(0, 0, i)
        time.sleep(0.02)
    for i in range(255, 0, -5):
        led.set_color(0, 0, i)
        time.sleep(0.02)

    led.cleanup()
    print("  [OK] Smooth fade test complete")


def test_rainbow():
    """Test rainbow color cycle."""
    print("\n" + "=" * 50)
    print("Test 4: Rainbow Cycle")
    print("=" * 50)

    CobLedSerial = get_cobled_serial()
    led = CobLedSerial()

    def wheel(pos):
        """Generate rainbow colors across 0-255 positions."""
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)

    print("  Running rainbow cycle (5 seconds)...")
    start = time.time()
    while time.time() - start < 5:
        pos = int((time.time() - start) * 50) % 256
        r, g, b = wheel(pos)
        led.set_color(r, g, b)
        time.sleep(0.02)

    led.cleanup()
    print("  [OK] Rainbow cycle complete")


def test_loading_animation():
    """Test loading animation."""
    print("\n" + "=" * 50)
    print("Test 5: Loading Animation")
    print("=" * 50)

    CobLedSerial = get_cobled_serial()
    led = CobLedSerial()

    print("  Running loading animation (5 seconds)...")
    led.start_loading_animation()
    time.sleep(5)
    led.stop_loading_animation()

    led.cleanup()
    print("  [OK] Loading animation complete")


def test_flash():
    """Test flash patterns."""
    print("\n" + "=" * 50)
    print("Test 6: Flash Patterns")
    print("=" * 50)

    CobLedSerial = get_cobled_serial()
    led = CobLedSerial()

    print("  Flashing success (green)...")
    led.flash_success()

    time.sleep(0.5)

    print("  Flashing error (red)...")
    led.flash_error()

    led.cleanup()
    print("  [OK] Flash patterns complete")


def test_speed():
    """Test update speed."""
    print("\n" + "=" * 50)
    print("Test 7: Update Speed")
    print("=" * 50)

    CobLedSerial = get_cobled_serial()
    led = CobLedSerial()

    updates = 1000
    print(f"  Sending {updates} updates...")

    start = time.time()
    for i in range(updates):
        led.set_color(i % 256, (i * 2) % 256, (i * 3) % 256)
    elapsed = time.time() - start

    ups = updates / elapsed
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Updates per second: {ups:.0f}")
    print(f"  Average latency: {elapsed / updates * 1000:.2f}ms")

    led.cleanup()
    print("  [OK] Speed test complete")


def main():
    print("=" * 50)
    print("CobLedSerial Test Suite")
    print("=" * 50)
    print("\nMake sure Arduino is connected and running the receiver sketch.")
    print("Wiring: Pi GPIO 14 (TX) -> Arduino RX")
    print("")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", "-t", choices=[
        "colors", "brightness", "fade", "rainbow", "loading", "flash", "speed", "all"
    ], default="all", help="Which test to run")
    parser.add_argument("--port", "-p", default="/dev/ttyAMA0", help="Serial port")
    args = parser.parse_args()

    tests = {
        "colors": test_basic_colors,
        "brightness": test_brightness,
        "fade": test_smooth_fade,
        "rainbow": test_rainbow,
        "loading": test_loading_animation,
        "flash": test_flash,
        "speed": test_speed,
    }

    if args.test == "all":
        for name, test_func in tests.items():
            try:
                test_func()
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
    else:
        tests[args.test]()

    print("\n" + "=" * 50)
    print("Tests complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
