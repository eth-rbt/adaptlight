# Agent Architecture Plan

## Overview

Evolving the state machine from rigid tool-call based parsing to a more flexible, pattern-based agent architecture. The light becomes an **ambient information display** - a calm technology interface.

---

## Goals

1. **More flexible rules** - Wildcards, priorities, enable/disable
2. **Extensible transitions** - Claude can define custom trigger types
3. **Data sources** - External data feeds that populate variables and fire transitions
4. **Custom functions** - Claude can define reusable functions for expressions
5. **Pattern-based generation** - Detect user intent, retrieve relevant patterns, adapt

---

## Tasks

### 1. Wildcard Rules

**What**: Allow `*` to match any state in rule matching.

**Changes**:
- `core/rule.py` - Update `matches()` method
  - `"*"` matches any state
  - `"prefix/*"` matches hierarchical states (e.g., `color/*` matches `color/red`)

**Example**:
```python
# Emergency exit from ANY state
{"state1": "*", "transition": "button_hold", "state2": "off", "priority": 100}
```

---

### 2. Priority Queue

**What**: Add `priority` field to rules. Higher priority rules evaluated first.

**Changes**:
- `core/rule.py` - Add `priority` field (default: 0)
- `core/state_machine.py` - Sort matching rules by priority before evaluation
- Update prompts to document priority field

**Example**:
```python
{"state1": "*", "transition": "click", "state2": "off", "priority": 100}  # Safety rule
{"state1": "off", "transition": "click", "state2": "on", "priority": 0}   # Default
```

**Evaluation order**: Sort descending by priority, first match wins.

---

### 3. Custom Transition Code

**What**: Allow Claude to write Python code that defines new transition triggers.

**Concept**: Beyond fixed transitions (button_click, timer, etc.), let Claude define custom triggers like:
- `motion_detected` - when PIR sensor fires
- `sound_level_high` - when ambient sound exceeds threshold
- `temperature_above` - when temp sensor reads above X

**Architecture**:
```
raspi/
  custom_transitions/
    __init__.py
    registry.py      # Transition registry
    executor.py      # Safe code execution
    builtin.py       # Built-in transitions (button, timer, etc.)
```

**Registry**:
```python
TRANSITIONS = {
    "button_click": {"source": "hardware", "handler": button_click_handler},
    "timer": {"source": "time", "handler": timer_handler},
    # Custom (added by Claude):
    "motion_detected": {"source": "custom", "code": "...", "handler": custom_handler}
}
```

**Safety**:
- Sandboxed execution (restricted builtins)
- Whitelist of allowed imports (time, math, etc.)
- No file/network access

**Tool for Claude**:
```json
{
  "defineTransition": {
    "name": "motion_detected",
    "description": "Fires when motion sensor detects movement",
    "code": "def check(): return gpio.read(PIR_PIN) == HIGH",
    "poll_interval_ms": 100
  }
}
```

---

### 4. Data Sources (External Data Layer)

**What**: A separate layer that fetches external data, stores in variables, and fires transitions. Rules stay pure - they only check local variables.

**Core Principle**:
```
┌─────────────────────────────────────────────────────────┐
│                    DATA LAYER                           │
│  ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │
│  │   Weather   │    │   Stocks    │    │  Calendar  │  │
│  │   Source    │    │   Source    │    │   Source   │  │
│  └──────┬──────┘    └──────┬──────┘    └─────┬──────┘  │
│         │                  │                  │         │
│         ▼                  ▼                  ▼         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              VARIABLES (state_data)              │   │
│  │  temperature: 45, stock_price: 150, next_event  │   │
│  └─────────────────────────────────────────────────┘   │
│         │                                              │
│         │ fires transition: "weather_updated"          │
└─────────┼──────────────────────────────────────────────┘
          ▼
┌─────────────────────────────────────────────────────────┐
│                    RULE LAYER                           │
│  Rules just check variables - no API logic             │
└─────────────────────────────────────────────────────────┘
```

**Architecture**:
```
raspi/
  data_sources/
    __init__.py
    registry.py      # Data source registry
    scheduler.py     # Manages polling intervals
    fetchers.py      # Built-in fetch tools
```

