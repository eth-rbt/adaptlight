# Implementation Plan: New State Representations

## Overview

Integrate three state representation versions into AdaptLight:
1. Remove `then`/`duration_ms` from states
2. Add `state_complete` transition triggered by renderer
3. Add config switching between representation versions
4. Create StateExecutor to manage rendering
5. Create comprehensive tests

---

## Phase 1: Remove `then` from State, Add `state_complete` Transition

### 1.1 Update `brain/core/state.py`

**Remove these fields from `State.__init__`:**
- `duration_ms`
- `then`

**Add new field:**
- `code: str` - Python code for pure_python/stdlib modes (optional, None for original mode)

**Updated State class:**
```python
class State:
    def __init__(self, name: str, r=None, g=None, b=None, speed=None,
                 code=None, description: str = '', voice_reactive=None):
        self.name = name
        self.r = r
        self.g = g
        self.b = b
        self.speed = speed
        self.code = code  # NEW: Python code for pure_python/stdlib
        self.voice_reactive = voice_reactive or {}
        self.description = description or self._generate_description()
```

**Update these methods:**
- `_generate_description()` - remove duration_ms/then references
- `get_params()` - remove duration_ms/then, add code

### 1.2 Update `brain/core/rule.py`

**Document new transition type in docstring:**
- `state_complete` - fired when a renderer returns `next_ms=0`

**Example rules:**
```python
# When "blink" state completes, go to "on"
{"state1": "blink", "transition": "state_complete", "state2": "on"}

# When any state completes, go to "off" (wildcard)
{"state1": "*", "transition": "state_complete", "state2": "off"}

# With condition
{"state1": "fade", "transition": "state_complete", "state2": "party",
 "condition": "getData('mode') == 'party'"}
```

### 1.3 No changes needed to `state_machine.py` for this phase

The existing `execute_transition("state_complete")` will work with current rule matching logic.

---

## Phase 2: Create StateExecutor

### 2.1 Create `brain/core/state_executor.py` (NEW FILE)

**Purpose:** Wrapper that manages rendering for all three representation versions.

```python
"""
StateExecutor - manages state rendering across representation versions.

Handles:
- Compiling state code into renderers
- Calling render(prev, t) and tracking timing
- Signaling state_complete when next_ms=0
"""

from brain.utils.state_representations import (
    OriginalRenderer, PurePythonRenderer, StdlibRenderer
)

class StateExecutor:
    def __init__(self, representation_version: str = "stdlib"):
        """
        Args:
            representation_version: "original", "pure_python", or "stdlib"
        """
        self.version = representation_version
        self.current_renderer = None
        self.state_start_time = None
        self.prev_rgb = (0, 0, 0)
        self.on_state_complete = None  # Callback when next_ms=0

    def set_on_state_complete(self, callback):
        """Set callback for when renderer signals completion (next_ms=0)."""
        self.on_state_complete = callback

    def compile_state(self, state) -> bool:
        """
        Compile a state into a renderer.

        For original: uses r/g/b/speed fields
        For pure_python/stdlib: uses code field

        Returns True if successful.
        """
        ...

    def enter_state(self, state, initial_rgb=(0, 0, 0)):
        """
        Called when entering a new state.
        Compiles the state and resets timing.
        """
        self.compile_state(state)
        self.state_start_time = time.time()
        self.prev_rgb = initial_rgb

    def render(self) -> tuple:
        """
        Render current frame.

        Returns:
            ((r, g, b), next_ms) or None if no renderer

        If next_ms == 0, calls on_state_complete callback.
        """
        if not self.current_renderer:
            return None

        t = time.time() - self.state_start_time
        rgb, next_ms = self.current_renderer.render(self.prev_rgb, t)
        self.prev_rgb = rgb

        if next_ms == 0 and self.on_state_complete:
            self.on_state_complete()

        return rgb, next_ms
```

### 2.2 Update `brain/utils/state_representations.py`

**Add completion signal to docstring:**
```python
"""
Return values for render(prev, t):
- ((r, g, b), next_ms > 0)  → call again in next_ms milliseconds
- ((r, g, b), None)         → static, no more updates needed
- ((r, g, b), 0)            → STATE COMPLETE, trigger state_complete transition
"""
```

