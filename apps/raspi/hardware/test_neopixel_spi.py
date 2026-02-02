#!/usr/bin/env python3
"""
Test script for NeoPixel SPI LED strip.

Tests:
1. Basic library import
2. SPI bus initialization
3. Color cycling (red, green, blue, white)
4. Brightness adjustment
5. Individual pixel control
6. Rainbow chase animation

Run with: python -m raspi.hardware.test_neopixel_spi
Or directly: python apps/raspi/hardware/test_neopixel_spi.py
"""

import sys
import time

# Configuration
LED_COUNT = 32
BRIGHTNESS = 0.5


def test_imports():
    """Test that required libraries are installed."""
    print("=" * 50)
    print("Test 1: Checking library imports")
    print("=" * 50)

    errors = []

    try:
        import board
        print(f"  [OK] board module imported")
        print(f"       Available pins: {[p for p in dir(board) if not p.startswith('_')][:10]}...")
    except ImportError as e:
        errors.append(f"  [FAIL] board: {e}")
        print(f"  [FAIL] board: {e}")
        print("         Install with: pip install adafruit-blinka")

    try:
        import neopixel_spi
        print(f"  [OK] neopixel_spi module imported")
    except ImportError as e:
        errors.append(f"  [FAIL] neopixel_spi: {e}")
        print(f"  [FAIL] neopixel_spi: {e}")
        print("         Install with: pip install adafruit-circuitpython-neopixel-spi")

    if errors:
        print("\nMissing dependencies. Install with:")
        print("  pip install adafruit-blinka adafruit-circuitpython-neopixel-spi")
        return False

    print("\n  All imports successful!")
    return True


def test_spi_bus():
    """Test SPI bus initialization."""
    print("\n" + "=" * 50)
    print("Test 2: SPI Bus Initialization")
    print("=" * 50)

    try:
        import board
        spi = board.SPI()
        print(f"  [OK] SPI bus initialized")
        print(f"       SPI object: {spi}")
        return spi
    except Exception as e:
        print(f"  [FAIL] SPI init failed: {e}")
        print("\n  Troubleshooting:")
        print("    1. Enable SPI: sudo raspi-config -> Interface Options -> SPI -> Enable")
        print("    2. Reboot after enabling")
        print("    3. Check /dev/spidev* exists: ls -la /dev/spidev*")
        print("    4. Check user is in spi group: groups")
        return None


def test_neopixel_init(spi):
    """Test NeoPixel initialization."""
    print("\n" + "=" * 50)
    print("Test 3: NeoPixel Strip Initialization")
    print("=" * 50)

    try:
        import neopixel_spi as neopixel

        pixels = neopixel.NeoPixel_SPI(
            spi,
            LED_COUNT,
            brightness=BRIGHTNESS,
            auto_write=False,
            pixel_order=neopixel.GRB
        )
        print(f"  [OK] NeoPixel strip initialized")
        print(f"       LED count: {LED_COUNT}")
        print(f"       Brightness: {BRIGHTNESS}")
        print(f"       Pixel order: GRB")
        return pixels
    except Exception as e:
        print(f"  [FAIL] NeoPixel init failed: {e}")
        print("\n  Troubleshooting:")
        print("    1. Check wiring: DATA -> GPIO10 (SPI MOSI)")
        print("    2. Check power: 5V and GND connected")
        print("    3. For long strips, use external 5V power supply")
        return None


def test_basic_colors(pixels):
    """Test basic color output."""
    print("\n" + "=" * 50)
    print("Test 4: Basic Colors")
    print("=" * 50)

    colors = [
        ("Red", (255, 0, 0)),
        ("Green", (0, 255, 0)),
        ("Blue", (0, 0, 255)),
        ("White", (255, 255, 255)),
        ("Yellow", (255, 255, 0)),
        ("Cyan", (0, 255, 255)),
        ("Magenta", (255, 0, 255)),
    ]

    try:
        for name, color in colors:
            print(f"  Setting {name}... ", end="", flush=True)
            pixels.fill(color)
            pixels.show()
            print(f"RGB{color}")
            time.sleep(0.5)

        # Turn off
        pixels.fill((0, 0, 0))
        pixels.show()
        print("  [OK] Basic colors test passed")
        return True
    except Exception as e:
        print(f"\n  [FAIL] Color test failed: {e}")
        return False


