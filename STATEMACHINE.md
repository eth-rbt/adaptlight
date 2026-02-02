# AdaptLight State Machine Documentation

## Overview

AdaptLight uses a state machine architecture to control LED lights based on button presses, voice commands, and time-based triggers. The system is split into two main components:

- **brain**: Shared library containing the state machine core, AI processing, SMgenerator, and tools
- **Apps**: Platform-specific implementations (RASPi, Web, Eval)

## Architecture

```
adaptlight/
├── brain/           # Shared library
│   ├── core/        # StateMachine, State, Rule, Memory, Pipeline
│   ├── tools/       # ToolRegistry (27+ tools for AI agent)
│   ├── processing/  # AgentExecutor (Claude), CommandParser (OpenAI)
│   └── prompts/     # System prompts for AI
├── apps/
│   ├── raspi/       # Raspberry Pi app (hardware, voice)
│   ├── web/         # Flask web interface
│   └── eval/        # Test runner
└── scripts/         # Deployment scripts
```

## Core Concepts

### States

States represent LED configurations with unified parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Unique identifier |
| `r` | int/string | Red value (0-255) or expression |
| `g` | int/string | Green value (0-255) or expression |
| `b` | int/string | Blue value (0-255) or expression |
| `speed` | int | Animation interval in ms (None = static) |
| `duration_ms` | int | Auto-transition after this duration |
| `then` | string | State to transition to when duration expires |
| `voice_reactive` | dict | Mic-reactive brightness config |

**Built-in states**: `off`, `on`

**Creating states via AI**:
```
"Create a state called sunset with orange fading to red"
"Make a breathing blue animation called ocean"
```

### Rules

Rules define state transitions:

```
state1 --[transition]--> state2
```

**Rule structure**:
- `state1`: Starting state (or `*` for any state)
- `transition`: Event that triggers the rule
- `state2`: Destination state
- `condition`: Optional expression that must be true
- `action`: Optional code to run before transitioning
- `priority`: Higher priority rules are evaluated first
- `pipeline`: Optional pipeline to execute on transition

### Transitions

| Transition | Description |
|------------|-------------|
| `button_click` | Single button press |
| `button_double_click` | Two quick presses |
| `button_hold` | Press and hold |
| `button_release` | Release after holding |
| `voice_command` | Voice input trigger |
| `timer` | One-time delayed trigger |
| `interval` | Recurring trigger |
| `schedule` | Time-of-day trigger |

### Time-based Triggers

Rules can use time-based transitions with `trigger_config`:

```python
# Timer (one-shot)
{
    "state1": "alert",
    "transition": "timer",
    "state2": "off",
    "trigger_config": {"delay_ms": 5000, "auto_cleanup": True}
}

# Interval (recurring)
{
    "state1": "*",
    "transition": "interval",
    "state2": "pulse",
    "trigger_config": {"delay_ms": 60000, "repeat": True}
}

# Schedule (time-of-day)
{
    "state1": "*",
    "transition": "schedule",
    "state2": "night_mode",
    "trigger_config": {"hour": 22, "minute": 0, "repeat_daily": True}
}
```

## Working with Colors

### Static Colors

```python
{"r": 255, "g": 0, "b": 0}  # Red
{"r": 0, "g": 255, "b": 0}  # Green
{"r": 0, "g": 0, "b": 255}  # Blue
{"r": 255, "g": 255, "b": 255}  # White
```

### Dynamic Expressions

Color values can be expressions evaluated each frame:

```python
{
    "r": "abs(sin(frame * 0.05)) * 255",  # Pulsing
    "g": "min(g + 30, 255)",              # Gradual increase
    "b": "random()"                        # Random
}
```

**Available variables**: `r`, `g`, `b`, `frame`, `t` (time in ms)

**Available functions**: `sin`, `cos`, `abs`, `min`, `max`, `floor`, `ceil`, `round`, `sqrt`, `pow`, `random`

## Conditions and Actions

### Conditions

Expressions that determine if a rule should fire:

```python
"condition": "getData('counter') > 0"
"condition": "getTime()['hour'] >= 20"
"condition": "getData('mode') == 'party'"
```

### Actions

Code executed before state transition:

```python
"action": "setData('counter', getData('counter') - 1)"
"action": "setData('last_press', getTime()['timestamp'])"
```

**Available functions**:
- `getData(key, default)` - Get stored value
- `setData(key, value)` - Store value
- `getTime()` - Returns `{hour, minute, second, weekday, is_weekend, timestamp}`