**Data Source Definition**:
```python
{
    "name": "weather",
    "interval_ms": 3600000,  # Every hour
    "fetch": {
        "tool": "get_weather",
        "args": {"location": "San Francisco"}
    },
    "store": {
        "temperature": "result.temp",
        "weather_condition": "result.condition"
    },
    "fires": "weather_updated"  # Transition to fire after storing
}
```

**Flow**:
1. **Scheduler** runs data source at interval
2. **Fetcher** calls external API → gets result
3. **Store** extracts values → saves to `state_data`
4. **Fire** triggers transition (e.g., `weather_updated`)
5. **Rules** evaluate with conditions checking variables

**Available Fetch Tools**:
```python
FETCH_TOOLS = {
    # External APIs
    "get_weather": "Get weather for location",
    "web_search": "Search the web",
    "fetch_json": "Fetch JSON from any URL",
    "fetch_text": "Fetch text from any URL",

    # Future integrations
    "get_calendar": "Get calendar events",
    "get_stock": "Get stock price",
    "get_news": "Get news headlines",
    "get_spotify": "Get currently playing track",
}
```

**Use Cases by Category**:

| Category | Data Source | Light Behavior |
|----------|-------------|----------------|
| **Weather** | Temperature, conditions, alerts | Blue=cold, red=hot, purple=storm |
| **Calendar** | Meetings, events, focus time | Yellow=meeting soon, red=busy |
| **Productivity** | Pomodoro, emails, notifications | Work state indicator |
| **Finance** | Stock prices, crypto | Green=up, red=down |
| **Smart Home** | Motion, door, temperature sensors | Presence-aware lighting |
| **Health** | Circadian rhythm, sleep schedule | Time-appropriate colors |
| **DevOps** | CI/CD status, server health | Build status monitor |
| **Sports** | Game scores, team events | Team color celebrations |
| **Presence** | Home/away, guests | Welcome/security modes |

**Internal Data Sources** (no API needed):
```python
{"name": "state_duration", "internal": True, "tracks": "time_in_state_ms"}
{"name": "activity", "internal": True, "tracks": "transitions_today"}
{"name": "pattern", "internal": True, "tracks": "last_5_transitions"}
```

**Event-Driven Sources** (push, not poll):
```python
{"name": "webhook", "type": "http_listener", "port": 8080, "fires": "webhook_received"}
{"name": "mqtt", "type": "mqtt_subscribe", "topic": "home/doorbell"}
```

**Example: Weather-Reactive Light**

User says: *"Check the weather - cold is blue, hot is red"*

Claude generates:
```json
{
    "createDataSource": {
        "name": "weather",
        "interval_ms": 3600000,
        "fetch": {"tool": "get_weather", "args": {"location": "auto"}},
        "store": {"temperature": "result.temp"},
        "fires": "weather_updated"
    },
    "createState": [
        {"name": "cold_blue", "r": 0, "g": 100, "b": 255},
        {"name": "hot_red", "r": 255, "g": 50, "b": 0}
    ],
    "appendRules": [
        {"from": "*", "on": "weather_updated", "to": "cold_blue",
         "condition": "getData('temperature') < 60"},
        {"from": "*", "on": "weather_updated", "to": "hot_red",
         "condition": "getData('temperature') >= 80"}
    ]
}
```

**Why This Scales**:
- Rules stay simple - just check variables
- Data sources are independent - add/remove without breaking rules
- API failures handled in data layer - rules use last known value
- Easy to test - mock variables, test rules in isolation

---

### 5. Custom Tools (Claude-Defined Integrations)

**What**: Allow Claude to write its own tools for fetching data from any API or service. These tools can then be used by data sources.

**Why**: Instead of being limited to pre-built fetchers (get_weather, get_stock), Claude can create any integration on the fly.

**Architecture**:
```
raspi/
  custom_tools/
    __init__.py
    registry.py      # Tool registry
    executor.py      # Safe sandboxed execution
    builtin.py       # Pre-built tools (weather, web_search, etc.)
```

**Tool Definition**:
```python
{
    "name": "get_weather",
    "description": "Fetch current weather for a location",
    "params": {
        "location": {"type": "string", "required": True}
    },
    "code": """
import requests
response = requests.get(f"https://wttr.in/{location}?format=j1")
data = response.json()
return {
    "temp": data["current_condition"][0]["temp_F"],
    "condition": data["current_condition"][0]["weatherDesc"][0]["value"],
    "humidity": data["current_condition"][0]["humidity"]
}
""",
    "returns": {"temp": "number", "condition": "string", "humidity": "number"}
}
```

