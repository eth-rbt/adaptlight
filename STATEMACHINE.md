# AdaptLight State Machine Documentation

## Overview

AdaptLight uses a state machine architecture to control LED lights based on button presses and voice commands. The system transitions between different states (like "off", "on", "color", "animation") based on rules you define.

## Core Concepts

### States

States represent the current condition of the light system. There are four built-in states:

| State | Description | Parameters |
|-------|-------------|------------|
| `off` | Light is turned off | None |
| `on` | Light is on with default white color | None |
| `color` | Light displays a static color | `{r, g, b}` - RGB values (0-255) |
| `animation` | Light displays an animated pattern | `{r, g, b, speed}` - RGB expressions + speed in ms |

### Transitions

Transitions are events that can trigger a state change:

| Transition | Description |
|------------|-------------|
| `button_click` | Single press of the button |
| `button_double_click` | Two quick presses |
| `button_hold` | Press and hold the button |
| `button_release` | Release after holding |
| `voice_command` | Triggered by voice input |

### Rules

Rules define how the system behaves. Each rule has the format:

```
state1 --[transition]--> state2
```

**Example:** `off --[button_click]--> on`

This means: "When in the off state and button_click happens, go to on state"

#### Rule Structure

A complete rule includes:

- **state1**: Starting state (where you are now)
- **state1Param**: Parameters for state1 (usually `null`)
- **transition**: The event that triggers the rule
- **state2**: Destination state (where to go)
- **state2Param**: Parameters for state2 (e.g., color values)
- **condition** (optional): Expression that must be true for rule to activate
- **action** (optional): Code to run before transitioning

## Working with Colors

### Static Colors

For the `color` state, specify RGB values (0-255):

```python
{
    "r": 255,  # Red
    "g": 0,    # Green
    "b": 0     # Blue
}
```

**Common Colors:**
- Red: `{r: 255, g: 0, b: 0}`
- Green: `{r: 0, g: 255, b: 0}`
- Blue: `{r: 0, g: 0, b: 255}`
- Yellow: `{r: 255, g: 255, b: 0}`
- Purple: `{r: 128, g: 0, b: 128}`
- White: `{r: 255, g: 255, b: 255}`

### Dynamic Color Expressions

Instead of static numbers, you can use expressions:

```python
{
    "r": "random()",           # Random red value
    "g": "min(g + 30, 255)",   # Increase green by 30
    "b": "b"                   # Keep blue the same
}
```

**Available Variables:**
- `r`, `g`, `b` - Current RGB values
- `random()` - Returns random number 0-255

**Available Functions:**
- Math: `min()`, `max()`, `abs()`, `floor()`, `ceil()`, `round()`, `sqrt()`, `pow()`
- Trig: `sin()`, `cos()`, `tan()`
- Constants: `PI`, `E`

**Examples:**
- Brighten: `{"r": "min(r + 30, 255)", "g": "min(g + 30, 255)", "b": "min(b + 30, 255)"}`
- Darken: `{"r": "max(r - 30, 0)", "g": "max(g - 30, 0)", "b": "max(b - 30, 0)"}`
- Cycle colors: `{"r": "b", "g": "r", "b": "g"}`

## Working with Animations

Animations continuously update colors based on expressions:

```python
{
    "r": "abs(sin(frame * 0.05)) * 255",
    "g": "abs(sin(frame * 0.05)) * 255",
    "b": "abs(sin(frame * 0.05)) * 255",
    "speed": 50  # Update interval in milliseconds
}
```

**Animation Variables:**
- `r`, `g`, `b` - Current RGB values (updated each frame)
- `frame` - Frame counter (increments each update)
- `t` - Time in milliseconds since animation started

**Examples:**

### Pulsing White
```python
{
    "r": "abs(sin(frame * 0.05)) * 255",
    "g": "abs(sin(frame * 0.05)) * 255",
    "b": "abs(sin(frame * 0.05)) * 255",
    "speed": 50
}
```

### Rainbow
```python
{
    "r": "(frame * 2) % 256",
    "g": "abs(sin(frame * 0.1)) * 255",
    "b": "abs(cos(frame * 0.1)) * 255",
    "speed": 50
}
```

### Rotating Colors
```python
{
    "r": "b",
    "g": "r",
    "b": "g",
    "speed": 200
}
```

## Conditions and Actions

### Conditions

Conditions determine if a rule should activate. They must evaluate to `true`:

```python
"condition": "time.hour >= 20"  # Only after 8 PM
```

**Available in Conditions:**
- `getData(key)` - Get stored value
- `time.hour` - Current hour (0-23)
- `time.minute` - Current minute (0-59)
- `time.second` - Current second (0-59)
- `time.dayOfWeek` - Day of week (0=Sunday)
- All math functions

### Actions

Actions run before the state transition. Often used to update counters:

```python
"action": "setData('counter', getData('counter') - 1)"
```

**Available in Actions:**
- `getData(key)` - Get value
- `setData(key, value)` - Set value
- `getTime()` - Get current time

## Example Use Cases

### Simple Toggle

**Goal:** Click to turn on/off

```python
[
    {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": null},
    {"state1": "on", "transition": "button_click", "state2": "off", "state2Param": null}
]
```

### Colored Light

**Goal:** Click for blue light, click again to turn off

