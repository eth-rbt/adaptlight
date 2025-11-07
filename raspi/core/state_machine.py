"""
State machine implementation for AdaptLight.

This module is a port of statemachine.js and contains:
- StateMachine: Main state machine class that manages rules, states, and transitions

The state machine:
1. Stores rules (state transitions with conditions)
2. Executes transitions based on events
3. Manages state data and intervals
4. Evaluates conditions and actions safely
"""

from typing import Any, Callable, Optional, List
from .state import State, States
from .rule import Rule


class StateMachine:
    """Main state machine for managing light behavior."""

    def __init__(self):
        """Initialize the state machine."""
        self.rules: List[Rule] = []
        self.current_state = 'off'
        self.current_state_params = None
        self.states = States()
        self.state_data = {}
        self.interval = None
        self.interval_callback = None

    def register_state(self, name: str, description: str = '', on_enter: Callable = None):
        """
        Register a state with its description and onEnter function.

        Args:
            name: The name of the state
            description: Description of what this state does
            on_enter: Function to execute when entering this state

        Returns:
            The created State object
        """
        state = State(name, description, on_enter)
        self.states.add_state(state)
        print(f"State registered: {name}")
        return state

    def get_state_object(self, name: str) -> Optional[State]:
        """Get a state by name."""
        return self.states.get_state_by_name(name)

    def get_state_list(self):
        """Get a list of all state names and descriptions."""
        return self.states.get_state_list()

    def add_rule(self, rule):
        """
        Add a new rule to the state machine.

        If a rule with the same state1, transition, and condition exists,
        it will be replaced.

        Args:
            rule: Can be a Rule instance, dict, or legacy [state1, action, state2] array
        """
        # Convert to Rule object if needed
        if isinstance(rule, Rule):
            rule_obj = rule
        elif isinstance(rule, dict):
            rule_obj = Rule(
                rule.get('state1'),
                rule.get('state1_param') or rule.get('state1Param'),
                rule.get('transition'),
                rule.get('state2'),
                rule.get('state2_param') or rule.get('state2Param'),
                rule.get('condition'),
                rule.get('action')
            )
        elif isinstance(rule, list) and len(rule) == 3:
            # Legacy format: [state1, action, state2]
            rule_obj = Rule(rule[0], None, rule[1], rule[2], None, None, None)
        else:
            raise ValueError("Invalid rule format")

        # Check if rule already exists
        existing_index = None
        for i, r in enumerate(self.rules):
            if (r.state1 == rule_obj.state1 and
                r.transition == rule_obj.transition and
                r.condition == rule_obj.condition):
                existing_index = i
                break

        if existing_index is not None:
            self.rules[existing_index] = rule_obj
            print(f"Rule replaced: {rule_obj}")
        else:
            self.rules.append(rule_obj)
            print(f"Rule added: {rule_obj}")

    def get_rules(self) -> List[Rule]:
        """Get all rules."""
        return self.rules

    def clear_rules(self):
        """Clear all rules."""
        self.rules = []
        print("All rules cleared")

    def remove_rule(self, index: int):
        """Remove a specific rule by index."""
        if 0 <= index < len(self.rules):
            removed = self.rules.pop(index)
            print(f"Rule removed: {removed}")

    def set_state(self, state_name: str, params=None):
        """
        Set the current state with optional parameters.

        Args:
            state_name: The new state name
            params: Optional parameters to pass to the state's onEnter function
        """
        self.current_state = state_name
        self.current_state_params = params
        print(f"State changed to: {state_name}")

        # Execute the onEnter function for this state if it exists
        state_object = self.get_state_object(state_name)
        if state_object:
            state_object.enter(params)

    def evaluate_rule_expression(self, expr: str, expr_type: str = 'condition'):
        """
        Evaluate a condition or action expression safely.

        Args:
            expr: The expression to evaluate
            expr_type: 'condition' or 'action'

        Returns:
            Result of evaluation (boolean for conditions, None for actions)
        """
        if not expr:
            return True if expr_type == 'condition' else None

        # TODO: Implement safe expression evaluation with restricted scope
        # Should allow: getData(), setData(), getTime(), Math functions
        # Should deny: file access, network, dangerous operations
        print(f"TODO: Evaluate {expr_type} expression: {expr}")
        return True if expr_type == 'condition' else None

    def execute_transition(self, action: str) -> bool:
        """
        Execute a transition based on an action.

        Args:
            action: The action/transition to execute

        Returns:
            True if transition was executed, False otherwise
        """
        # Find all matching rules (state + transition match)
        candidate_rules = [r for r in self.rules if r.matches(self.current_state, action)]

        # Filter by conditions - find first rule whose condition is true
        matching_rule = None
        for rule in candidate_rules:
            if not rule.condition:
                matching_rule = rule
                break
            if self.evaluate_rule_expression(rule.condition, 'condition'):
                matching_rule = rule
                break

        if matching_rule:
            print(f"Transition: {matching_rule}")

            # Execute action if present (before state transition)
            if matching_rule.action:
                print(f"Executing action: {matching_rule.action}")
                self.evaluate_rule_expression(matching_rule.action, 'action')

            # Transition to new state
            self.set_state(matching_rule.state2, matching_rule.state2_param)
            return True
        else:
            if candidate_rules:
                print(f"Rules found for action '{action}' in state {self.current_state}, "
                      f"but no conditions matched")
            else:
                print(f"No transition found for action '{action}' in state {self.current_state}")
            return False

    def get_state(self) -> str:
        """Get the current state."""
        return self.current_state

    def get_state_params(self):
        """Get the current state parameters."""
        return self.current_state_params

    def set_data(self, key: str, value: Any):
        """Set state data."""
        self.state_data[key] = value

    def get_data(self, key: str, default=None) -> Any:
        """Get state data."""
        return self.state_data.get(key, default)

    def get_time(self):
        """
        Get current time information.

        Returns:
            Dict with hour, minute, second, day_of_week (0=Monday), timestamp
        """
        from datetime import datetime
        now = datetime.now()
        return {
            'hour': now.hour,
            'minute': now.minute,
            'second': now.second,
            'day_of_week': now.weekday(),  # 0=Monday
            'timestamp': now.timestamp()
        }

    def clear_data(self):
        """Clear all state data."""
        self.state_data = {}

    def stop_interval(self):
        """Stop the current interval if running."""
        if self.interval:
            # Signal the thread to stop by setting interval to None
            interval_thread = self.interval
            self.interval = None
            self.interval_callback = None
            # Wait briefly for thread to finish
            if interval_thread.is_alive():
                interval_thread.join(timeout=0.5)
            print("State machine interval stopped")

    def start_interval(self, callback: Callable, interval_ms: int = 100):
        """
        Start an interval for state machine execution.

        Args:
            callback: Function to execute on each interval
            interval_ms: Interval in milliseconds
        """
        import threading

        self.stop_interval()

        self.interval_callback = callback
        self.interval_ms = interval_ms

        def interval_loop():
            """Run the callback in a loop until stopped."""
            while self.interval is not None:
                try:
                    self.interval_callback()
                except Exception as e:
                    print(f"Interval callback error: {e}")
                    break

                # Sleep for the interval duration
                if self.interval is not None:
                    import time
                    time.sleep(interval_ms / 1000.0)

        # Start the interval thread
        self.interval = threading.Thread(target=interval_loop, daemon=True)
        self.interval.start()
        print(f"State machine interval started ({interval_ms}ms)")

    def reset(self):
        """Reset the state machine to initial state."""
        self.stop_interval()
        self.current_state = 'off'
        self.state_data = {}
        print("State machine reset")

    def get_summary(self):
        """Get a summary of the state machine."""
        return {
            'rules_count': len(self.rules),
            'current_state': self.current_state,
            'state_data': dict(self.state_data),
            'is_running': self.interval is not None
        }