**How Claude Uses It**:

1. **User says**: "Track bitcoin price and show green when up, red when down"

2. **Claude creates tool**:
```json
{
    "defineTool": {
        "name": "get_bitcoin_price",
        "description": "Fetch current Bitcoin price",
        "params": {},
        "code": "import requests\nresponse = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot')\nreturn {'price': float(response.json()['data']['amount'])}",
        "returns": {"price": "number"}
    }
}
```

3. **Claude creates data source using that tool**:
```json
{
    "createDataSource": {
        "name": "bitcoin",
        "interval_ms": 60000,
        "fetch": {"tool": "get_bitcoin_price", "args": {}},
        "store": {"btc_price": "result.price"},
        "fires": "bitcoin_updated"
    }
}
```

4. **Claude creates rules**:
```json
{
    "appendRules": [
        {"from": "*", "on": "bitcoin_updated", "to": "green",
         "condition": "getData('btc_price') > getData('btc_price_prev')"},
        {"from": "*", "on": "bitcoin_updated", "to": "red",
         "condition": "getData('btc_price') < getData('btc_price_prev')"}
    ]
}
```

**Safety/Sandboxing**:
- Restricted imports whitelist: `requests`, `json`, `time`, `math`, `re`
- No file system access
- No subprocess/os access
- Timeout enforcement (5s max)
- Network access limited to HTTPS only
- Rate limiting per tool

**Built-in Tools** (pre-installed):
```python
BUILTIN_TOOLS = {
    "web_search": "Search the web via DuckDuckGo",
    "fetch_json": "GET JSON from any URL",
    "fetch_text": "GET text from any URL",
    "get_time": "Get current time/date info",
}
```

**Flow**:
```
User request: "show me green when Bitcoin is up"
                    ↓
Claude thinks: "I need a Bitcoin price tool"
                    ↓
Claude: defineTool(get_bitcoin_price)
                    ↓
Claude: createDataSource(bitcoin, uses get_bitcoin_price)
                    ↓
Claude: createState(green), createState(red)
                    ↓
Claude: appendRules(bitcoin_updated → green/red)
                    ↓
System runs: tool fetches → stores → fires → rules evaluate
```

---

### 6. Pattern Library (Agent Tool)

**What**: A library of common patterns that Claude can look up on demand. Claude decides when to retrieve a pattern based on context.

**Key Insight**: Instead of auto-detecting patterns, give Claude a tool to look them up. This is more agentic - Claude decides when it needs help.

**Available Patterns**:

| Pattern | Description |
|---------|-------------|
| `counter` | Temporary behavior that reverts after N occurrences |
| `toggle` | A↔B switching |
| `cycle` | A→B→C→A rotation |
| `hold_release` | Hold=active, release=inactive |
| `timer` | Delayed state change |
| `schedule` | Time-of-day triggers |
| `data_reactive` | React to data source updates |

**Architecture**:
```
raspi/
  patterns/
    __init__.py
    library.py       # Pattern definitions + templates
```

**How It Works**:

1. **Claude's context includes**:
```
Available patterns you can look up:
- counter: For "next N times", "then back to normal" behaviors
- toggle: For on/off switching
- cycle: For rotating through states
- hold_release: For hold-to-activate behaviors
- timer: For delayed actions
- schedule: For time-of-day triggers
- data_reactive: For reacting to external data

Use getPattern(name) to retrieve template and example.
```

2. **Claude sees user request**: "next 5 clicks random colors then back to normal"

3. **Claude decides**: "This matches the counter pattern"

4. **Claude calls tool**:
```json
{"getPattern": {"name": "counter"}}
```

5. **Tool returns**:
```json
{
    "name": "counter",
    "description": "Temporary behavior that reverts after N occurrences",
    "template": {
        "variables": ["N", "temp_state", "return_state", "transition"],
        "rules": [
            "Entry: * → temp_state (transition) [if getData('counter') === undefined] {setData('counter', N-1)}",
            "Continue: temp_state → temp_state (transition) [if getData('counter') > 0] {setData('counter', getData('counter') - 1)}",
            "Exit: temp_state → return_state (transition) [if getData('counter') === 0] {setData('counter', undefined)}"
        ]
    },
    "example": {
        "user_request": "next 3 clicks show red, then back to normal",
        "output": {
            "createState": {"name": "red", "r": 255, "g": 0, "b": 0},
            "appendRules": [
                {"from": "*", "on": "button_click", "to": "red", "condition": "getData('counter') === undefined", "action": "setData('counter', 2)"},
                {"from": "red", "on": "button_click", "to": "red", "condition": "getData('counter') > 0", "action": "setData('counter', getData('counter') - 1)"},
                {"from": "red", "on": "button_click", "to": "off", "condition": "getData('counter') === 0", "action": "setData('counter', undefined)"}
            ]
        }
    }
}
```

