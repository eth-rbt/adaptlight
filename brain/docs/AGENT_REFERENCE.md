# AdaptLight Agent Reference

This is the detailed reference for the smart light agent. Use `getDocs(topic)` to look up specific sections.

## Topics

- `states` - All state configuration options
- `animations` - Expression-based animations
- `voice_reactive` - Audio-reactive brightness
- `rules` - Rule configuration and triggers
- `timer` - One-shot timer rules
- `interval` - Repeating interval rules
- `schedule` - Time-of-day scheduling
- `pipelines` - Pipeline step types and examples
- `fetch` - Fetching data from APIs
- `llm` - LLM parsing in pipelines
- `apis` - Available preset APIs
- `memory` - Persistent storage
- `variables` - State machine variables
- `expressions` - Expression syntax and functions

---

# SECTION: states

## State Configuration

States define what the light looks like. Every state has a name and RGB values.

### Basic Static State
```json
createState(
  name="red",
  r=255, g=0, b=0,
  description="Solid red light"
)
```

### All State Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | YES | Unique identifier |
| `r` | number or string | YES | Red 0-255, or expression |
| `g` | number or string | YES | Green 0-255, or expression |
| `b` | number or string | YES | Blue 0-255, or expression |
| `speed` | number or null | NO | Animation frame rate in ms. null=static |
| `duration_ms` | number | NO | Auto-transition after this many ms |
| `then` | string | NO | State to transition to (required if duration_ms set) |
| `description` | string | NO | Human-readable description |
| `voice_reactive` | object | NO | Enable mic-reactive brightness |

### State Modes

1. **Static**: speed=null, r/g/b are numbers
2. **Animation**: speed is set, r/g/b can be expressions
3. **Timed**: duration_ms + then for auto-transition
4. **Voice-Reactive**: voice_reactive.enabled=true

---

# SECTION: animations

## Animation Expressions

When `speed` is set (e.g., 30ms), the r/g/b values can be expression strings that are evaluated each frame.

### Available Variables

| Variable | Description |
|----------|-------------|
| `frame` | Frame counter (0, 1, 2, ...) |
| `t` | Elapsed milliseconds since state started |
| `elapsed_ms` | Same as `t` |
| `r` | Current red value |
| `g` | Current green value |
| `b` | Current blue value |

### Available Functions

| Function | Description |
|----------|-------------|
| `sin(x)` | Sine (radians) |
| `cos(x)` | Cosine (radians) |
| `tan(x)` | Tangent (radians) |
| `abs(x)` | Absolute value |
| `min(a,b)` | Minimum |
| `max(a,b)` | Maximum |
| `floor(x)` | Round down |
| `ceil(x)` | Round up |
| `round(x)` | Round to nearest |
| `sqrt(x)` | Square root |
| `pow(x,y)` | Power |
| `random()` | Random integer 0-255 |
| `PI` | 3.14159... |
| `E` | 2.71828... |

### Animation Examples

#### Breathing/Pulsing (sine wave)
```json
createState(
  name="breathing",
  r="(sin(frame * 0.05) + 1) * 127",
  g="(sin(frame * 0.05) + 1) * 127",
  b="(sin(frame * 0.05) + 1) * 127",
  speed=30
)
```
- `frame * 0.05` controls speed (smaller = slower)
- `+ 1` shifts sine from [-1,1] to [0,2]
- `* 127` scales to [0,254]

#### Rainbow Cycle (phase-shifted sines)
```json
createState(
  name="rainbow",
  r="(sin(frame * 0.02) + 1) * 127",
  g="(sin(frame * 0.02 + 2.094) + 1) * 127",
  b="(sin(frame * 0.02 + 4.188) + 1) * 127",
  speed=30
)
```
- Phase offset of 2.094 radians (120 degrees) between channels
- Creates smooth RGB cycling

#### Random Strobe/Disco
```json
createState(
  name="disco",
  r="random()",
  g="random()",
  b="random()",
  speed=100
)
```

#### Time-Based Fade (using elapsed_ms)
```json
createState(
  name="fade_out",
  r="max(0, 255 - t / 20)",
  g="max(0, 255 - t / 20)",
  b="max(0, 255 - t / 20)",
  speed=50,
  duration_ms=5000,
  then="off"
)
```
- Fades from white to black over 5 seconds
- `t / 20` = 255 at t=5100ms

