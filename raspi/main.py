#!/usr/bin/env python3
"""
Main entry point for AdaptLight Raspberry Pi application.

Orchestrates all components:
- Hardware (LEDs, button)
- State machine
- Voice input
- Command parsing
- Logging and AWS uploads 
"""
 
import signal
import sys
import yaml
from pathlib import Path

# Import core components
from core.state_machine import StateMachine
from hardware.led_controller import LEDController
from hardware.button_controller import ButtonController
from hardware.hardware_config import HardwareConfig
from cobled import CobLed
from states.light_states import (
    initialize_default_states,
    initialize_default_rules,
    set_led_controller,
    set_state_machine,
    set_voice_reactive,
)
from voice.voice_input import VoiceInput
from voice.command_parser import CommandParser
from voice.agent_executor import AgentExecutor
from voice.audio_player import AudioPlayer
from voice.voice_reactive_light import VoiceReactiveLight
from event_logging.event_logger import EventLogger
from event_logging.log_manager import LogManager
from event_logging.aws_uploader import AWSUploader


class AdaptLight:
    """Main application class for AdaptLight."""

    def __init__(self, config_path='config.yaml', debug=False, verbose=False):
        """
        Initialize AdaptLight application.

        Args:
            config_path: Path to configuration file
            debug: Enable debug output (FPS timing for animations)
            verbose: Enable verbose output (transcription, timing, agent turns)
        """
        print("=" * 60)
        print("AdaptLight - Voice-Controlled Smart Lamp")
        if debug:
            print("DEBUG MODE ENABLED")
        if verbose:
            print("VERBOSE MODE ENABLED")
        print("=" * 60)

        # Load configuration
        self.config = self.load_config(config_path)
        self.debug = debug
        self.verbose = verbose

        # Initialize components
        self.state_machine = None
        self.led_controller = None
        self.button_controller = None
        self.record_button_controller = None
        self.voice_input = None
        self.command_parser = None
        self.agent_executor = None  # New: multi-turn agentic mode
        self.parsing_mode = 'json'  # 'json' or 'agent'
        self.audio_player = None
        self.event_logger = None
        self.log_manager = None
        self.aws_uploader = None
        self.is_recording = False
        self.voice_reactive = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def load_config(self, config_path):
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                print(f"Configuration loaded from {config_path}")
                return config
        except FileNotFoundError:
            print(f"Warning: {config_path} not found. Using defaults.")
            return self.get_default_config()

    def get_default_config(self):
        """Get default configuration."""
        return {
            'hardware': {
                'led_count': HardwareConfig.LED_COUNT,
                'led_brightness': HardwareConfig.LED_BRIGHTNESS,
                'button_pin': HardwareConfig.BUTTON_PIN
            },
            'voice': {
                'enabled': True,
                'stt_provider': 'whisper'
            },
            'logging': {
                'enabled': True,
                'log_dir': 'data/logs',
                'retention_days': 30
            },
            'aws': {
                'enabled': False
            }
        }

    def initialize(self):
        """Initialize all components."""
        print("\nInitializing components...")

        # Initialize state machine
        print("- State machine")
        self.state_machine = StateMachine(debug=self.debug)
        set_state_machine(self.state_machine)

        # Initialize LED controller
        print("- LED controller")
        led_config = self.config.get('hardware', {})
        led_type = led_config.get('led_type', 'neopixel')

        if led_type == 'cob':
            # COB PWM backend
            self.led_controller = CobLed(
                red_pin=led_config.get('cob_red_pin', 23),
                green_pin=led_config.get('cob_green_pin', 27),
                blue_pin=led_config.get('cob_blue_pin', 22),
                max_duty_cycle=led_config.get('cob_max_duty_cycle', led_config.get('max_duty_cycle', 1.0)),
                brightness=led_config.get('led_brightness', 0.3),
                frequency=led_config.get('cob_pwm_frequency', 1000)
            )
            print(f"COB LED mode (pins R/G/B = {led_config.get('cob_red_pin', 23)}/"
                  f"{led_config.get('cob_green_pin', 27)}/{led_config.get('cob_blue_pin', 22)}, "
                  f"max duty={led_config.get('cob_max_duty_cycle', led_config.get('max_duty_cycle', 1.0))})")
        else:
            # NeoPixel backend (default)
            self.led_controller = LEDController(
                led_count=led_config.get('led_count', 16),
                led_pin=HardwareConfig.LED_PIN,
                brightness=led_config.get('led_brightness', 0.3)
            )

        set_led_controller(self.led_controller)

        # Initialize default states
        print("- Default states")
        initialize_default_states(self.state_machine)

        # Initialize default rules (button toggle)
        print("- Default rules")
        initialize_default_rules(self.state_machine)

        # Initialize button controller (main control button)
        print("- Button controller (GPIO 2)")
        button_config = self.config.get('hardware', {})
        self.button_controller = ButtonController(
            button_pin=button_config.get('button_pin', 2)
        )

        # Set button callbacks
        self.button_controller.set_callbacks(
            on_single_click=lambda: self.handle_button_event('button_click'),
            on_double_click=lambda: self.handle_button_event('button_double_click'),
            on_hold=lambda: self.handle_button_event('button_hold'),
            on_release=lambda: self.handle_button_event('button_release')
        )

        # Initialize record button controller
        button_config = self.config.get('hardware', {})
        record_button_pin = button_config.get('record_button_pin', 17)
        print(f"- Record button controller (GPIO {record_button_pin})")
        self.record_button_controller = ButtonController(
            button_pin=record_button_pin
        )

        # Set record button callbacks
        self.record_button_controller.set_callbacks(
            on_single_click=lambda: self.handle_record_button(),
            on_double_click=None,
            on_hold=None,
            on_release=None
        )

        # Initialize logging
        print("- Event logger")
        log_config = self.config.get('logging', {})
        self.event_logger = EventLogger(
            log_dir=log_config.get('log_dir', 'data/logs')
        )

        print("- Log manager")
        self.log_manager = LogManager(
            log_dir=log_config.get('log_dir', 'data/logs'),
            retention_days=log_config.get('retention_days', 30)
        )

        # Initialize AWS uploader if enabled
        aws_config = self.config.get('aws', {})
        if aws_config.get('enabled', False):
            print("- AWS uploader")
            self.aws_uploader = AWSUploader(aws_config, self.log_manager)
            self.aws_uploader.start_scheduled_uploads()

        # Initialize voice input if enabled
        voice_config = self.config.get('voice', {})
        if voice_config.get('enabled', False):
            # Initialize audio player first (needed by CommandParser for TTS)
            print("- Audio player")
            self.audio_player = AudioPlayer(volume=2.0)  # 200% volume for louder playback

            # Check parsing mode: 'json' (old) or 'agent' (new multi-turn)
            self.parsing_mode = voice_config.get('parsing_mode', 'json')
            print(f"- Parsing mode: {self.parsing_mode}")

            if self.parsing_mode == 'agent':
                # New: Multi-turn agentic mode using Claude
                print("- Agent executor (multi-turn)")
                claude_config = self.config.get('claude', {})
                claude_key = claude_config.get('api_key')
                claude_model = claude_config.get('model', 'claude-sonnet-4-20250514')
                verbose = claude_config.get('verbose', False)
                prompt_variant = claude_config.get('prompt_variant', 'examples')

                # Debug: show if API key was loaded
                if claude_key:
                    print(f"  Claude API key: {claude_key[:20]}...{claude_key[-10:]}")
                else:
                    print("  WARNING: No Claude API key found in config!")
                print(f"  Prompt variant: {prompt_variant}")

                self.agent_executor = AgentExecutor(
                    state_machine=self.state_machine,
                    api_key=claude_key,
                    model=claude_model,
                    max_turns=10,
                    verbose=self.verbose or verbose,  # CLI flag or config
                    prompt_variant=prompt_variant
                )
            else:
                # Old: Single-shot JSON parsing
                print("- Command parser (single-shot)")
                openai_config = self.config.get('openai', {})
                openai_key = openai_config.get('api_key')
                parsing_method = openai_config.get('parsing_method', 'json_output')
                prompt_variant = openai_config.get('prompt_variant', 'full')
                model = openai_config.get('model', 'gpt-4o')
                reasoning_effort = openai_config.get('reasoning_effort', 'medium')
                verbosity = openai_config.get('verbosity', 0)
                self.command_parser = CommandParser(
                    api_key=openai_key,
                    parsing_method=parsing_method,
                    prompt_variant=prompt_variant,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    verbosity=verbosity,
                    audio_player=self.audio_player
                )

            print("- Voice input")
            # Get Replicate configuration
            replicate_config = self.config.get('replicate', {})
            replicate_token = replicate_config.get('api_token')

            # Get OpenAI client for transcription (if using whisper)
            openai_client = None
            if self.command_parser:
                openai_client = self.command_parser.client

            # Pass OpenAI client and Replicate token to VoiceInput for transcription
            self.voice_input = VoiceInput(
                stt_provider=voice_config.get('stt_provider', 'whisper'),
                openai_client=openai_client,
                replicate_token=replicate_token
            )
            self.voice_input.set_command_callback(self.handle_voice_command)

            # Initialize voice reactive light
            print("- Voice reactive light")
            self.voice_reactive = VoiceReactiveLight(
                led_controller=self.led_controller,
                color=(0, 255, 0),  # Green for voice input
                smoothing_alpha=0.2,  # Smooth (lower = smoother, higher = responsive)
                debug=self.debug  # Enable timing debug with --debug flag
            )
            set_voice_reactive(self.voice_reactive)

        print("\nInitialization complete!")

    def handle_button_event(self, event_type: str):
        """
        Handle button events.

        Args:
            event_type: Type of button event
        """
        print(f"\nButton event: {event_type}")

        # Execute transition in state machine
        if self.state_machine:
            old_state = self.state_machine.get_state()
            old_params = self.state_machine.get_state_params()

            self.state_machine.execute_transition(event_type)

            new_state = self.state_machine.get_state()
            new_params = self.state_machine.get_state_params()

            # Log button event with state information
            if self.event_logger:
                self.event_logger.log_button_event(
                    event_type,
                    state_before=old_state,
                    state_after=new_state,
                    state_params=new_params
                )

            # Log state change if it occurred
            if old_state != new_state and self.event_logger:
                self.event_logger.log_state_change(old_state, new_state, new_params)

    def handle_voice_command(self, command_text: str):
        """
        Handle voice commands.

        Args:
            command_text: Transcribed voice command
        """
        print(f"\nVoice command: {command_text}")

        if not self.state_machine:
            print("State machine not initialized")
            return

        # Check that we have either command_parser or agent_executor
        if not self.command_parser and not self.agent_executor:
            print("No command parser or agent executor initialized")
            return

        # Capture state before command execution
        state_before = self.state_machine.get_state()
        state_params_before = self.state_machine.get_state_params()

        # Note: Loading animation is already started before transcription in handle_record_button()

        try:
            if self.parsing_mode == 'agent':
                # New: Multi-turn agentic mode using Claude
                self._handle_voice_command_agent(command_text, state_before)
            else:
                # Old: Single-shot JSON parsing using OpenAI
                self._handle_voice_command_json(command_text, state_before)

        except Exception as e:
            # Make sure to stop loading animation even if there's an error
            if self.led_controller:
                self.led_controller.stop_loading_animation()
            raise e

    def _handle_voice_command_agent(self, command_text: str, state_before: str):
        """
        Handle voice command using multi-turn agent executor.

        Args:
            command_text: Transcribed voice command
            state_before: State before command execution
        """
        import asyncio
        import time

        if self.verbose:
            print("\n" + "=" * 60)
            print("🤖 AGENT EXECUTOR (multi-turn mode)")
            print("=" * 60)
            print(f"Input: {command_text}")
            print("-" * 60)
        else:
            print("🤖 Using agent executor (multi-turn mode)")

        # Capture state params before
        state_params_before = self.state_machine.get_state_params()

        # Run agent executor (asyncio.run() works in threads, get_event_loop() doesn't)
        agent_start = time.time()
        result = asyncio.run(self.agent_executor.run(command_text))
        agent_time = time.time() - agent_start

        # Stop loading animation after agent responds
        if self.led_controller:
            self.led_controller.stop_loading_animation()
            print("Loading animation stopped")

        print("=" * 60)
        print(f"💬 Agent Response: {result}")
        if self.verbose:
            print(f"⏱️  Agent execution time: {agent_time:.2f}s")
        print("=" * 60)

        # Optional: speak the response through TTS
        voice_config = self.config.get('voice', {})
        if voice_config.get('speak_response', False) and self.audio_player:
            self.audio_player.speak(result)

        # Capture state after
        state_after = self.state_machine.get_state()
        state_params_after = self.state_machine.get_state_params()

        # Always play success sound to indicate operation completed
        if self.audio_player:
            self.audio_player.play_success_sound(blocking=False)
        if self.led_controller:
            self.led_controller.flash_success()

        # Log the voice command
        if self.event_logger:
            self.event_logger.log_voice_command(
                command_text,
                {'success': True, 'message': result, 'mode': 'agent'},
                state_before=state_before,
                state_after=state_after,
                state_params=state_params_after
            )

    def _handle_voice_command_json(self, command_text: str, state_before: str):
        """
        Handle voice command using single-shot JSON parsing.

        Args:
            command_text: Transcribed voice command
            state_before: State before command execution
        """
        state_params_before = self.state_machine.get_state_params()

        # Gather system context for GPT
        available_states = self.state_machine.states.get_states_for_prompt()
        available_transitions = [
            {'name': 'button_click', 'description': 'Single click'},
            {'name': 'button_double_click', 'description': 'Double click'},
            {'name': 'button_hold', 'description': 'Hold button'},
            {'name': 'button_release', 'description': 'Release after hold'},
            {'name': 'voice_command', 'description': 'Voice command trigger'}
        ]
        current_rules = [r.to_dict() for r in self.state_machine.get_rules()]
        current_state = self.state_machine.get_state()
        global_variables = self.state_machine.state_data

        # Parse command using GPT (returns tool calls)
        result = self.command_parser.parse_command(
            command_text,
            available_states,
            available_transitions,
            current_rules,
            current_state,
            global_variables
        )

        # Stop loading animation after OpenAI responds
        if self.led_controller:
            self.led_controller.stop_loading_animation()
            print("Loading animation stopped")

        # Handle result
        changes_made = False
        if result['success']:
            print("=" * 60)

            # Print AI message if present
            if result.get('message'):
                print(f"💬 AI Response: {result['message']}")

            # Execute tool calls and track if changes were made
            if result.get('toolCalls'):
                print(f"⚡ Executing {len(result['toolCalls'])} action(s):")
                for i, tool_call in enumerate(result['toolCalls'], 1):
                    print(f"\n[{i}/{len(result['toolCalls'])}] {tool_call['name']}")
                    self.execute_tool(tool_call['name'], tool_call['arguments'])

                    # Track if any tools that modify state were called
                    if tool_call['name'] in ['append_rules', 'delete_rules', 'set_state', 'manage_variables', 'reset_rules']:
                        changes_made = True

            print("=" * 60)

            # Provide feedback based on whether changes were made
            if changes_made:
                # Start sound first (non-blocking)
                if self.audio_player:
                    self.audio_player.play_success_sound(blocking=False)
                # Then flash LEDs (happens simultaneously with sound)
                if self.led_controller:
                    self.led_controller.flash_success()
            else:
                # Only play error signal if no TTS was played
                tts_was_played = result.get('needsClarification', False)
                if not tts_was_played:
                    # Start sound first (non-blocking)
                    if self.audio_player:
                        self.audio_player.play_error_sound(blocking=False)
                    # Then flash LEDs (happens simultaneously with sound)
                    if self.led_controller:
                        self.led_controller.flash_error()
        else:
            print("❌ Failed to parse command")

            # Start sound first (non-blocking)
            if self.audio_player:
                self.audio_player.play_error_sound(blocking=False)

            # Then flash LEDs (happens simultaneously with sound)
            if self.led_controller:
                self.led_controller.flash_error()

        # Capture state after command execution
        state_after = self.state_machine.get_state()
        state_params_after = self.state_machine.get_state_params()

        # Log the voice command with state information
        if self.event_logger:
            self.event_logger.log_voice_command(
                command_text,
                result,
                state_before=state_before,
                state_after=state_after,
                state_params=state_params_after
            )

    def execute_tool(self, tool_name: str, args: dict):
        """
        Execute a tool call from GPT-5 (matching script.js executeTool function).

        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool
        """
        print(f"  🔧 Action: {tool_name}")
        print(f"  Arguments: {args}")

        if tool_name == 'append_rules':
            # Add new rules to the state machine
            if args.get('rules') and isinstance(args['rules'], list):
                print(f"  ➕ Adding {len(args['rules'])} rule(s):")
                new_rules = args['rules']
                for rule in new_rules:
                    self.state_machine.add_rule(rule)
                    print(f"    → {rule['state1']} --[{rule['transition']}]--> {rule['state2']}")

                # Safety check: ensure all destination states have exit rules
                # Collect unique destination states from the new rules
                destination_states = set()
                for rule in new_rules:
                    state2 = rule.get('state2')
                    if state2 and state2 != 'off':  # Don't need exit from 'off'
                        destination_states.add(state2)

                # For each destination state, check if an exit rule exists
                all_rules = self.state_machine.get_rules()
                for dest_state in destination_states:
                    has_exit_rule = any(r.state1 == dest_state for r in all_rules)
                    if not has_exit_rule:
                        # Auto-add a simple click-to-off exit rule
                        exit_rule = {
                            "state1": dest_state,
                            "transition": "button_click",
                            "state2": "off",
                            "condition": None,
                            "action": None
                        }
                        self.state_machine.add_rule(exit_rule)
                        print(f"  ⚠️  Auto-added exit rule: {dest_state} --[button_click]--> off (safety net)")

        elif tool_name == 'delete_rules':
            # Delete rules based on criteria
            all_rules = self.state_machine.get_rules()

            if args.get('delete_all'):
                # Delete all rules
                count = len(all_rules)
                self.state_machine.clear_rules()
                print(f"  🗑️  Deleted all {count} rule(s)")

            elif args.get('indices') and isinstance(args['indices'], list):
                # Delete by specific indices (sort descending to avoid index shifting)
                print(f"  🗑️  Deleting rules at indices: {args['indices']}")
                sorted_indices = sorted(args['indices'], reverse=True)
                for index in sorted_indices:
                    if 0 <= index < len(all_rules):
                        rule = all_rules[index]
                        print(f"    → [{index}] {rule.state1} --[{rule.transition}]--> {rule.state2}")
                        self.state_machine.remove_rule(index)

            else:
                # Delete by criteria (state1, transition, state2)
                criteria = []
                if args.get('state1'):
                    criteria.append(f"state1={args['state1']}")
                if args.get('transition'):
                    criteria.append(f"transition={args['transition']}")
                if args.get('state2'):
                    criteria.append(f"state2={args['state2']}")

                if criteria:
                    print(f"  🗑️  Deleting rules matching: {', '.join(criteria)}")
                    rules_to_delete = []

                    for i in range(len(all_rules) - 1, -1, -1):
                        rule = all_rules[i]
                        should_delete = False

                        if args.get('state1') and rule.state1 == args['state1']:
                            should_delete = True
                        if args.get('transition') and rule.transition == args['transition']:
                            should_delete = True
                        if args.get('state2') and rule.state2 == args['state2']:
                            should_delete = True

                        if should_delete:
                            rules_to_delete.append(i)
                            print(f"    → [{i}] {rule.state1} --[{rule.transition}]--> {rule.state2}")

                    # Delete the matching rules
                    for index in rules_to_delete:
                        self.state_machine.remove_rule(index)

        elif tool_name == 'set_state':
            # Change the current state immediately
            if args.get('state'):
                state_name = args['state']
                # Validate that state exists
                state_obj = self.state_machine.get_state_object(state_name)
                if state_obj is None:
                    print(f"  ❌ ERROR: State '{state_name}' does not exist")
                    print(f"     Available states: {', '.join([s.name for s in self.state_machine.states.get_states()])}")
                    raise ValueError(f"State '{state_name}' does not exist. Create it first with createState or use an existing state.")

                print(f"  🔄 Changing state to: {state_name}")
                self.state_machine.set_state(state_name)

                # Safety check: ensure there's at least one exit rule from this state
                # to prevent users from getting stuck
                all_rules = self.state_machine.get_rules()
                has_exit_rule = any(r.state1 == state_name for r in all_rules)
                if not has_exit_rule and state_name != 'off':
                    # Auto-add a simple click-to-off exit rule
                    exit_rule = {
                        "state1": state_name,
                        "transition": "button_click",
                        "state2": "off",
                        "condition": None,
                        "action": None
                    }
                    self.state_machine.add_rule(exit_rule)
                    print(f"  ⚠️  Auto-added exit rule: {state_name} --[button_click]--> off (safety net)")

        elif tool_name == 'manage_variables':
            # Manage global variables
            action = args.get('action')

            if action == 'set' and args.get('variables'):
                # Set/update variables
                print(f"  💾 Setting {len(args['variables'])} variable(s):")
                for key, value in args['variables'].items():
                    self.state_machine.set_data(key, value)
                    print(f"    → {key} = {value}")

            elif action == 'delete' and args.get('keys'):
                # Delete specific variables
                print(f"  💾 Deleting {len(args['keys'])} variable(s):")
                for key in args['keys']:
                    print(f"    → {key}")
                    self.state_machine.set_data(key, None)

            elif action == 'clear_all':
                # Clear all variables
                print(f"  💾 Clearing all variables")
                self.state_machine.clear_data()

        elif tool_name == 'create_state':
            # Create a new state with r, g, b, speed parameters
            if args.get('name'):
                from core.state import State
                name = args.get('name')
                r = args.get('r')
                g = args.get('g')
                b = args.get('b')
                speed = args.get('speed')
                description = args.get('description', '')
                voice_reactive_cfg = args.get('voice_reactive') or {}

                # Check if state already exists
                existing = self.state_machine.get_state_object(name)
                action = "Overwriting" if existing else "Creating"

                print(f"  ✨ {action} state: {name}")
                print(f"    → r={r}, g={g}, b={b}, speed={speed}")
                if description:
                    print(f"    → Description: {description}")
                if voice_reactive_cfg.get('enabled'):
                    print(f"    → Voice reactive: {voice_reactive_cfg}")

                # Create and add/replace the state
                state = State(
                    name=name,
                    r=r,
                    g=g,
                    b=b,
                    speed=speed,
                    description=description,
                    voice_reactive=voice_reactive_cfg
                )
                self.state_machine.states.add_state(state)
                print(f"    ✅ State '{name}' {'replaced' if existing else 'created'} successfully")

        elif tool_name == 'delete_state':
            # Delete a custom state by name
            if args.get('name'):
                name = args.get('name')

                # Prevent deletion of default states
                if name in ['on', 'off']:
                    print(f"  ❌ Cannot delete default state: {name}")
                    return

                print(f"  🗑️  Deleting state: {name}")
                success = self.state_machine.states.delete_state(name)
                if success:
                    print(f"    ✅ State '{name}' deleted successfully")
                else:
                    print(f"    ❌ State '{name}' not found")

        elif tool_name == 'reset_rules':
            # Reset rules back to default (on/off toggle)
            print(f"  🔄 Resetting rules to default")

            # Clear all existing rules
            rule_count = len(self.state_machine.get_rules())
            self.state_machine.clear_rules()
            print(f"    → Cleared {rule_count} existing rule(s)")

            # Re-initialize default rules
            from states.light_states import initialize_default_rules
            initialize_default_rules(self.state_machine)
            print(f"    → Restored default on/off toggle")

        else:
            print(f"  ❌ Unknown tool: {tool_name}")

    def handle_record_button(self):
        """
        Handle record button press - start/stop voice recording.
        """
        print(f"\nRecord button pressed! (is_recording={self.is_recording})")

        if not self.voice_input:
            print("Voice input not enabled")
            return

        if self.is_recording:
            print("\nStopping recording...")
            self.is_recording = False

            # Stop voice reactive light
            if self.voice_reactive:
                self.voice_reactive.stop()

            # Start loading animation before transcription
            if self.led_controller:
                print("Starting loading animation...")
                self.led_controller.start_loading_animation(color=(255, 255, 255), debug=self.debug)

            # Stop recording and transcribe
            import time
            if self.verbose:
                print("\n" + "=" * 60)
                print("📝 TRANSCRIPTION")
                print("=" * 60)

            transcribe_start = time.time()
            transcribed_text = self.voice_input.stop_recording()
            transcribe_time = time.time() - transcribe_start

            if transcribed_text:
                print(f"Transcribed: {transcribed_text}")
                if self.verbose:
                    print(f"⏱️  Transcription time: {transcribe_time:.2f}s")
                    print("=" * 60)
                self.handle_voice_command(transcribed_text)
            else:
                if self.verbose:
                    print("❌ No transcription result")
                    print(f"⏱️  Transcription time: {transcribe_time:.2f}s")
        else:
            print("\nStarting recording... Speak now!")
            self.is_recording = True

            # Set state to off before starting voice reactive mode
            if self.state_machine:
                self.state_machine.set_state("off")

            # Start voice reactive light in callback mode (no standalone stream)
            if self.voice_reactive:
                self.voice_reactive.start(standalone=False)

            # Start recording with audio callback for reactive light
            audio_callback = self.voice_reactive.process_audio_data if self.voice_reactive else None
            self.voice_input.start_recording(audio_callback=audio_callback)

    def run(self):
        """Main application loop."""
        print("\n" + "=" * 60)
        print("AdaptLight is running!")
        print("=" * 60)
        print("\nPress Ctrl+C to exit\n")

        # Start voice listening if enabled
        if self.voice_input:
            self.voice_input.start_listening()

        # Main loop
        try:
            while True:
                # In a real implementation, this would handle events
                # For now, just keep the process running
                import time
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\nShutting down...")
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown."""
        print("\nCleaning up...")

        # Stop voice input
        if self.voice_input:
            self.voice_input.cleanup()

        # Upload pending logs before shutdown
        if self.aws_uploader:
            print("Uploading pending logs to AWS...")
            try:
                self.aws_uploader.upload_pending_logs()
            except Exception as e:
                print(f"Error uploading logs during shutdown: {e}")

            # Stop the scheduled uploader
            self.aws_uploader.stop_scheduled_uploads()

        # Cleanup hardware
        if self.button_controller:
            self.button_controller.cleanup()

        if self.record_button_controller:
            self.record_button_controller.cleanup()

        if self.led_controller:
            self.led_controller.cleanup()

        # Cleanup audio player
        if self.audio_player:
            self.audio_player.cleanup()

        # Cleanup voice reactive light
        if self.voice_reactive:
            self.voice_reactive.stop()

        print("Goodbye!")
        sys.exit(0)

    def signal_handler(self, sig, frame):
        """Handle interrupt signals."""
        print(f"\nReceived signal {sig}")
        self.shutdown()


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='AdaptLight - Voice-Controlled Smart Lamp')
    parser.add_argument('--debug', action='store_true', help='Enable debug output (FPS timing for animations)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output (transcription, timing, agent turns)')
    args = parser.parse_args()

    app = AdaptLight(debug=args.debug, verbose=args.verbose)
    app.initialize()
    app.run()


if __name__ == '__main__':
    main()
