"""
Parallel Agent Processor for faster TTS response.

This processor works in two phases:
1. Planning Phase: Single API call to get plan + message
2. Execution Phase: Execute tools while TTS runs in parallel

This is faster because TTS starts immediately after planning,
rather than waiting for all tool calls to complete.
"""

import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from anthropic import Anthropic

from brain.tools.registry import ToolRegistry
from brain.prompts.agent.agent_prompt_with_examples import get_agent_system_prompt_with_examples


@dataclass
class PlanStep:
    """A single step in the execution plan."""
    tool: str
    args: Dict[str, Any]


@dataclass
class ExecutionPlan:
    """Plan returned by the planning phase."""
    steps: List[PlanStep]
    message: str
    reasoning: str = ""


class ParallelAgentExecutor:
    """
    Two-phase agent executor for faster TTS response.

    Phase 1: Planning - Get plan + message in one call
    Phase 2: Execution - Run tools (TTS starts in parallel)
    """

    def __init__(self, state_machine=None, api_key: str = None,
                 model: str = "claude-sonnet-4-20250514",
                 verbose: bool = False, prompt_variant: str = "examples",
                 speech_instructions: str = None,
                 representation_version: str = "stdlib",
                 on_message_ready: Callable = None):
        """
        Initialize parallel agent executor.

        Args:
            state_machine: StateMachine instance to operate on
            api_key: Anthropic API key
            model: Claude model for planning
            verbose: Print debug information
            prompt_variant: 'concise' or 'examples'
            speech_instructions: Extra instructions for speech output
            representation_version: State representation version
            on_message_ready: Callback when message is ready (fires early!)
        """
        self.state_machine = state_machine
        self.api_key = api_key
        self.model = model
        self.verbose = verbose
        self.prompt_variant = prompt_variant
        self.speech_instructions = speech_instructions
        self.representation_version = representation_version
        self.on_message_ready = on_message_ready

        # Initialize tool registry
        self.tools = ToolRegistry(state_machine, api_key=api_key)

        # Initialize Anthropic client
        self.client = Anthropic(api_key=api_key)

        # Execution state
        self.steps = []
        self.last_plan = None

    def _get_planning_prompt(self, base_prompt: str) -> str:
        """Get the planning-specific system prompt."""
        planning_addition = """

## IMPORTANT: Plan-First Response Format

You MUST respond with a JSON object containing your plan AND the user message.
Do NOT use tools directly. Instead, return this JSON format:

```json
{
    "reasoning": "Brief explanation of what you'll do",
    "message": "The response to speak to the user (keep under 1 sentence)",
    "plan": [
        {"tool": "createState", "args": {"name": "...", "code": "...", "description": "..."}},
        {"tool": "setState", "args": {"name": "..."}},
        {"tool": "appendRules", "args": {"rules": [...]}}
    ]
}
```

Rules for the plan:
- "message" should be concise and direct (this will be spoken aloud)
- "plan" is an array of tool calls to execute IN ORDER
- Available tools: createState, setState, appendRules, deleteRules, deleteState, remember, recall
- Do NOT include "done" in the plan - it's implicit
- The plan will be executed automatically after you respond
- For timer rules (delayed transitions), use trigger_config: {"delay_ms": milliseconds, "auto_cleanup": true}

Example responses:

Simple state change:
```json
{
    "reasoning": "User wants party mode - I'll create a rainbow cycling state",
    "message": "Party mode on! The light will cycle through colors.",
    "plan": [
        {"tool": "createState", "args": {"name": "party", "code": "def render(prev, t):\\n    return hsv(t * 0.3 % 1, 1, 1), 30", "description": "Rainbow color cycling"}},
        {"tool": "setState", "args": {"name": "party"}}
    ]
}
```

Timer (delayed transition):
```json
{
    "reasoning": "User wants light on in 30 minutes - schedule a timer",
    "message": "Got it, I'll turn on in 30 minutes.",
    "plan": [
        {"tool": "appendRules", "args": {"rules": [{"from": "*", "on": "timer", "to": "on", "trigger_config": {"delay_ms": 1800000, "auto_cleanup": true}}]}}
    ]
}
```

Respond ONLY with the JSON object, no other text.
"""
        return base_prompt + planning_addition

    async def run(self, user_input: str) -> str:
        """
        Process a voice command using plan-first approach.

        Args:
            user_input: The voice command text

        Returns:
            Response message for TTS
        """
        text = user_input
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"🚀 Parallel Agent: {text}")
            print(f"{'='*60}")

        # Phase 1: Planning
        plan = await self._planning_phase(text)

        if not plan:
            return "Sorry, I couldn't understand that request."

        self.last_plan = plan

        # Fire message ready callback IMMEDIATELY after planning
        # This allows TTS to start while we execute the plan
        if self.on_message_ready and plan.message:
            print(f"🔊 Message ready: {plan.message[:50]}...")
            self.on_message_ready(plan.message)

        # Phase 2: Execution
        await self._execution_phase(plan)

        # Run safety check
        self._run_safety_check()

        return plan.message

    async def _planning_phase(self, text: str) -> Optional[ExecutionPlan]:
        """
        Phase 1: Get execution plan and message from LLM.

        Returns:
            ExecutionPlan with steps and message, or None on failure
        """
        if self.verbose:
            print(f"\n📋 Phase 1: Planning...")

        # Build system prompt
        current_state = self.state_machine.get_state()
        available_states = self.state_machine.states.get_states_for_prompt()
        current_rules = [str(r) for r in self.state_machine.get_rules()]

        system_state = f"""Current state: {current_state}
Available states: {', '.join(available_states) if available_states else 'none (only default on/off)'}
Current rules: {len(current_rules)} rules defined"""

        base_prompt = get_agent_system_prompt_with_examples(
            system_state=system_state,
            representation_version=self.representation_version
        )

        # Add speech instructions if provided
        if self.speech_instructions:
            base_prompt += f"\n\n## Speech Output Instructions\n{self.speech_instructions}"

        system_prompt = self._get_planning_prompt(base_prompt)

        try:
            import time
            start = time.time()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": text}]
            )

            elapsed = time.time() - start
            if self.verbose:
                print(f"   ⏱️  Planning API call: {elapsed:.2f}s")

            # Parse the JSON response
            response_text = response.content[0].text.strip()

            # Handle markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first and last lines (```json and ```)
                response_text = "\n".join(lines[1:-1])

            plan_data = json.loads(response_text)

            # Build execution plan
            steps = []
            for step in plan_data.get("plan", []):
                steps.append(PlanStep(
                    tool=step["tool"],
                    args=step.get("args", {})
                ))

            plan = ExecutionPlan(
                steps=steps,
                message=plan_data.get("message", "Done"),
                reasoning=plan_data.get("reasoning", "")
            )

            if self.verbose:
                print(f"   📝 Plan: {len(plan.steps)} steps")
                print(f"   💬 Message: {plan.message}")

            return plan

        except json.JSONDecodeError as e:
            if self.verbose:
                print(f"   ❌ Failed to parse plan JSON: {e}")
                print(f"   Response: {response_text[:200]}...")
            return None
        except Exception as e:
            if self.verbose:
                print(f"   ❌ Planning failed: {e}")
            return None

    async def _execution_phase(self, plan: ExecutionPlan):
        """
        Phase 2: Execute the plan's tool calls.

        This runs while TTS is generating in parallel.
        """
        if self.verbose:
            print(f"\n⚡ Phase 2: Executing {len(plan.steps)} steps...")

        for i, step in enumerate(plan.steps):
            try:
                if self.verbose:
                    args_str = json.dumps(step.args)
                    if len(args_str) > 100:
                        args_str = args_str[:100] + "..."
                    print(f"   [{i+1}/{len(plan.steps)}] {step.tool}: {args_str}")

                import time
                start = time.time()

                result = await self.tools.execute(step.tool, step.args)

                elapsed = time.time() - start
                if self.verbose:
                    print(f"       ✓ {elapsed*1000:.0f}ms")

            except Exception as e:
                if self.verbose:
                    print(f"       ❌ Error: {e}")

    def _run_safety_check(self):
        """Run safety check to ensure all states have exit rules."""
        result = self.tools.run_safety_check()
        if self.verbose and result.get("rules_added", 0) > 0:
            print(f"🛡️  Safety check: Added {result['rules_added']} exit rule(s)")
