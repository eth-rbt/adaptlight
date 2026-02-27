"""
Three state representation approaches for AdaptLight.

All representations use the unified signature:
    render(prev, t) -> ((r, g, b), next_update_ms | None | 0)

- prev: tuple (r, g, b) of previous output (0-255 each)
- t: float, time in seconds since state started
- returns: ((r, g, b), next_ms) where:
    - next_ms > 0: animation continues, call render() again in next_ms milliseconds
    - next_ms = None: static state, no more render calls needed
    - next_ms = 0: STATE COMPLETE, triggers "state_complete" transition
                   Use this when an animation finishes (e.g., blink 3 times then done)
"""

import math
import random as random_module


# =============================================================================
# VERSION 1: Original (expression strings, existing math functions)
# =============================================================================

class OriginalRenderer:
    """
    Original approach: separate r/g/b expression strings.

    State definition:
        {
            "r": "sin(frame * 0.05) * 127 + 128",
            "g": 0,
            "b": "cos(frame * 0.05) * 127 + 128",
            "speed": 30  # ms between frames, None = static
        }
    """

    SAFE_MATH = {
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
        'E': math.e,
    }

    def __init__(self, r_expr, g_expr, b_expr, speed=None):
        self.r_expr = r_expr
        self.g_expr = g_expr
        self.b_expr = b_expr
        self.speed = speed  # None = static
        self.frame = 0

    def _eval_expr(self, expr, prev):
        if isinstance(expr, (int, float)):
            return int(max(0, min(255, expr)))
        if expr is None:
            return 0

        eval_globals = {
            '__builtins__': {},
            'frame': self.frame,
            'r': prev[0],
            'g': prev[1],
            'b': prev[2],
            'random': lambda: random_module.randint(0, 255),
            **self.SAFE_MATH
        }

        try:
            result = eval(expr, eval_globals, {})
            return int(max(0, min(255, result)))
        except Exception as e:
            print(f"Expression error: {e}")
            return 0

    def render(self, prev, t):
        r = self._eval_expr(self.r_expr, prev)
        g = self._eval_expr(self.g_expr, prev)
        b = self._eval_expr(self.b_expr, prev)

        self.frame += 1

        return (r, g, b), self.speed


# =============================================================================
# VERSION 2: Pure Python (no magic, write everything yourself)
# =============================================================================

class PurePythonRenderer:
    """
    Pure Python: code is a complete function, no helpers provided.
    You write everything from scratch.

    State definition:
        {
            "code": '''
def render(prev, t):
    # HSV to RGB - you write it yourself
    h = (t * 0.1) % 1.0
    s, v = 1.0, 1.0

    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t_val = v * (1 - (1 - f) * s)

    i = i % 6
    if i == 0: r, g, b = v, t_val, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t_val
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t_val, p, v
    else: r, g, b = v, p, q

    return (int(r*255), int(g*255), int(b*255)), 30
'''
        }

    Pros: No magic, fully explicit, portable
    Cons: Verbose, user must know Python well
    """

    # Only basic Python allowed - no imports except math/random
    ALLOWED_IMPORTS = {'math', 'random'}

    def __init__(self, code: str, get_data_fn=None, set_data_fn=None, num_pixels: int = 0):
        self.code = code
        self.render_fn = None
        self._get_data_fn = get_data_fn
        self._set_data_fn = set_data_fn
        self._num_pixels = num_pixels
        self._compile()

    def _compile(self):
        """Compile the code and extract the render function."""
        # Default getData/setData use local dict if no external functions provided
        local_data = {}

        def default_get_data(key, default=None):
            return local_data.get(key, default)

        def default_set_data(key, value):
            local_data[key] = value
            return value

        get_data = self._get_data_fn if self._get_data_fn else default_get_data
        set_data = self._set_data_fn if self._set_data_fn else default_set_data

        # Restricted globals - only safe builtins
        restricted_builtins = {
            'abs': abs,
            'min': min,
            'max': max,
            'int': int,
            'float': float,
            'bool': bool,
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'sum': sum,
            'round': round,
            'list': list,
            'tuple': tuple,
            'True': True,
            'False': False,
            'None': None,
        }

        exec_globals = {
            '__builtins__': restricted_builtins,
            'math': math,
            'random': random_module,
            'getData': get_data,
            'setData': set_data,
            'NUM_PIXELS': self._num_pixels,
        }

        try:
            exec(self.code, exec_globals)
            self.render_fn = exec_globals.get('render')
            if not callable(self.render_fn):
                raise ValueError("Code must define a 'render(prev, t)' function")
        except Exception as e:
            print(f"Compilation error: {e}")
            self.render_fn = lambda prev, t: (prev, None)

    def render(self, prev, t):
        try:
            return self.render_fn(prev, t)
        except Exception as e:
            print(f"Render error: {e}")
            return prev, None


