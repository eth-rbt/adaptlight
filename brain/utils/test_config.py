"""
Tests for configuration loading and representation switching.
"""
import unittest
import tempfile
import os
import sys
import yaml

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from brain.core.state_executor import StateExecutor
from brain.core.state import State


class TestConfigLoading(unittest.TestCase):
    def test_default_representation(self):
        """Default representation is stdlib."""
        executor = StateExecutor()
        self.assertEqual(executor.version, "stdlib")

    def test_original_representation(self):
        """Can set original representation."""
        executor = StateExecutor("original")
        self.assertEqual(executor.version, "original")

    def test_pure_python_representation(self):
        """Can set pure_python representation."""
        executor = StateExecutor("pure_python")
        self.assertEqual(executor.version, "pure_python")

    def test_stdlib_representation(self):
        """Can set stdlib representation."""
        executor = StateExecutor("stdlib")
        self.assertEqual(executor.version, "stdlib")

    def test_config_file_parsing(self):
        """Config file parses representation version correctly."""
        config = {
            'representation': {
                'version': 'pure_python'
            }
        }

        # Write temp config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        try:
            with open(config_path) as f:
                loaded = yaml.safe_load(f)

            version = loaded.get('representation', {}).get('version', 'stdlib')
            self.assertEqual(version, 'pure_python')
        finally:
            os.unlink(config_path)

    def test_missing_representation_defaults_to_stdlib(self):
        """Missing representation config defaults to stdlib."""
        config = {
            'brain': {
                'mode': 'agent'
            }
        }

        version = config.get('representation', {}).get('version', 'stdlib')
        self.assertEqual(version, 'stdlib')


class TestRepresentationSwitching(unittest.TestCase):
    def test_original_mode_uses_rgb_fields(self):
        """Original mode uses r/g/b expressions."""
        executor = StateExecutor("original")
        state = State(name="red", r=255, g=0, b=0)
        executor.enter_state(state)
        rgb, _ = executor.render()
        self.assertEqual(rgb, (255, 0, 0))

    def test_original_mode_with_expressions(self):
        """Original mode evaluates expressions."""
        executor = StateExecutor("original")
        state = State(name="half", r="128", g="64", b="32")
        executor.enter_state(state)
        rgb, _ = executor.render()
        self.assertEqual(rgb, (128, 64, 32))

    def test_stdlib_mode_uses_code_field(self):
        """Stdlib mode uses code field."""
        executor = StateExecutor("stdlib")
        state = State(name="red", code='''
def render(prev, t):
    return (255, 0, 0), None
''')
        executor.enter_state(state)
        rgb, _ = executor.render()
        self.assertEqual(rgb, (255, 0, 0))

    def test_pure_python_mode_uses_code_field(self):
        """Pure Python mode uses code field."""
        executor = StateExecutor("pure_python")
        state = State(name="red", code='''
def render(prev, t):
    return (255, 0, 0), None
''')
        executor.enter_state(state)
        rgb, _ = executor.render()
        self.assertEqual(rgb, (255, 0, 0))

    def test_code_state_in_original_mode_uses_stdlib(self):
        """Code-based state in original mode falls back to stdlib."""
        executor = StateExecutor("original")

        # If state has code, it should use the appropriate renderer
        state = State(name="blue", code='''
def render(prev, t):
    return (0, 0, 255), None
''')
        executor.enter_state(state)
        rgb, _ = executor.render()
        # Should still work, falling back to stdlib for code-based states
        self.assertEqual(rgb, (0, 0, 255))

    def test_rgb_state_in_stdlib_mode_uses_original(self):
        """RGB-based state in stdlib mode uses original renderer."""
        executor = StateExecutor("stdlib")

        # If state has r/g/b but no code, use original renderer
        state = State(name="green", r=0, g=255, b=0)
        executor.enter_state(state)
        rgb, _ = executor.render()
        self.assertEqual(rgb, (0, 255, 0))


class TestStateMachineIntegration(unittest.TestCase):
    def test_state_machine_uses_representation_version(self):
        """StateMachine uses configured representation version."""
        from brain.core.state_machine import StateMachine

        sm = StateMachine(default_rules=False, representation_version="stdlib")
        self.assertEqual(sm.representation_version, "stdlib")
        self.assertEqual(sm.state_executor.version, "stdlib")

    def test_state_machine_original_mode(self):
        """StateMachine works with original representation."""
        from brain.core.state_machine import StateMachine

        sm = StateMachine(default_rules=False, representation_version="original")
        self.assertEqual(sm.representation_version, "original")

    def test_state_machine_renders_state(self):
        """StateMachine renders state through executor."""
        from brain.core.state_machine import StateMachine

        sm = StateMachine(default_rules=False, representation_version="stdlib")

        # Add a test state
        state = State(name="test", code='''
def render(prev, t):
    return (123, 45, 67), None
''')
        sm.states.add_state(state)

        # Set state should trigger rendering
        sm.set_state("test")

        # Check current RGB
        rgb = sm.get_current_rgb()
        self.assertEqual(rgb, (123, 45, 67))


if __name__ == '__main__':
    unittest.main()
