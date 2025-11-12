#!/usr/bin/env python3
"""
Transcription Test Utility

Interactive tool for testing multiple speech-to-text providers:
1. Select microphone device
2. Press Enter to start recording
3. Press Enter to stop recording
4. View transcriptions from all available providers side-by-side
5. Repeat

Supported providers:
- OpenAI Whisper (gpt-4o-transcribe model)
- OpenAI Whisper (whisper-1 model)
- Google Speech-to-Text
- DeepGram
- Replicate (Whisper Large model)

Usage:
    python test_transcription.py
"""

import sys
import yaml
import pyaudio
import wave
import tempfile
import time
from pathlib import Path
from openai import OpenAI


class TranscriptionTester:
    """Test speech-to-text transcription with multiple providers."""

    def __init__(self, config):
        self.config = config
        self.p = pyaudio.PyAudio()
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = None  # Will be set based on device
        self.is_recording = False
        self.frames = []

        # Initialize providers
        self.providers = {}
        self._init_providers()

    def _init_providers(self):
        """Initialize available STT providers."""
        import traceback

        # OpenAI Whisper
        openai_config = self.config.get('openai', {})
        print(f"\n[DEBUG] OpenAI config: {openai_config.get('api_key', 'NOT_SET')[:20]}...")
        if openai_config.get('api_key'):
            try:
                self.providers['openai'] = OpenAI(api_key=openai_config['api_key'])
                print("✓ OpenAI Whisper initialized")
            except Exception as e:
                print(f"✗ OpenAI initialization failed: {e}")
                traceback.print_exc()

        # Google Speech-to-Text
        google_config = self.config.get('google', {})
        print(f"\n[DEBUG] Google config: {google_config}")
        if google_config.get('credentials_path'):
            try:
                from google.cloud import speech
                import os
                from pathlib import Path

                # Set credentials path (make it absolute if relative)
                creds_path = google_config['credentials_path']
                print(f"[DEBUG] Original creds path: {creds_path}")

                if not Path(creds_path).is_absolute():
                    creds_path = str(Path(__file__).parent.parent / creds_path)
                    print(f"[DEBUG] Converted to absolute: {creds_path}")

                print(f"[DEBUG] Checking if file exists: {Path(creds_path).exists()}")

                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
                print(f"[DEBUG] Set GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")

                self.providers['google'] = speech.SpeechClient()
                print("✓ Google Speech-to-Text initialized")
            except ImportError as e:
                print(f"✗ Google Speech-to-Text not available: {e}")
                print("  Install with: pip install google-cloud-speech")
            except Exception as e:
                print(f"✗ Google initialization failed: {e}")
                traceback.print_exc()

        # DeepGram
        deepgram_config = self.config.get('deepgram', {})
        print(f"\n[DEBUG] DeepGram config: api_key={'SET' if deepgram_config.get('api_key') else 'NOT_SET'}")
        if deepgram_config.get('api_key'):
            try:
                from deepgram import DeepgramClient
                print(f"[DEBUG] DeepGram API key: {deepgram_config['api_key'][:10]}...")

                # Initialize client with API key as parameter
                self.providers['deepgram'] = {
                    'client': DeepgramClient(api_key=deepgram_config['api_key']),
                    'api_key': deepgram_config['api_key']
                }
                print("✓ DeepGram initialized")
            except ImportError as e:
                print(f"✗ DeepGram not available: {e}")
                print("  Install with: pip install deepgram-sdk")
            except Exception as e:
                print(f"✗ DeepGram initialization failed: {e}")
                traceback.print_exc()

        # OpenAI Whisper-1 (alternative model)
        if openai_config.get('api_key'):
            try:
                self.providers['whisper-1'] = OpenAI(api_key=openai_config['api_key'])
                print("✓ OpenAI Whisper-1 initialized")
            except Exception as e:
                print(f"✗ OpenAI Whisper-1 initialization failed: {e}")
                traceback.print_exc()

        # Replicate (Large Whisper model)
        replicate_config = self.config.get('replicate', {})
        api_token = replicate_config.get('api_token') or replicate_config.get('api_key')
        print(f"\n[DEBUG] Replicate config: api_token={'SET' if api_token else 'NOT_SET'}")
        if api_token:
            try:
                import replicate
                import os
                os.environ['REPLICATE_API_TOKEN'] = api_token
                self.providers['replicate'] = api_token
                print("✓ Replicate Whisper Large initialized")
            except ImportError as e:
                print(f"✗ Replicate not available: {e}")
                print("  Install with: pip install replicate")
            except Exception as e:
                print(f"✗ Replicate initialization failed: {e}")
                traceback.print_exc()

        if not self.providers:
            print("\n✗ ERROR: No STT providers configured!")
            print("Add API keys to config.yaml for at least one provider")
            sys.exit(1)

        print(f"\nActive providers: {', '.join(self.providers.keys())}\n")

    def list_input_devices(self):
        """List all available input devices."""
        print("\n=== Available Input Devices ===")
        input_devices = []

        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                input_devices.append((i, info))
                print(f"[{i}] {info['name']}")
                print(f"    Channels: {info['maxInputChannels']}")
                print(f"    Sample Rate: {int(info['defaultSampleRate'])} Hz")
                print()

        return input_devices

    def select_device(self, devices):
        """
        Prompt user to select a device.

        Args:
            devices: List of (index, info) tuples

        Returns:
            Selected device index
        """
        while True:
            try:
                choice = input("Select input device index: ")
                device_index = int(choice)

                # Verify device exists in list
                if any(idx == device_index for idx, _ in devices):
                    return device_index
                else:
                    print("Invalid device index. Please choose from the list above.")
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nCancelled.")
                return None

    def record_audio(self, device_index):
        """
        Record audio from selected device until stopped.

        Args:
            device_index: PyAudio device index

        Returns:
            Path to temporary WAV file
        """
        self.frames = []
        self.is_recording = True

        try:
            # Get device's native sample rate if not already set
            if self.rate is None:
                device_info = self.p.get_device_info_by_index(device_index)
                self.rate = int(device_info['defaultSampleRate'])
                print(f"Using sample rate: {self.rate} Hz")

            # Open audio stream
            stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk
            )

            print("Recording... (press Enter to stop)")

            # Record until Enter is pressed
            while self.is_recording:
                try:
                    data = stream.read(self.chunk, exception_on_overflow=False)
                    self.frames.append(data)
                except KeyboardInterrupt:
                    break

            # Cleanup
            stream.stop_stream()
            stream.close()

            print("Recording stopped.")

            if not self.frames:
                print("No audio recorded!")
                return None

            # Save to temporary WAV file
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_path = temp_file.name
            temp_file.close()

            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
            wf.close()

            # Calculate duration
            duration = len(self.frames) * self.chunk / self.rate
            print(f"Recorded {duration:.1f} seconds of audio")

            return temp_path

        except Exception as e:
            print(f"Recording error: {e}")
            return None

    def transcribe_openai(self, audio_file):
        """Transcribe with OpenAI Whisper."""
        try:
            print(f"[DEBUG OpenAI] Starting transcription...")
            client = self.providers['openai']
            with open(audio_file, 'rb') as f:
                transcription = client.audio.transcriptions.create(
                    model="gpt-4o-transcribe",
                    file=f
                )
            print(f"[DEBUG OpenAI] Success: {transcription.text[:50]}...")
            return transcription.text
        except Exception as e:
            import traceback
            print(f"[DEBUG OpenAI] Error: {e}")
            traceback.print_exc()
            return f"Error: {e}"

    def transcribe_google(self, audio_file):
        """Transcribe with Google Speech-to-Text."""
        try:
            print(f"[DEBUG Google] Starting transcription...")
            print(f"[DEBUG Google] Sample rate: {self.rate} Hz")
            client = self.providers['google']
            from google.cloud import speech

            with open(audio_file, 'rb') as f:
                audio_content = f.read()

            print(f"[DEBUG Google] Audio size: {len(audio_content)} bytes")

            audio = speech.RecognitionAudio(content=audio_content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.rate,
                language_code="en-US",
            )

            print(f"[DEBUG Google] Sending request to Google API...")
            response = client.recognize(config=config, audio=audio)

            print(f"[DEBUG Google] Response: {response}")

            if response.results:
                transcript = response.results[0].alternatives[0].transcript
                print(f"[DEBUG Google] Success: {transcript[:50]}...")
                return transcript
            else:
                print(f"[DEBUG Google] No results in response")
                return "[No speech detected]"

        except Exception as e:
            import traceback
            print(f"[DEBUG Google] Error: {e}")
            traceback.print_exc()
            return f"Error: {e}"

    def transcribe_deepgram(self, audio_file):
        """Transcribe with DeepGram."""
        try:
            print(f"[DEBUG DeepGram] Starting transcription...")
            import requests

            api_key = self.providers['deepgram']['api_key']

            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            print(f"[DEBUG DeepGram] Audio size: {len(audio_data)} bytes")

            # Use REST API directly
            url = "https://api.deepgram.com/v1/listen"
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": "audio/wav"
            }
            params = {
                "model": "nova-2",
                "smart_format": "true"
            }

            print(f"[DEBUG DeepGram] Sending request to DeepGram API...")
            response = requests.post(url, headers=headers, params=params, data=audio_data)

            print(f"[DEBUG DeepGram] Response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"[DEBUG DeepGram] Response: {result}")

                transcript = result['results']['channels'][0]['alternatives'][0]['transcript']
                print(f"[DEBUG DeepGram] Success: {transcript[:50] if transcript else 'empty'}...")
                return transcript if transcript else "[No speech detected]"
            else:
                print(f"[DEBUG DeepGram] Error response: {response.text}")
                return f"Error: HTTP {response.status_code}"

        except Exception as e:
            import traceback
            print(f"[DEBUG DeepGram] Error: {e}")
            traceback.print_exc()
            return f"Error: {e}"

    def transcribe_whisper_1(self, audio_file):
        """Transcribe with OpenAI Whisper-1 model."""
        try:
            print(f"[DEBUG Whisper-1] Starting transcription...")
            client = self.providers['whisper-1']
            with open(audio_file, 'rb') as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            print(f"[DEBUG Whisper-1] Success: {transcription.text[:50]}...")
            return transcription.text
        except Exception as e:
            import traceback
            print(f"[DEBUG Whisper-1] Error: {e}")
            traceback.print_exc()
            return f"Error: {e}"

    def transcribe_replicate(self, audio_file):
        """Transcribe with Replicate's Large Whisper model."""
        try:
            print(f"[DEBUG Replicate] Starting transcription...")
            import replicate

            with open(audio_file, 'rb') as f:
                print(f"[DEBUG Replicate] Sending audio to Replicate API...")
                output = replicate.run(
                    "openai/whisper:8099696689d249cf8b122d833c36ac3f75505c666a395ca40ef26f68e7d3d16e",
                    input={"audio": f}
                )

            print(f"[DEBUG Replicate] Response type: {type(output)}")
            print(f"[DEBUG Replicate] Response: {output}")

            # Extract transcription from segments
            if isinstance(output, dict) and 'transcription' in output:
                transcript = output['transcription']
            elif isinstance(output, dict) and 'segments' in output:
                transcript = ''.join([seg['text'] for seg in output['segments']])
            elif isinstance(output, str):
                transcript = output
            else:
                transcript = str(output)

            print(f"[DEBUG Replicate] Success: {transcript[:50] if transcript else 'empty'}...")
            return transcript if transcript else "[No speech detected]"

        except Exception as e:
            import traceback
            print(f"[DEBUG Replicate] Error: {e}")
            traceback.print_exc()
            return f"Error: {e}"

    def transcribe_all(self, audio_file):
        """
        Transcribe audio with all available providers.

        Args:
            audio_file: Path to WAV file

        Returns:
            Dict of provider -> transcription
        """
        import concurrent.futures

        results = {}

        print("\nTranscribing with all providers...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            start_times = {}

            if 'openai' in self.providers:
                start_times['openai (gpt-4o)'] = time.time()
                futures['openai (gpt-4o)'] = executor.submit(self.transcribe_openai, audio_file)

            if 'whisper-1' in self.providers:
                start_times['openai (whisper-1)'] = time.time()
                futures['openai (whisper-1)'] = executor.submit(self.transcribe_whisper_1, audio_file)

            if 'google' in self.providers:
                start_times['google'] = time.time()
                futures['google'] = executor.submit(self.transcribe_google, audio_file)

            if 'deepgram' in self.providers:
                start_times['deepgram'] = time.time()
                futures['deepgram'] = executor.submit(self.transcribe_deepgram, audio_file)

            if 'replicate' in self.providers:
                start_times['replicate (whisper-large)'] = time.time()
                futures['replicate (whisper-large)'] = executor.submit(self.transcribe_replicate, audio_file)

            # Collect results with timing
            for provider, future in futures.items():
                try:
                    result_text = future.result()
                    elapsed = time.time() - start_times[provider]
                    results[provider] = {
                        'text': result_text,
                        'time': elapsed
                    }
                except Exception as e:
                    elapsed = time.time() - start_times[provider]
                    results[provider] = {
                        'text': f"Error: {e}",
                        'time': elapsed
                    }

        return results

    def cleanup(self):
        """Clean up resources."""
        self.p.terminate()

    def run_loop(self, device_index):
        """
        Run the interactive transcription loop.

        Args:
            device_index: PyAudio device index to use
        """
        print("\n" + "=" * 50)
        print("  Interactive Transcription Test")
        print("=" * 50)
        print("\nPress Enter to start recording")
        print("Press Enter again to stop and transcribe")
        print("Press Ctrl+C to exit")
        print("=" * 50)

        try:
            while True:
                # Wait for Enter to start recording
                input("\n[Press Enter to start recording]")

                # Start recording in background
                import threading

                def stop_on_enter():
                    input()
                    self.is_recording = False

                stop_thread = threading.Thread(target=stop_on_enter)
                stop_thread.daemon = True
                stop_thread.start()

                # Record audio
                audio_file = self.record_audio(device_index)

                if not audio_file:
                    continue

                # Transcribe with all providers
                results = self.transcribe_all(audio_file)

                # Display results
                print("\n" + "=" * 70)
                print("TRANSCRIPTION RESULTS")
                print("=" * 70)

                for provider, result in results.items():
                    print(f"\n[{provider.upper()}] ({result['time']:.2f}s)")
                    print(f"  {result['text']}")

                print("\n" + "=" * 70)

                # Cleanup temp file
                Path(audio_file).unlink()

        except KeyboardInterrupt:
            print("\n\nExiting...")


def load_config():
    """Load configuration from YAML file."""
    config_file = Path(__file__).parent.parent / 'config.yaml'

    if not config_file.exists():
        print(f"ERROR: config.yaml not found at {config_file}")
        print("\nCreate a config.yaml file with OpenAI API key configured")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    return config


def main():
    """Main entry point."""
    print("=" * 70)
    print("  Multi-Provider Transcription Test Tool")
    print("=" * 70)

    # Load config
    print("\nLoading configuration...")
    config = load_config()

    # Initialize tester (will initialize all available providers)
    print("\nInitializing STT providers...")
    tester = TranscriptionTester(config)

    try:
        # Select input device
        input_devices = tester.list_input_devices()
        if not input_devices:
            print("No input devices found!")
            return

        device_index = tester.select_device(input_devices)
        if device_index is None:
            return

        # Run interactive loop
        tester.run_loop(device_index)

    finally:
        tester.cleanup()


if __name__ == '__main__':
    main()
