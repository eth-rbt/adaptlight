"""
Microphone Quality Test Utility

Tests microphone quality by:
1. Listing all input devices
2. Recording 10 seconds of audio from selected device
3. Playing back the recording through selected output device

Usage:
    python test_mic_quality.py
"""

import pyaudio
import wave
import tempfile
from pathlib import Path


class MicQualityTester:
    """Test microphone quality by recording and playing back audio."""

    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.record_seconds = 5
        self.temp_file = None

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

    def list_output_devices(self):
        """List all available output devices."""
        print("\n=== Available Output Devices ===")
        output_devices = []

        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                output_devices.append((i, info))
                print(f"[{i}] {info['name']}")
                print(f"    Channels: {info['maxOutputChannels']}")
                print(f"    Sample Rate: {int(info['defaultSampleRate'])} Hz")
                print()

        return output_devices

    def select_device(self, devices, device_type="input"):
        """
        Prompt user to select a device.

        Args:
            devices: List of (index, info) tuples
            device_type: "input" or "output"

        Returns:
            Selected device index
        """
        while True:
            try:
                choice = input(f"\nSelect {device_type} device index: ")
                device_index = int(choice)

                # Verify device exists in list
                if any(idx == device_index for idx, _ in devices):
                    return device_index
                else:
                    print(f"Invalid device index. Please choose from the list above.")
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nCancelled.")
                return None

    def record_audio(self, device_index, output_device_index):
        """
        Record audio from selected device.

        Args:
            device_index: PyAudio device index for input
            output_device_index: PyAudio device index for output (to match sample rate)

        Returns:
            Path to temporary WAV file
        """
        print(f"\n=== Recording for {self.record_seconds} seconds ===")
        print("Speak now...")

        # Use output device's sample rate to avoid resampling
        output_device_info = self.p.get_device_info_by_index(output_device_index)
        self.rate = int(output_device_info['defaultSampleRate'])
        print(f"  Using sample rate: {self.rate} Hz")

        try:
            # Open stream
            stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk
            )

            frames = []

            # Record for specified duration
            for i in range(0, int(self.rate / self.chunk * self.record_seconds)):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

                # Show progress
                seconds_recorded = (i + 1) * self.chunk / self.rate
                if int(seconds_recorded) != int((i * self.chunk) / self.rate):
                    print(f"  {int(seconds_recorded)}/{self.record_seconds} seconds...")

            # Stop and close stream
            stream.stop_stream()
            stream.close()

            print("Recording complete!")

            # Save to temporary WAV file
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            self.temp_file = temp_file.name
            temp_file.close()

            wf = wave.open(self.temp_file, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))
            wf.close()

            return self.temp_file

        except Exception as e:
            print(f"Error during recording: {e}")
            return None

    def play_audio(self, device_index, audio_file):
        """
        Play audio through selected output device.

        Args:
            device_index: PyAudio device index
            audio_file: Path to WAV file to play
        """
        print(f"\n=== Playing back recording ===")

        try:
            # Open WAV file
            wf = wave.open(audio_file, 'rb')

            # Get audio parameters
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()

            # Open stream with the same rate as the recording
            stream = self.p.open(
                format=self.p.get_format_from_width(sampwidth),
                channels=channels,
                rate=framerate,
                output=True,
                output_device_index=device_index
            )

            # Read and play audio
            data = wf.readframes(self.chunk)

            while data:
                stream.write(data)
                data = wf.readframes(self.chunk)

            # Cleanup
            stream.stop_stream()
            stream.close()
            wf.close()

            print("Playback complete!")

        except Exception as e:
            print(f"Error during playback: {e}")

    def cleanup(self):
        """Clean up resources."""
        # Delete temporary file
        if self.temp_file and Path(self.temp_file).exists():
            Path(self.temp_file).unlink()
            print(f"\nCleaned up temporary file: {self.temp_file}")

        # Terminate PyAudio
        self.p.terminate()

    def run_test(self):
        """Run the complete mic quality test."""
        try:
            print("=" * 50)
            print("  Microphone Quality Test")
            print("=" * 50)

            # Step 1: List and select output device first (to match sample rate)
            output_devices = self.list_output_devices()
            if not output_devices:
                print("No output devices found!")
                return

            output_device = self.select_device(output_devices, "output")
            if output_device is None:
                return

            # Step 2: List and select input device
            input_devices = self.list_input_devices()
            if not input_devices:
                print("No input devices found!")
                return

            input_device = self.select_device(input_devices, "input")
            if input_device is None:
                return

            # Step 3: Record audio (using output device's sample rate)
            audio_file = self.record_audio(input_device, output_device)
            if not audio_file:
                print("Recording failed!")
                return

            # Step 4: Play back audio
            self.play_audio(output_device, audio_file)

            print("\n" + "=" * 50)
            print("  Test Complete!")
            print("=" * 50)

        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            self.cleanup()


def main():
    """Main entry point."""
    tester = MicQualityTester()
    tester.run_test()


if __name__ == '__main__':
    main()