## SMgenerator Interface

The SMgenerator class provides a unified interface for apps:

```python
from brain import SMgenerator

smgen = SMgenerator({
    'mode': 'agent',  # or 'parser'
    'model': 'claude-haiku-4-5',
    'anthropic_api_key': 'sk-ant-...',
    'storage_dir': 'data/storage',
})

# Register event hooks
smgen.on('processing_start', lambda d: print(f"Starting: {d['input']}"))
smgen.on('processing_end', lambda d: print(f"Done in {d['total_ms']:.0f}ms"))
smgen.on('tool_end', lambda d: print(f"Tool {d['tool']}: {d['duration_ms']:.0f}ms"))

# Process voice/text input
result = smgen.process("turn the light red")
print(result.state)  # {'name': 'color', 'r': 255, 'g': 0, 'b': 0, ...}

# Trigger button events
state = smgen.trigger('button_click')
```

### Hook Events

| Event | Data |
|-------|------|
| `processing_start` | `{input, run_id}` |
| `processing_end` | `{result, total_ms, run_id}` |
| `tool_start` | `{tool, input, run_id}` |
| `tool_end` | `{tool, result, duration_ms, run_id}` |
| `error` | `{error, run_id}` |

## Tool Reference (AI Agent)

The AI agent has access to 27+ tools:

### State Management
- `setState` - Set current state immediately
- `createState` - Create a new named state
- `getStates` - List all states
- `deleteState` - Remove a state

### Rule Management
- `appendRules` - Add new rules
- `getRules` - List all rules
- `deleteRules` - Remove rules by index or criteria
- `resetRules` - Clear all rules

### Variable Management
- `setVariable` - Store a value
- `getVariable` - Retrieve a value
- `clearVariables` - Clear all variables

### Pipeline Management
- `createPipeline` - Create automation sequence
- `runPipeline` - Execute a pipeline
- `getPipelines` - List pipelines

### Utility
- `getTime` - Get current time info
- `wait` - Delay execution
- `playSound` - Play audio file (RASPi)

## Example Use Cases

### Simple Toggle

```
"Make the button toggle between on and off"
```

Creates rules:
```python
[
    {"state1": "off", "transition": "button_click", "state2": "on"},
    {"state1": "on", "transition": "button_click", "state2": "off"}
]
```

### Color Cycling

```
"Click cycles through red, green, blue, then off"
```

Creates state machine with counter-based transitions.

### Timed Animation

```
"Hold for rainbow animation, release to stop"
```

Creates rules:
```python
[
    {"state1": "off", "transition": "button_hold", "state2": "rainbow"},
    {"state1": "rainbow", "transition": "button_release", "state2": "off"}
]
```

### Scheduled Behavior

```
"Turn on warm white at 7pm every day"
```

Creates scheduled rule:
```python
{
    "state1": "*",
    "transition": "schedule",
    "state2": "warm_white",
    "trigger_config": {"hour": 19, "minute": 0, "repeat_daily": True}
}
```

### Voice-Reactive Mode

```
"Create a voice reactive green state that pulses with sound"
```

Creates state with voice_reactive config:
```python
{
    "name": "voice_green",
    "r": 0, "g": 255, "b": 0,
    "voice_reactive": {
        "enabled": True,
        "color": [0, 255, 0],
        "smoothing_alpha": 0.6
    }
}
```

## Processing Modes

### Agent Mode (Default)
Multi-turn conversation with Claude using tool calls. Best for complex requests that require multiple operations.

### Parser Mode
Single-shot parsing with OpenAI. Faster but less capable for complex requests.

Configure in app config:
```yaml
brain:
  mode: agent  # or 'parser'
  model: claude-haiku-4-5
```

## Deployment

### Sync to Raspberry Pi

```bash
cd /path/to/adaptlight
./scripts/sync_to_raspi.sh
```

### Run on Pi

```bash
ssh pi@raspberrypi.local
cd /home/pi/adaptlight
./run.sh
```

## Tips

1. **Always include toggle-off rules**: If you create a rule to turn something on, create another to turn it off.

2. **Use appropriate speeds**: Fast animations: 20-50ms, Medium: 50-100ms, Slow: 100-300ms

3. **Test expressions**: Complex expressions can slow down animations.

4. **Use counters for sequences**: Great for "N clicks then do something" behaviors.

5. **Wildcard state matching**: Use `state1: "*"` to match any current state.

6. **Priority for conflicts**: Higher priority rules are evaluated first when multiple rules match.
