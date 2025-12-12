#!/usr/bin/env python3
"""
Test script for audio/voice-related features:
- Voice-reactive light (audio amplitude analysis)
- Voice input and transcription
- Audio utilities

Run: python -m eval.test_audio
"""

import sys
import asyncio
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_separator(char='=', length=60):
    print(char * length)


def print_result(test_name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    icon = "✓" if passed else "✗"
    print(f"  {icon} [{status}] {test_name}")
    if details and not passed:
        print(f"      {details}")


class AudioTestRunner:
    """Test runner for audio-related features."""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def run_all_tests(self):
        """Run all audio-related tests."""
        print_separator()
        print("  AdaptLight Audio Feature Tests")
        print_separator()

        # Test categories
        self.test_voice_reactive_light()
        self.test_audio_analysis()
        self.test_voice_input()

        # Summary
        print_separator()
        total = self.passed + self.failed
        print(f"  RESULTS: {self.passed}/{total} passed")
        print_separator()

        return self.failed == 0

    def test_voice_reactive_light(self):
        """Test VoiceReactiveLight functionality."""
        print("\n[Voice Reactive Light]")

        # Import with mock to avoid hardware requirements
        from voice.voice_reactive_light import VoiceReactiveLight

        # Create mock LED controller
        mock_led = MagicMock()
        mock_led.set_color = MagicMock()

        # Test initialization
        try:
            vrl = VoiceReactiveLight(mock_led, color=(255, 0, 0), smoothing_alpha=0.3)
            passed = True
        except Exception as e:
            passed = False
            vrl = None
        print_result("VoiceReactiveLight initializes", passed)
        self._record(passed)

        if not vrl:
            print("  Skipping remaining VRL tests due to init failure")
            return

        # Test RMS calculation
        # Generate synthetic audio (sine wave at 440Hz)
        sample_rate = 44100
        duration_samples = 1024
        t = np.linspace(0, duration_samples / sample_rate, duration_samples)
        sine_wave = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        audio_bytes = sine_wave.tobytes()

        rms = vrl.calculate_rms(audio_bytes)
        passed = rms > 0 and rms < 20000
        print_result("RMS calculation produces valid value", passed,
                    f"RMS: {rms}")
        self._record(passed)

        # Test smoothing
        vrl.current_brightness = 100
        smoothed = vrl.smooth_value(200, 100)
        # With alpha=0.3: 0.3*200 + 0.7*100 = 60 + 70 = 130
        expected = 0.3 * 200 + 0.7 * 100
        passed = abs(smoothed - expected) < 1
        print_result("Exponential smoothing works correctly", passed,
                    f"Expected: {expected}, Got: {smoothed}")
        self._record(passed)

        # Test amplitude to brightness mapping
        vrl.current_rms = 0
        vrl.current_brightness = 0
        brightness = vrl.map_amplitude_to_brightness(3000)
        passed = 0 <= brightness <= 255
        print_result("Amplitude maps to valid brightness", passed,
                    f"Brightness: {brightness}")
        self._record(passed)

        # Test color setting
        vrl.set_color((0, 255, 0))
        passed = vrl.base_color == (0, 255, 0)
        print_result("Color can be changed", passed)
        self._record(passed)

        # Test smoothing adjustment
        vrl.set_smoothing(0.5)
        passed = vrl.smoothing_alpha == 0.5
        print_result("Smoothing alpha can be adjusted", passed)
        self._record(passed)

        # Test smoothing bounds
        vrl.set_smoothing(1.5)  # Should clamp to 1.0
        passed = vrl.smoothing_alpha == 1.0
        vrl.set_smoothing(-0.5)  # Should clamp to 0.0
        passed = passed and vrl.smoothing_alpha == 0.0
        print_result("Smoothing alpha is bounded [0, 1]", passed)
        self._record(passed)

    def test_audio_analysis(self):
        """Test audio analysis utilities."""
        print("\n[Audio Analysis]")

        # Test with synthetic audio data
        sample_rate = 44100
        duration_samples = 4096

        # Test 1: Silent audio should have low RMS
        silent = np.zeros(duration_samples, dtype=np.int16).tobytes()
        rms_silent = self._calculate_rms(silent)
        passed = rms_silent < 10
        print_result("Silent audio has near-zero RMS", passed,
                    f"RMS: {rms_silent}")
        self._record(passed)

        # Test 2: Loud audio should have high RMS
        loud = (np.ones(duration_samples) * 10000).astype(np.int16).tobytes()
        rms_loud = self._calculate_rms(loud)
        passed = rms_loud > 5000
        print_result("Loud audio has high RMS", passed,
                    f"RMS: {rms_loud}")
        self._record(passed)

        # Test 3: Sine wave RMS should be amplitude / sqrt(2)
        amplitude = 10000
        t = np.linspace(0, duration_samples / sample_rate, duration_samples)
        sine = (np.sin(2 * np.pi * 440 * t) * amplitude).astype(np.int16)
        rms_sine = self._calculate_rms(sine.tobytes())
        expected_rms = amplitude / np.sqrt(2)
        tolerance = expected_rms * 0.1  # 10% tolerance
        passed = abs(rms_sine - expected_rms) < tolerance
        print_result("Sine wave RMS matches theoretical", passed,
                    f"Expected: {expected_rms:.0f}, Got: {rms_sine:.0f}")
        self._record(passed)

        # Test 4: Frequency detection (simple zero-crossing based)
        samples_per_cycle = sample_rate / 440  # ~100 samples per 440Hz cycle
        zero_crossings = self._count_zero_crossings(sine)
        estimated_freq = (zero_crossings / 2) * (sample_rate / duration_samples)
        passed = abs(estimated_freq - 440) < 50  # Within 50Hz
        print_result("Frequency estimation works", passed,
                    f"Expected: 440Hz, Got: {estimated_freq:.0f}Hz")
        self._record(passed)

    def test_voice_input(self):
        """Test VoiceInput functionality."""
        print("\n[Voice Input]")

        from voice.voice_input import VoiceInput

        # Test initialization without hardware
        try:
            vi = VoiceInput(stt_provider='whisper', openai_client=None)
            passed = True
        except Exception as e:
            passed = False
            vi = None
        print_result("VoiceInput initializes without hardware", passed)
        self._record(passed)

        if not vi:
            print("  Skipping remaining VoiceInput tests")
            return

        # Test callback setting
        callback_called = False

        def test_callback(text):
            nonlocal callback_called
            callback_called = True

        vi.set_command_callback(test_callback)
        passed = vi.on_command_callback is not None
        print_result("Command callback can be set", passed)
        self._record(passed)

        # Test STT provider selection
        vi_whisper = VoiceInput(stt_provider='whisper')
        vi_replicate = VoiceInput(stt_provider='replicate')
        passed = vi_whisper.stt_provider == 'whisper' and vi_replicate.stt_provider == 'replicate'
        print_result("STT provider can be selected", passed)
        self._record(passed)

        # Test cleanup
        try:
            vi.cleanup()
            passed = True
        except Exception as e:
            passed = False
        print_result("Cleanup executes without error", passed)
        self._record(passed)

    def _calculate_rms(self, audio_data):
        """Calculate RMS of audio data."""
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        return np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))

    def _count_zero_crossings(self, audio_array):
        """Count zero crossings in audio array."""
        return np.sum(np.abs(np.diff(np.sign(audio_array))) > 0)

    def _record(self, passed):
        """Record test result."""
        if passed:
            self.passed += 1
        else:
            self.failed += 1


