#!/usr/bin/env python3
"""
Button Test Script - Tests GPIO button functionality
Monitors button presses and displays status
"""

import time
from gpiozero import Button
from signal import pause

# Configuration
BUTTON_PIN = 2  # GPIO pin for button (GPIO 2)

print("=" * 50)
print("BUTTON TEST SCRIPT")
print("=" * 50)
print(f"\nConfiguration:")
print(f"  Button Pin: GPIO {BUTTON_PIN}")
print(f"  Pull-up: Enabled (button connects to GND)")
print("\nHardware Setup:")
print("  - Connect one side of button to GPIO 2")
print("  - Connect other side of button to GND")
print("  - Internal pull-up resistor is enabled")
print("  - Button press connects GPIO 2 to GND")
print("=" * 50)

# Button press counter
press_count = 0
last_press_time = None

def button_pressed():
    """Called when button is pressed"""
    global press_count, last_press_time
    press_count += 1
    current_time = time.time()

    # Calculate time since last press
    time_diff = ""
    if last_press_time is not None:
        diff = current_time - last_press_time
        time_diff = f" ({diff:.2f}s since last press)"

    last_press_time = current_time

    print(f"✓ Button PRESSED! (Count: {press_count}){time_diff}")

def button_released():
    """Called when button is released"""
    print(f"  Button RELEASED")

try:
    # Initialize button (pull_up=True means pressed = LOW)
    print("\n[1/2] Initializing button on GPIO 2...")
    button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
    print("✓ Button initialized successfully")
    print(f"  Bounce time: 50ms (debouncing enabled)")
    time.sleep(1)

    # Attach event handlers
    print("\n[2/2] Attaching button event handlers...")
    button.when_pressed = button_pressed
    button.when_released = button_released
    print("✓ Event handlers attached")

    print("\n" + "=" * 50)
    print("BUTTON TEST RUNNING")
    print("=" * 50)
    print("\nPress the button to test functionality")
    print("Each press will be counted and timed")
    print("\nExpected behavior:")
    print("  - Press button → '✓ Button PRESSED!' message")
    print("  - Release button → 'Button RELEASED' message")
    print("  - Counter increments with each press")
    print("\nPress Ctrl+C to exit and see results")
    print("=" * 50)

    # Wait for button presses
    pause()

except KeyboardInterrupt:
    print("\n\n" + "=" * 50)
    print("BUTTON TEST RESULTS")
    print("=" * 50)
    print(f"\nTotal button presses: {press_count}")

    if press_count == 0:
        print("\n⚠ WARNING: No button presses detected!")
        print("\nTroubleshooting:")
        print("  1. Check button wiring:")
        print("     - One side to GPIO 2")
        print("     - Other side to GND")
        print("  2. Test button continuity with multimeter")
        print("  3. Try a different button")
        print("  4. Verify GPIO 2 is not being used by another process")
    elif press_count < 3:
        print("\n✓ Button is working, but only a few presses detected")
        print("  Try pressing the button several more times to verify consistent operation")
    else:
        print("\n✓ Button is working correctly!")
        print("  Multiple presses detected successfully")

    print("=" * 50)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    print("\nTroubleshooting:")
    print("  1. Run with sudo: sudo python3 test_button.py")
    print("  2. Check if gpiozero library is installed")
    print("  3. Verify GPIO 2 is available (not used by I2C/other)")
    print("  4. Check button wiring")
    print("  5. Try: sudo apt-get install python3-gpiozero")
