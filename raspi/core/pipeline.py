"""
Pipeline Executor for AdaptLight.

Executes pipeline steps sequentially:
- fetch: Call a preset API
- llm: Parse data with LLM
- setState: Set lamp state based on result
- setVar: Store value in pipeline variables
- wait: Wait for specified milliseconds
- run: Execute another pipeline

All steps support:
- "as": Store result in variable (e.g., "as": "data")
- "if": Conditional execution (e.g., "if": "{{result}} == 'up'")

Variable interpolation: {{variable}} or {{memory.key}}
"""

import re
import time
from typing import Dict, Any, List, Optional


class PipelineExecutor:
    """Executes pipeline steps."""

    def __init__(self, api_executor=None, llm_parser=None, state_machine=None, memory=None):
        """
        Initialize pipeline executor.

        Args:
            api_executor: APIExecutor instance for fetch steps
            llm_parser: LLMParser instance for llm steps
            state_machine: StateMachine instance for setState steps
            memory: Memory instance for {{memory.key}} interpolation
        """
        self.api_executor = api_executor
        self.llm_parser = llm_parser
        self.state_machine = state_machine
        self.memory = memory

        # Import pipeline registry for "run" steps
        from .pipeline_registry import get_pipeline_registry
        self.registry = get_pipeline_registry()

    def execute(self, pipeline: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a pipeline.

        Args:
            pipeline: Pipeline definition with name and steps

        Returns:
            Dict with success status and final variables
        """
        name = pipeline.get("name", "unnamed")
        steps = pipeline.get("steps", [])

        print(f"\n{'='*50}")
        print(f"PIPELINE: {name}")
        print(f"{'='*50}")

        # Pipeline-local variables
        variables: Dict[str, Any] = {}

        for i, step in enumerate(steps):
            step_type = step.get("do")
            print(f"\nStep {i+1}/{len(steps)}: {step_type}")

            # Check condition if present
            condition = step.get("if")
            if condition:
                if not self._evaluate_condition(condition, variables):
                    print(f"  Condition not met: {condition}")
                    continue

            # Execute step
            try:
                result = self._execute_step(step, variables)

                # Store result if "as" is specified
                if "as" in step and result is not None:
                    variables[step["as"]] = result
                    print(f"  Stored as '{step['as']}': {result}")

            except Exception as e:
                print(f"  ERROR: {e}")
                return {"success": False, "error": str(e), "step": i}

        print(f"\n{'='*50}")
        print(f"PIPELINE COMPLETE: {name}")
        print(f"{'='*50}")

        return {"success": True, "variables": variables}

    def _execute_step(self, step: Dict[str, Any], variables: Dict[str, Any]) -> Any:
        """Execute a single pipeline step."""
        step_type = step.get("do")

        if step_type == "fetch":
            return self._step_fetch(step, variables)
        elif step_type == "llm":
            return self._step_llm(step, variables)
        elif step_type == "setState":
            return self._step_set_state(step, variables)
        elif step_type == "setVar":
            return self._step_set_var(step, variables)
        elif step_type == "wait":
            return self._step_wait(step, variables)
        elif step_type == "run":
            return self._step_run(step, variables)
        else:
            raise ValueError(f"Unknown step type: {step_type}")

    def _step_fetch(self, step: Dict[str, Any], variables: Dict[str, Any]) -> Any:
        """Execute fetch step - call preset API."""
        if not self.api_executor:
            raise RuntimeError("No API executor configured")

        api_name = step.get("api")
        params = step.get("params", {})

        # Interpolate params
        params = self._interpolate_dict(params, variables)

        print(f"  Fetching API: {api_name} with params: {params}")
        result = self.api_executor.execute(api_name, params)

        if result.get("success"):
            return result.get("data")
        else:
            raise RuntimeError(f"API error: {result.get('error')}")

    def _step_llm(self, step: Dict[str, Any], variables: Dict[str, Any]) -> str:
        """Execute llm step - parse data with LLM."""
        if not self.llm_parser:
            raise RuntimeError("No LLM parser configured")

        input_data = step.get("input", "")
        prompt = step.get("prompt", "")

        # Interpolate input and prompt
        input_data = self._interpolate(input_data, variables)
        prompt = self._interpolate(prompt, variables)

        # If input references a variable directly, get its value
        if isinstance(input_data, str) and input_data in variables:
            input_data = variables[input_data]

        print(f"  LLM parsing with prompt: {prompt[:50]}...")
        result = self.llm_parser.parse(input_data, prompt)
        print(f"  LLM result: {result}")

        return result

    def _step_set_state(self, step: Dict[str, Any], variables: Dict[str, Any]) -> str:
        """Execute setState step - set lamp state."""
        if not self.state_machine:
            raise RuntimeError("No state machine configured")

        # Option 1: Direct state name
        if "state" in step:
            state_name = self._interpolate(step["state"], variables)
            print(f"  Setting state: {state_name}")
            self.state_machine.set_state(state_name)
            return state_name

        # Option 2: Map result to state
        if "from" in step and "map" in step:
            result_var = step["from"]
            result_value = variables.get(result_var, "")
            if isinstance(result_value, str):
                result_value = result_value.lower().strip()

            mapping = step["map"]
            state_name = mapping.get(result_value)

            if state_name:
                print(f"  Mapped '{result_value}' -> state '{state_name}'")
                self.state_machine.set_state(state_name)
                return state_name
            else:
                print(f"  No mapping for '{result_value}'")
                return None

        raise ValueError("setState requires 'state' or 'from'+'map'")

    def _step_set_var(self, step: Dict[str, Any], variables: Dict[str, Any]) -> Any:
        """Execute setVar step - store value in variables."""
        key = step.get("key")
        value = step.get("value")

        # Interpolate value
        value = self._interpolate(value, variables)

        variables[key] = value
        print(f"  Set variable: {key} = {value}")
        return value

    def _step_wait(self, step: Dict[str, Any], variables: Dict[str, Any]) -> None:
        """Execute wait step - pause execution."""
        ms = step.get("ms", 1000)
        print(f"  Waiting {ms}ms...")
        time.sleep(ms / 1000.0)
        return None

    def _step_run(self, step: Dict[str, Any], variables: Dict[str, Any]) -> Any:
        """Execute run step - run another pipeline."""
        pipeline_name = step.get("pipeline")
        pipeline = self.registry.get(pipeline_name)

        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_name}")

        print(f"  Running sub-pipeline: {pipeline_name}")
        result = self.execute(pipeline)
        return result.get("variables", {})

    def _interpolate(self, value: Any, variables: Dict[str, Any]) -> Any:
        """Interpolate {{variable}} and {{memory.key}} in value."""
        if not isinstance(value, str):
            return value

        def replace_var(match):
            var_path = match.group(1)

            # Check for memory.key
            if var_path.startswith("memory."):
                key = var_path[7:]  # Remove "memory." prefix
                if self.memory:
                    return str(self.memory.get(key, ""))
                return ""

            # Check pipeline variables
            if var_path in variables:
                val = variables[var_path]
                if isinstance(val, dict) or isinstance(val, list):
                    import json
                    return json.dumps(val)
                return str(val)

            return match.group(0)  # Keep original if not found

        # Replace all {{...}} patterns
        result = re.sub(r'\{\{([^}]+)\}\}', replace_var, value)
        return result

    def _interpolate_dict(self, d: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Interpolate all string values in a dict."""
        return {k: self._interpolate(v, variables) for k, v in d.items()}

    def _evaluate_condition(self, condition: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a condition string."""
        # Interpolate variables first
        condition = self._interpolate(condition, variables)

        # Simple evaluation
        try:
            # Safe evaluation context
            safe_context = {
                '__builtins__': {},
                'True': True,
                'False': False,
                'None': None,
            }
            # Add variables to context
            safe_context.update(variables)

            return bool(eval(condition, safe_context, {}))
        except Exception as e:
            print(f"  Condition evaluation error: {e}")
            return False


# Global executor instance
_executor_instance: Optional[PipelineExecutor] = None


def get_pipeline_executor() -> PipelineExecutor:
    """Get the global pipeline executor instance."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = PipelineExecutor()
    return _executor_instance


def init_pipeline_executor(api_executor=None, llm_parser=None, state_machine=None, memory=None):
    """Initialize the global pipeline executor with dependencies."""
    global _executor_instance
    _executor_instance = PipelineExecutor(
        api_executor=api_executor,
        llm_parser=llm_parser,
        state_machine=state_machine,
        memory=memory
    )
    return _executor_instance
