"""
Light state behavior functions for AdaptLight.

This module is a port of states.js and contains the behavior
functions for each state:
- turnLightOn(): Turn LEDs on (white)
- turnLightOff(): Turn LEDs off
- setColor(params): Set RGB color
- startAnimation(params): Start expression-based animation

All functions control the LED hardware instead of DOM elements.
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


def turn_light_on():
    """Turn light on (pure white light)."""
    if led_controller:
        led_controller.set_color(255, 255, 200)  # Warm white
        print("Light turned ON")
    else:
        print("LED controller not initialized")


def turn_light_off():
    """Turn light off."""
    # Stop any running animations first
    if state_machine_ref:
        state_machine_ref.stop_interval()

    if led_controller:
        led_controller.set_color(0, 0, 0)
        print("Light turned OFF")
    else:
        print("LED controller not initialized")


def set_color(params):
    """
    Set light color based on RGB values.

    Args:
        params: Dict with r, g, b values (can be numbers or expressions)
                or array [r, g, b]
    """
    if state_machine_ref:
        state_machine_ref.stop_interval()

    if not led_controller:
        print("LED controller not initialized")
        return

    # Get current color for expression context
    current_r, current_g, current_b = led_controller.get_current_color()

    # Parse params
    if isinstance(params, dict):
        r = params.get('r', current_r)
        g = params.get('g', current_g)
        b = params.get('b', current_b)

        # Evaluate expressions if they are strings
        if isinstance(r, str):
            r = evaluate_color_expression(r, current_r, current_g, current_b, 'r')
        if isinstance(g, str):
            g = evaluate_color_expression(g, current_r, current_g, current_b, 'g')
        if isinstance(b, str):
            b = evaluate_color_expression(b, current_r, current_g, current_b, 'b')

    elif isinstance(params, (list, tuple)) and len(params) >= 3:
        r, g, b = params[0], params[1], params[2]
    else:
        r, g, b = current_r, current_g, current_b

    # Set the color
    led_controller.set_color(int(r), int(g), int(b))
    print(f"Light color set to: RGB({r}, {g}, {b})")


def start_animation(params):
    """
    Start an expression-based animation.

    Args:
        params: Dict with r, g, b expressions and speed
                Format: {r: "expr", g: "expr", b: "expr", speed: 50}
                Variables: r, g, b (current), t (time), frame (frame count)
                Functions: sin, cos, abs, min, max, floor, ceil, round, sqrt, pow, PI
    """
    if not state_machine_ref:
        print("State machine not initialized")
        return

    # Stop any existing animation
    state_machine_ref.stop_interval()

    if not params or not isinstance(params, dict):
        print("Animation requires parameters object with r, g, b expressions and speed")
        return

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
        state_machine_ref.start_interval(animation_fn, speed / 1000.0)  # Convert to seconds


def initialize_default_states(state_machine):
    """
    Register default states with the state machine.

    Args:
        state_machine: StateMachine instance
    """
    from core.state import State

    default_states = [
        State('off', 'turn light off, no extra parameters', turn_light_off),
        State('on', 'turn light on, no extra parameters', turn_light_on),
        State('color',
              'display a custom color. Parameters: {r: value, g: value, b: value} where values '
              'can be numbers or expressions. Expression variables: r, g, b (current RGB values), '
              'random() (returns 0-255). Functions: sin, cos, abs, min, max, floor, ceil, round, '
              'sqrt, pow, PI. Examples: {r: 255, g: 0, b: 0} or {r: "random()", g: "random()", '
              'b: "random()"} or {r: "r + 10", g: "g", b: "b"} or {r: "b", g: "r", b: "g"}',
              set_color),
        State('animation',
              'play an animated light pattern using expressions. Parameters: {r: "expr", g: "expr", '
              'b: "expr", speed: 50}. Variables: r,g,b (current RGB), t (time in ms), frame (frame '
              'count). Functions: sin, cos, abs, min, max, floor, ceil, round, sqrt, pow, PI. '
              'Example: {r: "abs(sin(t/1000)) * 255", g: "abs(cos(t/1000)) * 255", b: "128", speed: 50}',
              start_animation)
    ]

    for state in default_states:
        state_machine.register_state(state.name, state.description, state.on_enter)

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
        Rule('off', None, 'button_click', 'on', None),
        Rule('on', None, 'button_click', 'off', None),
    ]

    for rule in default_rules:
        state_machine.add_rule(rule)

    print(f"Default rules initialized: {len(default_rules)}")