#### Candle Flicker
```json
createState(
  name="candle",
  r="200 + random() * 0.2",
  g="100 + random() * 0.3",
  b="0",
  speed=50
)
```

---

# SECTION: voice_reactive

## Voice-Reactive Mode

Makes LED brightness follow audio input from the microphone. Great for music visualization.

### Configuration

```json
createState(
  name="party",
  r=0, g=255, b=100,
  voice_reactive={
    "enabled": true,
    "color": [0, 255, 100],
    "smoothing_alpha": 0.4,
    "min_amplitude": 100,
    "max_amplitude": 5000
  }
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | false | Must be true to activate |
| `color` | [r,g,b] | state's r,g,b | Override base color |
| `smoothing_alpha` | 0.0-1.0 | 0.6 | Lower=smoother/slower, higher=snappier |
| `min_amplitude` | number | 100 | Noise floor (RMS below this = dark) |
| `max_amplitude` | number | 5000 | Full brightness threshold |

### Tuning Tips

- **Quiet room**: Lower `min_amplitude` to 50-100
- **Loud environment**: Raise `min_amplitude` to 200-500
- **Bass-heavy music**: Lower `max_amplitude` to 3000-4000
- **Smoother response**: Lower `smoothing_alpha` to 0.2-0.3
- **Snappier response**: Raise `smoothing_alpha` to 0.6-0.8

### Examples

#### Basic Music Reactive
```json
createState(
  name="music",
  r=0, g=255, b=0,
  voice_reactive={"enabled": true}
)
```

#### Smooth Purple Pulse
```json
createState(
  name="chill_reactive",
  r=150, g=0, b=255,
  voice_reactive={
    "enabled": true,
    "smoothing_alpha": 0.2,
    "min_amplitude": 50
  }
)
```

#### High-Energy Party
```json
createState(
  name="rave",
  r=255, g=0, b=100,
  voice_reactive={
    "enabled": true,
    "smoothing_alpha": 0.7,
    "max_amplitude": 8000
  }
)
```

---

# SECTION: rules

## Rule Configuration

Rules define state transitions. When a trigger occurs, matching rules are evaluated by priority (highest first).

### Basic Rule Structure

```json
{
  "from": "state_name",
  "on": "trigger",
  "to": "destination_state"
}
```

### All Rule Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from` | string | YES | Source state, "*" for any, "prefix/*" for prefix match |
| `on` | string | YES | Trigger type (see triggers below) |
| `to` | string | YES | Destination state |
| `condition` | string | NO | Expression that must be true |
| `action` | string | NO | Expression to execute on transition |
| `priority` | number | NO | Higher = checked first (default 0) |
| `pipeline` | string | NO | Pipeline to execute when rule fires |
| `enabled` | boolean | NO | Set false to disable (default true) |
| `trigger_config` | object | NO | Config for timer/interval/schedule |

### Trigger Types

| Trigger | Description |
|---------|-------------|
| `button_click` | Single button press |
| `button_hold` | Button held down |
| `button_release` | Button released |
| `button_double_click` | Double-click |
| `timer` | One-shot delay (requires trigger_config) |
| `interval` | Repeating timer (requires trigger_config) |
| `schedule` | Time-of-day (requires trigger_config) |

### Wildcard Matching

```json
// Match ANY state
{"from": "*", "on": "button_hold", "to": "off"}

// Match states starting with "color/"
{"from": "color/*", "on": "button_click", "to": "off"}
```

### Conditions and Actions

Conditions use `getData()`, actions use `setData()`:

```json
{
  "from": "*",
  "on": "button_click",
  "to": "red",
  "condition": "getData('counter') > 0",
  "action": "setData('counter', getData('counter') - 1)"
}
```

### Priority

Higher priority rules are checked first:

```json
// Safety rule - always checked first
{"from": "*", "on": "button_hold", "to": "off", "priority": 100}

// Normal rule
{"from": "off", "on": "button_click", "to": "on", "priority": 0}
```

---

# SECTION: timer

## Timer Rules (One-Shot Delay)

