"""
Rule class for AdaptLight state machine.

This module is a port of rules.js and contains:
- Rule: Represents a state transition rule with conditions and actions

Rules define: state1 --[transition]--> state2
With optional conditions (must be true to match) and actions (executed during transition).
"""

from datetime import datetime, timezone


class Rule:
    """Represents a state machine transition rule."""

    def __init__(self, state1, transition, state2, condition=None, action=None, trigger_config=None):
        """
        Initialize a rule.

        Args:
            state1: Source state name
            transition: Transition/event name that triggers this rule
            state2: Destination state name
            condition: Python expression that must evaluate to True (optional)
            action: Python expression to execute during transition (optional)
            trigger_config: Timing configuration for time-based transitions (optional)
                For timer: {"delay_ms": <ms>, "auto_cleanup": true/false}
                For interval: {"delay_ms": <ms>, "repeat": true}
                For schedule: {"hour": <0-23>, "minute": <0-59>, "repeat_daily": true/false}
        """
        self.state1 = state1
        self.transition = transition
        self.state2 = state2
        self.condition = condition
        self.action = action
        self.trigger_config = trigger_config or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def matches(self, current_state: str, action: str) -> bool:
        """
        Check if this rule matches the current state and action.

        Args:
            current_state: Current state name
            action: Action/transition being executed

        Returns:
            True if rule matches
        """
        return self.state1 == current_state and self.transition == action

    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            'state1': self.state1,
            'transition': self.transition,
            'state2': self.state2,
            'condition': self.condition,
            'action': self.action,
            'trigger_config': self.trigger_config,
            'timestamp': self.timestamp
        }

    def __repr__(self):
        """String representation of the rule."""
        cond_str = f" (if: {self.condition})" if self.condition else ""
        action_str = f" (do: {self.action})" if self.action else ""
        return f"{self.state1} --[{self.transition}]--> {self.state2}{cond_str}{action_str}"
