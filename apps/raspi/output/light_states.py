"""
Light state behavior functions for AdaptLight.

This module implements a unified state system where all states
use the same parameters (r, g, b, speed) and a single execution function.
Static states have speed=None, animated states have speed in milliseconds.
"""

from ..hardware.led_controller import LEDController
from brain.utils.expression_evaluator import evaluate_color_expression, create_safe_expression_function
import threading
import time


# Global references (set by main.py)
led_controller: LEDController = None
state_machine_ref = None

# Duration timer for states with duration_ms
_duration_timer = None


def set_led_controller(controller: LEDController):
    """Set the global LED controller instance."""
    global led_controller
    led_controller = controller


def set_state_machine(machine):
    """Set the global state machine instance."""
    global state_machine_ref
    state_machine_ref = machine


def _cancel_duration_timer():
    """Cancel any active duration timer."""
    global _duration_timer
    if _duration_timer is not None:
        _duration_timer.cancel()
        _duration_timer = None


def _setup_duration_timer(duration_ms, then_state, state_name):
    """
    Set up a timer to transition to another state after duration expires.

    Args:
        duration_ms: Duration in milliseconds
        then_state: State to transition to
        state_name: Current state name (for logging)
    """
    global _duration_timer

    _cancel_duration_timer()

    def on_duration_complete():
        global _duration_timer
        _duration_timer = None

        if state_machine_ref:
            current = state_machine_ref.current_state
            # Only transition if we're still in the expected state
            if current == state_name:
                print(f"\n⏱️ Duration expired for '{state_name}' ({duration_ms}ms) → transitioning to '{then_state}'")
                state_machine_ref.set_state(then_state)
            else:
                print(f"⏱️ Duration expired but state changed ({state_name} → {current}), skipping transition")

    delay_seconds = duration_ms / 1000.0
    _duration_timer = threading.Timer(delay_seconds, on_duration_complete)
    _duration_timer.start()
    print(f"⏱️ Duration timer set: {duration_ms}ms, then → '{then_state}'")


def execute_unified_state(params):
    """
    Execute a unified state with r, g, b, and optional speed parameters.

    This is the core function that handles ALL states in the system.
    - If 'code' field exists: use stdlib renderer (code-based state)
    - If speed is None: set static color
    - If speed is a number: start animation
    - If duration_ms is set: auto-transition to 'then' state after duration

    Args:
        params: Dict with r, g, b (values or expressions), optional speed,
                or 'code' field for stdlib-based states,
                optional duration_ms and then for auto-transition
    """
    if not params or not isinstance(params, dict):
        print("State requires parameters dict with r, g, b, and optional speed")
        return

    # Cancel any existing duration timer (new state entry cancels old timers)
    _cancel_duration_timer()

    # Note: Voice reactive lighting is now handled separately by the NeoPixel strip
    # via the reactive_led controller in main.py. This module only handles COB LED states.

    # Check for code-based state (stdlib mode)
    code = params.get('code')
    if code:
        _execute_code_state(params)
        return

    speed = params.get('speed')

    if speed is None:
        # Static color mode
        _execute_static_state(params)
    else:
        # Animation mode
        _execute_animated_state(params)

    # Set up duration timer if specified
    duration_ms = params.get('duration_ms')
    then_state = params.get('then')
    state_name = params.get('state_name', 'unknown')

    if duration_ms is not None and then_state is not None:
        _setup_duration_timer(duration_ms, then_state, state_name)


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
        elapsed_ms = int((time.time() - start_time) * 1000)  # Time in milliseconds

        try:
            # Evaluate expressions with current context
            # 't' and 'elapsed_ms' are the same - elapsed time since state started
            context = {'r': r, 'g': g, 'b': b, 't': elapsed_ms, 'elapsed_ms': elapsed_ms, 'frame': frame[0]}
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
        debug = getattr(state_machine_ref, 'debug', False)
        state_machine_ref.start_interval(animation_fn, speed, debug=debug)