Fire once after a specified delay.

### Syntax

```json
{
  "from": "current_state",
  "on": "timer",
  "to": "next_state",
  "trigger_config": {
    "delay_ms": 5000,
    "auto_cleanup": true
  }
}
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `delay_ms` | number | Delay in milliseconds |
| `auto_cleanup` | boolean | Remove rule after firing (default false) |

### Examples

#### Alert in 5 minutes
```json
createState(name="alert", r=255, g=100, b=0)
appendRules(rules=[
  {
    "from": "*",
    "on": "timer",
    "to": "alert",
    "trigger_config": {"delay_ms": 300000, "auto_cleanup": true}
  }
])
```

#### Flash then off
```json
createState(name="flash", r=255, g=0, b=0)
appendRules(rules=[
  {"from": "off", "on": "button_click", "to": "flash"},
  {
    "from": "flash",
    "on": "timer",
    "to": "off",
    "trigger_config": {"delay_ms": 1000, "auto_cleanup": true}
  }
])
```

---

# SECTION: interval

## Interval Rules (Repeating Timer)

Fire repeatedly at a fixed interval.

### Syntax

```json
{
  "from": "state_a",
  "on": "interval",
  "to": "state_b",
  "trigger_config": {
    "delay_ms": 500,
    "repeat": true
  }
}
```

### Examples

#### Blinking Light
```json
createState(name="blink_on", r=255, g=255, b=255)
createState(name="blink_off", r=0, g=0, b=0)
appendRules(rules=[
  {
    "from": "blink_on",
    "on": "interval",
    "to": "blink_off",
    "trigger_config": {"delay_ms": 500, "repeat": true}
  },
  {
    "from": "blink_off",
    "on": "interval",
    "to": "blink_on",
    "trigger_config": {"delay_ms": 500, "repeat": true}
  },
  {"from": "*", "on": "button_click", "to": "off", "priority": 10}
])
setState(name="blink_on")
```

#### Slow Color Cycle
```json
createState(name="cycle_red", r=255, g=0, b=0)
createState(name="cycle_green", r=0, g=255, b=0)
createState(name="cycle_blue", r=0, g=0, b=255)
appendRules(rules=[
  {"from": "cycle_red", "on": "interval", "to": "cycle_green", "trigger_config": {"delay_ms": 2000, "repeat": true}},
  {"from": "cycle_green", "on": "interval", "to": "cycle_blue", "trigger_config": {"delay_ms": 2000, "repeat": true}},
  {"from": "cycle_blue", "on": "interval", "to": "cycle_red", "trigger_config": {"delay_ms": 2000, "repeat": true}}
])
```

---

# SECTION: schedule

## Schedule Rules (Time-of-Day)

Fire at a specific time of day.

### Syntax

```json
{
  "from": "*",
  "on": "schedule",
  "to": "on",
  "trigger_config": {
    "hour": 8,
    "minute": 0,
    "repeat_daily": true
  }
}
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `hour` | 0-23 | Hour in 24-hour format |
| `minute` | 0-59 | Minute |
| `repeat_daily` | boolean | Repeat every day (default false) |

### Examples

#### Turn on at 8am daily
```json
appendRules(rules=[
  {
    "from": "*",
    "on": "schedule",
    "to": "on",
    "trigger_config": {"hour": 8, "minute": 0, "repeat_daily": true}
  }
])
```

#### Turn off at 11pm daily
```json
appendRules(rules=[
  {
    "from": "*",
    "on": "schedule",
    "to": "off",
    "trigger_config": {"hour": 23, "minute": 0, "repeat_daily": true}
  }
])
```

#### Sunrise simulation at 6:30am
```json
createState(
  name="sunrise",
  r=255,
  g="min(255, t / 600000 * 255)",
  b="min(200, t / 600000 * 200)",
  speed=100,
  duration_ms=600000,
  then="on"
)
appendRules(rules=[
  {
    "from": "*",
    "on": "schedule",
    "to": "sunrise",
    "trigger_config": {"hour": 6, "minute": 30, "repeat_daily": true}
  }
])
```

---

# SECTION: pipelines

## Pipeline Overview