6. **Claude adapts** the pattern to user's specific request (5 clicks, random colors)

**Why This Is Better**:
- Claude decides when to look up patterns (not forced)
- Claude can combine multiple patterns
- Less preprocessing overhead
- More transparent - Claude explicitly retrieves what it needs
- Patterns are just another tool in Claude's toolkit

**State Memory** (bonus tool):
```json
{"getStates": {}}  // Returns list of user-created states
{"getState": {"name": "sunset"}}  // Returns specific state definition
```
- User can say "use my sunset state"
- Claude calls `getStates()` to see what's available

---

## Agent Execution Loop

**What**: Replace single-shot parsing with a multi-turn agent loop. Claude iterates until the task is complete.

**Current Model (Single-Shot)**:
```
User input → LLM → JSON output → Execute all → Done
```

**New Model (Agentic Loop)**:
```
User input
    ↓
┌─────────────────────────────────────────┐
│           AGENT LOOP                    │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Claude thinks about next step  │   │
│  └──────────────┬──────────────────┘   │
│                 ↓                       │
│  ┌─────────────────────────────────┐   │
│  │  Claude calls tool(s)           │   │
│  │  - getPattern("counter")        │   │
│  │  - defineTool("get_weather")    │   │
│  │  - createState("blue")          │   │
│  │  - appendRules([...])           │   │
│  │  - done()                       │   │
│  └──────────────┬──────────────────┘   │
│                 ↓                       │
│  ┌─────────────────────────────────┐   │
│  │  Execute tool, return result    │   │
│  └──────────────┬──────────────────┘   │
│                 ↓                       │
│        Loop until done() called        │
└─────────────────────────────────────────┘
    ↓
Final response to user
```

**Example: Weather-Reactive Light**

User: "Check the weather and show blue if cold, red if hot"

```
┌─ Turn 1 ─────────────────────────────────────────────────────┐
│ Claude thinks: "I need to fetch weather data. Let me create  │
│                a tool for that."                             │
│                                                              │
│ Claude calls: defineTool({                                   │
│   name: "get_weather",                                       │
│   code: "import requests\n..."                               │
│ })                                                           │
│                                                              │
│ Result: {success: true, tool: "get_weather"}                 │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌─ Turn 2 ─────────────────────────────────────────────────────┐
│ Claude thinks: "Now I need to set up periodic weather checks"│
│                                                              │
│ Claude calls: createDataSource({                             │
│   name: "weather",                                           │
│   interval_ms: 3600000,                                      │
│   fetch: {tool: "get_weather"},                              │
│   store: {temperature: "result.temp"},                       │
│   fires: "weather_updated"                                   │
│ })                                                           │
│                                                              │
│ Result: {success: true, data_source: "weather"}              │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌─ Turn 3 ─────────────────────────────────────────────────────┐
│ Claude thinks: "Now I need the blue and red states"          │
│                                                              │
│ Claude calls: createState({name: "blue", r: 0, g: 0, b: 255})│
│               createState({name: "red", r: 255, g: 0, b: 0}) │
│                                                              │
│ Result: {success: true, states: ["blue", "red"]}             │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌─ Turn 4 ─────────────────────────────────────────────────────┐
│ Claude thinks: "Finally, rules to react to weather updates"  │
│                                                              │
│ Claude calls: appendRules([                                  │
│   {from: "*", on: "weather_updated", to: "blue",             │
│    condition: "getData('temperature') < 60"},                │
│   {from: "*", on: "weather_updated", to: "red",              │
│    condition: "getData('temperature') >= 60"}                │
│ ])                                                           │
│                                                              │
│ Result: {success: true, rules_added: 2}                      │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌─ Turn 5 ─────────────────────────────────────────────────────┐
│ Claude thinks: "All set up. Let me confirm with the user."   │
│                                                              │
│ Claude calls: done({                                         │
│   message: "I've set up weather monitoring. The light will   │
│            check the weather every hour and show blue when   │
│            it's below 60°F, red when it's 60°F or above."    │
│ })                                                           │
└──────────────────────────────────────────────────────────────┘
```

