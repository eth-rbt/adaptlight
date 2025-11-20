# Claude Integration for AdaptLight

## Overview

AdaptLight now supports Claude 4.5 Sonnet as an alternative to OpenAI GPT for command parsing. Claude's superior tool calling capabilities make it excellent for complex state machine operations.

## Features

### 5 Core Tools

Claude has access to these tools for manipulating the state machine:

1. **set_state** - Immediately change the current LED state
2. **append_rules** - Add new transition rules to the state machine
3. **delete_rules** - Remove existing rules by index, criteria, or all
4. **create_state** - Define new color/animation states
5. **delete_state** - Remove existing states

### Key Advantages of Claude

- **Multiple tool calls in single response** - Claude can call multiple tools at once (e.g., create a state AND add rules for it in one go)
- **Better instruction following** - More reliable at understanding complex commands
- **Explicit tool ordering** - Creates states before referencing them in rules

## Configuration

### 1. Set parsing method to `claude` in config.yaml:

```yaml
openai:
  parsing_method: claude  # Changed from 'json_output' to 'claude'

claude:
  api_key: sk-ant-api03-...  # Your Anthropic API key
  model: claude-3-5-sonnet-20241022
```

### 2. Run the interactive evaluator:

```bash
cd /Users/ethrbt/code/adaptlight/raspi
python -m eval.interactive
```

## Example Usage

Once started, you can type commands like:

```
➤ add a red state
[Claude will call: create_state with r=255, g=0, b=0]

➤ when I double click, go to red
[Claude will call: append_rules with the transition]

➤ create a purple state and make it activate on button hold
[Claude will call BOTH: create_state AND append_rules in one response]

➤ delete all rules and reset to default
[Claude will call: delete_rules with reset_rules=true]
```

## Tool Calling Format

Claude returns tool calls in this format:

```python
{
    'toolCalls': [
        {
            'id': 'toolu_01ABC...',
            'name': 'create_state',
            'arguments': {
                'name': 'red',
                'r': 255,
                'g': 0,
                'b': 0,
                'speed': null,
                'description': 'Bright red color'
            }
        },
        {
            'id': 'toolu_02DEF...',
            'name': 'append_rules',
            'arguments': {
                'rules': [{
                    'state1': 'off',
                    'transition': 'button_double_click',
                    'state2': 'red',
                    'condition': null,
                    'action': null
                }]
            }
        }
    ],
    'message': 'I've created a red state and added a rule...',
    'success': True
}
```

## Switching Back to OpenAI

Just change the parsing_method back:

```yaml
openai:
  parsing_method: json_output  # or 'reasoning' or 'function_calling'
```

## Implementation Details

- **File**: `raspi/voice/command_parser.py`
- **Method**: `_parse_claude()` (line ~900)
- **Tool definitions**: Anthropic format with `input_schema`
- **System prompt**: Includes full state machine context
- **Conversation history**: Maintained for context across multiple commands
