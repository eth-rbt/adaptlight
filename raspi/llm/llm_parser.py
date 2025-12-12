"""
LLM Parser for AdaptLight pipelines.

Simple LLM wrapper that takes input data + prompt and returns parsed response.
Used by pipeline steps to interpret API data and make decisions.
"""

import json
from typing import Any


class LLMParser:
    """Simple LLM wrapper for pipeline parsing steps."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize the LLM parser.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.api_key = api_key
        self.model = model
        self.client = None

        if api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=api_key)
            except ImportError:
                print("ERROR: Anthropic library not available")
            except Exception as e:
                print(f"ERROR: Failed to initialize Anthropic client: {e}")

    def parse(self, input_data: Any, prompt: str) -> str:
        """
        Send input data + prompt to LLM and return response.

        Args:
            input_data: Data to analyze (will be converted to string/JSON)
            prompt: Instructions for how to interpret the data

        Returns:
            LLM response as string
        """
        if not self.client:
            return "Error: LLM client not initialized"

        # Convert input to string representation
        if isinstance(input_data, dict) or isinstance(input_data, list):
            input_str = json.dumps(input_data, indent=2)
        else:
            input_str = str(input_data)

        # Build the message
        user_message = f"""Data:
{input_str}

{prompt}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=256,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            # Extract text from response
            for block in response.content:
                if block.type == "text":
                    return block.text.strip()

            return ""

        except Exception as e:
            return f"Error: {str(e)}"
