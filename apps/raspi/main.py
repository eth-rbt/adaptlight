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
from brain.processing.vision_runtime import VisionRuntime
from brain.processing.api_runtime import APIRuntime
from brain.processing.audio_runtime import AudioRuntime
from brain.processing.volume_runtime import VolumeRuntime
from brain.apis.api_executor import APIExecutor

# Import supabase client for logging
from . import supabase_client


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

        # Session tracking for Supabase feedback
        self.last_session_id = None
        self.feedback_pending = False
        self.device_id = self.config.get('device', {}).get('id', 'lamp1')

        # Initialize Brain
        speech_config = self.config.get('speech', {})
        representation_config = self.config.get('representation', {})
        vision_config = self.config.get('vision', {})
        brain_config = {
            'mode': self.config['brain']['mode'],
            'model': self.config['brain']['model'],
            'prompt_variant': self.config['brain']['prompt_variant'],
            'max_turns': self.config['brain'].get('max_turns', 10),
            'verbose': verbose,
            'anthropic_api_key': self.config['anthropic']['api_key'],
            'openai_api_key': self.config['openai']['api_key'],
            'storage_dir': self.config.get('storage', {}).get('dir', 'data/storage'),
            'speech_instructions': speech_config.get('instructions') if speech_config.get('enabled') else None,
            'representation_version': representation_config.get('version', 'stdlib'),
            'speech_mode': speech_config.get('mode', 'default'),
            'vision_config': vision_config,  # Pass vision capabilities to agent
        }
        self.smgen = SMgenerator(brain_config)

        # Initialize Vision Runtime (for camera-reactive features)
        vision_config = self.config.get('vision', {})
        self.vision_runtime = VisionRuntime(
            smgen=self.smgen,
            config=vision_config,
            openai_api_key=self.config['openai']['api_key'],
            verbose=verbose
        ) if vision_config.get('enabled') else None

        # Initialize API Runtime (for api-reactive features)
        api_config = self.config.get('api', {})
        self.api_executor = APIExecutor(timeout=15.0) if api_config.get('enabled') else None
        self.api_runtime = APIRuntime(
            smgen=self.smgen,
            api_executor=self.api_executor,
            config=api_config
        ) if api_config.get('enabled') else None

        # Track API tick timing
        self._last_api_tick_ms = 0
        self._api_tick_interval_ms = api_config.get('tick_interval_ms', 1000)

        # Initialize Audio Runtime (for audio-reactive features via LLM)
        audio_config = self.config.get('audio', {})
        self.audio_runtime = AudioRuntime(
            smgen=self.smgen,
            config=audio_config,
            openai_api_key=self.config['openai']['api_key']
        ) if audio_config.get('enabled') else None

        # Initialize Volume Runtime (for volume-reactive features)
        volume_config = self.config.get('volume', {})
        self.volume_runtime = VolumeRuntime(
            smgen=self.smgen,
            config=volume_config
        ) if volume_config.get('enabled') else None

        # Register hooks for RASPi-specific feedback
        self.smgen.on('processing_start', self._on_processing_start)
        self.smgen.on('processing_end', self._on_processing_end)
        self.smgen.on('tool_end', self._on_tool_end)
        self.smgen.on('error', self._on_error)
        self.smgen.on('message_ready', self._on_message_ready)

        # Initialize hardware (lazy load to avoid import errors on non-Pi)
        self.led = None
        self.reactive_led = None  # NeoPixel for voice feedback
        self.button = None
        self.record_button = None
        self.feedback_yes_button = None
        self.tts = None  # Text-to-speech
        self.tts_thread = None  # Background TTS thread for early generation
        self.feedback_no_button = None
        self.voice = None
        self.mic_controller = None  # Unified mic controller

        self._init_hardware()
        self._init_voice()
        self._init_mic()
        self._init_camera()

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
            elif hw_config['led_type'] == 'cob_serial':
                from .hardware.cobled.cobled_serial import CobLedSerial
                self.led = CobLedSerial(
                    port=hw_config.get('cob_serial_port', '/dev/ttyAMA0'),
                    baudrate=hw_config.get('cob_serial_baudrate', 115200),
                    brightness=hw_config.get('led_brightness', 1.0)
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

            # Initialize feedback buttons (Yes/No for Supabase)
            if hw_config.get('feedback_yes_pin'):
                self.feedback_yes_button = ButtonController(
                    button_pin=hw_config['feedback_yes_pin'],
                    bounce_time=self.config['button']['bounce_time']
                )
                self.feedback_yes_button.on_single_click = lambda: self._handle_feedback(True)
                print(f"Feedback YES button on GPIO {hw_config['feedback_yes_pin']}")

            if hw_config.get('feedback_no_pin'):
                self.feedback_no_button = ButtonController(
                    button_pin=hw_config['feedback_no_pin'],
                    bounce_time=self.config['button']['bounce_time']
                )
                self.feedback_no_button.on_single_click = lambda: self._handle_feedback(False)
                print(f"Feedback NO button on GPIO {hw_config['feedback_no_pin']}")

            # Initialize reactive lights (NeoPixel for voice feedback)
            reactive_config = self.config.get('reactive_lights', {})
            if reactive_config.get('enabled', False):
                from .hardware.led_controller import LEDController
                self.reactive_led = LEDController(
                    led_count=reactive_config.get('led_count', 35),
                    brightness=reactive_config.get('brightness', 0.5),
                    spi_bus_id=reactive_config.get('spi_bus', 1)
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
                    # Get voice reactive settings from config
                    smoothing = reactive_config.get('smoothing_alpha', 0.25)
                    self.voice_reactive = VoiceReactiveLight(
                        reactive_led_target,
                        smoothing_alpha=smoothing
                    )
                    # Set amplitude range from config
                    min_amp = reactive_config.get('min_amplitude')
                    max_amp = reactive_config.get('max_amplitude')
                    if min_amp is not None or max_amp is not None:
                        self.voice_reactive.set_amplitude_range(min_amp, max_amp)
                    if self.verbose:
                        print(f"Voice reactive initialized (min={min_amp}, max={max_amp}, smooth={smoothing})")
                except Exception as e:
                    if self.verbose:
                        print(f"Voice reactive init failed: {e}")

            print("Hardware initialized")

        except Exception as e:
            print(f"Hardware initialization failed: {e}")
            print("Running in simulation mode")

    def _init_camera(self):
        """Initialize camera for vision processing."""
        self.camera = None
        self.camera_thread = None
        self._camera_running = False
        self._vision_session_id = None
        self._use_picamera = False

        vision_config = self.config.get('vision', {})
        if not vision_config.get('enabled') or not self.vision_runtime:
            return

        width = vision_config.get('camera_width', 320)
        height = vision_config.get('camera_height', 240)

        # Try picamera2 first (for Pi Camera ribbon cable)
        try:
            from picamera2 import Picamera2
            import threading

            print(f"📷 Initializing Pi Camera (picamera2)...")
            self.camera = Picamera2()

            # Check if camera is available
            camera_info = self.camera.global_camera_info()
            if not camera_info:
                print("❌ No Pi Camera detected, trying OpenCV...")
                self.camera = None
            else:
                print(f"   Found: {camera_info[0].get('Model', 'unknown')}")

                # Configure camera
                config = self.camera.create_still_configuration(
                    main={"size": (width, height), "format": "RGB888"}
                )
                self.camera.configure(config)
                self.camera.start()

                # Test capture
                import time
                time.sleep(0.3)  # Let camera warm up
                test_frame = self.camera.capture_array()
                if test_frame is not None:
                    actual_h, actual_w = test_frame.shape[:2]
                    print(f"✅ Pi Camera OK: {actual_w}x{actual_h}")
                    self._use_picamera = True
                else:
                    print("❌ Pi Camera test capture failed")
                    self.camera.stop()
                    self.camera = None

        except ImportError:
            print("📷 picamera2 not available, trying OpenCV...")
        except Exception as e:
            print(f"📷 Pi Camera init failed: {e}, trying OpenCV...")
            self.camera = None

        # Fallback to OpenCV (for USB webcams)
        if self.camera is None:
            try:
                import cv2
                import threading

                camera_index = vision_config.get('camera_index', 0)
                print(f"📷 Trying OpenCV camera {camera_index}...")

                self.camera = cv2.VideoCapture(camera_index)

                if not self.camera.isOpened():
                    print(f"❌ Camera {camera_index} not available, vision disabled")
                    self.camera = None
                    return

                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

                ret, test_frame = self.camera.read()
                if ret and test_frame is not None:
                    actual_h, actual_w = test_frame.shape[:2]
                    print(f"✅ OpenCV Camera OK: {actual_w}x{actual_h}")
                    self._use_picamera = False
                else:
                    print(f"❌ OpenCV camera test capture failed!")
                    self.camera.release()
                    self.camera = None
                    return

            except ImportError:
                print("❌ OpenCV not installed, vision disabled")
                return
            except Exception as e:
                print(f"❌ OpenCV camera init failed: {e}")
                return

        if self.camera is None:
            print("❌ No camera available, vision disabled")
            return

        # Start vision session
        import threading
        session = self.vision_runtime.start_session(user_id=self.device_id)
        self._vision_session_id = session.get('session_id')
        print(f"Vision session started: {self._vision_session_id}")

        # Start camera capture thread
        self._camera_running = True
        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()

    def _camera_loop(self):
        """Background thread for camera capture and vision processing."""
        import cv2
        import base64
        import time

        vision_config = self.config.get('vision', {})
        interval_ms = vision_config.get('interval_ms', 2000)
        cv_interval_ms = vision_config.get('cv', {}).get('interval_ms', 200)
        idle_check_ms = 1000  # Check for watchers every 1s when idle

        # Use CV interval if CV is the primary engine
        capture_interval_ms = min(interval_ms, cv_interval_ms) if vision_config.get('cv', {}).get('enabled') else interval_ms

        camera_type = "picamera2" if self._use_picamera else "OpenCV"
        print(f"📹 Camera loop started ({camera_type}, interval: {capture_interval_ms}ms)")

        was_idle = False

        while self._camera_running and self.camera:
            try:
                # Check if there are active vision watchers before capturing
                watchers = self.vision_runtime._get_active_watchers()
                if not watchers:
                    if not was_idle and self.verbose:
                        print(f"[Vision] No active watchers, camera idle")
                    was_idle = True
                    time.sleep(idle_check_ms / 1000.0)
                    continue

                if was_idle and self.verbose:
                    print(f"[Vision] Watchers active, camera resuming: {[w.get('name') for w in watchers]}")
                was_idle = False

                # Capture frame based on camera type
                if self._use_picamera:
                    # picamera2 returns RGB, convert to BGR for OpenCV
                    frame_rgb = self.camera.capture_array()
                    if frame_rgb is None:
                        time.sleep(0.1)
                        continue
                    frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                else:
                    # OpenCV VideoCapture
                    if not self.camera.isOpened():
                        break
                    ret, frame = self.camera.read()
                    if not ret or frame is None:
                        time.sleep(0.1)
                        continue

                # Encode frame as JPEG base64 data URL
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                base64_data = base64.b64encode(buffer).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{base64_data}"

                # Process frame through vision runtime
                if self._vision_session_id:
                    result = self.vision_runtime.process_frame(
                        session_id=self._vision_session_id,
                        image_data_url=image_data_url
                    )

                    if self.verbose and result.get('processed'):
                        vision_data = result.get('vision', {})
                        print(f"[Vision] Processed: {vision_data}")

                    if result.get('processed') and result.get('emitted_events'):
                        if self.verbose:
                            print(f"[Vision] Events: {result.get('emitted_events')}")
                        # Update LED if vision triggered a state change
                        self._execute_state(self.smgen.get_state())

                # Sleep for capture interval
                time.sleep(capture_interval_ms / 1000.0)

            except Exception as e:
                if self.verbose:
                    print(f"[Vision] Frame processing error: {e}")
                time.sleep(0.5)

    def _init_voice(self):
        """Initialize voice input and TTS output."""
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

        # Initialize TTS
        speech_config = self.config.get('speech', {})
        if speech_config.get('enabled', False):
            try:
                from .voice.tts import TextToSpeech
                speaker_config = self.config.get('speaker', {})
                audio_device = speaker_config.get('device', 'plughw:2,0')
                volume = speaker_config.get('volume', 1.0)
                self.tts = TextToSpeech(
                    provider=speech_config.get('provider', 'openai'),
                    voice=speech_config.get('voice'),
                    api_key=self.config['openai']['api_key'],
                    audio_device=audio_device,
                    volume=volume
                )
                print(f"Text-to-speech initialized (device: {audio_device}, volume: {volume}x)")
            except Exception as e:
                print(f"TTS initialization failed: {e}")

    def _init_mic(self):
        """Initialize the unified microphone controller."""
        if not self.config['voice']['enabled']:
            return

        try:
            from .voice.mic_controller import MicController

            self.mic_controller = MicController(
                config=self.config,
                volume_runtime=self.volume_runtime,
                audio_runtime=self.audio_runtime,
                state_machine=self.smgen.state_machine,
                replicate_token=self.config['replicate'].get('api_token'),
                device_id=self.device_id,
                verbose=self.verbose,
            )

            # Set callback for state changes
            self.mic_controller.set_on_state_change(
                lambda: self._execute_state(self.smgen.get_state())
            )

            # Start the controller
            if self.mic_controller.start():
                if self.verbose:
                    print("Mic controller initialized")
            else:
                if self.verbose:
                    print("Mic controller failed to start")
                self.mic_controller = None

        except Exception as e:
            if self.verbose:
                print(f"Mic controller initialization failed: {e}")
            import traceback
            traceback.print_exc()
            self.mic_controller = None

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

    def _on_message_ready(self, data):
        """Called when agent's done() message is ready - start TTS early."""
        message = data.get('message')
        if message and self.tts:
            import threading

            # Wait for any existing TTS to finish first
            if self.tts_thread and self.tts_thread.is_alive():
                if self.verbose:
                    print(f"🔊 Waiting for previous TTS to finish...")
                self.tts_thread.join(timeout=10)

            if self.verbose:
                print(f"🔊 Starting early TTS generation...")
            # Start TTS generation in background thread (non-daemon so it completes)
            self.tts_thread = threading.Thread(
                target=self.tts.speak,
                args=(message,)
            )
            self.tts_thread.start()

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
        if self.verbose:
            mic_status = "none"
            if self.mic_controller:
                mic_status = f"stream_open={self.mic_controller._stream_open}, recording={self.mic_controller.is_recording}"
            print(f"Record button pressed (is_recording={self.is_recording}, mic={mic_status})")

        # Check if we have a mic controller or voice input
        if not self.mic_controller and not self.voice:
            print("Voice input not enabled")
            return

        if self.is_recording:
            # ─── STOP RECORDING ───
            self.is_recording = False

            # Stop voice reactive
            if self.voice_reactive:
                self.voice_reactive.stop()

            # Start loading animation while transcribing
            if self.reactive_led:
                self.reactive_led.start_loading_animation()

            # Get audio bytes and transcribe
            if self.mic_controller:
                audio_bytes = self.mic_controller.stop_recording()
                transcribed_text = self._transcribe_audio(audio_bytes) if audio_bytes else None
            else:
                # Fallback to old VoiceInput
                transcribed_text = self.voice.stop_recording()

            if transcribed_text:
                if self.verbose:
                    print(f"Transcribed: {transcribed_text}")
                # Reset TTS thread before processing
                self.tts_thread = None
                result = self.smgen.process(transcribed_text)
                if result.message:
                    if self.verbose:
                        print(f"Response: {result.message}")

                    # Wait for early TTS thread if it was started, otherwise speak now
                    if self.tts_thread:
                        if self.tts_thread.is_alive():
                            if self.verbose:
                                print("🔊 Waiting for TTS to finish...")
                            self.tts_thread.join()
                            if self.verbose:
                                print("🔊 TTS thread completed")
                        else:
                            if self.verbose:
                                print("🔊 TTS thread already finished")
                    elif self.tts:
                        # Fallback: TTS wasn't started early, speak now
                        if self.verbose:
                            print("🔊 Fallback: speaking now...")
                        self.tts.speak(result.message)

                # Log to Supabase
                self._log_command_to_supabase(transcribed_text, result)
            else:
                if self.verbose:
                    print("No transcription result")
                if self.reactive_led:
                    self.reactive_led.stop_loading_animation()
        else:
            # ─── START RECORDING ───
            self.is_recording = True

            # Flash yellow twice to indicate recording started
            if self.reactive_led:
                for _ in range(2):
                    self.reactive_led.fill((255, 200, 0))  # Yellow flash
                    self.reactive_led.show()
                    time.sleep(0.15)
                    self.reactive_led.off()
                    time.sleep(0.1)

            # Transition COB LED to 'off' state when recording starts
            self.smgen.state_machine.set_state('off')
            self._execute_state(self.smgen.get_state())

            # Get voice reactive callback
            audio_callback = None
            if self.voice_reactive:
                self.voice_reactive.start(standalone=False)
                audio_callback = self.voice_reactive.process_audio_data

            # Start recording with mic controller or fallback to voice
            if self.mic_controller:
                self.mic_controller.start_recording(on_audio_data=audio_callback)
            else:
                self.voice.start_recording(audio_callback=audio_callback)

            if self.verbose:
                print("Recording... Speak now!")

    def _transcribe_audio(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes using Replicate Whisper."""
        if not audio_bytes:
            return ""

        try:
            import wave
            import tempfile
            import os
            import replicate

            # Get sample rate from mic controller
            sample_rate = 44100
            if self.mic_controller:
                sample_rate = self.mic_controller.get_sample_rate()

            # Write to temp WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            with wave.open(tmp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)

            try:
                # Set Replicate API token
                replicate_token = self.config['replicate'].get('api_token')
                if replicate_token:
                    os.environ['REPLICATE_API_TOKEN'] = replicate_token

                if self.verbose:
                    print(f"Transcribing {len(audio_bytes)} bytes with Replicate Whisper...")

                with open(tmp_path, 'rb') as audio_file:
                    output = replicate.run(
                        "openai/whisper:4d50797290df275329f202e48c76360b3f22b08d28c196cbc54600319435f8d2",
                        input={
                            "audio": audio_file,
                            "model": "large-v3",
                            "translate": False,
                            "temperature": 0,
                            "transcription": "plain text",
                        }
                    )

                if isinstance(output, dict):
                    return output.get('transcription', '').strip()
                elif isinstance(output, str):
                    return output.strip()
                else:
                    return str(output).strip()

            finally:
                os.unlink(tmp_path)

        except Exception as e:
            print(f"Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _log_command_to_supabase(self, command: str, result):
        """Log a processed command to Supabase."""
        try:
            # Get full state machine snapshot
            details = self.smgen.get_details()

            # Reset feedback state for new command
            self.feedback_pending = False
            self.last_session_id = None

            session_id = supabase_client.log_command_session(
                user_id=self.device_id,
                command=command,
                response_message=result.message,
                success=result.success,
                current_state=result.state.get('name') if result.state else None,
                current_state_data=result.state,
                all_states=details.get('states', []),
                all_rules=details.get('rules', []),
                tool_calls=result.tool_calls,
                agent_steps=result.agent_steps,
                timing_ms=result.timing.get('total_ms') if result.timing else None,
                run_id=result.run_id,
                source=self.device_id
            )

            if session_id:
                self.last_session_id = session_id
                self.feedback_pending = True
                print(f"Logged to Supabase: {session_id} - awaiting feedback")
        except Exception as e:
            print(f"Failed to log to Supabase: {e}")

    def _handle_feedback(self, worked: bool):
        """Handle feedback button press (Yes/No)."""
        if not self.last_session_id or not self.feedback_pending:
            print("No pending feedback to submit")
            return

        print(f"Feedback: {'YES' if worked else 'NO'}")

        # Submit to Supabase
        success = supabase_client.submit_quick_feedback(self.last_session_id, worked)

        if success:
            self.feedback_pending = False

            # Visual feedback on reactive LED
            if self.reactive_led:
                if worked:
                    self.reactive_led.flash_success()
                else:
                    self.reactive_led.flash_error()

            print(f"Feedback submitted: {'worked' if worked else 'did not work'}")
        else:
            print("Failed to submit feedback")

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
        print(f"Device ID: {self.device_id}")
        print(f"Mode: {self.config['brain']['mode']}")
        print(f"Model: {self.config['brain']['model']}")
        print(f"LED type: {self.config['hardware']['led_type']}")
        print(f"Vision: {'enabled' if self.vision_runtime and self.camera else 'disabled'}")
        print(f"API Reactive: {'enabled' if self.api_runtime else 'disabled'}")
        print("=" * 60)

        # Show initial state
        self._execute_state(self.smgen.get_state())

        print("\nReady! Press buttons or speak commands.")
        print("Press Ctrl+C to exit.\n")

        try:
            while self.running:
                # Tick API runtime if enabled
                self._tick_api_runtime()

                # Tick mic controller (manages stream lifecycle + processes frames)
                if self.mic_controller:
                    self.mic_controller.tick()

                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def _tick_api_runtime(self):
        """Tick the API runtime to check for due fetches."""
        if not self.api_runtime:
            return

        now_ms = int(time.time() * 1000)
        if (now_ms - self._last_api_tick_ms) < self._api_tick_interval_ms:
            return

        self._last_api_tick_ms = now_ms

        try:
            result = self.api_runtime.tick()
            if result.get('processed'):
                if self.verbose:
                    print(f"[API] Fetched: {result.get('fetched', [])}")
                # If state changed, update LED
                if result.get('emitted_events'):
                    self._execute_state(self.smgen.get_state())
        except Exception as e:
            if self.verbose:
                print(f"[API] Tick error: {e}")

    def cleanup(self):
        """Clean up resources."""
        print("Cleaning up...")

        # Stop camera capture
        self._camera_running = False
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=2)
        if self.camera:
            if self._use_picamera:
                self.camera.stop()
            else:
                self.camera.release()
            print("Camera released")

        # Stop vision session
        if self._vision_session_id and self.vision_runtime:
            self.vision_runtime.stop_session(self._vision_session_id)

        # Stop mic controller
        if self.mic_controller:
            self.mic_controller.stop()

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
