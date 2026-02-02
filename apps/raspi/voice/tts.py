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

    def __init__(self, provider="openai", voice=None, api_key=None):
        """
        Initialize TTS.

        Args:
            provider: "openai" or "edge" (edge_tts)
            voice: Voice name (provider-specific)
            api_key: OpenAI API key (for openai provider)
        """
        self.provider = provider
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

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

            # Create temp file for audio
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name

            # Generate speech
            response = client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=text
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
            # Try different players (with max volume boost, target USB audio)
            players = [
                ["mpv", "--no-video", "--volume=400", "--audio-device=alsa/plughw:2,0", file_path],
                ["ffplay", "-nodisp", "-autoexit", "-volume", "400", file_path],
                ["aplay", "-D", "plughw:2,0", file_path],
                ["paplay", file_path],
            ]

            for player_cmd in players:
                try:
                    if block:
                        subprocess.run(player_cmd, check=True,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
                    else:
                        subprocess.Popen(player_cmd,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                    return
                except FileNotFoundError:
                    continue

            print("No audio player found. Install mpv, ffplay, or aplay.")

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
