#!/usr/bin/env python3
"""
Text-to-Speech module for AdaptLight.

Supports multiple TTS backends:
- OpenAI TTS (high quality, requires API key)
- Edge TTS (free, Microsoft voices)
"""

import os
import tempfile
import subprocess
from pathlib import Path

# Try to import optional dependencies
OPENAI_AVAILABLE = False
EDGE_TTS_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    pass

try:
    import edge_tts
    import asyncio
    EDGE_TTS_AVAILABLE = True
except ImportError:
    pass


class TextToSpeech:
    """Text-to-speech with multiple backend support."""

    def __init__(self, provider="openai", voice=None, api_key=None, audio_device=None, volume=1.0):
        """
        Initialize TTS.

        Args:
            provider: "openai" or "edge" (edge_tts)
            voice: Voice name (provider-specific)
            api_key: OpenAI API key (for openai provider)
            audio_device: ALSA device (e.g., "hw:2,0" or "plughw:2,0")
            volume: Volume multiplier (1.0 = normal, 2.0 = 2x louder)
        """
        self.provider = provider
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.audio_device = audio_device
        self.volume = volume

        # Default voices
        if voice is None:
            if provider == "openai":
                self.voice = "nova"  # Options: alloy, echo, fable, onyx, nova, shimmer
            else:
                self.voice = "en-US-AriaNeural"  # Edge TTS default
        else:
            self.voice = voice

        # Validate provider
        if provider == "openai" and not OPENAI_AVAILABLE:
            print("Warning: OpenAI not available, falling back to edge_tts")
            self.provider = "edge"

        if self.provider == "edge" and not EDGE_TTS_AVAILABLE:
            print("Warning: edge_tts not available. Install with: pip install edge-tts")
            self.provider = None

        print(f"TTS initialized: provider={self.provider}, voice={self.voice}")

    def speak(self, text: str, block: bool = True) -> bool:
        """
        Convert text to speech and play it.

        Args:
            text: Text to speak
            block: Wait for playback to complete

        Returns:
            True if successful
        """
        if not text or not text.strip():
            return False

        if self.provider == "openai":
            return self._speak_openai(text, block)
        elif self.provider == "edge":
            return self._speak_edge(text, block)
        else:
            print(f"TTS: Would speak: {text}")
            return False

    def _speak_openai(self, text: str, block: bool) -> bool:
        """Use OpenAI TTS API."""
        try:
            client = OpenAI(api_key=self.api_key)

            # Create temp file for audio (PCM format for best quality)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name

            # Generate speech in PCM format (uncompressed)
            response = client.audio.speech.create(
                model="tts-1-hd",
                voice=self.voice,
                input=text,
                response_format="wav"
            )

            # Save to file
            response.stream_to_file(temp_path)

            # Play audio
            self._play_audio(temp_path, block)

            # Cleanup
            os.unlink(temp_path)
            return True

        except Exception as e:
            print(f"OpenAI TTS error: {e}")
            return False

    def _speak_edge(self, text: str, block: bool) -> bool:
        """Use Edge TTS (Microsoft)."""
        try:
            import asyncio

            async def generate_and_play():
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    temp_path = f.name

                # Generate speech
                communicate = edge_tts.Communicate(text, self.voice)
                await communicate.save(temp_path)

                # Play audio
                self._play_audio(temp_path, block=True)

                # Cleanup
                os.unlink(temp_path)

            # Run async function
            asyncio.run(generate_and_play())
            return True

        except Exception as e:
            print(f"Edge TTS error: {e}")
            return False

    def _play_audio(self, file_path: str, block: bool = True):
        """Play audio file using system player."""
        try:
            # Amplify audio if volume > 1.0
            play_path = file_path
            amplified_path = None
            if self.volume != 1.0:
                amplified_path = file_path.replace(".wav", "_amp.wav")
                try:
                    # Use sox to amplify (install: sudo apt install sox)
                    subprocess.run(
                        ["sox", file_path, amplified_path, "vol", str(self.volume)],
                        check=True, capture_output=True
                    )
                    play_path = amplified_path
                except FileNotFoundError:
                    # sox not installed, try ffmpeg
                    try:
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", file_path, "-filter:a", f"volume={self.volume}", amplified_path],
                            check=True, capture_output=True
                        )
                        play_path = amplified_path
                    except FileNotFoundError:
                        print("Warning: sox/ffmpeg not found, playing at normal volume")

            # Try configured device first, then fallback to alternatives
            # Card number can change between reboots
            primary_device = self.audio_device or "plughw:2,0"
            fallback_devices = ["plughw:2,0", "plughw:3,0", "plughw:1,0", "default"]

            # Put primary first, then add others (avoiding duplicates)
            devices_to_try = [primary_device] + [d for d in fallback_devices if d != primary_device]

            for device in devices_to_try:
                player_cmd = ["aplay", "-D", device, play_path]

                if block:
                    result = subprocess.run(player_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        # Success - remember this device for next time
                        if device != self.audio_device:
                            print(f"Audio device changed: {self.audio_device} → {device}")
                            self.audio_device = device
                        # Small delay to ensure audio buffer is fully flushed
                        import time
                        time.sleep(0.1)
                        break
                    else:
                        # Log failure and try next device
                        if result.stderr:
                            print(f"aplay {device} failed: {result.stderr.strip()}")
                else:
                    # For non-blocking, just try the first one
                    subprocess.Popen(player_cmd,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                    break
            else:
                print(f"aplay error: no working audio device found")

            # Cleanup amplified file
            if amplified_path and os.path.exists(amplified_path):
                os.unlink(amplified_path)

        except FileNotFoundError:
            print("aplay not found. Install alsa-utils: sudo apt install alsa-utils")
        except Exception as e:
            print(f"Audio playback error: {e}")

    def list_voices(self):
        """List available voices for current provider."""
        if self.provider == "openai":
            return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        elif self.provider == "edge":
            # Return common English voices
            return [
                "en-US-AriaNeural",
                "en-US-GuyNeural",
                "en-US-JennyNeural",
                "en-GB-SoniaNeural",
                "en-AU-NatashaNeural",
            ]
        return []


# Quick test
if __name__ == "__main__":
    tts = TextToSpeech(provider="openai")
    tts.speak("Hello! I've updated your light to a warm orange color.")