Pipelines are sequences of steps that execute in order. They can fetch data from APIs, process it with an LLM, and set the light state based on results.

### Creating a Pipeline

```json
definePipeline(
  name="check_stock",
  steps=[
    {"do": "fetch", "api": "stock", "params": {"symbol": "AAPL"}, "as": "data"},
    {"do": "llm", "input": "{{data}}", "prompt": "Is change positive? Reply 'up' or 'down'", "as": "direction"},
    {"do": "setState", "from": "direction", "map": {"up": "green", "down": "red"}}
  ],
  description="Check stock and show green/red"
)
```

### Triggering a Pipeline

Pipelines can be triggered:
1. **Immediately**: `runPipeline(name="check_stock")`
2. **On button press**: Add `pipeline` to a rule
3. **On schedule**: Combine with schedule rule

```json
appendRules(rules=[
  {"from": "*", "on": "button_click", "pipeline": "check_stock", "to": "checking"}
])
```

### Step Types

See sections: `fetch`, `llm`, `setstate`, `setvar`, `wait`, `run`

### Common Features

All steps support:
- `"as": "varname"` - Store result in pipeline variable
- `"if": "{{var}} == 'value'"` - Conditional execution

### Variable Interpolation

- `{{varname}}` - Reference pipeline variable
- `{{memory.key}}` - Reference persistent memory

---

# SECTION: fetch

## Fetch Step

Call a preset API to get data.

### Syntax

```json
{"do": "fetch", "api": "weather", "params": {"location": "NYC"}, "as": "data"}
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `api` | string | API name (see `apis` section) |
| `params` | object | Parameters for the API |
| `as` | string | Variable name to store result |

### Examples

```json
// Weather
{"do": "fetch", "api": "weather", "params": {"location": "San Francisco"}, "as": "weather"}

// Stock
{"do": "fetch", "api": "stock", "params": {"symbol": "TSLA"}, "as": "stock"}

// Crypto
{"do": "fetch", "api": "crypto", "params": {"coin": "bitcoin"}, "as": "btc"}

// Using memory for location
{"do": "fetch", "api": "weather", "params": {"location": "{{memory.location}}"}, "as": "weather"}
```

---

# SECTION: llm

## LLM Step

Process data with an AI model to extract simple answers.

### Syntax

```json
{"do": "llm", "input": "{{data}}", "prompt": "Is it raining? Reply yes or no", "as": "result"}
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | string | Data to process (use {{var}} interpolation) |
| `prompt` | string | Instructions for the LLM |
| `as` | string | Variable name to store result |

### Best Practices

1. **Ask for simple answers**: "Reply 'up' or 'down'" or "Reply yes or no"
2. **Be specific**: Tell the LLM exactly what to look for
3. **Keep prompts short**: Long prompts are slower and more expensive

### Examples

```json
// Stock direction
{
  "do": "llm",
  "input": "{{stock}}",
  "prompt": "Is change_percent positive or negative? Reply with just 'up' or 'down'",
  "as": "direction"
}

// Weather condition
{
  "do": "llm",
  "input": "{{weather}}",
  "prompt": "Is it sunny, cloudy, or rainy? Reply with one word.",
  "as": "condition"
}

// Temperature check
{
  "do": "llm",
  "input": "{{weather}}",
  "prompt": "Is temp_f above 70? Reply 'hot' or 'cold'",
  "as": "temp_status"
}
```

---

# SECTION: apis

## Available Preset APIs

Use with `fetchAPI()` or pipeline fetch steps.

### weather
Get current weather for a location.

**Params**: `{location: "City Name"}`

**Returns**:
```json
{
  "temp_f": 65,
  "temp_c": 18,
  "condition": "sunny",
  "humidity": 45,
  "wind_mph": 10
}
```

### stock
Get stock price and change.

**Params**: `{symbol: "AAPL"}`

**Returns**:
```json
{
  "symbol": "AAPL",
  "price": 178.52,
  "change": 2.34,
  "change_percent": 1.33
}
```

### crypto
Get cryptocurrency price.

**Params**: `{coin: "bitcoin"}`

**Returns**:
```json
{
  "coin": "bitcoin",
  "price_usd": 43250,
  "change_24h": -2.5
}
```

