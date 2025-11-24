"""
Tests for the pattern library.
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from patterns.library import PatternLibrary, PATTERNS


class TestPatternLibrary:
    """Test the pattern library."""

    def setup_method(self):
        """Set up test fixtures."""
        self.library = PatternLibrary()

    def test_list_patterns(self):
        """Test listing all patterns."""
        patterns = self.library.list()

        expected = ["counter", "toggle", "cycle", "hold_release", "timer", "schedule", "data_reactive"]
        for name in expected:
            assert name in patterns

    def test_get_counter_pattern(self):
        """Test getting counter pattern."""
        pattern = self.library.get("counter")

        assert pattern is not None
        assert pattern["name"] == "counter"
        assert "description" in pattern
        assert "template" in pattern
        assert "example" in pattern

    def test_get_toggle_pattern(self):
        """Test getting toggle pattern."""
        pattern = self.library.get("toggle")

        assert pattern is not None
        assert pattern["name"] == "toggle"
        assert "template" in pattern
        assert "rules" in pattern["template"]

    def test_get_nonexistent_pattern(self):
        """Test getting a pattern that doesn't exist."""
        pattern = self.library.get("nonexistent")
        assert pattern is None

    def test_list_with_descriptions(self):
        """Test listing patterns with descriptions."""
        patterns = self.library.list_with_descriptions()

        assert len(patterns) == len(PATTERNS)
        for p in patterns:
            assert "name" in p
            assert "description" in p

    def test_search_counter_keywords(self):
        """Test searching for counter-related keywords."""
        matches = self.library.search(["next", "clicks"])

        assert "counter" in matches

    def test_search_toggle_keywords(self):
        """Test searching for toggle-related keywords."""
        matches = self.library.search(["toggle", "switch"])

        assert "toggle" in matches

    def test_search_hold_keywords(self):
        """Test searching for hold-related keywords."""
        matches = self.library.search(["hold", "release"])

        assert "hold_release" in matches

    def test_search_timer_keywords(self):
        """Test searching for timer-related keywords."""
        matches = self.library.search(["seconds", "delayed"])

        assert "timer" in matches

    def test_search_weather_keywords(self):
        """Test searching for data_reactive pattern."""
        matches = self.library.search(["weather", "temperature"])

        assert "data_reactive" in matches


class TestPatternStructure:
    """Test pattern structure and completeness."""

    def test_all_patterns_have_required_fields(self):
        """Test that all patterns have required fields."""
        required_fields = ["name", "description", "template", "example"]

        for name, pattern in PATTERNS.items():
            for field in required_fields:
                assert field in pattern, f"Pattern '{name}' missing field '{field}'"

    def test_all_patterns_have_when_to_use(self):
        """Test that all patterns have when_to_use list."""
        for name, pattern in PATTERNS.items():
            assert "when_to_use" in pattern, f"Pattern '{name}' missing 'when_to_use'"
            assert len(pattern["when_to_use"]) > 0, f"Pattern '{name}' has empty 'when_to_use'"

    def test_counter_example_structure(self):
        """Test counter pattern example structure."""
        pattern = PATTERNS["counter"]
        example = pattern["example"]

        assert "user_request" in example
        assert "variables" in example
        assert "output" in example
        assert "appendRules" in example["output"]

    def test_toggle_example_structure(self):
        """Test toggle pattern example structure."""
        pattern = PATTERNS["toggle"]
        example = pattern["example"]

        assert "user_request" in example
        assert "output" in example
        assert "appendRules" in example["output"]

    def test_data_reactive_has_tool_example(self):
        """Test data_reactive pattern includes tool definition."""
        pattern = PATTERNS["data_reactive"]
        example = pattern["example"]
        output = example["output"]

        assert "defineTool" in output
        assert "createDataSource" in output
        assert "appendRules" in output


class TestPatternTemplates:
    """Test pattern templates."""

    def test_counter_template_has_three_rules(self):
        """Test counter template has entry, continue, exit rules."""
        pattern = PATTERNS["counter"]
        rules = pattern["template"]["rules"]

        assert len(rules) == 3

        descriptions = [r["description"] for r in rules]
        assert any("entry" in d.lower() for d in descriptions)
        assert any("continue" in d.lower() for d in descriptions)
        assert any("exit" in d.lower() for d in descriptions)

    def test_toggle_template_has_two_rules(self):
        """Test toggle template has two rules (A→B, B→A)."""
        pattern = PATTERNS["toggle"]
        rules = pattern["template"]["rules"]

        assert len(rules) == 2

    def test_hold_release_template(self):
        """Test hold_release template structure."""
        pattern = PATTERNS["hold_release"]
        rules = pattern["template"]["rules"]

        # Should have hold and release rules
        transitions = [r["on"] for r in rules]
        assert "button_hold" in str(transitions)
        assert "button_release" in str(transitions)
