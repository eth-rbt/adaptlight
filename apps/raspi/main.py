"""
AdaptLight RASPi Application

Voice-controlled smart lighting using the SMgenerator library.
"""

import os
import sys
import time
import signal
import yaml
from pathlib import Path
from typing import Optional

# Add parent directories to path for imports
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env file from root directory
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

from brain import SMgenerator


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / 'config.yaml'

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    def expand_env(obj):
        if isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            return os.environ.get(env_var, '')
        elif isinstance(obj, dict):
            return {k: expand_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [expand_env(item) for item in obj]
        return obj

    return expand_env(config)


class AdaptLightRaspi:
    """Main application class for RASPi."""

    def __init__(self, config_path: str = None, debug: bool = False, verbose: bool = False):
        """
        Initialize the application.

        Args:
            config_path: Path to config file
            debug: Enable debug output (FPS timing)
            verbose: Enable verbose output (transcription, timing)
        """
        self.config = load_config(config_path)
        self.debug = debug
        self.verbose = verbose

        self.is_recording = False
        self.voice_reactive = None
        self.running = True

        # Initialize Brain
        brain_config = {
            'mode': self.config['brain']['mode'],
            'model': self.config['brain']['model'],
            'prompt_variant': self.config['brain']['prompt_variant'],
            'max_turns': self.config['brain'].get('max_turns', 10),
            'verbose': verbose,
            'anthropic_api_key': self.config['anthropic']['api_key'],
            'openai_api_key': self.config['openai']['api_key'],
            'storage_dir': self.config.get('storage', {}).get('dir', 'data/storage'),
        }
        self.smgen = SMgenerator(brain_config)

        # Register hooks for RASPi-specific feedback
        self.smgen.on('processing_start', self._on_processing_start)
        self.smgen.on('processing_end', self._on_processing_end)
        self.smgen.on('tool_end', self._on_tool_end)
        self.smgen.on('error', self._on_error)

        # Initialize hardware (lazy load to avoid import errors on non-Pi)
        self.led = None
        self.reactive_led = None  # NeoPixel for voice feedback
        self.button = None
        self.record_button = None
        self.voice = None

        self._init_hardware()
        self._init_voice()

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _init_hardware(self):
        """Initialize hardware controllers."""
        try:
            hw_config = self.config['hardware']

            if hw_config['led_type'] == 'cob':
                from .hardware.cobled.cobled import CobLed
                self.led = CobLed(
                    red_pin=hw_config['cob_red_pin'],
                    green_pin=hw_config['cob_green_pin'],
                    blue_pin=hw_config['cob_blue_pin'],
                    max_duty_cycle=hw_config.get('cob_max_duty_cycle', 2.0),
                    frequency=hw_config.get('cob_pwm_frequency', 1000)
                )
            else:
                from .hardware.led_controller import LEDController
                self.led = LEDController(
                    num_leds=hw_config.get('led_count', 16),
                    pin=hw_config.get('led_pin', 18),
                    brightness=hw_config.get('led_brightness', 0.3)
                )

            from .hardware.button_controller import ButtonController
            self.button = ButtonController(
                button_pin=hw_config['button_pin'],
                bounce_time=self.config['button']['bounce_time']
            )
            self.button.set_config(
                double_click_threshold=self.config['button']['double_click_threshold'],
                hold_threshold=self.config['button']['hold_threshold']
            )
            self.button.on_single_click = lambda: self._handle_button('button_click')
            self.button.on_double_click = lambda: self._handle_button('button_double_click')
            self.button.on_hold = lambda: self._handle_button('button_hold')
            self.button.on_release = lambda: self._handle_button('button_release')

            if hw_config.get('record_button_pin'):
                self.record_button = ButtonController(
                    button_pin=hw_config['record_button_pin'],
                    bounce_time=self.config['button']['bounce_time']
                )
                self.record_button.on_single_click = self._handle_record_button

            # Initialize reactive lights (NeoPixel for voice feedback)
            reactive_config = self.config.get('reactive_lights', {})
            if reactive_config.get('enabled', False):
                from .hardware.led_controller import LEDController
                self.reactive_led = LEDController(
                    led_count=reactive_config.get('led_count', 35),
                    led_pin=reactive_config.get('pin', 18),
                    brightness=reactive_config.get('brightness', 0.5)
                )
                print(f"Reactive NeoPixel initialized: {reactive_config.get('led_count')} LEDs on GPIO {reactive_config.get('pin')}")

            # Initialize light_states globals
            from .output.light_states import set_led_controller, set_state_machine
            set_led_controller(self.led)
            set_state_machine(self.smgen.state_machine)

            # Initialize voice reactive controller
            # Use reactive_led for voice reactive if available, else fall back to main led
            reactive_led_target = self.reactive_led if self.reactive_led else self.led
            if reactive_led_target and self.config['voice'].get('reactive_enabled', True):
                try:
                    from .voice.reactive import VoiceReactiveLight
                    self.voice_reactive = VoiceReactiveLight(reactive_led_target)
                    print("Voice reactive controller initialized")
                except Exception as e:
                    print(f"Voice reactive init failed: {e}")

            print("Hardware initialized")

        except Exception as e:
            print(f"Hardware initialization failed: {e}")
            print("Running in simulation mode")

    def _init_voice(self):
        """Initialize voice input."""
        if not self.config['voice']['enabled']:
            return

        try:
            from .voice.input import VoiceInput
            self.voice = VoiceInput(
                stt_provider=self.config['voice']['stt_provider'],
                replicate_token=self.config['replicate'].get('api_token')
            )
            print("Voice input initialized")
        except Exception as e:
            print(f"Voice input initialization failed: {e}")

    # ─────────────────────────────────────────────────────────────
    # Hook Handlers
    # ─────────────────────────────────────────────────────────────

    def _on_processing_start(self, data):
        """Called when brain starts processing."""
        if self.reactive_led:
            self.reactive_led.start_loading_animation()
        elif self.led:
            self.led.start_loading_animation()
        if self.verbose:
            print(f"Processing: {data.get('input', '')[:50]}...")

    def _on_processing_end(self, data):
        """Called when brain finishes processing."""
        if self.reactive_led:
            self.reactive_led.stop_loading_animation()
            self.reactive_led.flash_success()
        elif self.led:
            self.led.stop_loading_animation()
        if self.verbose:
            print(f"Done in {data.get('total_ms', 0):.0f}ms")

        # Update LED to show new state
        result = data.get('result')
        if result and result.success:
            self._execute_state(result.state)

    def _on_tool_end(self, data):
        """Called when a tool finishes executing."""
        if self.verbose:
            print(f"  Tool {data.get('tool', 'unknown')}: {data.get('duration_ms', 0):.0f}ms")

    def _on_error(self, data):
        """Called on processing error."""
        print(f"Error: {data.get('error', 'Unknown error')}")
        if self.reactive_led:
            self.reactive_led.stop_loading_animation()
            self.reactive_led.flash_error()
        elif self.led:
            self.led.stop_loading_animation()

    # ─────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────

    def _handle_button(self, event: str):
        """Handle button events."""
        print(f"Button event: {event}")
        state = self.smgen.trigger(event)
        self._execute_state(state)

    def _handle_record_button(self):
        """Handle record button press."""
        print(f"Record button pressed (is_recording={self.is_recording})")

        if not self.voice:
            print("Voice input not enabled")
            return

        if self.is_recording:
            # Stop recording
            self.is_recording = False

            # Stop voice reactive
            if self.voice_reactive:
                self.voice_reactive.stop()

            # Transcribe and process
            transcribed_text = self.voice.stop_recording()
            if transcribed_text:
                print(f"Transcribed: {transcribed_text}")
                result = self.smgen.process(transcribed_text)
                if result.message:
                    print(f"Response: {result.message}")
        else:
            # Start recording
            self.is_recording = True

            # Start voice reactive in non-standalone mode (uses VoiceInput's audio stream)
            audio_callback = None
            if self.voice_reactive:
                self.voice_reactive.start(standalone=False)
                audio_callback = self.voice_reactive.process_audio_data

            self.voice.start_recording(audio_callback=audio_callback)
            print("Recording... Speak now!")

    def _execute_state(self, state: dict):
        """Execute a state on the LED."""
        if not self.led:
            print(f"Would show state: {state}")
            return

        try:
            from .output.light_states import execute_unified_state
            execute_unified_state(state)
        except Exception as e:
            print(f"State execution error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to simple color
            r = state.get('r', 0)
            g = state.get('g', 0)
            b = state.get('b', 0)
            if isinstance(r, (int, float)) and isinstance(g, (int, float)) and isinstance(b, (int, float)):
                self.led.set_color(int(r), int(g), int(b))

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\nShutting down...")
        self.running = False

    # ─────────────────────────────────────────────────────────────
    # Main Loop
    # ─────────────────────────────────────────────────────────────

    def run(self):
        """Main application loop."""
        print("=" * 60)
        print("AdaptLight RASPi")
        print("=" * 60)
        print(f"Mode: {self.config['brain']['mode']}")
        print(f"Model: {self.config['brain']['model']}")
        print(f"LED type: {self.config['hardware']['led_type']}")
        print("=" * 60)

        # Show initial state
        self._execute_state(self.smgen.get_state())

        print("\nReady! Press buttons or speak commands.")
        print("Press Ctrl+C to exit.\n")

        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        print("Cleaning up...")

        if self.voice and self.is_recording:
            self.voice.stop_recording()

        if self.reactive_led:
            self.reactive_led.off()

        if self.led:
            self.led.off()

        print("Goodbye!")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='AdaptLight RASPi')
    parser.add_argument('--config', '-c', help='Path to config file')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    app = AdaptLightRaspi(
        config_path=args.config,
        debug=args.debug,
        verbose=args.verbose
    )
    app.run()


if __name__ == '__main__':
    main()
