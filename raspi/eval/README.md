# AdaptLight Parser Evaluation

This directory contains example-based evaluation tests for the AdaptLight command parser.

## Structure

- **`examples.py`**: Test cases organized by category (basic rules, animations, conditionals, etc.)
- **`eval_parser.py`**: Evaluation script that runs tests and compares results
- **`__init__.py`**: Module initialization

## Usage

### Run All Tests

```bash
cd raspi
python -m eval.eval_parser
```

or

```bash
cd raspi/eval
./eval_parser.py
```

### Requirements

- OpenAI API key configured in `raspi/config.yaml`
- All dependencies from `raspi/requirements.txt` installed

## Test Categories

1. **Basic Rules**: Simple on/off toggles and colored lights
2. **Color Manipulation**: Brightness changes, color cycling
3. **Animations**: Rainbow, pulsing, and other animated patterns
4. **Conditionals**: Counter-based and time-based rules
5. **Immediate State**: Direct state changes (set_state)
6. **Rule Modifications**: Changing existing rules
7. **Resets**: Resetting to default configuration

## Adding New Tests

Edit `examples.py` and add your test case to the appropriate category:

```python
{
    "name": "Test name",
    "description": "What this tests",
    "previous_state": {
        "rules": [],
        "current_state": "off"
    },
    "user_input": "User command here",
    "expected_tools": [
        {
            "name": "tool_name",
            "arguments": {...}
        }
    ]
}
```

## Understanding Results

- **✅ PASSED**: Tool calls match expected output
- **❌ FAILED**: Tool calls don't match or parser failed
- **❌ ERROR**: Exception occurred during parsing

## Notes

- Tests verify tool call structure, not exact argument values
- More sophisticated comparison logic can be added as needed
- Tests use the actual OpenAI API, so they consume tokens
- See `../prompts/parsing_prompt_concise.py` for the streamlined prompt
