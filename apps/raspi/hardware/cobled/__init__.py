"""COB LED control module for RGB chip-on-board LEDs."""

from .cobled import CobLed
from .cobled_serial import CobLedSerial

__all__ = ["CobLed", "CobLedSerial"]
