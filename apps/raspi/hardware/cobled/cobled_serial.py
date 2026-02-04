#!/usr/bin/env python3
"""
Serial-based COB LED controller.

Sends RGB values over UART to an Arduino microcontroller,
which then outputs PWM signals to drive COB LEDs.

Protocol:
  [0xFF, R, G, B] - 4 bytes per update
  0xFF is sync marker, R/G/B are 0-254 (255 reserved for sync)

Wiring:
  Pi GPIO 14 (TX) -> Arduino RX (pin 0 on Micro)
  Pi GND -> Arduino GND
"""

import time
import threading

# Try to import serial
SERIAL_AVAILABLE = False
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    print("Warning: pyserial not available. Install with: pip install pyserial")


class CobLedSerial:
    """COB RGB LED controller via serial to Arduino."""

    SYNC_BYTE = 0xFF
    MAX_VALUE = 254  # Reserve 255 for sync byte

    def __init__(self, port='/dev/ttyAMA0', baudrate=115200, brightness=1.0):
        """
        Initialize serial COB LED controller.

        Args:
            port: Serial port (default: /dev/serial0 for Pi hardware UART)
            baudrate: Baud rate (default: 115200)
            brightness: Global brightness multiplier (0.0-1.0)
        """
        self.port = port
        self.baudrate = baudrate
        self.brightness = max(0.0, min(1.0, brightness))
        self.current_color = (0, 0, 0)
        self.serial = None

        # Animation flags
        self.loading_active = False
        self.recording_active = False
        self.loading_thread = None
        self.recording_thread = None

        if SERIAL_AVAILABLE:
            try:
                self.serial = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.1,
                    # Disable flow control for raw binary communication
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False
                )

                # Flush any stale data in buffers
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()

                # Give Arduino time to reset after serial connection opens
                # (Pro Micro resets when DTR toggles on serial open)
                time.sleep(2.0)

                # Flush again after Arduino boot
                self.serial.reset_input_buffer()

                # Send warm-up commands to prime the connection
                # This ensures Arduino is ready before user interaction
                for _ in range(3):
                    self._send_rgb(0, 0, 0)
                    time.sleep(0.05)

                print(f"CobLedSerial initialized: {port} @ {baudrate} baud")
            except Exception as e:
                print(f"Failed to open serial port {port}: {e}")
                self.serial = None
        else:
            print("CobLedSerial running in simulation mode (pyserial not available)")

    def _send_rgb(self, r: int, g: int, b: int):
        """
        Send RGB values over serial.

        Args:
            r, g, b: RGB values (0-254)
        """
        # Clamp values to valid range (0-254, reserve 255 for sync)
        r = max(0, min(self.MAX_VALUE, int(r)))
        g = max(0, min(self.MAX_VALUE, int(g)))
        b = max(0, min(self.MAX_VALUE, int(b)))

        if self.serial and self.serial.is_open:
            try:
                data = bytes([self.SYNC_BYTE, r, g, b])
                self.serial.write(data)
                self.serial.flush()  # Ensure data is sent immediately
            except Exception as e:
                print(f"Serial write error: {e}")
        else:
            # Simulation mode
            print(f"CobLedSerial: RGB({r}, {g}, {b})")

    def set_color(self, r: int, g: int, b: int):
        """
        Set COB LED color.

        Args:
            r, g, b: RGB values (0-255)
        """
        # Store original color
        self.current_color = (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b)))
        )

        # Apply brightness and scale to 0-254
        r_out = int(self.current_color[0] * self.brightness * self.MAX_VALUE / 255)
        g_out = int(self.current_color[1] * self.brightness * self.MAX_VALUE / 255)
        b_out = int(self.current_color[2] * self.brightness * self.MAX_VALUE / 255)

        self._send_rgb(r_out, g_out, b_out)

    def get_current_color(self):
        """Return the last requested RGB tuple."""
        return self.current_color

    def set_brightness(self, brightness: float):
        """Adjust global brightness and reapply current color."""
        self.brightness = max(0.0, min(1.0, brightness))
        self.set_color(*self.current_color)

    def clear(self):
        """Turn off all LEDs."""
        self.set_color(0, 0, 0)

    def off(self):
        """Turn off all LEDs (alias for clear)."""
        self.clear()

    def _stop_loading_animation(self):
        self.loading_active = False
        if self.loading_thread and self.loading_thread.is_alive():
            self.loading_thread.join(timeout=0.5)
        self.loading_thread = None

    def _stop_recording_animation(self):
        self.recording_active = False
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=0.5)
        self.recording_thread = None

    def start_loading_animation(self, color=(255, 255, 255), speed=0.01, period=2.0):
        """Soft breathing (sine) loading animation."""
        import math

        self.stop_loading_animation()
        self.loading_active = True

        def loading_loop():
            start = time.time()
            while self.loading_active:
                elapsed = time.time() - start
                phase = (elapsed % period) / period
                brightness_factor = 0.4 + 0.6 * (math.sin(2 * math.pi * phase) + 1) / 2
                r = int(color[0] * brightness_factor)
                g = int(color[1] * brightness_factor)
                b = int(color[2] * brightness_factor)
                self.set_color(r, g, b)
                time.sleep(speed)

        self.loading_thread = threading.Thread(target=loading_loop, daemon=True)
        self.loading_thread.start()

    def stop_loading_animation(self):
        """Stop loading animation."""
        self._stop_loading_animation()
        self.clear()

    def start_recording_animation(self, base_color=(0, 255, 0), speed=0.01):
        """Breathing animation for recording state."""
        import math

        self.stop_recording_animation()
        self.recording_active = True

        def recording_loop():
            step = 0
            while self.recording_active:
                brightness_factor = 0.2 + 0.8 * (math.sin(step * 0.1) + 1) / 2
                r = int(base_color[0] * brightness_factor)
                g = int(base_color[1] * brightness_factor)
                b = int(base_color[2] * brightness_factor)
                self.set_color(r, g, b)
                step += 1
                time.sleep(speed)

        self.recording_thread = threading.Thread(target=recording_loop, daemon=True)
        self.recording_thread.start()

    def stop_recording_animation(self):
        """Stop recording animation."""
        self._stop_recording_animation()
        self.clear()

    def flash_success(self, flashes=3, duration=0.2):
        """Flash green to indicate success."""
        for _ in range(flashes):
            self.set_color(0, 255, 0)
            time.sleep(duration)
            self.clear()
            time.sleep(duration)

    def flash_error(self, flashes=3, duration=0.3):
        """Flash red to indicate error."""
        for _ in range(flashes):
            self.set_color(255, 0, 0)
            time.sleep(duration)
            self.clear()
            time.sleep(duration)

    def cleanup(self):
        """Cleanup resources."""
        self._stop_loading_animation()
        self._stop_recording_animation()
        self.clear()
        if self.serial and self.serial.is_open:
            self.serial.close()
        print("CobLedSerial cleanup complete")

    def __del__(self):
        """Destructor - ensure serial port is closed."""
        if hasattr(self, 'serial') and self.serial and self.serial.is_open:
            self.serial.close()