**Implementation**:

```python
# voice/agent_executor.py

class AgentExecutor:
    def __init__(self, state_machine, tool_registry):
        self.state_machine = state_machine
        self.tools = tool_registry
        self.max_turns = 10  # Safety limit

    async def run(self, user_input: str) -> str:
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]

        for turn in range(self.max_turns):
            # Call Claude with tools
            response = await claude.messages.create(
                model="claude-sonnet-4-20250514",
                messages=messages,
                tools=self.tools.get_tool_definitions()
            )

            # Check if done
            if response.stop_reason == "end_turn":
                return self.extract_final_message(response)

            # Execute tool calls
            tool_results = []
            for tool_use in response.content:
                if tool_use.type == "tool_use":
                    result = await self.tools.execute(
                        tool_use.name,
                        tool_use.input
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result)
                    })

            # Add assistant response and tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return "Max turns reached"
```

**Agent System Prompt**:
```
You are a light controller agent. You configure a smart light by calling tools.

Available tools:
- getPattern(name): Look up a pattern template (counter, toggle, cycle, etc.)
- getStates(): List existing states
- createState(name, r, g, b, speed, description): Create a light state
- deleteState(name): Remove a state
- appendRules(rules): Add transition rules
- deleteRules(criteria): Remove rules
- setState(name): Immediately change to a state
- defineTool(name, code, params, returns): Create a new API integration
- createDataSource(name, interval_ms, fetch, store, fires): Set up data fetching
- done(message): Signal completion and respond to user

Process:
1. Understand what the user wants
2. Look up patterns if the request matches a known pattern
3. Create any tools needed for external data
4. Set up data sources if needed
5. Create states
6. Create rules
7. Call done() with a summary for the user

You can call multiple tools in a single turn if they don't depend on each other.
```

**Tool Definitions**:
```python
AGENT_TOOLS = [
    {
        "name": "getPattern",
        "description": "Look up a pattern template. Available: counter, toggle, cycle, hold_release, timer, schedule, data_reactive",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": ["counter", "toggle", "cycle", "hold_release", "timer", "schedule", "data_reactive"]}
            },
            "required": ["name"]
        }
    },
    {
        "name": "defineTool",
        "description": "Create a custom tool for fetching external data",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "params": {"type": "object"},
                "code": {"type": "string"},
                "returns": {"type": "object"}
            },
            "required": ["name", "code"]
        }
    },
    {
        "name": "createDataSource",
        "description": "Set up periodic data fetching that stores results and fires transitions",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "interval_ms": {"type": "number"},
                "fetch": {"type": "object"},
                "store": {"type": "object"},
                "fires": {"type": "string"}
            },
            "required": ["name", "fetch", "fires"]
        }
    },
    {
        "name": "createState",
        "description": "Create a named light state",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "r": {"type": ["number", "string"]},
                "g": {"type": ["number", "string"]},
                "b": {"type": ["number", "string"]},
                "speed": {"type": ["number", "null"]},
                "description": {"type": "string"}
            },
            "required": ["name", "r", "g", "b"]
        }
    },
    {
        "name": "appendRules",
        "description": "Add transition rules",
        "input_schema": {
            "type": "object",
            "properties": {
                "rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "on": {"type": "string"},
                            "to": {"type": "string"},
                            "condition": {"type": "string"},
                            "action": {"type": "string"},
                            "priority": {"type": "number"}
                        },
                        "required": ["from", "on", "to"]
                    }
                }
            },
            "required": ["rules"]
        }
    },
    {
        "name": "setState",
        "description": "Immediately change to a state",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "done",
        "description": "Signal completion and provide final message to user",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"}
            },
            "required": ["message"]
        }
    }
]
```

**Benefits of Agentic Loop**:
- Claude can gather information before acting (getPattern, getStates)
- Claude can create dependencies in order (defineTool → createDataSource → rules)
- Claude can recover from errors (if a tool fails, it can try another approach)
- More natural conversation flow
- Claude can ask clarifying questions if needed

