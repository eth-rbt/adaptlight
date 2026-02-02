#!/usr/bin/env python3
"""
White color tuning tool for COB RGB LEDs.

Allows manual adjustment of RGB duty cycles to find optimal white balance.
Use this to determine the correct proportions for your specific COB LEDs.
"""

import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from gpiozero import PWMLED
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: gpiozero not available. Running in simulation mode.")
    print("Install with: pip install gpiozero")


# PWM Pin configuration (matches config.yaml)
RED_PIN = 12    # Hardware PWM0
GREEN_PIN = 13  # Hardware PWM1
BLUE_PIN = 19   # Hardware PWM1 (will use software PWM if GPIO 13 is active)


class SimulatedPWMLED:
    """Simulated PWM LED for testing without hardware."""

    def __init__(self, pin):
        self.pin = pin
        self._value = 0.0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        print(f"  GPIO {self.pin}: {val * 100:.1f}% duty cycle")

    def close(self):
        pass


def create_led(pin):
    """Create a PWM LED (real or simulated)."""
    if GPIO_AVAILABLE:
        led = PWMLED(pin)
        if pin in [12, 13, 18, 19]:
            print(f"  GPIO {pin}: Hardware PWM enabled")
        return led
    return SimulatedPWMLED(pin)


class WhiteTuner:
    """Interactive white color tuning tool."""

    def __init__(self):
        print("=" * 60)
        print("COB LED White Color Tuner")
        print("=" * 60)
        print(f"Pins: R=GPIO{RED_PIN}, G=GPIO{GREEN_PIN}, B=GPIO{BLUE_PIN}")
        print()

        # Initialize LEDs
        self.red = create_led(RED_PIN)
        self.green = create_led(GREEN_PIN)
        self.blue = create_led(BLUE_PIN)

        # Current duty cycle values (0.0 to 1.0)
        self.r_duty = 0.0
        self.g_duty = 0.0
        self.b_duty = 0.0

        # Apply initial values (all off)
        self.update_leds()

    def update_leds(self):
        """Update all LEDs with current duty cycle values."""
        self.red.value = self.r_duty
        self.green.value = self.g_duty
        self.blue.value = self.b_duty

    def show_current(self):
        """Display current duty cycle values."""
        print(f"\nCurrent values:")
        print(f"  Red:   {self.r_duty:.3f} ({self.r_duty*100:.1f}%)")
        print(f"  Green: {self.g_duty:.3f} ({self.g_duty*100:.1f}%)")
        print(f"  Blue:  {self.b_duty:.3f} ({self.b_duty*100:.1f}%)")
        print(f"  Total: {self.r_duty + self.g_duty + self.b_duty:.3f}")

    def set_value(self, channel, value):
        """Set a duty cycle value for a channel."""
        value = max(0.0, min(1.0, float(value)))
        
        if channel.lower() == 'r':
            self.r_duty = value
        elif channel.lower() == 'g':
            self.g_duty = value
        elif channel.lower() == 'b':
            self.b_duty = value
        else:
            print(f"Invalid channel: {channel}. Use 'r', 'g', or 'b'")
            return False
        
        self.update_leds()
        return True

    def set_all(self, r, g, b):
        """Set all three channels at once."""
        self.r_duty = max(0.0, min(1.0, float(r)))
        self.g_duty = max(0.0, min(1.0, float(g)))
        self.b_duty = max(0.0, min(1.0, float(b)))
        self.update_leds()

    def adjust(self, channel, delta):
        """Adjust a channel by a delta amount."""
        if channel.lower() == 'r':
            self.r_duty = max(0.0, min(1.0, self.r_duty + delta))
        elif channel.lower() == 'g':
            self.g_duty = max(0.0, min(1.0, self.g_duty + delta))
        elif channel.lower() == 'b':
            self.b_duty = max(0.0, min(1.0, self.b_duty + delta))
        else:
            print(f"Invalid channel: {channel}. Use 'r', 'g', or 'b'")
            return False
        
        self.update_leds()
        return True

    def preset(self, name):
        """Apply a preset white balance."""
        presets = {
            'equal': (1.0, 1.0, 1.0),
            'warm': (1.0, 0.9, 0.7),      # More red/yellow
            'cool': (0.8, 0.9, 1.0),     # More blue
            'neutral': (0.95, 1.0, 0.9), # Slightly warm
            'low': (0.3, 0.3, 0.3),      # Low brightness
            'medium': (0.5, 0.5, 0.5),   # Medium brightness
            'high': (0.8, 0.8, 0.8),     # High brightness
        }
        
        if name.lower() in presets:
            r, g, b = presets[name.lower()]
            self.set_all(r, g, b)
            print(f"Applied preset: {name}")
            return True
        else:
            print(f"Unknown preset: {name}")
            print(f"Available presets: {', '.join(presets.keys())}")
            return False

    def help(self):
        """Show help message."""
        print("\nCommands:")
        print("  r <value>     - Set red duty cycle (0.0-1.0)")
        print("  g <value>     - Set green duty cycle (0.0-1.0)")
        print("  b <value>     - Set blue duty cycle (0.0-1.0)")
        print("  set <r> <g> <b> - Set all three channels")
        print("  +r <delta>    - Increase red by delta (e.g., +r 0.1)")
        print("  -r <delta>    - Decrease red by delta")
        print("  +g <delta>    - Increase green by delta")
        print("  -g <delta>    - Decrease green by delta")
        print("  +b <delta>    - Increase blue by delta")
        print("  -b <delta>    - Decrease blue by delta")
        print("  preset <name> - Apply preset (equal, warm, cool, neutral, low, medium, high)")
        print("  show          - Show current values")
        print("  off           - Turn all LEDs off")
        print("  help          - Show this help")
        print("  quit/exit     - Exit and turn off LEDs")

    def cleanup(self):
        """Turn off all LEDs and cleanup."""
        self.set_all(0, 0, 0)
        self.red.close()
        self.green.close()
        self.blue.close()
        print("\nLEDs turned off. Cleanup complete.")

    def run(self):
        """Run the interactive tuning loop."""
        print("\nType 'help' for commands, 'quit' to exit")
        print("Example: r 0.5  (set red to 50%)")
        print("         set 0.8 0.9 0.7  (set all channels)")
        print("         +g 0.1  (increase green by 10%)")
        print()

        try:
            while True:
                self.show_current()
                cmd = input("\n> ").strip().split()

                if not cmd:
                    continue

                command = cmd[0].lower()

                if command in ['quit', 'exit', 'q']:
                    break
                elif command == 'help' or command == 'h':
                    self.help()
                elif command == 'show' or command == 's':
                    self.show_current()
                elif command == 'off':
                    self.set_all(0, 0, 0)
                    print("All LEDs turned off")
                elif command in ['r', 'g', 'b']:
                    if len(cmd) < 2:
                        print(f"Usage: {command} <value>")
                        continue
                    try:
                        value = float(cmd[1])
                        self.set_value(command, value)
                    except ValueError:
                        print(f"Invalid value: {cmd[1]}")
                elif command == 'set':
                    if len(cmd) < 4:
                        print("Usage: set <r> <g> <b>")
                        continue
                    try:
                        r, g, b = float(cmd[1]), float(cmd[2]), float(cmd[3])
                        self.set_all(r, g, b)
                    except ValueError:
                        print("Invalid values")
                elif command.startswith('+') or command.startswith('-'):
                    # Adjust commands: +r 0.1, -g 0.05, etc.
                    if len(command) < 2 or len(cmd) < 2:
                        print(f"Usage: {command} <delta>")
                        continue
                    channel = command[1]
                    try:
                        delta = float(cmd[1])
                        if command.startswith('-'):
                            delta = -delta
                        self.adjust(channel, delta)
                    except ValueError:
                        print(f"Invalid delta: {cmd[1]}")
                elif command == 'preset':
                    if len(cmd) < 2:
                        print("Usage: preset <name>")
                        print("Available: equal, warm, cool, neutral, low, medium, high")
                        continue
                    self.preset(cmd[1])
                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' for available commands")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        finally:
            self.cleanup()


def main():
    """Main entry point."""
    tuner = WhiteTuner()
    tuner.run()
    print("\n" + "=" * 60)
    print("White tuning complete!")
    print("=" * 60)
    print("\nRecommended values for config.yaml:")
    print(f"  cob_max_duty_cycle: {max(tuner.r_duty, tuner.g_duty, tuner.b_duty):.2f}")
    print("\nFor optimal white, use these duty cycle ratios:")
    print(f"  Red:   {tuner.r_duty:.3f}")
    print(f"  Green: {tuner.g_duty:.3f}")
    print(f"  Blue:  {tuner.b_duty:.3f}")
    print("\nNote: These are raw duty cycles. The brightness multiplier")
    print("in config.yaml will scale these further.")


if __name__ == "__main__":
    main()


