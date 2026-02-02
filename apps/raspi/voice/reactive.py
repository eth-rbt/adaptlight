#!/usr/bin/env python3
"""
Voice-reactive light module for AdaptLight.

Uses real-time audio input to create reactive lighting effects
with smooth exponential smoothing (alpha window).
"""

import threading
import time
import numpy as np
import os
from contextlib import contextmanager

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False


@contextmanager
def suppress_alsa_errors():
    """Temporarily redirect stderr to suppress ALSA warnings."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)


class VoiceReactiveLight:
    """Real-time voice-reactive lighting with smooth exponential smoothing."""

    def __init__(self, led_controller, color=(255, 255, 255), smoothing_alpha=0.25, debug=False):
        """
        Initialize voice-reactive light.

        Args:
            led_controller: LEDController instance to control lights
            color: RGB tuple for the reactive color (default: green)
            smoothing_alpha: Alpha value for exponential smoothing (0.0-1.0)
                           Lower = smoother but slower response
                           Higher = faster but more jittery
                           Recommended: 0.1-0.3
            debug: Enable timing debug output
        """
        self.led_controller = led_controller
        self.base_color = color
        self.smoothing_alpha = smoothing_alpha
        self.debug = debug

        # Audio settings
        # Smaller chunk = faster updates (512 @ 44100Hz = ~11.6ms per update = ~86 FPS)
        self.chunk = 512
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.selected_device = None

        # Amplitude settings
        self.min_amplitude = 10000  # Noise floor
        self.max_amplitude = 30000  # Max RMS for full brightness (higher = less saturation)

        # Smoothing state
        self.current_brightness = 0
        self.current_rms = 0

        # Random bubble pattern state
        self.rng = np.random.default_rng()

        # Threading
        self.running = False
        self.thread = None
        self.pyaudio_instance = None
        self.stream = None

        # Timing stats
        self.update_count = 0
        self.start_time = None

        # Select audio device
        self._select_audio_device()

    def _select_audio_device(self):
        """Auto-select USB audio device."""
        if not AUDIO_AVAILABLE:
            return

        try:
            with suppress_alsa_errors():
                p = pyaudio.PyAudio()

            # Look for USB device
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    device_name = info['name'].lower()
                    # Prioritize USB Audio devices
                    if 'usb' in device_name and 'audio' in device_name:
                        self.selected_device = i
                        self.rate = int(info['defaultSampleRate'])
                        break

            # Fallback to any USB device
            if self.selected_device is None:
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    if info['maxInputChannels'] > 0:
                        device_name = info['name'].lower()
                        if 'usb' in device_name or 'pnp' in device_name:
                            self.selected_device = i
                            self.rate = int(info['defaultSampleRate'])
                            break

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

    def smooth_value(self, new_value, current_value):
        """
        Apply exponential smoothing (alpha window).

        Formula: smoothed = alpha * new + (1 - alpha) * current

        Args:
            new_value: New incoming value
            current_value: Current smoothed value

        Returns:
            Smoothed value
        """
        return self.smoothing_alpha * new_value + (1 - self.smoothing_alpha) * current_value

    def map_amplitude_to_brightness(self, rms):
        """
        Map RMS amplitude to LED brightness (0-255) with smoothing.

        Args:
            rms: RMS amplitude value

        Returns:
            Brightness value (0-255)
        """
        # First smooth the RMS value itself
        self.current_rms = self.smooth_value(rms, self.current_rms)

        # Clamp RMS to range
        clamped_rms = max(self.min_amplitude, min(self.current_rms, self.max_amplitude))

        # Map to 0-255 range
        normalized = (clamped_rms - self.min_amplitude) / (self.max_amplitude - self.min_amplitude)
        brightness = int(normalized * 255)

        # Apply additional smoothing to brightness
        smoothed_brightness = int(self.smooth_value(brightness, self.current_brightness))

        self.current_brightness = smoothed_brightness

        return smoothed_brightness

    def update_leds_with_bubbles(self, brightness):
        """
        Update LEDs with a random bubble pattern.
        More brightness = more random pixels lit up.

        Args:
            brightness: Overall brightness level (0-255) based on audio amplitude
        """
        led_count = getattr(self.led_controller, 'led_count', 16)

        # Calculate how many pixels should be lit based on brightness
        # At full brightness (255), all pixels lit; at 0, none lit
        lit_ratio = brightness / 255.0
        num_lit = int(led_count * lit_ratio)

        # Generate random brightness for each pixel
        # Each pixel has a chance to be "on" based on the lit_ratio
        for i in range(led_count):
            if self.rng.random() < lit_ratio:
                # Random brightness between 50% and 100% for lit pixels
                pixel_brightness = 0.5 + 0.5 * self.rng.random()

                r = int(self.base_color[0] * pixel_brightness)
                g = int(self.base_color[1] * pixel_brightness)
                b = int(self.base_color[2] * pixel_brightness)

                self.led_controller.set_pixel(i, r, g, b)
            else:
                # Pixel is off
                self.led_controller.set_pixel(i, 0, 0, 0)

        # Show the updated pixels
        self.led_controller.show()

    def _audio_loop(self):
        """Main audio processing loop (runs in separate thread)."""
        if not AUDIO_AVAILABLE:
            print("PyAudio not available")
            return

        try:
            with suppress_alsa_errors():
                self.pyaudio_instance = pyaudio.PyAudio()

                # Open audio stream
                self.stream = self.pyaudio_instance.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=self.selected_device,
                    frames_per_buffer=self.chunk
                )

            # Main loop - continuously read audio and update LEDs
            while self.running:
                # Read audio chunk
                audio_data = self.stream.read(self.chunk, exception_on_overflow=False)

                # Calculate RMS amplitude
                rms = self.calculate_rms(audio_data)

                # Map to brightness with smoothing
                brightness = self.map_amplitude_to_brightness(rms)

                # Update LEDs with wave pattern
                self.update_leds_with_bubbles(brightness)

        except Exception as e:
            print(f"Error in voice reactive loop: {e}")

        finally:
            # Cleanup
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()

    def process_audio_data(self, audio_data):
        """
        Process audio data and update LEDs (for use with external audio source).

        Args:
            audio_data: Raw audio bytes from external source
        """
        if not self.running:
            return

        # Initialize timing on first call
        if self.start_time is None:
            self.start_time = time.time()
            self.update_count = 0

        # Calculate RMS amplitude
        rms = self.calculate_rms(audio_data)

        # Map to brightness with smoothing
        brightness = self.map_amplitude_to_brightness(rms)

        # Update LEDs with wave pattern
        self.update_leds_with_bubbles(brightness)

        # Debug timing
        self.update_count += 1
        if self.debug and self.update_count % 50 == 0:
            elapsed = time.time() - self.start_time
            avg_interval = elapsed / self.update_count * 1000
            fps = self.update_count / elapsed if elapsed > 0 else 0
            print(f"[VOICE_REACTIVE] Updates: {self.update_count}, Avg interval: {avg_interval:.1f}ms, FPS: {fps:.1f}")

    def start(self, standalone=True):
        """
        Start voice-reactive lighting.

        Args:
            standalone: If True, opens own audio stream in background thread.
                       If False, expects external audio via process_audio_data()
        """
        if self.running:
            print("Voice reactive light already running")
            return False

        print("Starting voice-reactive light...")
        self.running = True

        # Reset timing stats
        self.start_time = None
        self.update_count = 0

        if standalone:
            if not AUDIO_AVAILABLE:
                print("Cannot start standalone - PyAudio not available")
                return False
            self.thread = threading.Thread(target=self._audio_loop, daemon=True)
            self.thread.start()

        return True

    def stop(self):
        """Stop voice-reactive lighting."""
        if not self.running:
            return

        print("Stopping voice-reactive light...")
        self.running = False

        # Wait for thread to finish
        if self.thread:
            self.thread.join(timeout=2.0)

        # Reset brightness
        self.current_brightness = 0
        self.current_rms = 0

    def set_color(self, color):
        """
        Change the base color for reactive lighting.

        Args:
            color: RGB tuple (e.g., (255, 0, 0) for red)
        """
        self.base_color = color

    def set_smoothing(self, alpha):
        """
        Adjust smoothing factor.

        Args:
            alpha: Smoothing alpha (0.0-1.0)
                  Lower = smoother, Higher = more responsive
        """
        self.smoothing_alpha = max(0.0, min(1.0, alpha))

    def set_amplitude_range(self, min_amp=None, max_amp=None):
        """
        Adjust amplitude mapping range.

        Args:
            min_amp: Optional new noise floor
            max_amp: Optional new max RMS for full brightness
        """
        if min_amp is not None:
            self.min_amplitude = max(0, min_amp)
        if max_amp is not None:
            self.max_amplitude = max(self.min_amplitude + 1, max_amp)

    def is_running(self):
        """Check if voice reactive light is currently running."""
        return self.running