**Safety**:
- Max turns limit (default: 10)
- Tool execution sandboxing
- Rate limiting on API calls
- Timeout per turn

---

## Implementation Order

1. **Wildcards** - Quick win, foundation for safety rules
2. **Priority** - Quick win, enables rule layering
3. **Agent Executor** - Multi-turn agentic loop (replaces single-shot parser)
4. **Custom Tools** - Claude can write API integrations
5. **Data Sources** - Use tools on schedule, store results, fire transitions
6. **Pattern Library** - getPattern() tool for Claude to look up templates
7. **Prompt Refactor** - Move examples to patterns, document individual tools
8. **Test Suite** - Unit tests for all new components

---

## 7. Prompt Refactor

**What**: Simplify the system prompt. Move all examples into the pattern library. The prompt only explains what each tool does.

**Current Prompt** (bloated):
```
You are a state machine configuration assistant...
[100+ lines of examples]
[JSON schemas]
[Edge cases]
[Counter examples]
[Toggle examples]
...
```

**New Prompt** (lean):
```
You are a light controller agent. Configure a smart light by calling tools.

## Your Tools

### Information Gathering
- getPattern(name) - Look up a pattern template. Available: counter, toggle, cycle, hold_release, timer, schedule, data_reactive
- getStates() - List all existing states
- getRules() - List current rules

### State Management
- createState(name, r, g, b, speed?, description?) - Create a named light state
  - r, g, b: 0-255 or expression string like "random()" or "sin(frame * 0.1) * 255"
  - speed: null for static, milliseconds for animation
- deleteState(name) - Remove a state

### Rule Management
- appendRules(rules[]) - Add transition rules
  - Each rule: {from, on, to, condition?, action?, priority?}
  - from: state name or "*" for any state
  - on: transition name (button_click, timer, custom, etc.)
  - to: destination state
  - condition: expression like "getData('x') > 5"
  - action: expression like "setData('x', 0)"
  - priority: higher = checked first (default: 0)
- deleteRules(criteria) - Remove rules matching criteria

### Immediate Actions
- setState(name) - Change to a state immediately

### External Data
- defineTool(name, code, params?, returns?) - Create a custom API fetcher
- createDataSource(name, interval_ms, fetch, store, fires) - Set up periodic data fetching

### Completion
- done(message) - Signal you're finished and respond to user

## Process
1. Understand user request
2. If it matches a pattern (counter, toggle, etc.), call getPattern() first
3. Create any custom tools needed for external data
4. Set up data sources if needed
5. Create states
6. Create rules (remember wildcards and priorities)
7. Call done() with a summary

## Current System State
{dynamic_content}
```

**Key Changes**:
- No inline examples (those live in pattern library)
- Each tool documented with parameters
- Clear process flow
- Dynamic content injected (current states, rules, variables)

**Examples moved to patterns/library.py**:
- Counter example → `getPattern("counter")`
- Toggle example → `getPattern("toggle")`
- Timer example → `getPattern("timer")`
- etc.

---

## 8. Test Suite

**What**: Comprehensive unit tests for all new components.

**Test Structure**:
```
raspi/
  tests/
    __init__.py
    test_wildcards.py        # Rule wildcard matching
    test_priority.py         # Priority-based rule evaluation
    test_agent_executor.py   # Multi-turn agent loop
    test_custom_tools.py     # Tool definition and sandboxed execution
    test_data_sources.py     # Scheduler, fetching, variable storage
    test_patterns.py         # Pattern library and getPattern tool
    test_integration.py      # End-to-end scenarios
```

**test_wildcards.py**:
```python
import pytest
from core.rule import Rule

class TestWildcardMatching:
    def test_exact_match(self):
        rule = Rule("off", "button_click", "on")
        assert rule.matches("off", "button_click") == True
        assert rule.matches("on", "button_click") == False

    def test_star_wildcard(self):
        rule = Rule("*", "button_hold", "off")
        assert rule.matches("off", "button_hold") == True
        assert rule.matches("on", "button_hold") == True
        assert rule.matches("rainbow", "button_hold") == True
        assert rule.matches("off", "button_click") == False

    def test_prefix_wildcard(self):
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("color/red", "button_click") == True
        assert rule.matches("color/blue", "button_click") == True
        assert rule.matches("animation/pulse", "button_click") == False
```