# =============================================================================
# VERSION 3: Minimalist Standard Library (documented helpers + Python)
# =============================================================================

class StdlibRenderer:
    """
    Minimalist stdlib: documented helper functions available, plus Python.

    Available functions (ONLY these, nothing else):

    Color:
        hsv(h, s, v) -> (r, g, b)    # h: 0-1, s: 0-1, v: 0-1
        rgb(r, g, b) -> (r, g, b)    # clamps to 0-255
        lerp_color(c1, c2, t) -> (r, g, b)  # interpolate between colors

    Math:
        sin(x), cos(x), tan(x)       # trig (radians)
        abs(x), min(*args), max(*args)
        floor(x), ceil(x), round(x)
        sqrt(x), pow(x, y)
        clamp(x, lo, hi)             # bound x between lo and hi
        lerp(a, b, t)                # linear interpolation
        map_range(x, in_lo, in_hi, out_lo, out_hi)  # remap value

    Easing:
        ease_in(t), ease_out(t), ease_in_out(t)  # t: 0-1

    Random:
        random() -> 0.0-1.0
        randint(lo, hi) -> int

    Data (shared across states):
        getData(key, default=None) -> value   # read from state_data
        setData(key, value) -> value          # write to state_data

    Constants:
        PI, E

    State definition:
        {
            "code": '''
def render(prev, t):
    # Rainbow cycle - hsv is provided
    return hsv(t * 0.1 % 1, 1, 1), 30
'''
        }

    Or for "make it brighter":
        {
            "code": '''
def render(prev, t):
    # Use prev, increase brightness
    r, g, b = prev
    return rgb(r * 1.3, g * 1.3, b * 1.3), None
'''
        }

    Or for counting/stateful animations:
        {
            "code": '''
def render(prev, t):
    count = getData('blink_count', 0)
    if count < 3:
        setData('blink_count', count + 1)
        on = int(t * 2) % 2 == 0
        return (255, 0, 0) if on else (0, 0, 0), 500
    return prev, 0  # state_complete
'''
        }
    """

    @staticmethod
    def _hsv(h, s, v):
        """Convert HSV to RGB. h/s/v in 0-1 range, returns 0-255 RGB."""
        h = h % 1.0
        i = int(h * 6)
        f = h * 6 - i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t_val = v * (1 - (1 - f) * s)

        i = i % 6
        if i == 0: r, g, b = v, t_val, p
        elif i == 1: r, g, b = q, v, p
        elif i == 2: r, g, b = p, v, t_val
        elif i == 3: r, g, b = p, q, v
        elif i == 4: r, g, b = t_val, p, v
        else: r, g, b = v, p, q

        return (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def _rgb(r, g, b):
        """Clamp RGB values to 0-255."""
        return (
            int(max(0, min(255, r))),
            int(max(0, min(255, g))),
            int(max(0, min(255, b)))
        )

    @staticmethod
    def _lerp(a, b, t):
        """Linear interpolation."""
        return a + (b - a) * t

    @staticmethod
    def _lerp_color(c1, c2, t):
        """Interpolate between two RGB colors."""
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t)
        )

    @staticmethod
    def _clamp(x, lo, hi):
        """Clamp x between lo and hi."""
        return max(lo, min(hi, x))

    @staticmethod
    def _map_range(x, in_lo, in_hi, out_lo, out_hi):
        """Map x from input range to output range."""
        return out_lo + (x - in_lo) * (out_hi - out_lo) / (in_hi - in_lo)

    @staticmethod
    def _ease_in(t):
        """Ease in (quadratic)."""
        return t * t

    @staticmethod
    def _ease_out(t):
        """Ease out (quadratic)."""
        return 1 - (1 - t) * (1 - t)

    @staticmethod
    def _ease_in_out(t):
        """Ease in-out (quadratic)."""
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - pow(-2 * t + 2, 2) / 2

    def __init__(self, code: str, get_data_fn=None, set_data_fn=None, num_pixels: int = 0):
        self.code = code
        self.render_fn = None
        self._get_data_fn = get_data_fn
        self._set_data_fn = set_data_fn
        self._num_pixels = num_pixels
        self._compile()

    def _compile(self):
        """Compile the code with stdlib available."""
        # Default getData/setData use local dict if no external functions provided
        local_data = {}

        def default_get_data(key, default=None):
            return local_data.get(key, default)

        def default_set_data(key, value):
            local_data[key] = value
            return value

        get_data = self._get_data_fn if self._get_data_fn else default_get_data
        set_data = self._set_data_fn if self._set_data_fn else default_set_data

        # The stdlib - ONLY these functions are available
        stdlib = {
            # Color
            'hsv': self._hsv,
            'rgb': self._rgb,
            'lerp_color': self._lerp_color,

            # Math
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
            'clamp': self._clamp,
            'lerp': self._lerp,
            'map_range': self._map_range,

            # Easing
            'ease_in': self._ease_in,
            'ease_out': self._ease_out,
            'ease_in_out': self._ease_in_out,

            # Random
            'random': random_module.random,
            'randint': random_module.randint,

            # Constants
            'PI': math.pi,
            'E': math.e,

            # Ring LED pixel count (0 = no ring available)
            'NUM_PIXELS': self._num_pixels,

            # Data access (shared state)
            'getData': get_data,
            'setData': set_data,

            # Basic Python (no imports!)
            'int': int,
            'float': float,
            'bool': bool,
            'len': len,
            'range': range,
            'list': list,
            'tuple': tuple,
            'True': True,
            'False': False,
            'None': None,
        }

        exec_globals = {
            '__builtins__': {},  # No builtins!
            **stdlib
        }

        try:
            exec(self.code, exec_globals)
            self.render_fn = exec_globals.get('render')
            if not callable(self.render_fn):
                raise ValueError("Code must define a 'render(prev, t)' function")
        except Exception as e:
            print(f"Compilation error: {e}")
            self.render_fn = lambda prev, t: (prev, None)

    def render(self, prev, t):
        try:
            return self.render_fn(prev, t)
        except Exception as e:
            print(f"Render error: {e}")
            return prev, None