---

## Phase 3: Integrate StateExecutor into State Machine

### 3.1 Update `brain/core/state_machine.py`

**Add to `__init__`:**
```python
def __init__(self, debug=False, default_rules=True, representation_version="stdlib"):
    ...
    self.state_executor = StateExecutor(representation_version)
    self.state_executor.set_on_state_complete(self._on_state_complete)
    self.render_timer = None  # Timer for next render call
```

**Add new methods:**
```python
def _on_state_complete(self):
    """Called when renderer returns next_ms=0."""
    print(f"State '{self.current_state}' completed, firing state_complete transition")
    self.execute_transition("state_complete")

def _schedule_render(self, delay_ms: int):
    """Schedule next render call."""
    if self.render_timer:
        self.render_timer.cancel()

    if delay_ms and delay_ms > 0:
        self.render_timer = threading.Timer(
            delay_ms / 1000.0,
            self._do_render
        )
        self.render_timer.start()

def _do_render(self):
    """Execute render and schedule next if needed."""
    result = self.state_executor.render()
    if result:
        rgb, next_ms = result
        # Send RGB to output (via callback)
        if self._on_render_callback:
            self._on_render_callback(rgb)
        # Schedule next render
        if next_ms and next_ms > 0:
            self._schedule_render(next_ms)

def _cancel_render(self):
    """Cancel any pending render."""
    if self.render_timer:
        self.render_timer.cancel()
        self.render_timer = None
```

**Update `set_state`:**
```python
def set_state(self, state_name: str, params=None):
    # Cancel any pending renders from previous state
    self._cancel_render()

    self.current_state = state_name
    self.current_state_params = params

    state_object = self.get_state_object(state_name)
    if state_object:
        # Initialize executor with new state
        self.state_executor.enter_state(state_object, self.prev_rgb)

        # Do initial render
        self._do_render()

        # Execute onEnter callback
        state_object.enter(params)
```

---

## Phase 3.5: Update Prompts for Each Representation

### 3.5.1 Update `brain/prompts/agent/agent_prompt_with_examples.py`

The prompt should be generated dynamically based on representation version:

**Original mode:**
```
### States
- **createState(name, r, g, b, speed?, description?)** - Create a light state
  - r, g, b: 0-255 for static, or expression string for animation
  - speed: null=static, or milliseconds for animation frame rate
  - Available functions: sin, cos, abs, min, max, floor, ceil, random, PI
  - Example: r="sin(frame * 0.05) * 127 + 128"
```

**Pure Python mode:**
```
### States
- **createState(name, code, description?)** - Create a light state
  - code: Python function that returns ((r,g,b), next_ms)
  - next_ms > 0: animation continues
  - next_ms = None: static state
  - next_ms = 0: state complete, triggers state_complete transition
  - Available: math module, basic Python (no imports)

  Example:
  createState(name="rainbow", code='''
def render(prev, t):
    h = (t * 0.1) % 1.0
    # ... HSV to RGB conversion ...
    return (r, g, b), 30
''')
```

**Stdlib mode:**
```
### States
- **createState(name, code, description?)** - Create a light state
  - code: Python function using stdlib helpers

  Available functions:
  - Color: hsv(h,s,v), rgb(r,g,b), lerp_color(c1,c2,t)
  - Math: sin, cos, tan, abs, min, max, floor, ceil, sqrt, pow, clamp, lerp, map_range
  - Easing: ease_in(t), ease_out(t), ease_in_out(t)
  - Random: random(), randint(lo,hi)
  - Constants: PI, E

  Return values:
  - ((r,g,b), next_ms) where next_ms > 0 = animate, None = static, 0 = complete

  Example:
  createState(name="rainbow", code='''
def render(prev, t):
    return hsv(t * 0.1 % 1, 1, 1), 30
''')

  Example (brighten current color):
  createState(name="brighter", code='''
def render(prev, t):
    r, g, b = prev
    return rgb(r * 1.3, g * 1.3, b * 1.3), None
''')

  Example (blink 3 times then stay on):
  createState(name="blink_then_on", code='''
def render(prev, t):
    if t >= 0.6:  # 3 blinks done
        return (255, 255, 255), 0  # Signal complete
    on = int(t * 10) % 2 == 0
    return ((255, 255, 255) if on else (0, 0, 0)), 30
''')
```