### sun
Get sunrise/sunset times.

**Params**: `{location: "City Name"}`

**Returns**:
```json
{
  "sunrise": "06:45",
  "sunset": "18:30",
  "day_length_hours": 11.75
}
```

### air_quality
Get air quality index.

**Params**: `{location: "City Name"}`

**Returns**:
```json
{
  "aqi": 42,
  "category": "good",
  "dominant_pollutant": "pm25"
}
```

### time
Get current time info.

**Params**: `{timezone: "America/Los_Angeles"}` (optional)

**Returns**:
```json
{
  "hour": 14,
  "minute": 30,
  "day_of_week": "Monday",
  "is_weekend": false
}
```

### fear_greed
Get crypto fear & greed index.

**Params**: none

**Returns**:
```json
{
  "value": 65,
  "classification": "greed"
}
```

### github_repo
Get GitHub repository stats.

**Params**: `{owner: "anthropics", repo: "claude-code"}`

**Returns**:
```json
{
  "stars": 1234,
  "forks": 567,
  "open_issues": 42
}
```

### random
Get random number.

**Params**: `{min: 0, max: 100}` (optional)

**Returns**:
```json
{
  "value": 42
}
```

---

# SECTION: memory

## Persistent Memory

Store values that persist across sessions and restarts.

### Tools

| Tool | Description |
|------|-------------|
| `remember(key, value)` | Store a value |
| `recall(key)` | Retrieve a value (null if not found) |
| `forgetMemory(key)` | Delete a value |
| `listMemory()` | List all stored memories |

### Common Uses

- **Location**: `remember("location", "San Francisco")`
- **Favorite color**: `remember("favorite_color", "blue")`
- **Stock symbol**: `remember("stock", "AAPL")`
- **User preferences**: `remember("brightness", 0.8)`

### Using Memory in Pipelines

Use `{{memory.key}}` interpolation:

```json
{
  "do": "fetch",
  "api": "weather",
  "params": {"location": "{{memory.location}}"},
  "as": "weather"
}
```

### Example: First-Time Setup

```
1. recall(key="location")
2. // If null, ask user:
   askUser(question="What city should I use for weather?")
3. // Store their response:
   remember(key="location", value="[user's response]")
4. // Now use it:
   fetchAPI(api="weather", params={location: recall("location")})
```

---

# SECTION: variables

## State Machine Variables

Temporary variables stored in the state machine (not persistent across restarts).

### Tools

| Tool | Description |
|------|-------------|
| `setVariable(key, value)` | Set a variable |
| `getVariables()` | List all variables |

### Using in Conditions/Actions

In rule conditions and actions, use `getData()` and `setData()`:

```json
{
  "condition": "getData('counter') > 0",
  "action": "setData('counter', getData('counter') - 1)"
}
```

### Example: Click Counter

```json
setVariable(key="clicks", value=5)
appendRules(rules=[
  {
    "from": "*",
    "on": "button_click",
    "to": "red",
    "condition": "getData('clicks') > 0",
    "action": "setData('clicks', getData('clicks') - 1)",
    "priority": 10
  },
  {
    "from": "*",
    "on": "button_click",
    "to": "off",
    "condition": "getData('clicks') <= 0"
  }
])
```

---

# SECTION: expressions

## Expression Syntax

Expressions are used in:
- Animation r/g/b values
- Rule conditions
- Rule actions

### Animation Expressions

Variables: `frame`, `t`, `elapsed_ms`, `r`, `g`, `b`
Functions: `sin`, `cos`, `tan`, `abs`, `min`, `max`, `floor`, `ceil`, `round`, `sqrt`, `pow`, `random`, `PI`, `E`

```
"(sin(frame * 0.05) + 1) * 127"
"min(255, t / 1000 * 255)"
"random()"
```

### Condition Expressions

Functions: `getData(key)`, `getTime()`

```
"getData('counter') > 0"
"getData('mode') == 'party'"
"getTime() > 18"  // After 6pm
```

### Action Expressions

Functions: `setData(key, value)`, `getData(key)`

```
"setData('counter', getData('counter') - 1)"
"setData('mode', 'normal')"
"setData('last_click', getTime())"
```

---

# SECTION: examples

