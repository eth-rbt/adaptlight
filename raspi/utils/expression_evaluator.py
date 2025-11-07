"""
Safe expression evaluator for AdaptLight.

Provides safe evaluation of user-defined expressions for:
- Color value calculations
- Animation expressions
- Rule conditions and actions

Restricts access to dangerous operations while allowing math functions.
"""

import math
import random as random_module


def evaluate_color_expression(expr: str, current_r: int, current_g: int, current_b: int, channel: str = 'r'):
    """
    Evaluate a color expression safely.

    Args:
        expr: The expression string
        current_r: Current red value
        current_g: Current green value
        current_b: Current blue value
        channel: Which channel this is for ('r', 'g', or 'b') - used for error fallback

    Returns:
        The evaluated result (int 0-255)
    """
    # Whitelist of allowed Math functions
    safe_math = {
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'abs': abs,
        'min': min,
        'max': max,
        'floor': math.floor,
        'ceil': math.ceil,
        'round': round,
        'sqrt': math.sqrt,
        'pow': pow,
        'PI': math.pi,
        'E': math.e
    }

    # Random function
    def random():
        return random_module.randint(0, 255)

    # Current color object
    current = {
        'r': current_r,
        'g': current_g,
        'b': current_b
    }

    try:
        # Create safe evaluation context
        eval_globals = {
            '__builtins__': {},
            'current': current,
            'r': current_r,
            'g': current_g,
            'b': current_b,
            'random': random,
            **safe_math
        }

        result = eval(expr, eval_globals, {})
        return int(result)

    except Exception as e:
        print(f"Color expression evaluation error for {channel} channel (\"{expr}\"): {e}")
        # Return appropriate current value based on channel
        fallback = current_r if channel == 'r' else (current_g if channel == 'g' else current_b)
        print(f"Using fallback value: {fallback}")
        return fallback


def create_safe_expression_function(expr: str):
    """
    Create a safe expression evaluation function.

    Args:
        expr: The expression string

    Returns:
        A function that evaluates the expression with given context
    """
    # Whitelist of allowed Math functions
    safe_math = {
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'abs': abs,
        'min': min,
        'max': max,
        'floor': math.floor,
        'ceil': math.ceil,
        'round': round,
        'sqrt': math.sqrt,
        'pow': pow,
        'PI': math.pi,
        'E': math.e
    }

    def eval_fn(context):
        """
        Evaluate expression with context.

        Args:
            context: Dict with variables (r, g, b, t, frame)

        Returns:
            Evaluated result
        """
        try:
            # Create safe evaluation context
            eval_globals = {
                '__builtins__': {},
                **context,
                **safe_math
            }

            result = eval(expr, eval_globals, {})
            return result

        except Exception as e:
            print(f"Expression evaluation error (\"{expr}\"): {e}")
            # Return current value of first variable in context
            return context.get('r', 0)

    return eval_fn


def evaluate_condition(expr: str, state_machine):
    """
    Evaluate a rule condition expression.

    Args:
        expr: Condition expression string
        state_machine: StateMachine instance for context

    Returns:
        Boolean result
    """
    if not expr:
        return True

    # Whitelist of allowed functions
    safe_funcs = {
        'abs': abs,
        'min': min,
        'max': max,
        'sin': math.sin,
        'cos': math.cos,
        'floor': math.floor,
        'ceil': math.ceil,
        'round': round,
        'PI': math.pi,
        'E': math.e
    }

    try:
        # Create evaluation context
        eval_globals = {
            '__builtins__': {},
            'getData': state_machine.get_data,
            'getTime': state_machine.get_time,
            'time': state_machine.get_time(),
            **safe_funcs
        }

        result = eval(expr, eval_globals, {})
        return bool(result)

    except Exception as e:
        print(f"Condition evaluation error (\"{expr}\"): {e}")
        return False


def evaluate_action(expr: str, state_machine):
    """
    Evaluate a rule action expression.

    Args:
        expr: Action expression string
        state_machine: StateMachine instance for context
    """
    if not expr:
        return

    # Whitelist of allowed functions
    safe_funcs = {
        'abs': abs,
        'min': min,
        'max': max,
        'sin': math.sin,
        'cos': math.cos,
        'floor': math.floor,
        'ceil': math.ceil,
        'round': round,
        'PI': math.pi,
        'E': math.e
    }

    try:
        # Create evaluation context
        eval_globals = {
            '__builtins__': {},
            'setData': state_machine.set_data,
            'getData': state_machine.get_data,
            'getTime': state_machine.get_time,
            'time': state_machine.get_time(),
            **safe_funcs
        }

        eval(expr, eval_globals, {})

    except Exception as e:
        print(f"Action evaluation error (\"{expr}\"): {e}")