class AgentAudioCommandTestRunner:
    """Test runner for agent handling of audio-related commands."""

    def __init__(self, api_key, model='claude-sonnet-4-20250514'):
        self.api_key = api_key
        self.model = model
        self.passed = 0
        self.failed = 0

    async def run_all_tests(self):
        """Run all agent audio command tests."""
        print_separator()
        print("  AdaptLight Agent Audio Command Tests")
        print_separator()

        await self.test_voice_reactive_commands()

        # Summary
        print_separator()
        total = self.passed + self.failed
        print(f"  RESULTS: {self.passed}/{total} passed")
        print_separator()

        return self.failed == 0

    async def test_voice_reactive_commands(self):
        """Test agent handling of voice-reactive related commands."""
        print("\n[Agent Voice-Reactive Commands]")

        from voice.agent_executor import AgentExecutor
        from core.state_machine import StateMachine
        from core.state import State

        # Initialize state machine
        sm = StateMachine()
        sm.states.add_state(State('off', r=0, g=0, b=0))
        sm.states.add_state(State('on', r=255, g=255, b=255))
        sm.add_rule({"from": "off", "on": "button_click", "to": "on"})
        sm.add_rule({"from": "on", "on": "button_click", "to": "off"})

        executor = AgentExecutor(
            state_machine=sm,
            api_key=self.api_key,
            model=self.model,
            max_turns=10,
            verbose=False
        )

        # Test: Create a pulsing animation (common audio visualization color)
        result = await executor.run("Create a green pulsing animation for music visualization")

        # Check that a pulsing/breathing state was created
        states = [s.name for s in sm.states.get_states()]
        has_animation = any(
            s.name not in ['off', 'on'] and
            (s.speed is not None or 'sin' in str(s.r) or 'pulse' in s.name.lower() or 'breath' in s.name.lower())
            for s in sm.states.get_states()
        )
        passed = has_animation
        print_result("Agent creates animation state for music viz", passed,
                    f"States: {states}")
        self._record(passed)

        # Test: Set up reactive colors
        sm2 = StateMachine()
        sm2.states.add_state(State('off', r=0, g=0, b=0))
        sm2.states.add_state(State('on', r=255, g=255, b=255))
        sm2.add_rule({"from": "off", "on": "button_click", "to": "on"})
        sm2.add_rule({"from": "on", "on": "button_click", "to": "off"})

        executor2 = AgentExecutor(
            state_machine=sm2,
            api_key=self.api_key,
            model=self.model,
            max_turns=10,
            verbose=False
        )

        result = await executor2.run(
            "Set up rainbow colors that cycle. Use expressions for RGB."
        )

        # Check for expression-based states
        has_expressions = any(
            isinstance(s.r, str) or isinstance(s.g, str) or isinstance(s.b, str)
            for s in sm2.states.get_states()
        )
        passed = has_expressions
        print_result("Agent creates expression-based color states", passed)
        self._record(passed)

    def _record(self, passed):
        if passed:
            self.passed += 1
        else:
            self.failed += 1


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Audio Feature Tests')
    parser.add_argument('--with-agent', action='store_true',
                       help='Include agent command tests (requires API key)')
    args = parser.parse_args()

    # Run basic audio tests (no API key needed)
    runner = AudioTestRunner()
    basic_success = runner.run_all_tests()

    # Run agent tests if requested
    agent_success = True
    if args.with_agent:
        import yaml
        config_file = Path(__file__).parent.parent / 'config.yaml'
        if config_file.exists():
            with open(config_file) as f:
                config = yaml.safe_load(f)
            api_key = config.get('claude', {}).get('api_key')
            if api_key:
                model = config.get('claude', {}).get('model', 'claude-sonnet-4-20250514')
                agent_runner = AgentAudioCommandTestRunner(api_key=api_key, model=model)
                agent_success = asyncio.run(agent_runner.run_all_tests())
            else:
                print("\nSkipping agent tests: no API key in config.yaml")
        else:
            print("\nSkipping agent tests: config.yaml not found")

    sys.exit(0 if (basic_success and agent_success) else 1)


if __name__ == '__main__':
    main()
