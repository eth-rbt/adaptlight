#!/usr/bin/env python3
"""
UART Setup and Diagnostic Script for Raspberry Pi.

This script checks and configures the UART for communication with Arduino.

Run this BEFORE testing the COB LED serial communication.

Usage:
    python setup_uart.py --check     # Check current UART status
    python setup_uart.py --test      # Run loopback test (short TX to RX first!)
    python setup_uart.py --send      # Send test data to Arduino
"""

import argparse
import os
import subprocess
import sys
import time


def run_cmd(cmd, shell=True):
    """Run a command and return output."""
    try:
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1


def check_uart_config():
    """Check UART configuration on the Pi."""
    print("=" * 60)
    print("UART Configuration Check")
    print("=" * 60)

    # Check if running on a Pi
    stdout, _, _ = run_cmd("cat /proc/cpuinfo | grep 'Model'")
    print(f"\nDevice: {stdout or 'Unknown'}")

    # Check /boot/config.txt for UART settings
    print("\n--- /boot/config.txt UART settings ---")
    config_paths = ["/boot/config.txt", "/boot/firmware/config.txt"]
    config_file = None
    for path in config_paths:
        if os.path.exists(path):
            config_file = path
            break

    if config_file:
        stdout, _, _ = run_cmd(f"grep -E '(uart|serial)' {config_file} || echo 'No UART settings found'")
        print(stdout)
    else:
        print("Config file not found")

    # Check /boot/cmdline.txt for console settings
    print("\n--- /boot/cmdline.txt (serial console) ---")
    cmdline_paths = ["/boot/cmdline.txt", "/boot/firmware/cmdline.txt"]
    for path in cmdline_paths:
        if os.path.exists(path):
            stdout, _, _ = run_cmd(f"cat {path}")
            if "console=serial" in stdout or "console=ttyAMA" in stdout or "console=ttyS" in stdout:
                print(f"WARNING: Serial console is ENABLED in {path}")
                print("This will interfere with UART communication!")
                print(stdout)
            else:
                print(f"OK: No serial console in {path}")
            break

    # Check serial port symlink
    print("\n--- Serial port symlinks ---")
    stdout, _, _ = run_cmd("ls -la /dev/serial* 2>/dev/null || echo 'No serial ports found'")
    print(stdout)

    # Check if serial ports exist
    print("\n--- Available serial devices ---")
    stdout, _, _ = run_cmd("ls -la /dev/ttyAMA* /dev/ttyS* /dev/ttyUSB* 2>/dev/null || echo 'None found'")
    print(stdout)

    # Check current serial port settings
    print("\n--- Current /dev/ttyAMA0 settings ---")
    stdout, stderr, rc = run_cmd("stty -F /dev/ttyAMA0 -a 2>&1")
    if rc == 0:
        # Parse out the important settings
        lines = stdout.split('\n')
        for line in lines:
            if 'speed' in line or 'baud' in line:
                print(line)
        # Check for problematic settings
        if 'icrnl' in stdout and '-icrnl' not in stdout:
            print("WARNING: icrnl is ON (converts CR to NL) - will corrupt binary data")
        if 'opost' in stdout and '-opost' not in stdout:
            print("WARNING: opost is ON (output processing) - will corrupt binary data")
        if 'echo' in stdout and '-echo' not in stdout.replace('-echoe', '').replace('-echok', ''):
            print("WARNING: echo may be ON")
    else:
        print(f"Error: {stderr}")

    # Check GPIO pin functions
    print("\n--- GPIO 14/15 pin configuration ---")
    stdout, _, _ = run_cmd("pinctrl get 14 2>/dev/null || raspi-gpio get 14 2>/dev/null || echo 'pinctrl not available'")
    print(f"GPIO 14: {stdout}")
    stdout, _, _ = run_cmd("pinctrl get 15 2>/dev/null || raspi-gpio get 15 2>/dev/null || echo 'pinctrl not available'")
    print(f"GPIO 15: {stdout}")

    # Check for services using serial port
    print("\n--- Services using serial port ---")
    stdout, _, _ = run_cmd("systemctl list-units --type=service | grep -i serial || echo 'No serial services found'")
    print(stdout)
    stdout, _, _ = run_cmd("lsof /dev/ttyAMA0 2>/dev/null || echo 'No processes using /dev/ttyAMA0'")
    print(stdout)

    print("\n" + "=" * 60)
    print("Recommended Steps if UART isn't working:")
    print("=" * 60)
    print("""
1. Disable serial console:
   sudo raspi-config
   -> Interface Options -> Serial Port
   -> "Would you like a login shell to be accessible over serial?" -> NO
   -> "Would you like the serial port hardware to be enabled?" -> YES
   -> Reboot

2. Or manually edit config files:
   sudo nano /boot/firmware/cmdline.txt (or /boot/cmdline.txt)
   Remove: console=serial0,115200 or console=ttyAMA0,115200

   sudo nano /boot/firmware/config.txt (or /boot/config.txt)
   Add: enable_uart=1
   Add: dtoverlay=disable-bt (optional, gives primary UART to GPIO)

3. Configure serial port for raw binary mode:
   sudo stty -F /dev/ttyAMA0 115200 cs8 -cstopb -parenb raw -echo -echoe -echok

4. Reboot the Pi after changes
""")