def test_brightness(pixels):
    """Test brightness adjustment."""
    print("\n" + "=" * 50)
    print("Test 5: Brightness Control")
    print("=" * 50)

    try:
        pixels.fill((255, 255, 255))

        for brightness in [0.1, 0.3, 0.5, 0.7, 1.0, 0.5]:
            print(f"  Brightness: {brightness * 100:.0f}%")
            pixels.brightness = brightness
            pixels.show()
            time.sleep(0.4)

        pixels.fill((0, 0, 0))
        pixels.show()
        print("  [OK] Brightness test passed")
        return True
    except Exception as e:
        print(f"  [FAIL] Brightness test failed: {e}")
        return False


def test_individual_pixels(pixels):
    """Test individual pixel control."""
    print("\n" + "=" * 50)
    print("Test 6: Individual Pixel Control")
    print("=" * 50)

    try:
        # Clear all
        pixels.fill((0, 0, 0))
        pixels.show()

        # Chase a single red pixel
        print("  Running pixel chase...")
        for i in range(LED_COUNT):
            pixels.fill((0, 0, 0))
            pixels[i] = (255, 0, 0)
            pixels.show()
            time.sleep(0.03)

        # Reverse with blue
        for i in range(LED_COUNT - 1, -1, -1):
            pixels.fill((0, 0, 0))
            pixels[i] = (0, 0, 255)
            pixels.show()
            time.sleep(0.03)

        pixels.fill((0, 0, 0))
        pixels.show()
        print("  [OK] Individual pixel test passed")
        return True
    except Exception as e:
        print(f"  [FAIL] Individual pixel test failed: {e}")
        return False


def test_rainbow(pixels):
    """Test rainbow animation."""
    print("\n" + "=" * 50)
    print("Test 7: Rainbow Animation")
    print("=" * 50)

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

    try:
        print("  Running rainbow cycle (3 seconds)...")
        start = time.time()

        while time.time() - start < 3:
            offset = int((time.time() - start) * 50) % 256
            for i in range(LED_COUNT):
                pixel_index = (i * 256 // LED_COUNT + offset) % 256
                pixels[i] = wheel(pixel_index)
            pixels.show()
            time.sleep(0.02)

        pixels.fill((0, 0, 0))
        pixels.show()
        print("  [OK] Rainbow animation test passed")
        return True
    except Exception as e:
        print(f"  [FAIL] Rainbow test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("NeoPixel SPI Test Suite")
    print(f"LED Count: {LED_COUNT}")
    print(f"Brightness: {BRIGHTNESS}")
    print("=" * 50)

    # Test 1: Imports
    if not test_imports():
        print("\n[ABORT] Cannot continue without required libraries")
        sys.exit(1)

    # Test 2: SPI bus
    spi = test_spi_bus()
    if not spi:
        print("\n[ABORT] SPI bus not available")
        sys.exit(1)

    # Test 3: NeoPixel init
    pixels = test_neopixel_init(spi)
    if not pixels:
        print("\n[ABORT] NeoPixel initialization failed")
        sys.exit(1)

    # Test 4-7: LED tests
    results = []
    results.append(("Basic Colors", test_basic_colors(pixels)))
    results.append(("Brightness", test_brightness(pixels)))
    results.append(("Individual Pixels", test_individual_pixels(pixels)))
    results.append(("Rainbow Animation", test_rainbow(pixels)))

    # Summary
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)

    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n  Total: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n  All tests passed! NeoPixel SPI is working correctly.")
    else:
        print("\n  Some tests failed. Check wiring and SPI configuration.")

    # Cleanup
    pixels.fill((0, 0, 0))
    pixels.show()


if __name__ == "__main__":
    main()
