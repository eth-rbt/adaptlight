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

    def __init__(self, state1, state1_param, transition, state2, state2_param,
                 condition=None, action=None):
        """
        Initialize a rule.

        Args:
            state1: Source state name
            state1_param: Parameters for source state (optional)
            transition: Transition/event name that triggers this rule
            state2: Destination state name
            state2_param: Parameters for destination state (optional)
            condition: Python expression that must evaluate to True (optional)
            action: Python expression to execute during transition (optional)
        """
        self.state1 = state1
        self.state1_param = state1_param
        self.transition = transition
        self.state2 = state2
        self.state2_param = state2_param
        self.condition = condition
        self.action = action
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
            'state1_param': self.state1_param,
            'transition': self.transition,
            'state2': self.state2,
            'state2_param': self.state2_param,
            'condition': self.condition,
            'action': self.action,
            'timestamp': self.timestamp
        }

    def __repr__(self):
        """String representation of the rule."""
        cond_str = f" (if: {self.condition})" if self.condition else ""
        action_str = f" (do: {self.action})" if self.action else ""
        return f"{self.state1} --[{self.transition}]--> {self.state2}{cond_str}{action_str}"
