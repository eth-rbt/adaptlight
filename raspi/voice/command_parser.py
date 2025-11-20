"""
Command parser for AdaptLight voice commands.

This module is a port of server.js and uses OpenAI API to parse
natural language commands into state machine rules.

Takes voice input like "turn on the light when button is clicked"
and converts it to structured rules using GPT-5 function calling.
"""

import json
from typing import List, Dict


class CommandParser:
    """Parses natural language commands into state machine rules using OpenAI GPT-5."""

    def __init__(self, api_key=None, parsing_method='json_output', prompt_variant='full', model='gpt-4o',
                 reasoning_effort='medium', verbosity=0, audio_player=None, claude_api_key=None):
        """
        Initialize command parser.

        Args:
            api_key: OpenAI API key
            parsing_method: Parsing method to use ('json_output', 'reasoning', 'function_calling', or 'claude')
            prompt_variant: Prompt variant to use ('full' or 'concise')
            model: Model to use (e.g., 'gpt-4o', 'gpt-5-mini', 'claude-3-5-sonnet-20241022')
            reasoning_effort: Reasoning effort level ('low', 'medium', 'high')
            verbosity: Verbosity level for reasoning mode (0-2)
            audio_player: Optional AudioPlayer instance for TTS playback
            claude_api_key: Anthropic API key for Claude (optional)
        """
        self.api_key = api_key
        self.claude_api_key = claude_api_key
        self.conversation_history = []
        self.max_history = 2  # Keep last 2 commands with actions for context
        self.parsing_method = parsing_method
        self.prompt_variant = prompt_variant
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.audio_player = audio_player

        # Initialize OpenAI client
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            print(f"CommandParser initialized: method={parsing_method}, variant={prompt_variant}, model={model}")
        except ImportError:
            self.client = None
            print("Warning: OpenAI library not available")

        # Initialize Claude client if using Claude
        self.claude_client = None
        if parsing_method == 'claude' or claude_api_key:
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic(api_key=claude_api_key)
                print(f"Claude client initialized with model: {model}")
            except ImportError:
                print("Warning: Anthropic library not available. Install with: pip install anthropic")

        # No longer using function calling - using JSON output instead
        # Keeping tool definitions commented out for reference
        """
        self.tools = [
            {
                "type": "function",
                "name": "append_rules",
                "description": "Add new state transition rules to the state machine. Use this to create new behaviors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rules": {
                            "type": "array",
                            "description": "Array of rule objects to add",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "state1": {
                                        "type": "string",
                                        "enum": ["off", "on", "color", "animation"],
                                        "description": "Starting state name"
                                    },
                                    "state1Param": {
                                        "oneOf": [
                                            {"type": "null"},
                                            {"type": "object"}
                                        ],
                                        "description": "Parameters for state1 (null if none)"
                                    },
                                    "transition": {
                                        "type": "string",
                                        "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"],
                                        "description": "Transition/event that triggers this rule"
                                    },
                                    "state2": {
                                        "type": "string",
                                        "enum": ["off", "on", "color", "animation"],
                                        "description": "Destination state name"
                                    },
                                    "state2Param": {
                                        "oneOf": [
                                            {"type": "null"},
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "r": {"type": ["number", "string"]},
                                                    "g": {"type": ["number", "string"]},
                                                    "b": {"type": ["number", "string"]},
                                                    "speed": {"type": "number"}
                                                },
                                                "required": ["r", "g", "b"],
                                                "additionalProperties": False
                                            }
                                        ],
                                        "description": "Parameters for state2 (object with r,g,b for color/animation, null for on/off)"
                                    },
                                    "condition": {
                                        "type": ["string", "null"],
                                        "description": "Optional condition expression"
                                    },
                                    "action": {
                                        "type": ["string", "null"],
                                        "description": "Optional action to execute"
                                    }
                                },
                                "required": ["state1", "transition", "state2", "state2Param"],
                                "allOf": [
                                    {
                                        "if": {"properties": {"state2": {"enum": ["on", "off"]}}},
                                        "then": {"properties": {"state2Param": {"const": None}}}
                                    },
                                    {
                                        "if": {"properties": {"state2": {"const": "color"}}},
                                        "then": {"properties": {"state2Param": {"type": "object", "required": ["r", "g", "b"]}}}
                                    },
                                    {
                                        "if": {"properties": {"state2": {"const": "animation"}}},
                                        "then": {"properties": {"state2Param": {"type": "object", "required": ["r", "g", "b", "speed"]}}}
                                    }
                                ]
                            }
                        }
                    },
                    "required": ["rules"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "delete_rules",
                "description": "Delete existing rules from the state machine. Can delete by index, by criteria, or all rules.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "indices": {
                            "type": "array",
                            "description": "Array of rule indices to delete (0-based)",
                            "items": {"type": "number"}
                        },
                        "state1": {
                            "type": "string",
                            "enum": ["off", "on", "color", "animation"],
                            "description": "Delete rules matching this starting state"
                        },
                        "transition": {
                            "type": "string",
                            "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"],
                            "description": "Delete rules matching this transition"
                        },
                        "state2": {
                            "type": "string",
                            "enum": ["off", "on", "color", "animation"],
                            "description": "Delete rules matching this destination state"
                        },
                        "delete_all": {"type": "boolean", "description": "If true, delete all rules"}
                    },
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "set_state",
                "description": "Change the current state of the system immediately.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["off", "on", "color", "animation"],
                            "description": "The state to switch to"
                        },
                        "params": {
                            "oneOf": [
                                {"type": "null"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "r": {"type": ["number", "string"]},
                                        "g": {"type": ["number", "string"]},
                                        "b": {"type": ["number", "string"]},
                                        "speed": {"type": "number"}
                                    }
                                }
                            ],
                            "description": "Optional parameters to pass to the state (e.g., color values)"
                        }
                    },
                    "required": ["state"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "manage_variables",
                "description": "Manage global variables in the state machine data store.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["set", "delete", "clear_all"],
                            "description": "Action to perform: 'set' to add/update variables, 'delete' to remove specific keys, 'clear_all' to remove all variables"
                        },
                        "variables": {
                            "type": "object",
                            "description": "Key-value pairs to set (used with action: 'set')"
                        },
                        "keys": {
                            "type": "array",
                            "description": "Array of keys to delete (used with action: 'delete')",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["action"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "reset_rules",
                "description": "Reset all rules back to the default state (simple on/off toggle with button click). Use this when the user wants to start fresh or go back to basics.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False
                }
            }
        ]
        """

    def parse_command(self, user_input: str, available_states: str,
                     available_transitions: List[Dict], current_rules: List[Dict],
                     current_state: str = "off", global_variables: Dict = None) -> Dict:
        """
        Parse a natural language command into tool calls.

        Args:
            user_input: User's voice command
            available_states: Formatted string of available states
            available_transitions: List of available transitions
            current_rules: Current rules in the system
            current_state: Current state of the lamp
            global_variables: Global variables dict (optional)

        Returns:
            Dict with format: {
                'toolCalls': [...],
                'message': str,
                'success': bool
            }
        """
        # Route to the appropriate parsing method
        if self.parsing_method == 'claude':
            if not self.claude_client:
                print("Claude client not available")
                return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}
            return self._parse_claude(
                user_input, available_states, available_transitions,
                current_rules, current_state, global_variables
            )
        elif self.parsing_method == 'json_output':
            if not self.client:
                print("OpenAI client not available")
                return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}
            return self._parse_json_output(
                user_input, available_states, available_transitions,
                current_rules, current_state, global_variables
            )
        elif self.parsing_method == 'reasoning':
            if not self.client:
                print("OpenAI client not available")
                return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}
            return self._parse_reasoning(
                user_input, available_states, available_transitions,
                current_rules, current_state, global_variables
            )
        elif self.parsing_method == 'function_calling':
            if not self.client:
                print("OpenAI client not available")
                return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}
            return self._parse_function_calling(
                user_input, available_states, available_transitions,
                current_rules, current_state, global_variables
            )
        else:
            print(f"Unknown parsing method: {self.parsing_method}")
            return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}

    def _parse_json_output(self, user_input: str, available_states: str,
                          available_transitions: List[Dict], current_rules: List[Dict],
                          current_state: str = "off", global_variables: Dict = None) -> Dict:
        """
        Parse command using JSON structured output.

        Returns:
            Dict with format: {'toolCalls': [...], 'message': str, 'success': bool}
        """
        # Build dynamic content for the prompt
        dynamic_content = self._build_dynamic_content(
            available_states, available_transitions, current_rules,
            current_state, global_variables or {}
        )

        # Load the parsing prompt from configured folder
        import importlib
        prompt_module_path = f'prompts.{self.parsing_method}.{self.prompt_variant}'
        prompt_module = importlib.import_module(prompt_module_path)
        get_system_prompt = prompt_module.get_system_prompt
        system_prompt = get_system_prompt(dynamic_content)

        # Define JSON schema for structured outputs
        json_schema = {
            "type": "object",
            "properties": {
                "setState": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "state": {"type": "string"}
                            },
                            "required": ["state"],
                            "additionalProperties": False
                        }
                    ]
                },
                "createState": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "r": {"type": ["number", "string"]},
                                "g": {"type": ["number", "string"]},
                                "b": {"type": ["number", "string"]},
                                "speed": {"type": ["number", "null"]},
                                "description": {"type": ["string", "null"]}
                            },
                            "required": ["name", "r", "g", "b", "speed", "description"],
                            "additionalProperties": False
                        }
                    ]
                },
                "deleteState": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"}
                            },
                            "required": ["name"],
                            "additionalProperties": False
                        }
                    ]
                },
                "appendRules": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "rules": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "state1": {"type": "string"},
                                            "transition": {
                                                "type": "string",
                                                "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"]
                                            },
                                            "state2": {"type": "string"},
                                            "condition": {"type": ["string", "null"]},
                                            "action": {"type": ["string", "null"]}
                                        },
                                        "required": ["state1", "transition", "state2", "condition", "action"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["rules"],
                            "additionalProperties": False
                        }
                    ]
                },
                "deleteRules": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "transition": {"type": ["string", "null"]},
                                "state1": {"type": ["string", "null"]},
                                "state2": {"type": ["string", "null"]},
                                "indices": {
                                    "anyOf": [
                                        {"type": "null"},
                                        {
                                            "type": "array",
                                            "items": {"type": "number"}
                                        }
                                    ]
                                },
                                "delete_all": {"type": ["boolean", "null"]},
                                "reset_rules": {"type": ["boolean", "null"]}
                            },
                            "required": ["transition", "state1", "state2", "indices", "delete_all", "reset_rules"],
                            "additionalProperties": False
                        }
                    ]
                }
            },
            "required": ["deleteState", "createState", "deleteRules", "appendRules", "setState"],
            "additionalProperties": False
        }

        try:
            # Call OpenAI API using responses.create with Structured Outputs
            print(f"Calling OpenAI API with model: {self.model} (Structured Outputs)")
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                reasoning={"effort": self.reasoning_effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "command_response",
                        "schema": json_schema,
                        "strict": True
                    }
                }
            )

            # Extract text output (should be JSON)
            text_output = None
            for item in response.output:
                if item.type == "text":
                    text_output = item.text
                    break
                elif item.type == "message":
                    # For structured outputs, text is in message.content[0].text
                    if item.content and len(item.content) > 0:
                        text_output = item.content[0].text
                        break

            if not text_output:
                print("Error: No text output from API")
                return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}

            # Parse JSON output
            # Clean up potential markdown code blocks
            json_text = text_output.strip()
            if json_text.startswith("```json"):
                json_text = json_text[7:]  # Remove ```json
            if json_text.startswith("```"):
                json_text = json_text[3:]  # Remove ```
            if json_text.endswith("```"):
                json_text = json_text[:-3]  # Remove trailing ```
            json_text = json_text.strip()

            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")
                print(f"Raw output: {text_output}")
                return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}

            # Store raw JSON for debugging
            print(f"Parsed JSON: {json.dumps(parsed, indent=2)}")

            # Clean up the JSON before converting to tool calls
            def cleanup_json(data):
                """Remove null speed fields from params and clean deleteRules"""
                if isinstance(data, dict):
                    # Clean setState params - remove null speed
                    if data.get('setState') and data['setState'].get('params') and isinstance(data['setState']['params'], dict):
                        # Only delete if key exists and value is None
                        if 'speed' in data['setState']['params'] and data['setState']['params']['speed'] is None:
                            del data['setState']['params']['speed']

                    # Clean deleteRules - remove null fields
                    if data.get('deleteRules') and isinstance(data['deleteRules'], dict):
                        # Remove all null fields from deleteRules
                        data['deleteRules'] = {k: v for k, v in data['deleteRules'].items() if v is not None}
                        # If deleteRules becomes empty, set it to None
                        if not data['deleteRules']:
                            data['deleteRules'] = None

                return data

            parsed = cleanup_json(parsed)

            # Convert JSON to toolCalls format for compatibility with eval script
            results = {
                'toolCalls': [],
                'message': None,
                'reasoning': None,
                'rawJson': parsed,  # Store raw JSON for inspection
                'success': True
            }

            # CRITICAL: Execute in correct order!
            # 1. deleteState first (delete old states before creating new ones)
            # 2. createState second (create states before they can be used in rules)
            # 3. deleteRules third (remove old rules)
            # 4. appendRules fourth (add new rules that may reference new states)
            # 5. setState fifth (immediate state change after rules are set)
            # This order ensures states exist before being referenced in rules!

            if parsed.get('deleteState'):
                results['toolCalls'].append({
                    'id': 'delete_state_1',
                    'name': 'delete_state',
                    'arguments': parsed['deleteState']
                })

            if parsed.get('createState'):
                results['toolCalls'].append({
                    'id': 'create_state_1',
                    'name': 'create_state',
                    'arguments': parsed['createState']
                })

            if parsed.get('deleteRules'):
                results['toolCalls'].append({
                    'id': 'delete_rules_1',
                    'name': 'delete_rules',
                    'arguments': parsed['deleteRules']
                })

            if parsed.get('appendRules'):
                results['toolCalls'].append({
                    'id': 'append_rules_1',
                    'name': 'append_rules',
                    'arguments': parsed['appendRules']
                })

            if parsed.get('setState'):
                results['toolCalls'].append({
                    'id': 'set_state_1',
                    'name': 'set_state',
                    'arguments': parsed['setState']
                })

            # Add to conversation history with JSON action
            history_entry = {
                'input': user_input,
                'json': parsed,  # Store the actual JSON output
                'state': current_state,  # Store state at time of command
                'rules': current_rules  # Store rules at time of command
            }
            self.conversation_history.append(history_entry)
            if len(self.conversation_history) > self.max_history:
                self.conversation_history.pop(0)

            return results

        except Exception as e:
            print(f"Error parsing command: {e}")
            import traceback
            traceback.print_exc()
            return {'toolCalls': [], 'message': None, 'reasoning': None, 'success': False}

    def _parse_reasoning(self, user_input: str, available_states: str,
                        available_transitions: List[Dict], current_rules: List[Dict],
                        current_state: str = "off", global_variables: Dict = None) -> Dict:
        """
        Parse command using reasoning with clarification support.

        Returns:
            Dict with format: {
                'toolCalls': [...],
                'message': str,
                'reasoning': str,
                'needsClarification': bool,
                'clarifyingQuestion': str,
                'success': bool
            }
        """
        # Build dynamic content for the prompt
        dynamic_content = self._build_dynamic_content(
            available_states, available_transitions, current_rules,
            current_state, global_variables or {}
        )

        # Load the reasoning prompt
        import importlib
        prompt_module_path = f'prompts.{self.parsing_method}.{self.prompt_variant}'
        prompt_module = importlib.import_module(prompt_module_path)
        get_system_prompt = prompt_module.get_system_prompt
        system_prompt = get_system_prompt(dynamic_content)

        # Define JSON schema with reasoning fields
        json_schema = {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "needsClarification": {"type": "boolean"},
                "clarifyingQuestion": {
                    "anyOf": [
                        {"type": "null"},
                        {"type": "string"}
                    ]
                },
                "setState": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "state": {"type": "string"}
                            },
                            "required": ["state"],
                            "additionalProperties": False
                        }
                    ]
                },
                "createState": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "r": {"type": ["number", "string"]},
                                "g": {"type": ["number", "string"]},
                                "b": {"type": ["number", "string"]},
                                "speed": {"type": ["number", "null"]},
                                "description": {"type": ["string", "null"]}
                            },
                            "required": ["name", "r", "g", "b", "speed", "description"],
                            "additionalProperties": False
                        }
                    ]
                },
                "deleteState": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"}
                            },
                            "required": ["name"],
                            "additionalProperties": False
                        }
                    ]
                },
                "appendRules": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "rules": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "state1": {"type": "string"},
                                            "transition": {
                                                "type": "string",
                                                "enum": ["button_click", "button_double_click", "button_hold", "button_release", "voice_command"]
                                            },
                                            "state2": {"type": "string"},
                                            "condition": {"type": ["string", "null"]},
                                            "action": {"type": ["string", "null"]}
                                        },
                                        "required": ["state1", "transition", "state2", "condition", "action"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["rules"],
                            "additionalProperties": False
                        }
                    ]
                },
                "deleteRules": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "transition": {"type": ["string", "null"]},
                                "state1": {"type": ["string", "null"]},
                                "state2": {"type": ["string", "null"]},
                                "indices": {
                                    "anyOf": [
                                        {"type": "null"},
                                        {
                                            "type": "array",
                                            "items": {"type": "number"}
                                        }
                                    ]
                                },
                                "delete_all": {"type": ["boolean", "null"]},
                                "reset_rules": {"type": ["boolean", "null"]}
                            },
                            "required": ["transition", "state1", "state2", "indices", "delete_all", "reset_rules"],
                            "additionalProperties": False
                        }
                    ]
                }
            },
            "required": ["reasoning", "needsClarification", "clarifyingQuestion", "deleteState", "createState", "deleteRules", "appendRules", "setState"],
            "additionalProperties": False
        }

        try:
            # Call OpenAI API using responses.create with Structured Outputs
            print(f"Calling OpenAI API with model: {self.model} (Reasoning Mode, effort={self.reasoning_effort})")
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                reasoning={"effort": self.reasoning_effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "reasoning_response",
                        "schema": json_schema,
                        "strict": True
                    }
                }
            )

            # Parse the JSON response
            parsed = json.loads(response.output_text)
            print(f"💭 Reasoning: {parsed.get('reasoning')}")

            # Convert JSON to toolCalls format
            results = {
                'toolCalls': [],
                'message': None,
                'reasoning': parsed.get('reasoning'),
                'needsClarification': parsed.get('needsClarification', False),
                'clarifyingQuestion': parsed.get('clarifyingQuestion'),
                'rawJson': parsed,
                'success': True
            }

            # If clarification is needed, don't execute actions
            if results['needsClarification']:
                print(f"❓ Needs clarification: {results['clarifyingQuestion']}")
                # Speak the clarification question using TTS
                if results['clarifyingQuestion']:
                    self.speak_clarification(results['clarifyingQuestion'])
                # Tool calls remain empty when asking for clarification
            else:
                # Execute actions in correct order
                if parsed.get('setState'):
                    results['toolCalls'].append({
                        'id': 'set_state_1',
                        'name': 'set_state',
                        'arguments': parsed['setState']
                    })

                if parsed.get('deleteRules'):
                    # Clean deleteRules - remove null fields
                    delete_rules = {k: v for k, v in parsed['deleteRules'].items() if v is not None}
                    if delete_rules:
                        results['toolCalls'].append({
                            'id': 'delete_rules_1',
                            'name': 'delete_rules',
                            'arguments': delete_rules
                        })

                if parsed.get('appendRules'):
                    results['toolCalls'].append({
                        'id': 'append_rules_1',
                        'name': 'append_rules',
                        'arguments': parsed['appendRules']
                    })

            # Add to conversation history
            history_entry = {
                'input': user_input,
                'json': parsed,
                'reasoning': parsed.get('reasoning'),
                'state': current_state,
                'rules': current_rules
            }
            self.conversation_history.append(history_entry)
            if len(self.conversation_history) > self.max_history:
                self.conversation_history.pop(0)

            return results

        except Exception as e:
            print(f"Error in reasoning mode: {e}")
            import traceback
            traceback.print_exc()
            return {'toolCalls': [], 'message': None, 'reasoning': None, 'needsClarification': False, 'clarifyingQuestion': None, 'success': False}

    def _parse_function_calling(self, user_input: str, available_states: str,
                               available_transitions: List[Dict], current_rules: List[Dict],
                               current_state: str = "off", global_variables: Dict = None) -> Dict:
        """
        Parse command using OpenAI function calling.

        Returns:
            Dict with format: {'toolCalls': [...], 'message': str, 'success': bool}
        """
        # Build dynamic content for the prompt
        dynamic_content = self._build_dynamic_content(
            available_states, available_transitions, current_rules,
            current_state, global_variables or {}
        )

        # Load the parsing prompt from configured folder
        import importlib
        prompt_module_path = f'prompts.{self.parsing_method}.{self.prompt_variant}'
        prompt_module = importlib.import_module(prompt_module_path)
        get_system_prompt = prompt_module.get_system_prompt
        get_tools = prompt_module.get_tools
        system_prompt = get_system_prompt(dynamic_content)
        tools = get_tools()

        try:
            # Call OpenAI API with function calling
            print(f"Calling OpenAI API with model: {self.model} (Function Calling)")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                tools=tools,
                tool_choice="auto"
            )

            message = response.choices[0].message

            # Extract tool calls from response
            results = {
                'toolCalls': [],
                'message': message.content,
                'success': True
            }

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    results['toolCalls'].append({
                        'id': tool_call.id,
                        'name': tool_call.function.name,
                        'arguments': json.loads(tool_call.function.arguments)
                    })

            # Add to conversation history
            history_entry = {
                'input': user_input,
                'tool_calls': results['toolCalls'],
                'state': current_state,
                'rules': current_rules
            }
            self.conversation_history.append(history_entry)
            if len(self.conversation_history) > self.max_history:
                self.conversation_history.pop(0)

            return results

        except Exception as e:
            print(f"Error in function calling: {e}")
            import traceback
            traceback.print_exc()
            return {'toolCalls': [], 'message': None, 'success': False}

    def _parse_claude(self, user_input: str, available_states: str,
                     available_transitions: List[Dict], current_rules: List[Dict],
                     current_state: str = "off", global_variables: Dict = None) -> Dict:
        """
        Parse command using Claude with tool calling.

        Returns:
            Dict with format: {'toolCalls': [...], 'message': str, 'success': bool}
        """
        # Build dynamic content for the prompt
        dynamic_content = self._build_dynamic_content(
            available_states, available_transitions, current_rules,
            current_state, global_variables or {}
        )

        # Load Claude-specific prompts
        import importlib
        claude_prompts = importlib.import_module('prompts.claude')
        system_prompt = claude_prompts.get_system_prompt(dynamic_content)
        tools = claude_prompts.get_tools()

        try:
            # Call Claude API with tools
            print(f"Calling Claude API with model: {self.model} (Tool Calling)")

            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=tools,
                messages=[
                    {"role": "user", "content": f"{system_prompt}\n\nUser command: {user_input}"}
                ]
            )

            # Extract tool calls from response
            results = {
                'toolCalls': [],
                'message': None,
                'success': True
            }

            # Process response content
            for content_block in response.content:
                if content_block.type == 'text':
                    results['message'] = content_block.text
                elif content_block.type == 'tool_use':
                    results['toolCalls'].append({
                        'id': content_block.id,
                        'name': content_block.name,
                        'arguments': content_block.input
                    })

            print(f"Claude returned {len(results['toolCalls'])} tool call(s)")
            for tool_call in results['toolCalls']:
                print(f"  - {tool_call['name']}: {json.dumps(tool_call['arguments'])}")

            # Add to conversation history
            history_entry = {
                'input': user_input,
                'tool_calls': results['toolCalls'],
                'state': current_state,
                'rules': current_rules
            }
            self.conversation_history.append(history_entry)
            if len(self.conversation_history) > self.max_history:
                self.conversation_history.pop(0)

            return results

        except Exception as e:
            print(f"Error calling Claude: {e}")
            import traceback
            traceback.print_exc()
            return {'toolCalls': [], 'message': None, 'success': False}

    def speak_clarification(self, question_text: str):
        """
        Use OpenAI TTS to speak a clarifying question.

        Args:
            question_text: The text to speak
        """
        if not self.client:
            print("OpenAI client not available, cannot speak question")
            return

        if not self.audio_player:
            print("Audio player not available, cannot speak question")
            print(f"Question: {question_text}")
            return

        try:
            import tempfile
            from pathlib import Path

            print(f"🔊 Speaking clarification: {question_text}")

            # Call OpenAI TTS API
            response = self.client.audio.speech.create(
                model="tts-1",  # Can also use "tts-1-hd" for higher quality
                voice="alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
                input=question_text
            )

            # Save to temporary file
            temp_dir = Path(tempfile.gettempdir())
            tts_file = temp_dir / "adaptlight_clarification.mp3"

            # Write the audio stream to file
            response.stream_to_file(str(tts_file))

            # Play the audio using the audio player with boosted volume (2x louder)
            # Note: pygame can play MP3 if pygame is built with MP3 support
            # Otherwise we may need to convert to WAV
            self.audio_player.play_sound(str(tts_file), blocking=True, volume=4.0)

            print("✅ Finished speaking clarification")

        except Exception as e:
            print(f"Error speaking clarification: {e}")
            print(f"Question text: {question_text}")
            import traceback
            traceback.print_exc()

    def _build_dynamic_content(self, available_states: str,
                              available_transitions: List[Dict],
                              current_rules: List[Dict],
                              current_state: str = "off",
                              global_variables: Dict = None) -> str:
        """Build dynamic content section for the prompt (matching server.js format)."""
        content = "\n\n"

        # Available states
        if available_states:
            content += f"### Available States\n{available_states}\n\n"

        # Available transitions
        if available_transitions:
            content += "### Available Transitions\n"
            for t in available_transitions:
                if isinstance(t, dict):
                    content += f"- {t['name']}: {t['description']}\n"
                elif isinstance(t, str):
                    content += f"- {t}\n"
            content += "\n"

        # Current state
        if current_state:
            content += f"### Current State\n{current_state}\n\n"

        # Global variables (matching server.js)
        if global_variables and len(global_variables) > 0:
            content += "### Global Variables\n"
            for key, value in global_variables.items():
                content += f"- {key}: {json.dumps(value)}\n"
            content += "\n"

        # Conversation history with previous state, comment, and JSON action
        if self.conversation_history:
            content += "### Conversation History\n"
            for i, entry in enumerate(self.conversation_history, 1):
                if isinstance(entry, dict):
                    content += f"\n**Turn {i}:**\n"

                    # Show previous state
                    prev_state = entry.get('state', 'unknown')
                    content += f"Previous State: {prev_state}\n"

                    # Show previous rules (abbreviated)
                    prev_rules = entry.get('rules', [])
                    if prev_rules:
                        content += f"Previous Rules:\n"
                        for idx, rule in enumerate(prev_rules):
                            content += f"  [{idx}] {rule['state1']} --[{rule['transition']}]--> {rule['state2']}\n"
                    else:
                        content += "Previous Rules: None\n"

                    # Show user comment
                    content += f"User: \"{entry['input']}\"\n"

                    # Show JSON action taken
                    if entry.get('json'):
                        content += f"Action JSON:\n```json\n{json.dumps(entry['json'], indent=2)}\n```\n"
                else:
                    # Legacy format
                    content += f"{i}. \"{entry}\"\n"
            content += "\n"

        # Current rules (matching server.js format with indices)
        if current_rules:
            content += "### Current Rules\n"
            for idx, rule in enumerate(current_rules):
                condition = ""
                if rule.get('condition'):
                    condition = f" [condition: {rule['condition']}]"
                action = ""
                if rule.get('action'):
                    action = f" [action: {rule['action']}]"
                content += f"[{idx}] {rule['state1']} --[{rule['transition']}]--> {rule['state2']}{condition}{action}\n"
            content += "\n"
        else:
            content += "### Current Rules\nNo rules defined yet.\n\n"

        return content

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("Conversation history cleared")