### 3.5.2 Update `getDocs()` function

Add representation-specific documentation topics:
- `getDocs("states_original")` - original r/g/b format
- `getDocs("states_python")` - pure Python format
- `getDocs("states_stdlib")` - stdlib format with all available functions

### 3.5.3 Update `createState` tool

Modify the tool to accept both formats:
```python
def create_state(name, r=None, g=None, b=None, speed=None, code=None, description=None):
    """
    Create a state.

    For original mode: provide r, g, b, speed
    For pure_python/stdlib mode: provide code
    """
    if code is not None:
        state = State(name=name, code=code, description=description)
    else:
        state = State(name=name, r=r, g=g, b=b, speed=speed, description=description)
```

### 3.5.4 Add `state_complete` to rule documentation

Update prompts to explain the new transition type:
```
### Rules
- **appendRules(rules[])** - Add rules. Each rule:
  - on: trigger types:
    - button_click, button_hold, button_release, button_double_click
    - timer, interval, schedule
    - state_complete (fires when state's render returns next_ms=0)

  Example (auto-transition after animation):
  appendRules([{
      "from": "blink_3x",
      "on": "state_complete",
      "to": "on"
  }])
```

---

## Phase 4: Add Config File Support

### 4.1 Update `apps/web/config.yaml`

```yaml
# AdaptLight Web Configuration

# Brain settings
brain:
  mode: agent
  model: claude-sonnet-4-5-20250929
  prompt_variant: examples
  max_turns: 10
  verbose: false

# NEW: State representation settings
representation:
  # Options: "original", "pure_python", "stdlib"
  version: stdlib

# API keys (loaded from environment or set here)
anthropic:
  api_key: ${ANTHROPIC_API_KEY}

openai:
  api_key: ${OPENAI_API_KEY}

# Supabase (loaded from environment)
supabase:
  url: ${SUPABASE_URL}
  anon_key: ${SUPABASE_ANON_KEY}

# Server settings
server:
  host: 0.0.0.0
  port: 3000
  debug: false

# Storage
storage:
  dir: data/storage
```

### 4.2 Update `apps/web/main.py`

```python
def create_app(config_path: str = None) -> Flask:
    config = load_config(config_path)

    # Get representation version from config
    representation_version = config.get('representation', {}).get('version', 'stdlib')

    smgen_config = {
        'mode': config['brain']['mode'],
        'model': config['brain']['model'],
        'prompt_variant': config['brain']['prompt_variant'],
        'max_turns': config['brain'].get('max_turns', 10),
        'verbose': config['brain'].get('verbose', False),
        'anthropic_api_key': config['anthropic']['api_key'],
        'openai_api_key': config['openai']['api_key'],
        'storage_dir': config.get('storage', {}).get('dir', 'data/storage'),
        'representation_version': representation_version,  # NEW
    }
    smgen = SMgenerator(smgen_config)
    ...
```

### 4.3 Update `brain/__init__.py` (SMgenerator)

Pass `representation_version` to StateMachine constructor.

---

## Phase 5: Create Tests

### 5.1 Create `brain/utils/test_state_representations.py`

