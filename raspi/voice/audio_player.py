"""
Audio playback for AdaptLight.

Handles playing WAV files through the speaker for audio feedback.
Uses pygame for reliable cross-platform audio playback.
"""

import os
from pathlib import Path

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not available. Install with: pip install pygame")


class AudioPlayer:
    """Handles audio playback for feedback sounds."""

    def __init__(self):
        """Initialize audio player."""
        self.initialized = False

        if PYGAME_AVAILABLE:
            try:
                # Initialize pygame mixer for audio playback
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                self.initialized = True
                print("AudioPlayer initialized successfully")
            except Exception as e:
                print(f"Warning: Could not initialize pygame mixer: {e}")
                self.initialized = False
        else:
            print("AudioPlayer: pygame not available, audio playback disabled")

    def play_sound(self, sound_path: str, blocking=False):
        """
        Play a WAV audio file.

        Args:
            sound_path: Path to the WAV file to play
            blocking: If True, wait for sound to finish before returning

        Returns:
            True if playback started successfully, False otherwise
        """
        if not self.initialized:
            print(f"AudioPlayer not initialized, skipping sound: {sound_path}")
            return False

        # Check if file exists
        if not os.path.exists(sound_path):
            print(f"Warning: Sound file not found: {sound_path}")
            return False

        try:
            # Load and play the sound
            sound = pygame.mixer.Sound(sound_path)
            channel = sound.play()

            if blocking and channel:
                # Wait for sound to finish
                while channel.get_busy():
                    pygame.time.wait(100)

            return True

        except Exception as e:
            print(f"Error playing sound {sound_path}: {e}")
            return False

    def play_error_sound(self, blocking=False):
        """
        Play the error sound.

        Args:
            blocking: If True, wait for sound to finish before returning

        Returns:
            True if playback started successfully, False otherwise
        """
        # Look for error sound in data/sounds/ directory
        sound_path = Path(__file__).parent.parent / 'data' / 'sounds' / 'error.wav'

        if not sound_path.exists():
            print(f"Warning: Error sound not found at {sound_path}")
            print("Please add an error.wav file to data/sounds/ directory")
            return False

        print(f"  🔊 Playing error sound")
        return self.play_sound(str(sound_path), blocking=blocking)

    def play_success_sound(self, blocking=False):
        """
        Play the success sound.

        Args:
            blocking: If True, wait for sound to finish before returning

        Returns:
            True if playback started successfully, False otherwise
        """
        # Look for success sound in data/sounds/ directory
        sound_path = Path(__file__).parent.parent / 'data' / 'sounds' / 'success.wav'

        if not sound_path.exists():
            print(f"Info: Success sound not found at {sound_path}")
            return False

        print(f"  🔊 Playing success sound")
        return self.play_sound(str(sound_path), blocking=blocking)

    def cleanup(self):
        """Cleanup audio player resources."""
        if self.initialized:
            try:
                pygame.mixer.quit()
                print("AudioPlayer cleanup complete")
            except Exception as e:
                print(f"Error during AudioPlayer cleanup: {e}")