## Command Examples

These examples show how to handle common voice commands.

### IMPORTANT: When to Add Rules

**Only add rules if user explicitly mentions button/trigger behavior!**
- "go to X" / "turn X" / "make it X" → createState + setState only (NO rules)
- "set up" / "configure" / "click to" / "hold to" → OK to add rules

**Keywords that allow rules**: set up, configure, toggle, click, hold, press, double-click, button, when I, schedule, timer, at [time]

### Basic Commands (NO rules needed)

#### "Turn the light red"
```
1. createState(name="red", r=255, g=0, b=0)
2. setState(name="red")
3. done(message="Light is now red!")
```

#### "Make it blue"
```
1. createState(name="blue", r=0, g=0, b=255)
2. setState(name="blue")
3. done(message="Light is now blue!")
```

#### "Turn off the light"
```
1. setState(name="off")
2. done(message="Light turned off.")
```

#### "Go to party mode" (NO rules - user said "go to")
```
1. createState(name="party", r="random()", g="random()", b="random()", speed=100)
2. setState(name="party")
3. done(message="Party mode activated!")
```

### Toggle & Cycle (rules needed - user says "set up")

#### "Set up a toggle between red and blue"
```
1. createState(name="red", r=255, g=0, b=0)
2. createState(name="blue", r=0, g=0, b=255)
3. appendRules(rules=[
     {"from": "red", "on": "button_click", "to": "blue"},
     {"from": "blue", "on": "button_click", "to": "red"},
     {"from": "off", "on": "button_click", "to": "red"}
   ])
4. setState(name="red")
5. done(message="Toggle set up! Click to switch between red and blue.")
```

#### "Cycle through red, green, blue on click"
```
1. createState(name="red", r=255, g=0, b=0)
2. createState(name="green", r=0, g=255, b=0)
3. createState(name="blue", r=0, g=0, b=255)
4. appendRules(rules=[
     {"from": "off", "on": "button_click", "to": "red"},
     {"from": "red", "on": "button_click", "to": "green"},
     {"from": "green", "on": "button_click", "to": "blue"},
     {"from": "blue", "on": "button_click", "to": "off"}
   ])
5. setState(name="red")
6. done(message="Cycle set up!")
```

### Animations

#### "Make a breathing/pulsing animation"
```
1. createState(
     name="breathing",
     r="(sin(frame * 0.05) + 1) * 127",
     g="(sin(frame * 0.05) + 1) * 127",
     b="(sin(frame * 0.05) + 1) * 127",
     speed=30
   )
2. appendRules(rules=[{"from": "breathing", "on": "button_click", "to": "off"}])
3. setState(name="breathing")
4. done(message="Breathing animation started!")
```

#### "Make a rainbow cycle"
```
1. createState(
     name="rainbow",
     r="(sin(frame * 0.02) + 1) * 127",
     g="(sin(frame * 0.02 + 2.094) + 1) * 127",
     b="(sin(frame * 0.02 + 4.188) + 1) * 127",
     speed=30
   )
2. appendRules(rules=[{"from": "rainbow", "on": "button_click", "to": "off"}])
3. setState(name="rainbow")
4. done(message="Rainbow animation started!")
```

### Button Behaviors

#### "Hold to turn on, release to turn off"
```
1. appendRules(rules=[
     {"from": "*", "on": "button_hold", "to": "on"},
     {"from": "*", "on": "button_release", "to": "off"}
   ])
2. done(message="Hold button to turn on, release to turn off.")
```

#### "Double click for party mode"
```
1. createState(name="party", r="random()", g="random()", b="random()", speed=100)
2. appendRules(rules=[
     {"from": "*", "on": "button_double_click", "to": "party", "priority": 50},
     {"from": "party", "on": "button_click", "to": "off"}
   ])
3. done(message="Double-click for party mode!")
```

### Counter Pattern

#### "Next 5 clicks turn red, then back to normal"
```
1. createState(name="red", r=255, g=0, b=0)
2. setVariable(key="click_counter", value=5)
3. appendRules(rules=[
     {
       "from": "*", "on": "button_click", "to": "red",
       "condition": "getData('click_counter') > 0",
       "action": "setData('click_counter', getData('click_counter') - 1)",
       "priority": 10
     },
     {
       "from": "red", "on": "button_click", "to": "off",
       "condition": "getData('click_counter') <= 0",
       "priority": 20
     }
   ])
4. done(message="Next 5 clicks will show red, then back to off.")
```

