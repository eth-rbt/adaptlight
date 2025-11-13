"""
Volume-reactive LED feedback during voice recording.

Makes LED brightness correspond to microphone input volume.
Replaces the fixed sine-wave breathing animation with real-time audio reactivity.
"""

import threading
import time
import numpy as np

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: pyaudio not available. Volume reactive LED disabled.")


class VolumeReactiveLED:
    """Controls LED brightness based on real-time audio volume."""

    def __init__(self, led_controller, audio_settings=None):
        """
        Initialize volume-reactive LED controller.

        Args:
            led_controller: LEDController instance
            audio_settings: Dict with audio config (chunk, rate, channels, device_index)
        """
        self.led_controller = led_controller
        self.is_active = False
        self.animation_thread = None

        # Audio settings
        self.audio_settings = audio_settings or {
            'chunk': 1024,
            'rate': 44100,
            'channels': 1,
            'format': pyaudio.paInt16 if AUDIO_AVAILABLE else None,
            'device_index': None
        }

        # LED color for recording (green by default)
        self.base_color = (0, 255, 0)

        # Volume sensitivity (adjust these for tuning)
        self.min_brightness = 0.1  # Minimum LED brightness (silent)
        self.max_brightness = 1.0  # Maximum LED brightness (loud)
        self.volume_threshold = 500  # Minimum volume to trigger (noise floor)
        self.volume_scale = 5000  # Scale factor for volume to brightness

    def start(self, color=(0, 255, 0)):
        """
        Start volume-reactive LED animation.

        Args:
            color: Base RGB color for the LED (default green)
        """
        if not AUDIO_AVAILABLE:
            print("Audio not available, cannot start volume-reactive LED")
            return

        self.base_color = color
        self.is_active = True
        self.animation_thread = threading.Thread(target=self._volume_reactive_loop)
        self.animation_thread.daemon = True
        self.animation_thread.start()
        print("  Volume-reactive LED started")

    def stop(self):
        """Stop volume-reactive LED animation."""
        self.is_active = False
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join(timeout=0.5)
        self.led_controller.clear()
        print("  Volume-reactive LED stopped")

    def _volume_reactive_loop(self):
        """Main loop that reads audio and adjusts LED brightness."""
        if not AUDIO_AVAILABLE:
            return

        p = pyaudio.PyAudio()

        try:
            # Open audio stream
            stream = p.open(
                format=self.audio_settings['format'],
                channels=self.audio_settings['channels'],
                rate=self.audio_settings['rate'],
                input=True,
                input_device_index=self.audio_settings.get('device_index'),
                frames_per_buffer=self.audio_settings['chunk']
            )

            while self.is_active:
                try:
                    # Read audio chunk
                    data = stream.read(self.audio_settings['chunk'], exception_on_overflow=False)

                    # Convert bytes to numpy array
                    audio_data = np.frombuffer(data, dtype=np.int16)

                    # Calculate RMS (Root Mean Square) volume
                    rms = np.sqrt(np.mean(audio_data**2))

                    # Convert volume to brightness (0.0 to 1.0)
                    brightness = self._volume_to_brightness(rms)

                    # Apply brightness to base color
                    r = int(self.base_color[0] * brightness)
                    g = int(self.base_color[1] * brightness)
                    b = int(self.base_color[2] * brightness)

                    # Update LEDs
                    if self.led_controller.pixels:
                        for i in range(self.led_controller.led_count):
                            self.led_controller.set_pixel(i, r, g, b)
                        self.led_controller.show()
                    else:
                        # Simulation mode
                        if brightness > self.min_brightness + 0.05:  # Only print when active
                            print(f"Volume LED: RMS={rms:.0f} → Brightness={brightness:.2f} RGB({r}, {g}, {b})")

                    # Small delay to prevent overwhelming the LED updates
                    time.sleep(0.01)

                except Exception as e:
                    print(f"Error reading audio: {e}")
                    time.sleep(0.1)

            # Cleanup
            stream.stop_stream()
            stream.close()

        except Exception as e:
            print(f"Error initializing audio stream: {e}")
        finally:
            p.terminate()

    def _volume_to_brightness(self, rms_volume):
        """
        Convert RMS volume to LED brightness value.

        Args:
            rms_volume: RMS volume level from audio

        Returns:
            Brightness value between min_brightness and max_brightness
        """
        # Apply threshold (ignore noise floor)
        if rms_volume < self.volume_threshold:
            return self.min_brightness

        # Scale volume to brightness range
        # Subtract threshold and scale
        adjusted_volume = rms_volume - self.volume_threshold
        brightness = self.min_brightness + (adjusted_volume / self.volume_scale) * (self.max_brightness - self.min_brightness)

        # Clamp to valid range
        brightness = max(self.min_brightness, min(self.max_brightness, brightness))

        return brightness

    def set_sensitivity(self, min_brightness=0.1, max_brightness=1.0, threshold=500, scale=5000):
        """
        Adjust volume sensitivity parameters.

        Args:
            min_brightness: Minimum LED brightness (0.0 to 1.0)
            max_brightness: Maximum LED brightness (0.0 to 1.0)
            threshold: Minimum volume to trigger (noise floor)
            scale: Scale factor for volume to brightness conversion
        """
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.volume_threshold = threshold
        self.volume_scale = scale
        print(f"  Sensitivity updated: min={min_brightness}, max={max_brightness}, threshold={threshold}, scale={scale}")
