# AdaptLight Agent Tools Reference

Complete reference for all tools available to the AdaptLight agent.

---

## Table of Contents

1. [Information Tools](#information-tools)
2. [State Management](#state-management)
3. [Rule Management](#rule-management)
4. [Variable Management](#variable-management)
5. [Preset APIs](#preset-apis)
6. [Memory (Persistent Storage)](#memory-persistent-storage)
7. [Pipelines](#pipelines)
8. [User Interaction](#user-interaction)
9. [Custom Tools](#custom-tools)
10. [Completion](#completion)

---

## Information Tools

### getPattern(name)
Look up a pattern template for common configurations.

**Parameters:**
- `name` (string, required): Pattern name

**Available Patterns:**
- `counter` - Temporary behavior for N occurrences
- `toggle` - Simple A↔B switching
- `cycle` - Rotate through multiple states
- `hold_release` - Hold to activate, release to stop
- `timer` - Delayed state change
- `schedule` - Time-of-day triggers
- `data_reactive` - React to external data
- `timed` - Auto-transitioning states
- `sunrise` - Gradual color transitions
- `api_reactive` - React to API data
- `pipeline` - Button-triggered API checks with LLM

**Example:**
```json
getPattern(name="toggle")
```

---

### getStates()
List all existing states with their definitions.

**Returns:** List of states with name, RGB values, speed, duration_ms, then

**Example:**
```json
getStates()
// Returns: {states: [{name: "red", r: 255, g: 0, b: 0, ...}], current_state: "off"}
```

---

### getRules()
List all current transition rules.

**Returns:** List of rules with from, on, to, condition, action, priority, pipeline

**Example:**
```json
getRules()
// Returns: {rules: [{from: "off", on: "button_click", to: "on", ...}]}
```

---

### getVariables()
List all variables in state_data.

**Returns:** Dictionary of all stored variables

---

## State Management

### createState(name, r, g, b, speed?, duration_ms?, then?, description?, voice_reactive?)
Create a named light state.

**Parameters:**
- `name` (string, required): Unique state name
- `r` (number|string, required): Red value 0-255, or expression
- `g` (number|string, required): Green value 0-255, or expression
- `b` (number|string, required): Blue value 0-255, or expression
- `speed` (number|null): Animation frame rate in ms (null = static)
- `duration_ms` (number|null): Auto-transition after this many ms
- `then` (string|null): State to transition to when duration expires
- `description` (string|null): Human-readable description
- `voice_reactive` (object|null): Enable mic-reactive brightness for this state.
  - `enabled` (bool)
  - `color` ([r,g,b], optional) base color to scale (defaults to state r/g/b)
  - `smoothing_alpha` (0.0-1.0, optional) responsiveness
  - `min_amplitude` (number, optional) noise floor
  - `max_amplitude` (number, optional) max RMS for full brightness

**Expression Variables:**
- `frame` - Current animation frame number
- `elapsed_ms` / `t` - Milliseconds since state started
- `r`, `g`, `b` - Current RGB values (for freezing)

**Expression Functions:**
- `sin()`, `cos()` - Trigonometry
- `random()` - Random 0-255
- `min()`, `max()`, `abs()` - Math

**Examples:**

Static color:
```json
createState(name="red", r=255, g=0, b=0)
```

Animation:
```json
createState(
  name="rainbow",
  r="(sin(frame * 0.02) + 1) * 127",
  g="(sin(frame * 0.02 + 2.094) + 1) * 127",
  b="(sin(frame * 0.02 + 4.188) + 1) * 127",
  speed=30
)
```

Timed state:
```json
createState(
  name="flash",
  r=255, g=0, b=0,
  duration_ms=3000,
  then="off"
)
```

Voice-reactive state:
```json
createState(
  name="music_reactive",
  r=0, g=200, b=255,
  voice_reactive={
    "enabled": true,
    "color": [0, 200, 255],
    "smoothing_alpha": 0.6,
    "min_amplitude": 80,
    "max_amplitude": 4000
  },
  description="Teal glow that follows mic volume"
)
```

---

### deleteState(name)
Remove a state (cannot delete "on" or "off").

**Parameters:**
- `name` (string, required): State name to delete

---

### setState(name)
Immediately switch to a state.

**Parameters:**
- `name` (string, required): State name to switch to

---

## Rule Management

### appendRules(rules[])
Add transition rules.

**Parameters:**
- `rules` (array, required): Array of rule objects

**Rule Object:**
- `from` (string, required): Source state ("*" = any)
- `on` (string, required): Trigger event
- `to` (string, required): Destination state
- `condition` (string|null): Expression that must be true
- `action` (string|null): Expression to execute
- `priority` (number): Higher = checked first (default: 0)
- `pipeline` (string|null): Pipeline to execute when rule fires

**Trigger Events:**
- `button_click` - Single button press
- `button_hold` - Button held down
- `button_release` - Button released
- `button_double_click` - Double press
- `timer` - Timed trigger (needs trigger_config)
- `interval` - Repeating trigger (needs trigger_config)
- `schedule` - Time-of-day trigger (needs trigger_config)

**Trigger Config (for time-based):**
```json
// Timer: fires once after delay
{"delay_ms": 5000, "auto_cleanup": true}

// Interval: fires repeatedly
{"delay_ms": 10000, "repeat": true}

// Schedule: fires at specific time
{"hour": 20, "minute": 0, "repeat_daily": true}
```

**Examples:**

Simple toggle:
```json
appendRules(rules=[
  {from: "off", on: "button_click", to: "on"},
  {from: "on", on: "button_click", to: "off"}
])
```

With condition and action:
```json
appendRules(rules=[
  {
    from: "*",
    on: "button_click",
    to: "red",
    condition: "getData('counter') > 0",
    action: "setData('counter', getData('counter') - 1)",
    priority: 10
  }
])
```

With pipeline:
```json
appendRules(rules=[
  {from: "*", on: "button_click", pipeline: "check_weather"}
])
```

---

### deleteRules(...)
Delete rules by criteria.

**Parameters (use one):**
- `indices` (array): Rule indices to delete
- `transition` (string): Delete rules with this trigger
- `from_state` (string): Delete rules from this state
- `to_state` (string): Delete rules to this state
- `all` (boolean): Delete all rules

---

## Variable Management

### setVariable(key, value)
Set a runtime variable (lost on restart - use Memory for persistence).

**Parameters:**
- `key` (string, required): Variable name
- `value` (any, required): Value to store

**Note:** Access in conditions/actions with `getData('key')`

---

## Preset APIs

### listAPIs()
List all available preset APIs with parameters and example responses.

**Returns:** List of APIs with name, description, params, example_response

---

### fetchAPI(api, params)
Call a preset API and get raw data.

**Parameters:**
- `api` (string, required): API name
- `params` (object): Parameters for the API

**Available APIs:**

| API | Params | Returns |
|-----|--------|---------|
| `weather` | `location` | temp_f, temp_c, condition, humidity, wind_mph, is_day |
| `stock` | `symbol` | price, change_percent, change_absolute, market_open |
| `crypto` | `coin` | price_usd, change_24h, market_cap |
| `sun` | `location` | sunrise, sunset, is_daytime, day_length_hours |
| `air_quality` | `location` | aqi, level, pm25, pm10, dominant_pollutant |
| `time` | (none) | hour, minute, second, weekday, is_weekend |
| `fear_greed` | (none) | value (0-100), classification |
| `github_repo` | `repo` | stars, forks, open_issues, watchers |
| `random` | `min`, `max` | value |

**Examples:**
```json
fetchAPI(api="weather", params={location: "NYC"})
// Returns: {success: true, data: {temp_f: 45, condition: "cloudy", ...}}

fetchAPI(api="stock", params={symbol: "TSLA"})
// Returns: {success: true, data: {price: 178.52, change_percent: 2.5, ...}}
```

---

## Memory (Persistent Storage)

Memory persists across restarts. Use for user preferences like location, favorite colors, etc.

### remember(key, value)
Store something in memory.

**Parameters:**
- `key` (string, required): Memory key (e.g., "location")
- `value` (any, required): Value to store

**Example:**
```json
remember(key="location", value="San Francisco")
```

---

### recall(key)
Retrieve from memory.

**Parameters:**
- `key` (string, required): Memory key

**Returns:** `{value: <stored_value>}` or `{value: null}`

**Example:**
```json
recall(key="location")
// Returns: {value: "San Francisco"} or {value: null}
```

---

### forgetMemory(key)
Delete from memory.

**Parameters:**
- `key` (string, required): Memory key to delete

---

### listMemory()
List all stored memories.

**Returns:** `{memories: {key1: value1, key2: value2, ...}, count: N}`

---

## Pipelines

Pipelines are programmable sequences triggered by button events. They can fetch APIs, parse data with LLM, and set states.

### definePipeline(name, steps, description?)
Create a pipeline.

**Parameters:**
- `name` (string, required): Pipeline name
- `steps` (array, required): Array of step objects
- `description` (string): Human-readable description

**Step Types:**

#### fetch - Call a preset API
```json
{
  "do": "fetch",
  "api": "stock",
  "params": {"symbol": "TSLA"},
  "as": "stock_data"  // Store result in variable
}
```

#### llm - Parse data with LLM
```json
{
  "do": "llm",
  "input": "{{stock_data}}",  // Reference previous result
  "prompt": "Is change_percent positive or negative? Reply 'up' or 'down'",
  "as": "direction"
}
```

#### setState - Set lamp state
```json
// Option 1: Direct state
{"do": "setState", "state": "green"}

// Option 2: Map from variable
{
  "do": "setState",
  "from": "direction",  // Variable name
  "map": {"up": "green", "down": "red"}
}
```

#### setVar - Store a value
```json
{"do": "setVar", "key": "last_check", "value": "{{direction}}"}
```

#### wait - Pause execution
```json
{"do": "wait", "ms": 1000}
```

#### run - Execute another pipeline
```json
{"do": "run", "pipeline": "other_pipeline"}
```

**Variable Interpolation:**
- `{{variable}}` - Reference pipeline variable
- `{{memory.key}}` - Reference stored memory

**Conditional Steps:**
```json
{"do": "setState", "state": "alert", "if": "{{direction}} == 'down'"}
```

**Full Example:**
```json
definePipeline(
  name="check_tesla",
  steps=[
    {"do": "fetch", "api": "stock", "params": {"symbol": "TSLA"}, "as": "stock"},
    {"do": "llm", "input": "{{stock}}", "prompt": "Is change_percent positive? Reply 'up' or 'down'", "as": "direction"},
    {"do": "setState", "from": "direction", "map": {"up": "green", "down": "red"}}
  ],
  description="Check Tesla stock direction"
)
```

---

### runPipeline(name)
Execute a pipeline immediately.

**Parameters:**
- `name` (string, required): Pipeline name

---

### deletePipeline(name)
Delete a pipeline.

**Parameters:**
- `name` (string, required): Pipeline name

---

### listPipelines()
List all defined pipelines.

**Returns:** `{pipelines: [{name, description, steps: N}], count: N}`

---

## User Interaction

### askUser(question)
Ask the user a question and wait for response.

**Parameters:**
- `question` (string, required): Question to ask

**Use for:**
- Getting location
- Clarifying preferences
- Asking for stock symbols
- Any info you need from the user

**Example:**
```json
askUser(question="What city should I use for weather?")
```

---

## Custom Tools

For APIs not in the preset list.

### defineTool(name, code, description?, params?, returns?)
Create a custom Python tool.

**Parameters:**
- `name` (string, required): Tool name
- `code` (string, required): Python code (must return dict)
- `description` (string): What the tool does
- `params` (object): Parameter definitions
- `returns` (object): Return value schema

**Available in code:** `requests`, `json`, `math`, `datetime`

**Example:**
```json
defineTool(
  name="get_btc_price",
  code="import requests; r=requests.get('https://api.example.com/btc'); return {'price': r.json()['price']}",
  description="Get Bitcoin price"
)
```

---

### callTool(name, args?)
Execute a custom tool.

**Parameters:**
- `name` (string, required): Tool name
- `args` (object): Arguments to pass

---

### createDataSource(name, fetch, fires, interval_ms?, store?)
Set up periodic data fetching.

**Parameters:**
- `name` (string, required): Data source name
- `fetch` (object, required): `{tool: "tool_name", args: {}}`
- `fires` (string, required): Transition to fire after fetch
- `interval_ms` (number): Polling interval (default: 60000)
- `store` (object): Map result paths to variables

---

### triggerDataSource(name)
Trigger immediate fetch from a data source.

**Parameters:**
- `name` (string, required): Data source name

---

## Completion

### done(message)
Signal completion. **ALWAYS call this when finished!**

**Parameters:**
- `message` (string, required): Message to show the user

**Example:**
```json
done(message="Toggle set up! Click to switch between red and blue.")
```

---

## Grammar Reference

### State Definition
```json
{
  "name": "string",
  "r": "number|expression",
  "g": "number|expression",
  "b": "number|expression",
  "speed": "number|null",
  "duration_ms": "number|null",
  "then": "string|null",
  "description": "string|null"
}
```

### Rule Definition
```json
{
  "from": "string (* = any)",
  "on": "button_click|button_hold|button_release|button_double_click|timer|interval|schedule",
  "to": "string",
  "condition": "string|null",
  "action": "string|null",
  "priority": "number (default: 0)",
  "trigger_config": "object|null",
  "pipeline": "string|null"
}
```

### Pipeline Definition
```json
{
  "name": "string",
  "steps": [
    {"do": "fetch|llm|setState|setVar|wait|run", ...},
    ...
  ],
  "description": "string|null"
}
```

### Pipeline Step Types
```json
// fetch
{"do": "fetch", "api": "string", "params": {}, "as": "var_name"}

// llm
{"do": "llm", "input": "{{var}}", "prompt": "string", "as": "var_name"}

// setState (direct)
{"do": "setState", "state": "state_name"}

// setState (mapped)
{"do": "setState", "from": "var_name", "map": {"value": "state"}}

// setVar
{"do": "setVar", "key": "var_name", "value": "any"}

// wait
{"do": "wait", "ms": 1000}

// run
{"do": "run", "pipeline": "pipeline_name"}

// Any step can have "if" for conditional execution
{"do": "...", ..., "if": "{{var}} == 'value'"}
```

---

## Quick Reference

| Category | Tools |
|----------|-------|
| Info | getPattern, getStates, getRules, getVariables |
| States | createState, deleteState, setState |
| Rules | appendRules, deleteRules |
| Variables | setVariable |
| APIs | listAPIs, fetchAPI |
| Memory | remember, recall, forgetMemory, listMemory |
| Pipelines | definePipeline, runPipeline, deletePipeline, listPipelines |
| User | askUser |
| Custom | defineTool, callTool, createDataSource, triggerDataSource |
| Completion | done |
