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

    def __init__(self, volume=1.0):
        """
        Initialize audio player.

        Args:
            volume: Playback volume (0.0 to 1.0). Values > 1.0 will boost volume.
                   Default: 1.0 (100%)
        """
        self.initialized = False
        self.volume = volume

        if PYGAME_AVAILABLE:
            try:
                # Initialize pygame mixer for audio playback
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                self.initialized = True
                print(f"AudioPlayer initialized successfully (volume: {volume})")
            except Exception as e:
                print(f"Warning: Could not initialize pygame mixer: {e}")
                self.initialized = False
        else:
            print("AudioPlayer: pygame not available, audio playback disabled")

    def play_sound(self, sound_path: str, blocking=False, volume=None):
        """
        Play a WAV audio file.

        Args:
            sound_path: Path to the WAV file to play
            blocking: If True, wait for sound to finish before returning
            volume: Override volume for this sound (0.0 to 1.0+). If None, uses default.

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
            # Load the sound
            sound = pygame.mixer.Sound(sound_path)

            # Set volume (use override if provided, otherwise use instance volume)
            sound.set_volume(volume if volume is not None else self.volume)

            # Play the sound
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
        # Look for error sound in wav/ directory
        sound_path = Path(__file__).parent.parent / 'wav' / 'error.wav'

        if not sound_path.exists():
            print(f"Warning: Error sound not found at {sound_path}")
            print("Please add an error.wav file to wav/ directory")
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
        # Look for success sound in wav/ directory
        sound_path = Path(__file__).parent.parent / 'wav' / 'success.wav'

        if not sound_path.exists():
            print(f"Info: Success sound not found at {sound_path}")
            return False

        print(f"  🔊 Playing success sound")
        return self.play_sound(str(sound_path), blocking=blocking)

    def set_volume(self, volume):
        """
        Set the default playback volume.

        Args:
            volume: Volume level (0.0 to 1.0+). Values > 1.0 will boost volume.
        """
        self.volume = volume
        print(f"Audio volume set to {volume}")

    def cleanup(self):
        """Cleanup audio player resources."""
        if self.initialized:
            try:
                pygame.mixer.quit()
                print("AudioPlayer cleanup complete")
            except Exception as e:
                print(f"Error during AudioPlayer cleanup: {e}")