```python
[
    {"state1": "off", "transition": "button_click", "state2": "color",
     "state2Param": {"r": 0, "g": 0, "b": 255}},
    {"state1": "color", "transition": "button_click", "state2": "off",
     "state2Param": null}
]
```

### Multiple Buttons

**Goal:** Click for red, double-click for blue

```python
[
    {"state1": "off", "transition": "button_click", "state2": "color",
     "state2Param": {"r": 255, "g": 0, "b": 0}},
    {"state1": "color", "transition": "button_click", "state2": "off",
     "state2Param": null},
    {"state1": "off", "transition": "button_double_click", "state2": "color",
     "state2Param": {"r": 0, "g": 0, "b": 255}},
    {"state1": "color", "transition": "button_double_click", "state2": "off",
     "state2Param": null}
]
```

### Hold for Animation

**Goal:** Hold to start rainbow, release to stop

```python
[
    {"state1": "off", "transition": "button_hold", "state2": "animation",
     "state2Param": {
         "r": "(frame * 2) % 256",
         "g": "abs(sin(frame * 0.1)) * 255",
         "b": "abs(cos(frame * 0.1)) * 255",
         "speed": 50
     }},
    {"state1": "animation", "transition": "button_release", "state2": "off",
     "state2Param": null}
]
```

### Counter-Based Behavior

**Goal:** Next 5 clicks are random colors, then turn off

```python
[
    {"state1": "off", "transition": "button_click",
     "condition": "getData('counter') === undefined",
     "action": "setData('counter', 4)",
     "state2": "color",
     "state2Param": {"r": "random()", "g": "random()", "b": "random()"}},

    {"state1": "color", "transition": "button_click",
     "condition": "getData('counter') > 0",
     "action": "setData('counter', getData('counter') - 1)",
     "state2": "color",
     "state2Param": {"r": "random()", "g": "random()", "b": "random()"}},

    {"state1": "color", "transition": "button_click",
     "condition": "getData('counter') === 0",
     "state2": "off",
     "state2Param": null}
]
```

### Time-Based Rules

**Goal:** Blue light only after 8 PM

```python
[
    {"state1": "off", "transition": "button_click",
     "condition": "time.hour >= 20",
     "state2": "color",
     "state2Param": {"r": 0, "g": 0, "b": 255}}
]
```

## Voice Control

You can use voice commands to control the light:

### Creating Rules
- "Click to turn on red light"
- "Hold for rainbow animation"
- "Double click for random color"

### Modifying Rules
- "Make it blue" (changes existing color)
- "Make it faster" (changes animation speed)
- "Change to double click instead"

### Immediate Actions
- "Turn red now" (changes state immediately)
- "Turn off"

### Managing Rules
- "Delete all rules"
- "Reset to default"
- "Remove the double click rule"

## Tool Reference

When using the API or voice commands, these tools are available:

### append_rules

Add new rules to the system.

```python
append_rules({
    "rules": [
        {"state1": "off", "transition": "button_click", "state2": "on", "state2Param": null}
    ]
})
```

### delete_rules

Remove rules by index or criteria.

```python
# Delete by index
delete_rules({"indices": [0, 2]})

# Delete all click rules
delete_rules({"transition": "button_click"})

# Delete everything
delete_rules({"delete_all": true})
```

### set_state

Change state immediately.

```python
# Turn on red light now
set_state({"state": "color", "params": {"r": 255, "g": 0, "b": 0}})

# Turn off
set_state({"state": "off"})
```

### manage_variables

Manage global variables.

```python
# Set variables
manage_variables({"action": "set", "variables": {"counter": 5, "mode": "party"}})

# Delete variables
manage_variables({"action": "delete", "keys": ["counter"]})

# Clear all
manage_variables({"action": "clear_all"})
```

### reset_rules

Reset to default (simple on/off toggle).

```python
reset_rules()
```

## Tips and Best Practices

1. **Always include toggle-off rules**: If you create a rule to turn something on, create another to turn it off.

2. **Use appropriate speeds**:
   - Fast animations: 20-50ms
   - Medium: 50-100ms
   - Slow: 100-300ms

3. **Test conditions carefully**: Time conditions use 24-hour format (0-23 for hours).

4. **Keep expressions simple**: Complex expressions can slow down animations.

5. **Use counters for sequences**: Great for "N clicks then do something" behaviors.

6. **Preserve colors carefully**: Use `{"r": "r", "g": "g", "b": "b"}` to keep current color.

7. **Parameter requirements**:
   - `on` and `off` states: Must use `null` for params
   - `color` state: Must provide `{r, g, b}`
   - `animation` state: Must provide `{r, g, b, speed}`

## Troubleshooting

**Light doesn't respond to button:**
- Check that rules exist for that transition
- Verify you're in the expected starting state

**Animation is too fast/slow:**
- Adjust the `speed` parameter (higher = slower)
- Typical range: 20-300ms

**Color expressions not working:**
- Check that variables are quoted: `"r"` not `r`
- Verify all functions are available
- Test expressions individually

**Rules not triggering:**
- Check conditions are met
- Verify you're in the correct starting state (state1)
- Look for conflicting rules

**Want to start over:**
- Use voice command: "Reset everything"
- Or use API: `reset_rules()`