**test_priority.py**:
```python
import pytest
from core.state_machine import StateMachine

class TestPriorityEvaluation:
    def test_higher_priority_wins(self):
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "click", "to": "blue", "priority": 0})
        sm.add_rule({"from": "off", "on": "click", "to": "red", "priority": 10})

        sm.set_state("off")
        sm.execute_transition("click")
        assert sm.current_state == "red"  # Higher priority wins

    def test_same_priority_first_wins(self):
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "click", "to": "blue", "priority": 0})
        sm.add_rule({"from": "off", "on": "click", "to": "red", "priority": 0})

        sm.set_state("off")
        sm.execute_transition("click")
        assert sm.current_state == "blue"  # First added wins
```

**test_agent_executor.py**:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from voice.agent_executor import AgentExecutor

class TestAgentExecutor:
    @pytest.mark.asyncio
    async def test_simple_request(self):
        executor = AgentExecutor(mock_state_machine, mock_tools)
        result = await executor.run("Turn the light red")
        assert "red" in result.lower()

    @pytest.mark.asyncio
    async def test_multi_turn_with_pattern(self):
        executor = AgentExecutor(mock_state_machine, mock_tools)
        result = await executor.run("Next 5 clicks random colors then back to normal")
        # Should have called getPattern, createState, appendRules
        assert mock_tools.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_max_turns_limit(self):
        executor = AgentExecutor(mock_state_machine, mock_tools)
        executor.max_turns = 2
        # Mock Claude to never call done()
        result = await executor.run("Infinite loop request")
        assert "max turns" in result.lower()
```

**test_custom_tools.py**:
```python
import pytest
from custom_tools.executor import SafeExecutor
from custom_tools.registry import ToolRegistry

class TestToolDefinition:
    def test_define_simple_tool(self):
        registry = ToolRegistry()
        registry.define_tool({
            "name": "get_number",
            "code": "return 42"
        })
        assert "get_number" in registry.list_tools()

    def test_execute_tool(self):
        executor = SafeExecutor()
        result = executor.run("return 1 + 1")
        assert result == 2

class TestSandboxing:
    def test_blocked_imports(self):
        executor = SafeExecutor()
        with pytest.raises(SecurityError):
            executor.run("import os; os.system('rm -rf /')")

    def test_allowed_imports(self):
        executor = SafeExecutor()
        result = executor.run("import math; return math.sqrt(16)")
        assert result == 4.0

    def test_timeout(self):
        executor = SafeExecutor(timeout=1)
        with pytest.raises(TimeoutError):
            executor.run("while True: pass")
```

**test_data_sources.py**:
```python
import pytest
from data_sources.scheduler import DataSourceScheduler
from data_sources.registry import DataSourceRegistry

class TestDataSourceRegistry:
    def test_register_source(self):
        registry = DataSourceRegistry()
        registry.add({
            "name": "test",
            "interval_ms": 1000,
            "fetch": {"tool": "get_number"},
            "store": {"value": "result"},
            "fires": "test_updated"
        })
        assert "test" in registry.list_sources()

class TestDataSourceScheduler:
    @pytest.mark.asyncio
    async def test_fires_transition(self):
        fired = []
        def on_fire(transition):
            fired.append(transition)

        scheduler = DataSourceScheduler(on_transition=on_fire)
        scheduler.add_source({
            "name": "test",
            "interval_ms": 100,
            "fetch": {"tool": "mock_tool"},
            "fires": "test_updated"
        })

        await asyncio.sleep(0.15)
        assert "test_updated" in fired
```

**test_patterns.py**:
```python
import pytest
from patterns.library import PatternLibrary

class TestPatternLibrary:
    def test_get_counter_pattern(self):
        library = PatternLibrary()
        pattern = library.get("counter")
        assert pattern["name"] == "counter"
        assert "template" in pattern
        assert "example" in pattern

    def test_pattern_not_found(self):
        library = PatternLibrary()
        pattern = library.get("nonexistent")
        assert pattern is None

    def test_list_patterns(self):
        library = PatternLibrary()
        patterns = library.list()
        assert "counter" in patterns
        assert "toggle" in patterns
        assert "cycle" in patterns
```

**test_integration.py**:
```python
import pytest
from voice.agent_executor import AgentExecutor