```python
"""
Tests for the three state representation versions.
"""
import unittest
from brain.utils.state_representations import (
    OriginalRenderer, PurePythonRenderer, StdlibRenderer
)

class TestOriginalRenderer(unittest.TestCase):
    def test_static_color(self):
        """Static color returns correct RGB and next_ms=speed."""
        renderer = OriginalRenderer(r_expr=255, g_expr=0, b_expr=0, speed=None)
        rgb, next_ms = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 0, 0))
        self.assertIsNone(next_ms)

    def test_animation(self):
        """Animation returns next_ms=speed."""
        renderer = OriginalRenderer(
            r_expr="sin(frame * 0.1) * 127 + 128",
            g_expr=0, b_expr=0, speed=30
        )
        rgb, next_ms = renderer.render((0, 0, 0), 0)
        self.assertEqual(next_ms, 30)

    def test_uses_prev_value(self):
        """Expression can access previous r/g/b values."""
        renderer = OriginalRenderer(r_expr="r + 10", g_expr="g", b_expr="b", speed=None)
        rgb, _ = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (110, 50, 25))


class TestPurePythonRenderer(unittest.TestCase):
    def test_basic_function(self):
        """Basic render function works."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    return (255, 128, 64), None
''')
        rgb, next_ms = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 128, 64))
        self.assertIsNone(next_ms)

    def test_uses_prev(self):
        """Can use prev parameter."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    r, g, b = prev
    return (min(255, r + 50), g, b), None
''')
        rgb, _ = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (150, 50, 25))

    def test_uses_time(self):
        """Can use t parameter."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    return (int(t * 100) % 256, 0, 0), 30
''')
        rgb, _ = renderer.render((0, 0, 0), 2.5)
        self.assertEqual(rgb[0], 250)

    def test_state_complete_signal(self):
        """Returns next_ms=0 to signal completion."""
        renderer = PurePythonRenderer('''
def render(prev, t):
    if t > 1.0:
        return (255, 255, 255), 0  # Done!
    return (0, 0, 0), 30
''')
        _, next_ms = renderer.render((0, 0, 0), 0.5)
        self.assertEqual(next_ms, 30)
        _, next_ms = renderer.render((0, 0, 0), 1.5)
        self.assertEqual(next_ms, 0)  # Completion signal


class TestStdlibRenderer(unittest.TestCase):
    def test_hsv_function(self):
        """hsv() helper works."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return hsv(0, 1, 1), None  # Red
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 0, 0))

    def test_rgb_clamp(self):
        """rgb() clamps values to 0-255."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return rgb(300, -50, 128), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (255, 0, 128))

    def test_lerp(self):
        """lerp() interpolation works."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = lerp(0, 100, 0.5)
    return (int(v), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 50)

    def test_lerp_color(self):
        """lerp_color() interpolates between colors."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return lerp_color((0, 0, 0), (100, 200, 50), 0.5), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb, (50, 100, 25))

    def test_easing_functions(self):
        """Easing functions work."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = ease_in(0.5)
    return (int(v * 255), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 63)  # 0.25 * 255

    def test_math_functions(self):
        """Math functions available."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = sin(PI / 2) * 255
    return (int(v), 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 255)

    def test_random_functions(self):
        """Random functions available."""
        renderer = StdlibRenderer('''
def render(prev, t):
    v = randint(100, 100)  # Always 100
    return (v, 0, 0), None
''')
        rgb, _ = renderer.render((0, 0, 0), 0)
        self.assertEqual(rgb[0], 100)


class TestErrorHandling(unittest.TestCase):
    def test_syntax_error_fallback(self):
        """Syntax error returns prev color."""
        renderer = StdlibRenderer('''
def render(prev, t)
    return (255, 0, 0), None  # Missing colon
''')
        rgb, next_ms = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (100, 50, 25))
        self.assertIsNone(next_ms)

    def test_runtime_error_fallback(self):
        """Runtime error returns prev color."""
        renderer = StdlibRenderer('''
def render(prev, t):
    return (1/0, 0, 0), None  # Division by zero
''')
        rgb, _ = renderer.render((100, 50, 25), 0)
        self.assertEqual(rgb, (100, 50, 25))


class TestEquivalentOutput(unittest.TestCase):
    def test_all_versions_same_output(self):
        """All three versions produce same output for equivalent code."""
        # Static red
        orig = OriginalRenderer(r_expr=255, g_expr=0, b_expr=0, speed=None)
        pure = PurePythonRenderer('''
def render(prev, t):
    return (255, 0, 0), None
''')
        stdlib = StdlibRenderer('''
def render(prev, t):
    return (255, 0, 0), None
''')

        prev = (0, 0, 0)
        t = 0

        self.assertEqual(orig.render(prev, t)[0], (255, 0, 0))
        self.assertEqual(pure.render(prev, t)[0], (255, 0, 0))
        self.assertEqual(stdlib.render(prev, t)[0], (255, 0, 0))


if __name__ == '__main__':
    unittest.main()
```

