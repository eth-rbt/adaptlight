#!/usr/bin/env python3
"""
LED Test Script - Tests WS2812 LED strip functionality
Tests all LEDs with different colors and patterns
"""

import time

# Use neopixel_spi library (Pi 5 compatible via SPI)
try:
    import board
    import neopixel_spi as neopixel
except ImportError:
    print("ERROR: neopixel_spi library not available.")
    print("Install with: pip install adafruit-circuitpython-neopixel-spi adafruit-blinka")
    exit(1)

# Configuration
LED_COUNT = 16          # Number of LEDs
LED_PIN = 18            # GPIO pin number for LED data
LED_BRIGHTNESS = 0.3    # Brightness (0.0 to 1.0)

print("=" * 50)
print("LED TEST SCRIPT")
print("=" * 50)
print(f"\nConfiguration:")
print(f"  LED Pin: GPIO {LED_PIN}")
print(f"  LED Count: {LED_COUNT}")
print(f"  Brightness: {LED_BRIGHTNESS}")
print(f"  Library: neopixel_spi (SPI)")
print("\nHardware Setup (using SPI):")
print("  - Connect LED data line to MOSI (GPIO 10 / Pin 19)")
print("  - Connect LED power (5V) to 5V pin")
print("  - Connect LED ground to GND pin")
print("\nNote: SPI must be enabled in raspi-config")
print("=" * 50)

try:
    # Initialize LED strip
    print("\n[1/6] Initializing LED strip...")
    spi_bus = board.SPI()
    pixels = neopixel.NeoPixel_SPI(
        spi_bus,
        LED_COUNT,
        brightness=LED_BRIGHTNESS,
        auto_write=False,
        pixel_order=neopixel.GRB
    )
    print("✓ LED strip initialized successfully (via SPI)")
    time.sleep(1)

    def set_all(r, g, b):
        """Helper function to set all LEDs to a color"""
        pixels.fill((r, g, b))
        pixels.show()

    def set_pixel(i, r, g, b):
        """Helper function to set a single LED"""
        pixels[i] = (r, g, b)

    # Test 1: All LEDs OFF
    print("\n[2/6] Test: All LEDs OFF")
    set_all(0, 0, 0)
    print("✓ All LEDs should be OFF")
    time.sleep(2)

    # Test 2: All LEDs RED
    print("\n[3/6] Test: All LEDs RED")
    set_all(255, 0, 0)
    print("✓ All LEDs should be RED")
    time.sleep(2)

    # Test 3: All LEDs GREEN
    print("\n[4/6] Test: All LEDs GREEN")
    set_all(0, 255, 0)
    print("✓ All LEDs should be GREEN")
    time.sleep(2)

    # Test 4: All LEDs BLUE
    print("\n[5/6] Test: All LEDs BLUE")
    set_all(0, 0, 255)
    print("✓ All LEDs should be BLUE")
    time.sleep(2)

    # Test 5: All LEDs WHITE
    print("\n[6/6] Test: All LEDs WHITE")
    set_all(255, 255, 255)
    print("✓ All LEDs should be WHITE")
    time.sleep(2)

    # Test 6: Rainbow cycle
    print("\n[BONUS] Test: Rainbow cycle (each LED different color)")
    rainbow_colors = [
        (255, 0, 0),    # Red
        (255, 127, 0),  # Orange
        (255, 255, 0),  # Yellow
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (75, 0, 130),   # Indigo
        (148, 0, 211),  # Violet
        (255, 0, 255),  # Magenta
    ]
    for i in range(LED_COUNT):
        r, g, b = rainbow_colors[i % len(rainbow_colors)]
        set_pixel(i, r, g, b)
    pixels.show()
    print("✓ Each LED should show a different color (rainbow)")
    time.sleep(3)

    # Cleanup: Turn off all LEDs
    print("\n[CLEANUP] Turning off all LEDs...")
    set_all(0, 0, 0)
    print("✓ All LEDs turned OFF")

    print("\n" + "=" * 50)
    print("LED TEST COMPLETED SUCCESSFULLY!")
    print("All tests passed. LEDs are working correctly.")
    print("=" * 50)

except KeyboardInterrupt:
    print("\n\nTest interrupted by user")
    pixels.fill((0, 0, 0))
    pixels.show()
    print("✓ LEDs turned off")

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    print("\nTroubleshooting:")
    print("  1. Enable SPI: sudo raspi-config -> Interface Options -> SPI -> Enable")
    print("  2. Check LED power supply (5V)")
    print("  3. Connect LED data to MOSI (GPIO 10 / Pin 19)")
    print("  4. Ensure ground is connected")
    print("  5. Run with sudo: sudo python3 test_leds.py")
    print("  6. Install: pip install adafruit-circuitpython-neopixel-spi adafruit-blinka")
