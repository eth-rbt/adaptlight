#!/usr/bin/env python3
"""
Test script for voice-reactive green light.

This script:
1. Captures audio from microphone in real-time
2. Calculates loudness (RMS amplitude) of incoming audio
3. Maps loudness to green LED brightness
4. Updates LEDs continuously to react to voice volume

Press Ctrl+C to exit.
"""

import sys
import time
import numpy as np

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Error: pyaudio not available. Install with: pip install pyaudio")
    sys.exit(1)

# Import LED controller
from hardware.led_controller import LEDController


class VoiceReactiveLightTest:
    """Test class for voice-reactive green light."""

    def __init__(self):
        """Initialize LED controller and audio settings."""
        self.led_controller = LEDController()

        # Audio settings
        self.chunk = 1024  # Frames per buffer
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.selected_device = None

        # Amplitude settings
        self.min_amplitude = 100  # Minimum RMS to register (noise floor)
        self.max_amplitude = 5000  # Maximum RMS for full brightness
        self.smoothing_factor = 0.3  # Smoothing for less jittery response
        self.current_brightness = 0

        self._select_audio_device()

    def _select_audio_device(self):
        """Auto-select USB audio device."""
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
                        print(f"Selected audio device: [{i}] {info['name']}")
                        print(f"Sample rate: {self.rate} Hz")
                        break

            if self.selected_device is None:
                print("No USB audio device found, using default input")

            p.terminate()
        except Exception as e:
            print(f"Warning: Could not auto-select audio device: {e}")

    def calculate_rms(self, audio_data):
        """
        Calculate RMS (Root Mean Square) amplitude of audio data.

        Args:
            audio_data: Raw audio bytes

        Returns:
            RMS amplitude value
        """
        # Convert bytes to numpy array of int16
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate RMS
        rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))

        return rms

    def map_amplitude_to_brightness(self, rms):
        """
        Map RMS amplitude to LED brightness (0-255).

        Args:
            rms: RMS amplitude value

        Returns:
            Brightness value (0-255)
        """
        # Clamp RMS to range
        clamped_rms = max(self.min_amplitude, min(rms, self.max_amplitude))

        # Map to 0-255 range
        normalized = (clamped_rms - self.min_amplitude) / (self.max_amplitude - self.min_amplitude)
        brightness = int(normalized * 255)

        # Apply smoothing to reduce jitter
        smoothed_brightness = int(
            self.smoothing_factor * brightness +
            (1 - self.smoothing_factor) * self.current_brightness
        )

        self.current_brightness = smoothed_brightness

        return smoothed_brightness

    def run(self):
        """Run the voice-reactive light test."""
        if not AUDIO_AVAILABLE:
            print("Audio not available")
            return

        print("\n" + "="*60)
        print("VOICE-REACTIVE GREEN LIGHT TEST")
        print("="*60)
        print("\nSpeak into the microphone to see the green light react!")
        print("Loudness will control brightness (0-255)")
        print("\nPress Ctrl+C to exit\n")
        print("="*60 + "\n")

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

            print("Listening... (speak now!)\n")

            # Main loop - continuously read audio and update LEDs
            frame_count = 0
            while True:
                # Read audio chunk
                audio_data = stream.read(self.chunk, exception_on_overflow=False)

                # Calculate RMS amplitude
                rms = self.calculate_rms(audio_data)

                # Map to brightness
                brightness = self.map_amplitude_to_brightness(rms)

                # Update LEDs with green color scaled by brightness
                # Green at full brightness is (0, 255, 0)
                # Scale it down based on calculated brightness
                green_value = brightness
                self.led_controller.set_color(0, green_value, 0)

                # Print status every 10 frames (~0.25 seconds)
                frame_count += 1
                if frame_count % 10 == 0:
                    # Print bar graph visualization
                    bar_length = int(brightness / 255 * 40)
                    bar = "█" * bar_length + "░" * (40 - bar_length)
                    print(f"\rRMS: {rms:6.0f} | Brightness: {brightness:3d}/255 | {bar}", end="")
                    sys.stdout.flush()

        except KeyboardInterrupt:
            print("\n\nStopping test...")

        except Exception as e:
            print(f"\nError: {e}")

        finally:
            # Cleanup
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            if 'p' in locals():
                p.terminate()

            # Turn off LEDs
            self.led_controller.set_color(0, 0, 0)
            print("LEDs turned off")
            print("Test complete!")


def main():
    """Main entry point."""
    test = VoiceReactiveLightTest()
    test.run()


if __name__ == "__main__":
    main()