### 5.2 Create `brain/utils/test_state_complete.py`

```python
"""
Tests for state_complete transition mechanism.
"""
import unittest
import time
from unittest.mock import Mock, patch
from brain.core.state_executor import StateExecutor
from brain.core.state import State

class TestStateComplete(unittest.TestCase):
    def test_callback_on_completion(self):
        """on_state_complete callback fires when next_ms=0."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        # State that completes immediately
        state = State(name="done", code='''
def render(prev, t):
    return (255, 255, 255), 0  # Complete immediately
''')
        executor.enter_state(state)
        executor.render()

        callback.assert_called_once()

    def test_no_callback_on_animation(self):
        """Callback doesn't fire when next_ms > 0."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        state = State(name="animate", code='''
def render(prev, t):
    return (255, 0, 0), 30  # Keep animating
''')
        executor.enter_state(state)
        executor.render()

        callback.assert_not_called()

    def test_no_callback_on_static(self):
        """Callback doesn't fire when next_ms=None (static)."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        state = State(name="static", code='''
def render(prev, t):
    return (255, 0, 0), None  # Static
''')
        executor.enter_state(state)
        executor.render()

        callback.assert_not_called()

    def test_completion_after_duration(self):
        """State completes after animation finishes."""
        executor = StateExecutor("stdlib")
        callback = Mock()
        executor.set_on_state_complete(callback)

        # Blink that completes after 0.5 seconds
        state = State(name="blink", code='''
def render(prev, t):
    if t >= 0.5:
        return (255, 255, 255), 0  # Done
    on = int(t * 10) % 2 == 0
    return ((255, 255, 255) if on else (0, 0, 0)), 30
''')
        executor.enter_state(state)

        # Simulate time passing
        executor.render()  # t ~ 0
        callback.assert_not_called()

        # Manually set start time to simulate 0.6s elapsed
        executor.state_start_time = time.time() - 0.6
        executor.render()  # t ~ 0.6
        callback.assert_called_once()


class TestStateCompleteIntegration(unittest.TestCase):
    def test_rule_fires_on_completion(self):
        """state_complete transition fires correct rule."""
        from brain.core.state_machine import StateMachine

        sm = StateMachine(default_rules=False, representation_version="stdlib")

        # Add states
        sm.states.add_state(State(name="blink", code='''
def render(prev, t):
    if t >= 0.1:
        return (255, 255, 255), 0  # Complete quickly for test
    return (255, 255, 255), 10
'''))
        sm.states.add_state(State(name="on", code='''
def render(prev, t):
    return (255, 255, 255), None
'''))

        # Add rule: blink -> on when complete
        sm.add_rule({
            "state1": "blink",
            "transition": "state_complete",
            "state2": "on"
        })

        # Enter blink state
        sm.set_state("blink")
        self.assertEqual(sm.current_state, "blink")

        # Wait for completion
        time.sleep(0.15)

        # Should have transitioned to "on"
        self.assertEqual(sm.current_state, "on")


if __name__ == '__main__':
    unittest.main()
```

### 5.3 Create `brain/utils/test_config.py`