def _create_renderer_with_data(code: str):
    """
    Create a renderer that includes getData/setData from state machine.
    """
    import math
    import random as random_module

    # Stdlib functions (same as StdlibRenderer)
    def _hsv(h, s, v):
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
        return (int(r * 255), int(g * 255), int(b * 255))

    def _rgb(r, g, b):
        return (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))

    def _clamp(x, lo, hi):
        return max(lo, min(hi, x))

    def _lerp(a, b, t):
        return a + (b - a) * t

    def _map_range(x, in_lo, in_hi, out_lo, out_hi):
        return out_lo + (x - in_lo) * (out_hi - out_lo) / (in_hi - in_lo)

    def _lerp_color(c1, c2, t):
        return tuple(int(_lerp(c1[i], c2[i], t)) for i in range(3))

    def _ease_in(t):
        return t * t

    def _ease_out(t):
        return 1 - (1 - t) ** 2

    def _ease_in_out(t):
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - pow(-2 * t + 2, 2) / 2

    # Get getData/setData from state machine
    def getData(key, default=None):
        if state_machine_ref:
            return state_machine_ref.get_data(key, default)
        return default

    def setData(key, value):
        if state_machine_ref:
            state_machine_ref.set_data(key, value)

    stdlib = {
        'hsv': _hsv, 'rgb': _rgb, 'lerp_color': _lerp_color,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'abs': abs, 'min': min, 'max': max,
        'floor': math.floor, 'ceil': math.ceil, 'round': round,
        'sqrt': math.sqrt, 'pow': pow,
        'clamp': _clamp, 'lerp': _lerp, 'map_range': _map_range,
        'ease_in': _ease_in, 'ease_out': _ease_out, 'ease_in_out': _ease_in_out,
        'random': random_module.random, 'randint': random_module.randint,
        'PI': math.pi, 'E': math.e,
        'int': int, 'float': float, 'bool': bool, 'len': len, 'range': range,
        'True': True, 'False': False, 'None': None,
        # State machine data functions
        'getData': getData, 'setData': setData,
    }

    exec_globals = {'__builtins__': {}, **stdlib}
    exec(code, exec_globals)
    render_fn = exec_globals.get('render')
    if not callable(render_fn):
        raise ValueError("Code must define a 'render(prev, t)' function")
    return render_fn


def _execute_code_state(params):
    """
    Execute a code-based state (stdlib mode with render() function).

    Args:
        params: Dict with 'code' field containing Python code with render(prev, t) function
    """
    if not state_machine_ref:
        print("State machine not initialized")
        return

    # Stop any existing animation
    state_machine_ref.stop_interval()

    if not led_controller:
        print("LED controller not initialized")
        return

    code = params.get('code', '')
    if not code:
        print("No code provided for code-based state")
        return

    print(f"Starting code-based state")

    # Create renderer with getData/setData access
    try:
        render_fn = _create_renderer_with_data(code)
    except Exception as e:
        print(f"Failed to create renderer: {e}")
        return

    # Animation state
    start_time = time.time()
    r, g, b = led_controller.get_current_color()
    prev_color = (r, g, b)

    # Animation update function
    def animation_fn():
        nonlocal prev_color
        elapsed_s = time.time() - start_time

        try:
            # Call render(prev, t) and get (r,g,b), next_ms
            result = render_fn(prev_color, elapsed_s)
            rgb, next_ms = result

            # Update color
            r, g, b = rgb
            r = max(0, min(255, int(r)))
            g = max(0, min(255, int(g)))
            b = max(0, min(255, int(b)))

            led_controller.set_color(r, g, b)
            prev_color = (r, g, b)

            # Handle state_complete transition (next_ms = 0 signals completion)
            if next_ms == 0:
                print(f"State completed, firing state_complete transition")
                if state_machine_ref:
                    # Defer to avoid "cannot join current thread" error
                    def trigger_complete():
                        state_machine_ref.stop_interval()
                        state_machine_ref.execute_transition("state_complete")
                    threading.Timer(0.01, trigger_complete).start()

        except Exception as e:
            print(f"Code state frame error: {e}")
            if state_machine_ref:
                state_machine_ref.stop_interval()

    # Default speed from code or fallback to 30ms
    default_speed = 30
    if state_machine_ref:
        debug = getattr(state_machine_ref, 'debug', False)
        state_machine_ref.start_interval(animation_fn, default_speed, debug=debug)


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