# =============================================================================
# VERSION 4: Stdlib JS (JavaScript for frontend execution)
# =============================================================================

class StdlibJSRenderer:
    """
    JavaScript stdlib: code is executed directly in the browser.
    The backend just stores the code; frontend evaluates it.

    Available functions (same as Python stdlib, but in JS):
    - Color: hsv(h,s,v), rgb(r,g,b), lerp_color(c1,c2,t)
    - Math: sin, cos, tan, abs, min, max, floor, ceil, sqrt, pow, clamp, lerp, map_range
    - Easing: ease_in(t), ease_out(t), ease_in_out(t)
    - Random: random(), randint(lo,hi)
    - Utility: int(x)
    - Constants: PI, E

    State definition:
        {
            "code": `
function render(prev, t) {
    return [hsv(t * 0.1 % 1, 1, 1), 30];
}
`
        }

    Return format: [[r, g, b], nextMs]
    - nextMs > 0: animation continues
    - nextMs = null: static state
    - nextMs = 0: state complete, triggers transition
    """

    def __init__(self, code: str):
        self.code = code
        # No compilation on backend - JS runs in browser

    def render(self, prev, t):
        """
        Backend render - returns a placeholder.
        Actual rendering happens in the browser.
        """
        # For backend compatibility, return a neutral value
        # The frontend will use the code directly
        return prev, None

    def get_code(self):
        """Return the JS code for frontend execution."""
        return self.code


# =============================================================================
# EXAMPLES
# =============================================================================

if __name__ == "__main__":
    # Test all three versions

    print("=== Version 1: Original ===")
    v1 = OriginalRenderer(
        r_expr="sin(frame * 0.1) * 127 + 128",
        g_expr=0,
        b_expr="cos(frame * 0.1) * 127 + 128",
        speed=30
    )
    for _ in range(5):
        print(v1.render((0, 0, 0), 0))

    print("\n=== Version 2: Pure Python ===")
    v2 = PurePythonRenderer('''
def render(prev, t):
    # math module is pre-injected, no import needed
    h = (t * 0.5) % 1.0
    i = int(h * 6)
    f = h * 6 - i
    v = 1.0
    s = 1.0
    p = v * (1 - s)
    q = v * (1 - f * s)
    t_val = v * (1 - (1 - f) * s)
    i = i % 6
    if i == 0: r, g, b = v, t_val, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t_val
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t_val, p, v
    else: r, g, b = v, p, q
    return (int(r*255), int(g*255), int(b*255)), 30
''')
    for t in [0, 0.5, 1.0, 1.5, 2.0]:
        print(v2.render((0, 0, 0), t))

    print("\n=== Version 3: Stdlib ===")
    v3 = StdlibRenderer('''
def render(prev, t):
    return hsv(t * 0.5 % 1, 1, 1), 30
''')
    for t in [0, 0.5, 1.0, 1.5, 2.0]:
        print(v3.render((0, 0, 0), t))

    print("\n=== Version 3: Brighter ===")
    v3_bright = StdlibRenderer('''
def render(prev, t):
    r, g, b = prev
    return rgb(r * 1.5, g * 1.5, b * 1.5), None
''')
    print(v3_bright.render((100, 50, 25), 0))
    print(v3_bright.render((200, 100, 50), 0))