```python
"""
Tests for configuration loading and representation switching.
"""
import unittest
import tempfile
import os
import yaml

class TestConfigLoading(unittest.TestCase):
    def test_default_representation(self):
        """Default representation is stdlib."""
        from brain.core.state_executor import StateExecutor
        executor = StateExecutor()
        self.assertEqual(executor.version, "stdlib")

    def test_config_sets_representation(self):
        """Config file sets representation version."""
        config = {
            'representation': {
                'version': 'pure_python'
            }
        }

        # Write temp config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        try:
            with open(config_path) as f:
                loaded = yaml.safe_load(f)

            version = loaded.get('representation', {}).get('version', 'stdlib')
            self.assertEqual(version, 'pure_python')
        finally:
            os.unlink(config_path)

    def test_invalid_version_fallback(self):
        """Invalid version falls back to stdlib."""
        from brain.core.state_executor import StateExecutor
        executor = StateExecutor("invalid_version")
        # Should still work, defaulting to stdlib behavior
        # (implementation detail - may want to warn)


class TestRepresentationSwitching(unittest.TestCase):
    def test_original_mode(self):
        """Original mode uses r/g/b expressions."""
        from brain.core.state_executor import StateExecutor
        from brain.core.state import State

        executor = StateExecutor("original")
        state = State(name="red", r=255, g=0, b=0)
        executor.enter_state(state)
        rgb, _ = executor.render()
        self.assertEqual(rgb, (255, 0, 0))

    def test_stdlib_mode(self):
        """Stdlib mode uses code field."""
        from brain.core.state_executor import StateExecutor
        from brain.core.state import State

        executor = StateExecutor("stdlib")
        state = State(name="red", code='''
def render(prev, t):
    return (255, 0, 0), None
''')
        executor.enter_state(state)
        rgb, _ = executor.render()
        self.assertEqual(rgb, (255, 0, 0))


if __name__ == '__main__':
    unittest.main()
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `brain/core/state.py` | MODIFY | Remove `then`/`duration_ms`, add `code` field |
| `brain/core/rule.py` | MODIFY | Document `state_complete` transition in docstring |
| `brain/core/state_executor.py` | CREATE | New file - manages rendering for all versions |
| `brain/core/state_machine.py` | MODIFY | Add StateExecutor, render scheduling, `_on_state_complete` |
| `brain/utils/state_representations.py` | MODIFY | Add `next_ms=0` completion signal to docstring |
| `apps/web/config.yaml` | MODIFY | Add `representation.version` setting |
| `apps/web/main.py` | MODIFY | Pass representation version to SMgenerator |
| `brain/__init__.py` | MODIFY | Pass representation version to StateMachine |
| `brain/prompts/agent/agent_prompt_with_examples.py` | MODIFY | Dynamic prompt based on representation |
| `brain/tools/` (create_state) | MODIFY | Accept both r/g/b and code formats |
| `brain/utils/test_state_representations.py` | CREATE | Tests for three renderers |
| `brain/utils/test_state_complete.py` | CREATE | Tests for completion mechanism |
| `brain/utils/test_config.py` | CREATE | Tests for config loading |

---

## Implementation Order

### Step 1: Core State Changes
1. Update `brain/core/state.py` - remove `then`/`duration_ms`, add `code`
2. Update `brain/core/rule.py` - document `state_complete`

### Step 2: StateExecutor
1. Create `brain/core/state_executor.py`
2. Update `brain/utils/state_representations.py` docstring

### Step 3: State Machine Integration
1. Update `brain/core/state_machine.py` - add executor, render scheduling

### Step 4: Update Prompts & Tools
1. Update `brain/prompts/agent/agent_prompt_with_examples.py` - dynamic prompt generation
2. Update `getDocs()` - add representation-specific documentation
3. Update `createState` tool - accept both r/g/b and code formats
4. Document `state_complete` transition in prompts

### Step 5: Config Support
1. Update `apps/web/config.yaml`
2. Update `apps/web/main.py`
3. Update `brain/__init__.py` (SMgenerator)

### Step 6: Tests
1. Create `brain/utils/test_state_representations.py`
2. Create `brain/utils/test_state_complete.py`
3. Create `brain/utils/test_config.py`
4. Run all tests and fix issues

---

## Completion Signal Summary

```
next_ms > 0   → Animation continues, call render() again in next_ms milliseconds
next_ms = None → Static state, no more render calls needed
next_ms = 0   → STATE COMPLETE, fire "state_complete" transition
```

When `next_ms = 0`:
1. StateExecutor calls `on_state_complete` callback
2. StateMachine receives callback, calls `execute_transition("state_complete")`
3. Rule matching finds rules where `transition == "state_complete"` AND `state1 == current_state`
4. First matching rule executes, transitioning to `state2`
