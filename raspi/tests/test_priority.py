"""
Tests for priority-based rule evaluation.
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.rule import Rule
from core.state_machine import StateMachine


class TestPriorityEvaluation:
    """Test that higher priority rules are evaluated first."""

    def test_higher_priority_wins(self):
        """Higher priority rule should be selected even if added second."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "blue", "priority": 0})
        sm.add_rule({"from": "off", "on": "button_click", "to": "red", "priority": 10})

        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "red"

    def test_lower_priority_when_no_higher(self):
        """Lower priority rule should work when no higher priority matches."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "blue", "priority": 0})
        sm.add_rule({"from": "on", "on": "button_click", "to": "red", "priority": 10})

        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "blue"

    def test_same_priority_order_preserved(self):
        """When priorities are equal, order is preserved (first match wins)."""
        sm = StateMachine()
        # Use different conditions to prevent replacement (conditions must differ)
        sm.add_rule({"from": "off", "on": "button_click", "to": "blue", "priority": 5, "condition": "1 == 1"})
        sm.add_rule({"from": "off", "on": "button_click", "to": "red", "priority": 5, "condition": "2 == 2"})

        sm.current_state = "off"
        sm.execute_transition("button_click")
        # With same priority, rules are evaluated in the order they appear after sorting
        # Python's sort is stable, so first added should be checked first
        assert sm.current_state == "blue"

    def test_negative_priority(self):
        """Negative priority should be lower than zero."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "blue", "priority": -10})
        sm.add_rule({"from": "off", "on": "button_click", "to": "red", "priority": 0})

        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "red"


class TestWildcardWithPriority:
    """Test wildcard rules with priority."""

    def test_specific_rule_overrides_wildcard_with_priority(self):
        """Specific rule with higher priority overrides wildcard."""
        sm = StateMachine()
        sm.add_rule({"from": "*", "on": "button_click", "to": "off", "priority": 0})
        sm.add_rule({"from": "red", "on": "button_click", "to": "blue", "priority": 10})

        sm.current_state = "red"
        sm.execute_transition("button_click")
        assert sm.current_state == "blue"

    def test_wildcard_with_higher_priority_wins(self):
        """Wildcard with higher priority should win over specific rule."""
        sm = StateMachine()
        sm.add_rule({"from": "red", "on": "button_click", "to": "blue", "priority": 0})
        sm.add_rule({"from": "*", "on": "button_click", "to": "off", "priority": 100})

        sm.current_state = "red"
        sm.execute_transition("button_click")
        assert sm.current_state == "off"

    def test_safety_rule_pattern(self):
        """Common pattern: high-priority wildcard safety rule."""
        sm = StateMachine()
        # Normal rules
        sm.add_rule({"from": "off", "on": "button_click", "to": "on", "priority": 0})
        sm.add_rule({"from": "on", "on": "button_click", "to": "off", "priority": 0})
        # Safety rule: hold always goes to off
        sm.add_rule({"from": "*", "on": "button_hold", "to": "off", "priority": 100})

        # Test normal behavior
        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "on"

        # Test safety rule from any state
        sm.current_state = "rainbow_animation"
        sm.execute_transition("button_hold")
        assert sm.current_state == "off"


class TestEnabledWithPriority:
    """Test enabled flag interaction with priority."""

    def test_disabled_high_priority_skipped(self):
        """Disabled rule should be skipped even with high priority."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "red", "priority": 100, "enabled": False})
        sm.add_rule({"from": "off", "on": "button_click", "to": "blue", "priority": 0, "enabled": True})

        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "blue"

    def test_all_disabled_no_transition(self):
        """No transition should occur if all matching rules are disabled."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "red", "enabled": False})
        sm.add_rule({"from": "off", "on": "button_click", "to": "blue", "enabled": False})

        sm.current_state = "off"
        result = sm.execute_transition("button_click")
        assert result is False
        assert sm.current_state == "off"


class TestAddRuleFormat:
    """Test various rule format support in add_rule."""

    def test_old_format_state1_state2(self):
        """Old format with state1/transition/state2."""
        sm = StateMachine()
        sm.add_rule({"state1": "off", "transition": "button_click", "state2": "on"})

        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "on"

    def test_new_format_from_on_to(self):
        """New format with from/on/to."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "on"})

        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "on"

    def test_legacy_list_format(self):
        """Legacy list format [state1, action, state2]."""
        sm = StateMachine()
        sm.add_rule(["off", "button_click", "on"])

        sm.current_state = "off"
        sm.execute_transition("button_click")
        assert sm.current_state == "on"

    def test_rule_object_format(self):
        """Direct Rule object."""
        sm = StateMachine()
        rule = Rule("off", "button_click", "on", priority=5)
        sm.add_rule(rule)

        assert sm.rules[0].priority == 5


class TestDefaultPriority:
    """Test default priority behavior."""

    def test_default_priority_is_zero(self):
        """Rules should have priority 0 by default."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "on"})

        assert sm.rules[0].priority == 0

    def test_default_enabled_is_true(self):
        """Rules should be enabled by default."""
        sm = StateMachine()
        sm.add_rule({"from": "off", "on": "button_click", "to": "on"})

        assert sm.rules[0].enabled is True
