"""
Light state behavior functions for AdaptLight.

This module implements a unified state system where all states
use the same parameters (r, g, b, speed) and a single execution function.
Static states have speed=None, animated states have speed in milliseconds.
"""

from hardware.led_controller import LEDController
from utils.expression_evaluator import evaluate_color_expression, create_safe_expression_function
import threading
import time


# Global references (set by main.py)
led_controller: LEDController = None
state_machine_ref = None


def set_led_controller(controller: LEDController):
    """Set the global LED controller instance."""
    global led_controller
    led_controller = controller


def set_state_machine(machine):
    """Set the global state machine instance."""
    global state_machine_ref
    state_machine_ref = machine


def execute_unified_state(params):
    """
    Execute a unified state with r, g, b, and optional speed parameters.

    This is the core function that handles ALL states in the system.
    - If speed is None: set static color
    - If speed is a number: start animation

    Args:
        params: Dict with r, g, b (values or expressions) and optional speed
    """
    if not params or not isinstance(params, dict):
        print("State requires parameters dict with r, g, b, and optional speed")
        return

    speed = params.get('speed')

    if speed is None:
        # Static color mode
        _execute_static_state(params)
    else:
        # Animation mode
        _execute_animated_state(params)


def _execute_static_state(params):
    """
    Execute a static color state (speed=None).

    Args:
        params: Dict with r, g, b values (can be numbers or expressions)
    """
    if state_machine_ref:
        state_machine_ref.stop_interval()

    if not led_controller:
        print("LED controller not initialized")
        return

    # Get current color for expression context
    current_r, current_g, current_b = led_controller.get_current_color()

    r = params.get('r', 0)
    g = params.get('g', 0)
    b = params.get('b', 0)

    # Evaluate expressions if they are strings
    if isinstance(r, str):
        r = evaluate_color_expression(r, current_r, current_g, current_b, 'r')
    if isinstance(g, str):
        g = evaluate_color_expression(g, current_r, current_g, current_b, 'g')
    if isinstance(b, str):
        b = evaluate_color_expression(b, current_r, current_g, current_b, 'b')

    # Set the color
    led_controller.set_color(int(r), int(g), int(b))
    print(f"Static state set to: RGB({r}, {g}, {b})")


def _execute_animated_state(params):
    """
    Execute an animated state (speed is a number in milliseconds).

    Args:
        params: Dict with r, g, b expressions and speed
    """
    if not state_machine_ref:
        print("State machine not initialized")
        return

    # Stop any existing animation
    state_machine_ref.stop_interval()

    if not led_controller:
        print("LED controller not initialized")
        return

    speed = params.get('speed', 50)  # milliseconds
    r_expr = params.get('r', 'r')
    g_expr = params.get('g', 'g')
    b_expr = params.get('b', 'b')

    print(f"Starting animation: r={r_expr}, g={g_expr}, b={b_expr}, speed={speed}ms")

    # Create safe evaluation functions for each channel
    try:
        r_fn = create_safe_expression_function(r_expr)
        g_fn = create_safe_expression_function(g_expr)
        b_fn = create_safe_expression_function(b_expr)
    except Exception as e:
        print(f"Failed to create animation functions: {e}")
        return

    # Animation state
    frame = [0]  # Use list to allow mutation in closure
    start_time = time.time()

    # Get or initialize color state
    r, g, b = led_controller.get_current_color()

    # Animation update function
    def animation_fn():
        nonlocal r, g, b
        t = int((time.time() - start_time) * 1000)  # Time in milliseconds

        try:
            # Evaluate expressions with current context
            context = {'r': r, 'g': g, 'b': b, 't': t, 'frame': frame[0]}
            new_r = r_fn(context)
            new_g = g_fn(context)
            new_b = b_fn(context)

            # Clamp values to 0-255
            r = max(0, min(255, int(new_r)))
            g = max(0, min(255, int(new_g)))
            b = max(0, min(255, int(new_b)))

            # Update the display
            led_controller.set_color(r, g, b)

            frame[0] += 1

        except Exception as e:
            print(f"Animation frame error: {e}")
            if state_machine_ref:
                state_machine_ref.stop_interval()

    # Start the interval
    if state_machine_ref:
        state_machine_ref.start_interval(animation_fn, speed)


def initialize_default_states(state_machine):
    """
    Create default 'on' and 'off' states with the state machine.

    Args:
        state_machine: StateMachine instance
    """
    from core.state import State

    # Create default states using unified parameters
    # Note: on = white (255, 255, 255), off = black (0, 0, 0)
    default_states = [
        State('off', r=0, g=0, b=0, speed=None,
              description='turn light off - black (0,0,0)'),
        State('on', r=255, g=255, b=255, speed=None,
              description='turn light on - white (255,255,255)'),
    ]

    for state in default_states:
        state_machine.states.add_state(state)
        print(f"Default state created: {state.name} - RGB({state.r}, {state.g}, {state.b})")

    print(f"Default states initialized: {len(default_states)}")


def initialize_default_rules(state_machine):
    """
    Add default transition rules on startup.

    Args:
        state_machine: StateMachine instance
    """
    from core.rule import Rule

    default_rules = [
        # Toggle light on/off with button click
        Rule('off', 'button_click', 'on', None, None),
        Rule('on', 'button_click', 'off', None, None),
    ]

    for rule in default_rules:
        state_machine.add_rule(rule)

    print(f"Default rules initialized: {len(default_rules)}")
