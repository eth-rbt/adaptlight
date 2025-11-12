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

    def __init__(self, api_key=None):
        """
        Initialize command parser.

        Args:
            api_key: OpenAI API key
        """
        self.api_key = api_key
        self.conversation_history = []
        self.max_history = 2  # Keep last 2 commands with actions for context

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            print("CommandParser initialized with OpenAI GPT-5")
        except ImportError:
            self.client = None
            print("Warning: OpenAI library not available")

        # Define tool schemas for GPT-5 function calling with strict validation
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

    def parse_command(self, user_input: str, available_states: str,
                     available_transitions: List[Dict], current_rules: List[Dict],
                     current_state: str = "off", global_variables: Dict = None) -> Dict:
        """
        Parse a natural language command into tool calls using GPT-5.

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
        if not self.client:
            print("OpenAI client not available")
            return {'toolCalls': [], 'message': None, 'success': False}

        # Build dynamic content for the prompt
        dynamic_content = self._build_dynamic_content(
            available_states, available_transitions, current_rules,
            current_state, global_variables or {}
        )

        # Load the parsing prompt
        from prompts.parsing_prompt import get_system_prompt
        system_prompt = get_system_prompt(dynamic_content)

        try:
            # Call GPT-5 API using responses.create with reasoning padding
            print(f"Calling OpenAI API with model: gpt-5")
            response = self.client.responses.create(
                model="gpt-5",
                tools=self.tools,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                reasoning={"effort": "medium"},  # Medium effort for better tool call reasoning
                text={"verbosity": "low"}
            )

            # Process the output (matching server.js processing)
            results = {
                'toolCalls': [],
                'message': None,
                'success': True
            }

            # Extract function calls and text from the output
            for item in response.output:
                if item.type == "function_call":
                    args = json.loads(item.arguments)
                    results['toolCalls'].append({
                        'id': item.call_id,
                        'name': item.name,
                        'arguments': args
                    })
                elif item.type == "text":
                    results['message'] = item.text

            # Add to conversation history with actions taken
            history_entry = {
                'input': user_input,
                'toolCalls': results.get('toolCalls', []),
                'message': results.get('message')
            }
            self.conversation_history.append(history_entry)
            if len(self.conversation_history) > self.max_history:
                self.conversation_history.pop(0)

            return results

        except Exception as e:
            print(f"Error parsing command: {e}")
            import traceback
            traceback.print_exc()
            return {'toolCalls': [], 'message': None, 'success': False}

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

        # Conversation history with actions taken
        if self.conversation_history:
            content += "### Past User Inputs (with actions taken)\n"
            for i, entry in enumerate(self.conversation_history, 1):
                # Add the user input
                if isinstance(entry, dict):
                    content += f"{i}. User: \"{entry['input']}\"\n"

                    # Add AI message if present
                    if entry.get('message'):
                        content += f"   AI: {entry['message']}\n"

                    # Add tool calls executed
                    if entry.get('toolCalls'):
                        content += f"   Actions taken:\n"
                        for tc in entry['toolCalls']:
                            tool_name = tc.get('name', 'unknown')
                            args = tc.get('arguments', {})

                            # Format action description
                            if tool_name == 'append_rules':
                                rule_count = len(args.get('rules', []))
                                content += f"   - Added {rule_count} rule(s)\n"
                            elif tool_name == 'delete_rules':
                                if args.get('delete_all'):
                                    content += f"   - Deleted all rules\n"
                                elif args.get('indices'):
                                    content += f"   - Deleted rules at indices {args['indices']}\n"
                                else:
                                    content += f"   - Deleted rules matching criteria\n"
                            elif tool_name == 'set_state':
                                content += f"   - Changed state to {args.get('state')}\n"
                            elif tool_name == 'manage_variables':
                                action = args.get('action')
                                if action == 'set':
                                    var_count = len(args.get('variables', {}))
                                    content += f"   - Set {var_count} variable(s)\n"
                                elif action == 'delete':
                                    content += f"   - Deleted variables\n"
                                elif action == 'clear_all':
                                    content += f"   - Cleared all variables\n"
                            elif tool_name == 'reset_rules':
                                content += f"   - Reset rules to default (on/off toggle)\n"
                else:
                    # Legacy format (just string)
                    content += f"{i}. \"{entry}\"\n"
            content += "\n"

        # Current rules (matching server.js format with indices)
        if current_rules:
            content += "### Current Rules\n"
            for idx, rule in enumerate(current_rules):
                params = ""
                if rule.get('state2Param') or rule.get('state2_param'):
                    param_value = rule.get('state2Param') or rule.get('state2_param')
                    params = f" (with params: {json.dumps(param_value)})"
                condition = ""
                if rule.get('condition'):
                    condition = f" [condition: {rule['condition']}]"
                content += f"[{idx}] {rule['state1']} --[{rule['transition']}]--> {rule['state2']}{params}{condition}\n"
            content += "\n"
        else:
            content += "### Current Rules\nNo rules defined yet.\n\n"

        return content

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("Conversation history cleared")