### Timed States

#### "Flash red for 3 seconds then turn off"
```
1. createState(name="flash_red", r=255, g=0, b=0, duration_ms=3000, then="off")
2. setState(name="flash_red")
3. done(message="Flashing red for 3 seconds!")
```

#### "Sunrise simulation - fade over 10 seconds"
```
1. createState(
     name="sunrise",
     r=255,
     g="min(255, elapsed_ms / 10000 * 255)",
     b="min(255, elapsed_ms / 10000 * 200)",
     speed=100,
     duration_ms=10000,
     then="on"
   )
2. setState(name="sunrise")
3. done(message="Sunrise starting!")
```

### Time-Based Rules

#### "Turn on a timer - alert in 5 minutes"
```
1. createState(name="alert", r=255, g=100, b=0)
2. appendRules(rules=[
     {"from": "*", "on": "timer", "to": "alert", "trigger_config": {"delay_ms": 300000, "auto_cleanup": true}},
     {"from": "alert", "on": "button_click", "to": "off"}
   ])
3. done(message="Timer set! Light will turn orange in 5 minutes.")
```

#### "Make a blinking light"
```
1. createState(name="blink_on", r=255, g=255, b=255)
2. createState(name="blink_off", r=0, g=0, b=0)
3. appendRules(rules=[
     {"from": "blink_on", "on": "interval", "to": "blink_off", "trigger_config": {"delay_ms": 500, "repeat": true}},
     {"from": "blink_off", "on": "interval", "to": "blink_on", "trigger_config": {"delay_ms": 500, "repeat": true}},
     {"from": "*", "on": "button_click", "to": "off", "priority": 10}
   ])
4. setState(name="blink_on")
5. done(message="Blinking!")
```

#### "Turn on at 8am every day"
```
1. appendRules(rules=[
     {"from": "*", "on": "schedule", "to": "on", "trigger_config": {"hour": 8, "minute": 0, "repeat_daily": true}}
   ])
2. done(message="Scheduled! Light will turn on at 8:00 AM every day.")
```

### Voice-Reactive (Music Mode)

#### "React to music"
```
1. createState(
     name="music_reactive",
     r=0, g=255, b=100,
     voice_reactive={"enabled": true, "smoothing_alpha": 0.4}
   )
2. appendRules(rules=[{"from": "music_reactive", "on": "button_click", "to": "off"}])
3. setState(name="music_reactive")
4. done(message="Music reactive mode on!")
```

#### "Purple pulsing with music"
```
1. createState(
     name="purple_reactive",
     r=150, g=0, b=255,
     voice_reactive={"enabled": true, "color": [150, 0, 255], "smoothing_alpha": 0.3}
   )
2. appendRules(rules=[{"from": "purple_reactive", "on": "button_click", "to": "off"}])
3. setState(name="purple_reactive")
4. done(message="Purple music reactive mode!")
```

### API & Weather

#### "What's the weather in NYC?"
```
1. fetchAPI(api="weather", params={location: "New York"})
   // Returns: {temp_f: 45, condition: "cloudy", humidity: 65}
2. done(message="NYC is 45°F and cloudy with 65% humidity.")
```

#### "Make light blue when cold, red when hot"
```
1. fetchAPI(api="weather", params={location: "San Francisco"})
   // Get data: {temp_f: 58, condition: "sunny"}
2. createState(name="cold_blue", r=0, g=100, b=255)
3. createState(name="hot_red", r=255, g=50, b=0)
4. createState(name="mild_green", r=100, g=255, b=100)
5. // temp_f=58, that's mild
6. setState(name="mild_green")
7. done(message="It's 58°F - showing mild green.")
```

### Memory

#### "Remember my location is San Francisco"
```
1. remember(key="location", value="San Francisco")
2. done(message="Got it! I'll remember your location.")
```

#### "What do you remember about me?"
```
1. listMemory()
   // Returns: {memories: {location: "San Francisco"}, count: 1}
2. done(message="I remember your location is San Francisco.")
```