class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_weather_reactive_flow(self):
        """Full flow: define tool → create data source → create rules"""
        executor = AgentExecutor(state_machine, tool_registry)
        result = await executor.run(
            "Check the weather every hour. Blue if cold, red if hot."
        )

        # Verify tool was created
        assert "get_weather" in tool_registry.list_tools()

        # Verify data source was created
        assert "weather" in data_source_registry.list_sources()

        # Verify rules were created
        rules = state_machine.get_rules()
        assert any(r.transition == "weather_updated" for r in rules)

    @pytest.mark.asyncio
    async def test_counter_pattern_flow(self):
        """User requests counter behavior, agent looks up pattern"""
        executor = AgentExecutor(state_machine, tool_registry)
        result = await executor.run(
            "Next 3 clicks give me random colors, then back to normal"
        )

        # Should have rules with counter conditions
        rules = state_machine.get_rules()
        assert any("getData('counter')" in (r.condition or "") for r in rules)
```

**Running Tests**:
```bash
# Run all tests
pytest raspi/tests/ -v

# Run specific test file
pytest raspi/tests/test_wildcards.py -v

# Run with coverage
pytest raspi/tests/ --cov=raspi --cov-report=html
```

---

## File Changes Summary

| File | Changes |
|------|---------|
| `core/rule.py` | Add wildcard matching, priority field, enabled field |
| `core/state_machine.py` | Sort by priority, filter enabled |
| `voice/agent_executor.py` | NEW - multi-turn agentic loop |
| `voice/tool_registry.py` | NEW - registry of all agent tools |
| `voice/tools/` | NEW - tool implementations (getPattern, createState, etc.) |
| `voice/agent_prompt.py` | NEW - lean system prompt (replaces old prompts) |
| `custom_tools/__init__.py` | NEW - custom tools package |
| `custom_tools/registry.py` | NEW - tool registry (stores Claude-defined tools) |
| `custom_tools/executor.py` | NEW - sandboxed code execution |
| `custom_tools/builtin.py` | NEW - pre-built tools (fetch_json, web_search, etc.) |
| `data_sources/__init__.py` | NEW - data source package |
| `data_sources/registry.py` | NEW - data source registry |
| `data_sources/scheduler.py` | NEW - polling scheduler |
| `patterns/library.py` | NEW - pattern definitions + examples (moved from prompts) |
| `tests/` | NEW - comprehensive test suite |
| `prompts/` | DEPRECATED - replaced by agent_prompt.py + patterns/library.py |

---

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                  │
│                    (Voice / Button / API)                          │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                      PATTERN DETECTOR                               │
│         Recognizes: counter, toggle, cycle, timer, etc.            │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                         CLAUDE AGENT                                │
│                                                                     │
│  Tools available:                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ createState  │ │ appendRules  │ │ setState     │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ createData   │ │ defineFunc   │ │ defineTrans  │               │
│  │ Source       │ │              │ │ ition        │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  DATA SOURCES   │   │     RULES       │   │     STATES      │
│                 │   │                 │   │                 │
│ weather         │   │ * → blue        │   │ blue: 0,0,255   │
│ calendar        │   │ (weather_upd)   │   │ red: 255,0,0    │
│ stocks          │   │ [temp < 60]     │   │ pulse: anim     │
│                 │   │ priority: 10    │   │                 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         │    ┌────────────────┘                     │
         │    │                                      │
         ▼    ▼                                      │
┌─────────────────┐                                  │
│   VARIABLES     │                                  │
│  (state_data)   │◄─────────────────────────────────┘
│                 │
│ temperature: 45 │
│ is_home: true   │
│ counter: 3      │
└────────┬────────┘
         │
         │ fires transitions
         ▼
┌─────────────────┐
│ STATE MACHINE   │
│                 │
│ evaluate rules  │
│ execute actions │
│ change state    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LED CONTROLLER │
│                 │
│ set_color(r,g,b)│
└─────────────────┘
```

---

## Open Questions

1. **Persistence**: Where to store data sources, custom functions, custom transitions? (config.yaml? separate file? database?)
2. **Versioning**: How to handle breaking changes to patterns?
3. **Validation**: How strictly to validate custom code?
4. **Limits**: Max number of custom functions/transitions/data sources?
5. **Rate limits**: How to handle API rate limits in data sources?
6. **Credentials**: How to securely store API keys for data sources?
7. **Offline mode**: What happens when data sources can't reach APIs?
