"""
Voice input handling for AdaptLight.

Handles speech-to-text (STT) using OpenAI Whisper API or other STT services.
Captures audio from microphone and converts to text commands.

Key features:
- Continuous listening or push-to-talk
- Voice activity detection (VAD)
- Background noise filtering
- Audio preprocessing
"""

import queue
import threading
import wave
import tempfile
from pathlib import Path

try:
    import pyaudio
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: pyaudio/numpy not available. Voice input disabled.")

try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False
    print("Warning: replicate not available. Install with: pip install replicate")


class VoiceInput:
    """Handles voice input and speech-to-text conversion."""

    def __init__(self, stt_provider='whisper', openai_client=None, replicate_token=None):
        """
        Initialize voice input system.

        Args:
            stt_provider: 'whisper' (OpenAI), 'replicate', 'google', or 'vosk' (offline)
            openai_client: OpenAI client instance for transcription
            replicate_token: Replicate API token for transcription
        """
        self.stt_provider = stt_provider
        self.openai_client = openai_client
        self.replicate_token = replicate_token
        self.is_listening = False
        self.audio_queue = queue.Queue()
        self.listener_thread = None
        self.on_command_callback = None

        # Audio settings
        self.chunk = 1024
        self.format = pyaudio.paInt16 if AUDIO_AVAILABLE else None
        self.channels = 1
        self.rate = 44100  # Will be updated to device native rate
        self.selected_device = None

        if AUDIO_AVAILABLE:
            self._select_audio_device()

        print(f"VoiceInput initialized with {stt_provider} STT")

    def _select_audio_device(self):
        """Auto-select USB audio device."""
        if not AUDIO_AVAILABLE:
            return

        try:
            p = pyaudio.PyAudio()

            # Look for USB device
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    device_name = info['name'].lower()
                    if 'usb' in device_name or 'pnp' in device_name:
                        self.selected_device = i
                        self.rate = int(info['defaultSampleRate'])
                        print(f"  Selected audio device: [{i}] {info['name']}")
                        print(f"  Sample rate: {self.rate} Hz")
                        break

            p.terminate()
        except Exception as e:
            print(f"  Warning: Could not auto-select audio device: {e}")

    def start_listening(self):
        """Start continuous listening for voice commands."""
        if self.is_listening:
            print("Already listening")
            return

        self.is_listening = True
        self.listener_thread = threading.Thread(target=self._listen_loop)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        print("Started listening for voice commands")

    def stop_listening(self):
        """Stop listening for voice commands."""
        self.is_listening = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)
        print("Stopped listening for voice commands")

    def start_recording(self):
        """Start push-to-talk recording."""
        if not AUDIO_AVAILABLE:
            print("Audio not available")
            return False

        self.audio_queue = queue.Queue()
        self.is_recording = True

        # Start recording thread
        self.recording_thread = threading.Thread(target=self._record_audio)
        self.recording_thread.daemon = True
        self.recording_thread.start()

        return True

    def stop_recording(self):
        """Stop recording and transcribe audio."""
        if not self.is_recording:
            return None

        self.is_recording = False

        # Wait for recording thread to finish
        if hasattr(self, 'recording_thread'):
            self.recording_thread.join(timeout=1.0)

        # Get all recorded frames
        frames = []
        while not self.audio_queue.empty():
            frames.append(self.audio_queue.get())

        if not frames:
            print("No audio recorded")
            return None

        # Combine all frames
        audio_data = b''.join(frames)

        # Transcribe
        return self._transcribe_audio(audio_data)

    def _record_audio(self):
        """Record audio from microphone (runs in thread)."""
        if not AUDIO_AVAILABLE:
            return

        try:
            p = pyaudio.PyAudio()

            # Open audio stream
            stream = p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.selected_device,
                frames_per_buffer=self.chunk
            )

            print("  Recording...")

            # Record until stopped
            while self.is_recording:
                data = stream.read(self.chunk, exception_on_overflow=False)
                self.audio_queue.put(data)

            # Cleanup
            stream.stop_stream()
            stream.close()
            p.terminate()

            print("  Recording complete")

        except Exception as e:
            print(f"Recording error: {e}")
            self.is_recording = False

    def _listen_loop(self):
        """
        Main listening loop.

        Continuously captures audio, detects voice activity,
        and sends audio chunks for transcription.
        """
        # TODO: Implement audio capture using pyaudio or sounddevice
        # TODO: Implement VAD (Voice Activity Detection)
        # TODO: Send audio chunks to STT service
        print("TODO: Implement audio listening loop")

    def _transcribe_audio(self, audio_data):
        """
        Transcribe audio to text using selected STT provider.

        Args:
            audio_data: Raw audio data

        Returns:
            Transcribed text string
        """
        if self.stt_provider == 'whisper':
            return self._transcribe_whisper(audio_data)
        elif self.stt_provider == 'replicate':
            return self._transcribe_replicate(audio_data)
        elif self.stt_provider == 'google':
            return self._transcribe_google(audio_data)
        elif self.stt_provider == 'vosk':
            return self._transcribe_vosk(audio_data)
        else:
            raise ValueError(f"Unknown STT provider: {self.stt_provider}")

    def _transcribe_whisper(self, audio_data):
        """Transcribe using OpenAI transcription API."""
        if not self.openai_client:
            print("OpenAI client not available")
            return ""

        try:
            # Save audio data to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name

                # Write WAV file
                wf = wave.open(tmp_path, 'wb')
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(self.rate)
                wf.writeframes(audio_data)
                wf.close()

                # Transcribe using OpenAI
                with open(tmp_path, 'rb') as audio_file:
                    transcription = self.openai_client.audio.transcriptions.create(
                        model="gpt-4o-transcribe",
                        file=audio_file
                    )

                # Cleanup temp file
                Path(tmp_path).unlink()

                return transcription.text

        except Exception as e:
            print(f"Transcription error: {e}")
            return ""

    def _transcribe_replicate(self, audio_data):
        """Transcribe using Replicate's Whisper API."""
        if not REPLICATE_AVAILABLE:
            print("Replicate not available. Install with: pip install replicate")
            return ""

        if not self.replicate_token:
            print("Replicate API token not available")
            return ""

        try:
            # Save audio data to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name

                # Write WAV file
                wf = wave.open(tmp_path, 'wb')
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(self.rate)
                wf.writeframes(audio_data)
                wf.close()

                # Set Replicate API token
                import os
                os.environ['REPLICATE_API_TOKEN'] = self.replicate_token

                # Transcribe using Replicate's Whisper Large v3
                print("  Transcribing with Replicate Whisper Large v3...")
                with open(tmp_path, 'rb') as audio_file:
                    output = replicate.run(
                        "openai/whisper:4d50797290df275329f202e48c76360b3f22b08d28c196cbc54600319435f8d2",
                        input={
                            "audio": audio_file,
                            "model": "large-v3",
                            "translate": False,
                            "temperature": 0,
                            "transcription": "plain text",
                            "suppress_tokens": "-1",
                            "logprob_threshold": -1,
                            "no_speech_threshold": 0.6,
                            "condition_on_previous_text": True,
                            "compression_ratio_threshold": 2.4,
                            "temperature_increment_on_fallback": 0.2
                        }
                    )

                # Cleanup temp file
                Path(tmp_path).unlink()

                # Extract transcription text from output
                if isinstance(output, dict):
                    transcription_text = output.get('transcription', '')
                elif isinstance(output, str):
                    transcription_text = output
                else:
                    transcription_text = str(output)

                return transcription_text.strip()

        except Exception as e:
            print(f"Replicate transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _transcribe_google(self, audio_data):
        """Transcribe using Google Speech-to-Text."""
        # TODO: Implement Google STT
        print("TODO: Implement Google transcription")
        return ""

    def _transcribe_vosk(self, audio_data):
        """Transcribe using Vosk (offline)."""
        # TODO: Implement Vosk transcription
        print("TODO: Implement Vosk transcription")
        return ""

    def set_command_callback(self, callback):
        """
        Set callback function to be called when a command is recognized.

        Args:
            callback: Function that takes (text) as argument
        """
        self.on_command_callback = callback

    def cleanup(self):
        """Cleanup resources."""
        self.stop_listening()
        print("VoiceInput cleanup complete")
