"""
Button controller for GPIO button input.

This module is a port of transitions.js and detects:
- Single click
- Double click
- Hold (long press)
- Release (after hold)

Uses GPIO with debouncing to prevent spurious triggers.
"""

import time
import threading
from typing import Callable

try:
    from gpiozero import Button
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    print("Warning: gpiozero library not available. Button control will be simulated.")


class ButtonController:
    """Handles button input and detects different press patterns."""

    def __init__(self, button_pin=2, bounce_time=0.05):
        """
        Initialize button controller.

        Args:
            button_pin: GPIO pin number for the button
            bounce_time: Debounce time in seconds
        """
        self.button_pin = button_pin
        self.bounce_time = bounce_time

        # Configuration thresholds (in seconds)
        self.DOUBLE_CLICK_THRESHOLD = 0.3  # 300ms
        self.HOLD_THRESHOLD = 0.5  # 500ms

        # State tracking
        self.click_count = 0
        self.click_timer = None
        self.hold_timer = None
        self.press_start_time = None
        self.is_holding = False
        self.hold_fired = False

        # Callbacks
        self.on_single_click = None
        self.on_double_click = None
        self.on_hold = None
        self.on_release = None

        # Initialize button
        if GPIOZERO_AVAILABLE:
            self.button = Button(button_pin, pull_up=True, bounce_time=bounce_time)
            self.button.when_pressed = self._handle_press
            self.button.when_released = self._handle_release
            print(f"Button initialized on GPIO {button_pin}")
        else:
            self.button = None
            print(f"Button simulation mode on GPIO {button_pin}")

    def _handle_press(self):
        """Handle button press event."""
        print(f"[DEBUG] GPIO {self.button_pin} - Button PRESSED")
        self.press_start_time = time.time()
        self.hold_fired = False

        # Start hold timer - will fire if button is still held after threshold
        if self.hold_timer:
            self.hold_timer.cancel()
        self.hold_timer = threading.Timer(self.HOLD_THRESHOLD, self._on_hold_threshold)
        self.hold_timer.start()

    def _on_hold_threshold(self):
        """Called when hold threshold is reached while button is still pressed."""
        self.hold_fired = True
        self._emit_transition('button_hold')

    def _handle_release(self):
        """Handle button release event."""
        print(f"[DEBUG] GPIO {self.button_pin} - Button RELEASED")
        if not self.press_start_time:
            return

        # Cancel hold timer if it hasn't fired yet
        if self.hold_timer:
            self.hold_timer.cancel()
            self.hold_timer = None

        # Check if hold was fired
        if self.hold_fired:
            # Emit release after hold
            self._emit_transition('button_release')
            self.hold_fired = False
        else:
            # This is a click (not a hold)
            self._handle_click()

        self.press_start_time = None

    def _handle_click(self):
        """Handle click detection (single vs double)."""
        self.click_count += 1

        if self.click_count == 1:
            # First click - start timer to wait for potential second click
            if self.click_timer:
                self.click_timer.cancel()
            self.click_timer = threading.Timer(self.DOUBLE_CLICK_THRESHOLD, self._on_single_click_timeout)
            self.click_timer.start()
        elif self.click_count == 2:
            # Second click detected - cancel timer and emit double click
            if self.click_timer:
                self.click_timer.cancel()
                self.click_timer = None
            self.click_count = 0
            self._emit_transition('button_double_click')

    def _on_single_click_timeout(self):
        """Called when double-click timeout expires - emit single click."""
        if self.click_count == 1:
            self._emit_transition('button_click')
        self.click_count = 0
        self.click_timer = None

    def _emit_transition(self, transition_name: str):
        """Emit a transition event."""
        print(f"[DEBUG] GPIO {self.button_pin} - Transition: {transition_name}")

        # Call the appropriate callback
        if transition_name == 'button_click' and self.on_single_click:
            print(f"[DEBUG] GPIO {self.button_pin} - Calling single_click callback")
            self.on_single_click()
        elif transition_name == 'button_double_click' and self.on_double_click:
            print(f"[DEBUG] GPIO {self.button_pin} - Calling double_click callback")
            self.on_double_click()
        elif transition_name == 'button_hold' and self.on_hold:
            print(f"[DEBUG] GPIO {self.button_pin} - Calling hold callback")
            self.on_hold()
        elif transition_name == 'button_release' and self.on_release:
            print(f"[DEBUG] GPIO {self.button_pin} - Calling release callback")
            self.on_release()

    def set_callbacks(self, on_single_click=None, on_double_click=None,
                     on_hold=None, on_release=None):
        """
        Set callback functions for button events.

        Args:
            on_single_click: Called on single click
            on_double_click: Called on double click
            on_hold: Called when button is held
            on_release: Called when button is released after hold
        """
        self.on_single_click = on_single_click
        self.on_double_click = on_double_click
        self.on_hold = on_hold
        self.on_release = on_release
        print(f"[DEBUG] GPIO {self.button_pin} - Callbacks set: single={on_single_click is not None}, double={on_double_click is not None}, hold={on_hold is not None}, release={on_release is not None}")

    def get_config(self):
        """Get current configuration."""
        return {
            'double_click_threshold': self.DOUBLE_CLICK_THRESHOLD,
            'hold_threshold': self.HOLD_THRESHOLD,
            'bounce_time': self.bounce_time
        }

    def set_config(self, double_click_threshold=None, hold_threshold=None):
        """
        Update configuration thresholds.

        Args:
            double_click_threshold: Time window for double click (seconds)
            hold_threshold: Time before hold is registered (seconds)
        """
        if double_click_threshold is not None:
            self.DOUBLE_CLICK_THRESHOLD = double_click_threshold
        if hold_threshold is not None:
            self.HOLD_THRESHOLD = hold_threshold
        print(f"Button config updated: {self.get_config()}")

    def cleanup(self):
        """Cleanup GPIO resources."""
        # Cancel any active timers
        if self.click_timer:
            self.click_timer.cancel()
            self.click_timer = None
        if self.hold_timer:
            self.hold_timer.cancel()
            self.hold_timer = None

        # Close button
        if self.button:
            self.button.close()
        print("Button controller cleanup complete")