def configure_serial_raw():
    """Configure serial port for raw binary communication."""
    print("\nConfiguring /dev/ttyAMA0 for raw binary mode...")

    # Set raw mode with correct settings
    cmd = "stty -F /dev/ttyAMA0 115200 cs8 -cstopb -parenb raw -echo -echoe -echok -echoctl -echonl -icanon -iexten -isig -brkint -icrnl -inpck -istrip -ixon -ixoff -opost -onlcr"
    stdout, stderr, rc = run_cmd(cmd)

    if rc == 0:
        print("OK: Serial port configured for 115200 baud, raw binary mode")
    else:
        print(f"ERROR: {stderr}")
        return False

    # Verify settings
    stdout, _, _ = run_cmd("stty -F /dev/ttyAMA0 speed")
    print(f"Verified baud rate: {stdout}")

    return True


def test_loopback():
    """Test UART loopback (TX shorted to RX)."""
    print("\n" + "=" * 60)
    print("UART Loopback Test")
    print("=" * 60)
    print("\nMAKE SURE GPIO 14 (TX) IS SHORTED TO GPIO 15 (RX)!")
    print("Press Enter to continue or Ctrl+C to abort...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nAborted")
        return

    # Configure serial port
    if not configure_serial_raw():
        return

    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        return

    try:
        # Open serial port with explicit settings
        ser = serial.Serial(
            port='/dev/ttyAMA0',
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )

        # Flush buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)

        # Test data
        test_data = bytes([0xFF, 0x55, 0xAA, 0x00, 0x80, 0xFE])

        print(f"\nSending: {test_data.hex()}")
        ser.write(test_data)
        ser.flush()

        # Wait for data to loop back
        time.sleep(0.1)

        # Read response
        received = ser.read(len(test_data))
        print(f"Received: {received.hex() if received else '(nothing)'}")

        if received == test_data:
            print("\n✓ LOOPBACK TEST PASSED!")
            print("UART is working correctly. The issue is with the Arduino connection.")
        elif received:
            print("\n✗ LOOPBACK TEST FAILED - Data corrupted")
            print("Serial port may still have terminal processing enabled.")
            print("Try: sudo stty -F /dev/ttyAMA0 115200 raw -echo")
        else:
            print("\n✗ LOOPBACK TEST FAILED - No data received")
            print("Possible causes:")
            print("  1. TX not actually shorted to RX")
            print("  2. Serial console still grabbing the port")
            print("  3. Wrong UART (try /dev/ttyAMA0 or /dev/ttyS0)")

        ser.close()

    except Exception as e:
        print(f"ERROR: {e}")


def send_test_to_arduino():
    """Send test data to Arduino."""
    print("\n" + "=" * 60)
    print("Send Test Data to Arduino")
    print("=" * 60)
    print("\nMake sure Arduino is connected:")
    print("  Pi GPIO 14 (TX) -> Arduino RX")
    print("  Pi GND -> Arduino GND")
    print("\nPress Enter to continue...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nAborted")
        return

    # Configure serial port
    if not configure_serial_raw():
        return

    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed")
        return

    try:
        ser = serial.Serial(
            port='/dev/ttyAMA0',
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )

        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print("\nNote: Pro Micro resets when serial opens. Waiting 2s...")
        time.sleep(2.0)
        ser.reset_input_buffer()

        colors = [
            ("Red", 254, 0, 0),
            ("Green", 0, 254, 0),
            ("Blue", 0, 0, 254),
            ("White", 254, 254, 254),
            ("Off", 0, 0, 0),
        ]

        print("\nSending colors (watch the Arduino Serial Monitor at 115200):")
        for name, r, g, b in colors:
            data = bytes([0xFF, r, g, b])
            print(f"  {name}: {data.hex()} -> RGB({r}, {g}, {b})")
            ser.write(data)
            ser.flush()
            time.sleep(0.5)

        print("\nDone! Check if Arduino received the data.")
        print("If Arduino Serial Monitor shows nothing, check wiring.")

        ser.close()

    except Exception as e:
        print(f"ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(description="UART Setup and Diagnostic Tool")
    parser.add_argument("--check", action="store_true", help="Check UART configuration")
    parser.add_argument("--test", action="store_true", help="Run loopback test")
    parser.add_argument("--send", action="store_true", help="Send test data to Arduino")
    args = parser.parse_args()

    if not any([args.check, args.test, args.send]):
        # Default to check
        args.check = True

    if args.check:
        check_uart_config()

    if args.test:
        test_loopback()

    if args.send:
        send_test_to_arduino()


if __name__ == "__main__":
    main()