### Pipelines (Button-Triggered API Checks)

#### "Click to check Tesla stock"
```
1. createState(name="stock_up", r=0, g=255, b=0)
2. createState(name="stock_down", r=255, g=0, b=0)
3. definePipeline(
     name="check_tesla",
     steps=[
       {"do": "fetch", "api": "stock", "params": {"symbol": "TSLA"}, "as": "stock"},
       {"do": "llm", "input": "{{stock}}", "prompt": "Is change_percent positive? Reply 'up' or 'down'", "as": "direction"},
       {"do": "setState", "from": "direction", "map": {"up": "stock_up", "down": "stock_down"}}
     ]
   )
4. appendRules(rules=[{"from": "*", "on": "button_click", "pipeline": "check_tesla"}])
5. done(message="Click to check Tesla! Green=up, Red=down.")
```

### Utility Commands

#### "Reset everything to default"
```
1. deleteRules(all=true)
2. appendRules(rules=[
     {"from": "off", "on": "button_click", "to": "on"},
     {"from": "on", "on": "button_click", "to": "off"}
   ])
3. setState(name="off")
4. done(message="Reset to default on/off toggle.")
```

#### "What's my current state?"
```
1. getStates()
2. getRules()
3. done(message="Current state is [state]. You have [N] states and [M] rules.")
```

---

# SECTION: complete_examples

## Complete Pipeline Examples

### Stock Checker with Button

```json
// States
createState(name="checking", r=100, g=100, b=100)
createState(name="stock_up", r=0, g=255, b=0)
createState(name="stock_down", r=255, g=0, b=0)

// Pipeline
definePipeline(
  name="check_stock",
  steps=[
    {"do": "fetch", "api": "stock", "params": {"symbol": "{{memory.stock}}"}, "as": "data"},
    {"do": "llm", "input": "{{data}}", "prompt": "Is change_percent positive? Reply 'up' or 'down'", "as": "direction"},
    {"do": "setState", "from": "direction", "map": {"up": "stock_up", "down": "stock_down"}}
  ]
)

// Rules
appendRules(rules=[
  {"from": "*", "on": "button_click", "to": "checking", "pipeline": "check_stock"},
  {"from": "stock_up", "on": "button_click", "to": "off"},
  {"from": "stock_down", "on": "button_click", "to": "off"}
])
```

### Weather-Based Daily Schedule

```json
// States
createState(name="sunny", r=255, g=200, b=50)
createState(name="cloudy", r=150, g=150, b=150)
createState(name="rainy", r=0, g=100, b=200)

// Pipeline
definePipeline(
  name="weather_check",
  steps=[
    {"do": "fetch", "api": "weather", "params": {"location": "{{memory.location}}"}, "as": "weather"},
    {"do": "llm", "input": "{{weather}}", "prompt": "Is condition sunny, cloudy, or rainy? Reply one word.", "as": "cond"},
    {"do": "setState", "from": "cond", "map": {"sunny": "sunny", "cloudy": "cloudy", "rainy": "rainy"}}
  ]
)

// Schedule for 7am daily
appendRules(rules=[
  {
    "from": "*",
    "on": "schedule",
    "to": "checking",
    "pipeline": "weather_check",
    "trigger_config": {"hour": 7, "minute": 0, "repeat_daily": true}
  }
])
```

### Multi-Step Pipeline with Conditionals

```json
definePipeline(
  name="smart_lights",
  steps=[
    {"do": "fetch", "api": "time", "as": "time"},
    {"do": "fetch", "api": "weather", "params": {"location": "{{memory.location}}"}, "as": "weather"},

    // If after sunset, dim the lights
    {"do": "setVar", "key": "brightness", "value": "1.0"},
    {"do": "setVar", "key": "brightness", "value": "0.3", "if": "{{time.hour}} > 20"},

    // Set color based on weather
    {"do": "llm", "input": "{{weather}}", "prompt": "sunny/cloudy/rainy?", "as": "cond"},
    {"do": "setState", "from": "cond", "map": {"sunny": "warm", "cloudy": "neutral", "rainy": "cool"}}
  ]
)
```
