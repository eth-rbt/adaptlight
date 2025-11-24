"""
Tests for wildcard rule matching.
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.rule import Rule


class TestExactMatching:
    """Test exact state matching (no wildcards)."""

    def test_exact_match_succeeds(self):
        rule = Rule("off", "button_click", "on")
        assert rule.matches("off", "button_click") is True

    def test_exact_match_wrong_state(self):
        rule = Rule("off", "button_click", "on")
        assert rule.matches("on", "button_click") is False

    def test_exact_match_wrong_transition(self):
        rule = Rule("off", "button_click", "on")
        assert rule.matches("off", "button_hold") is False

    def test_exact_match_both_wrong(self):
        rule = Rule("off", "button_click", "on")
        assert rule.matches("on", "button_hold") is False


class TestStarWildcard:
    """Test '*' wildcard matching any state."""

    def test_star_matches_off(self):
        rule = Rule("*", "button_hold", "off")
        assert rule.matches("off", "button_hold") is True

    def test_star_matches_on(self):
        rule = Rule("*", "button_hold", "off")
        assert rule.matches("on", "button_hold") is True

    def test_star_matches_custom_state(self):
        rule = Rule("*", "button_hold", "off")
        assert rule.matches("rainbow_animation", "button_hold") is True

    def test_star_matches_nested_state(self):
        rule = Rule("*", "button_hold", "off")
        assert rule.matches("color/red", "button_hold") is True

    def test_star_requires_transition_match(self):
        rule = Rule("*", "button_hold", "off")
        assert rule.matches("off", "button_click") is False


class TestPrefixWildcard:
    """Test 'prefix/*' wildcard matching states with that prefix."""

    def test_prefix_matches_child(self):
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("color/red", "button_click") is True

    def test_prefix_matches_another_child(self):
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("color/blue", "button_click") is True

    def test_prefix_matches_deep_child(self):
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("color/warm/sunset", "button_click") is True

    def test_prefix_does_not_match_different_prefix(self):
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("animation/pulse", "button_click") is False

    def test_prefix_does_not_match_exact(self):
        """'color/*' should NOT match 'color' (only children)."""
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("color", "button_click") is False

    def test_prefix_does_not_match_similar_name(self):
        """'color/*' should NOT match 'colorful' (must have '/')."""
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("colorful", "button_click") is False

    def test_prefix_requires_transition_match(self):
        rule = Rule("color/*", "button_click", "off")
        assert rule.matches("color/red", "button_hold") is False


class TestEnabledFlag:
    """Test the enabled flag functionality."""

    def test_enabled_rule_matches(self):
        rule = Rule("off", "button_click", "on", enabled=True)
        assert rule.matches("off", "button_click") is True

    def test_disabled_rule_does_not_match(self):
        rule = Rule("off", "button_click", "on", enabled=False)
        assert rule.matches("off", "button_click") is False

    def test_disabled_wildcard_does_not_match(self):
        rule = Rule("*", "button_hold", "off", enabled=False)
        assert rule.matches("on", "button_hold") is False

    def test_default_enabled_is_true(self):
        rule = Rule("off", "button_click", "on")
        assert rule.enabled is True


class TestRuleRepr:
    """Test string representation of rules."""

    def test_simple_rule_repr(self):
        rule = Rule("off", "button_click", "on")
        assert "off" in repr(rule)
        assert "button_click" in repr(rule)
        assert "on" in repr(rule)

    def test_priority_in_repr(self):
        rule = Rule("off", "button_click", "on", priority=10)
        assert "[p=10]" in repr(rule)

    def test_zero_priority_not_in_repr(self):
        rule = Rule("off", "button_click", "on", priority=0)
        assert "[p=" not in repr(rule)

    def test_disabled_in_repr(self):
        rule = Rule("off", "button_click", "on", enabled=False)
        assert "[DISABLED]" in repr(rule)

    def test_condition_in_repr(self):
        rule = Rule("off", "button_click", "on", condition="getData('x') > 5")
        assert "getData('x') > 5" in repr(rule)


class TestToDict:
    """Test dictionary conversion."""

    def test_to_dict_includes_priority(self):
        rule = Rule("off", "button_click", "on", priority=10)
        d = rule.to_dict()
        assert d['priority'] == 10

    def test_to_dict_includes_enabled(self):
        rule = Rule("off", "button_click", "on", enabled=False)
        d = rule.to_dict()
        assert d['enabled'] is False

    def test_to_dict_all_fields(self):
        rule = Rule("off", "button_click", "on",
                    condition="x > 5",
                    action="setData('y', 1)",
                    priority=5,
                    enabled=True)
        d = rule.to_dict()
        assert d['state1'] == "off"
        assert d['transition'] == "button_click"
        assert d['state2'] == "on"
        assert d['condition'] == "x > 5"
        assert d['action'] == "setData('y', 1)"
        assert d['priority'] == 5
        assert d['enabled'] is True
