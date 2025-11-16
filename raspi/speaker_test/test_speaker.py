#!/usr/bin/env python3
"""
I2S Speaker Test Script
Test audio playback through I2S interface on Raspberry Pi 5
"""

import pyaudio
import numpy as np
import time
import sys

# Audio configuration
RATE = 44100  # Sample rate (Hz)
CHUNK = 1024  # Buffer size

def generate_sine_wave(frequency, duration, sample_rate=RATE):
    """Generate a sine wave at given frequency and duration"""
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, False)
    wave = np.sin(2 * np.pi * frequency * t)
    # Apply fade in/out to avoid clicks
    fade_samples = int(sample_rate * 0.05)  # 50ms fade
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    wave[:fade_samples] *= fade_in
    wave[-fade_samples:] *= fade_out
    return (wave * 0.5).astype(np.float32)  # Reduce volume to 50%

def play_audio(audio_data, sample_rate=RATE):
    """Play audio data through I2S speaker"""
    p = pyaudio.PyAudio()

    try:
        stream = p.open(format=pyaudio.paFloat32,
                       channels=1,
                       rate=sample_rate,
                       output=True,
                       frames_per_buffer=CHUNK)

        stream.write(audio_data.tobytes())

        stream.stop_stream()
        stream.close()
    finally:
        p.terminate()

def test_single_tone(frequency=440, duration=1.0):
    """Play a single tone"""
    print(f"Playing {frequency}Hz tone for {duration} seconds...")
    wave = generate_sine_wave(frequency, duration)
    play_audio(wave)
    print("Done!")

def test_scale():
    """Play a musical scale (C major)"""
    notes = {
        'C4': 261.63,
        'D4': 293.66,
        'E4': 329.63,
        'F4': 349.23,
        'G4': 392.00,
        'A4': 440.00,
        'B4': 493.88,
        'C5': 523.25
    }

    print("Playing C major scale...")
    for note_name, freq in notes.items():
        print(f"  {note_name} ({freq:.2f} Hz)")
        wave = generate_sine_wave(freq, 0.5)
        play_audio(wave)
        time.sleep(0.1)
    print("Done!")

def test_sweep(start_freq=200, end_freq=2000, duration=3.0):
    """Play a frequency sweep"""
    print(f"Playing frequency sweep from {start_freq}Hz to {end_freq}Hz...")
    samples = int(RATE * duration)
    t = np.linspace(0, duration, samples, False)
    # Logarithmic sweep
    freq_sweep = np.logspace(np.log10(start_freq), np.log10(end_freq), samples)
    phase = 2 * np.pi * np.cumsum(freq_sweep) / RATE
    wave = (np.sin(phase) * 0.5).astype(np.float32)
    play_audio(wave)
    print("Done!")

def test_stereo_pan():
    """Test stereo panning (if supported)"""
    print("Testing stereo channels...")
    duration = 1.0
    frequency = 440

    p = pyaudio.PyAudio()

    try:
        # Try stereo output
        stream = p.open(format=pyaudio.paFloat32,
                       channels=2,
                       rate=RATE,
                       output=True,
                       frames_per_buffer=CHUNK)

        # Generate mono signal
        mono_wave = generate_sine_wave(frequency, duration)

        # Create stereo: left only
        print("  Left channel only...")
        stereo_left = np.zeros((len(mono_wave), 2), dtype=np.float32)
        stereo_left[:, 0] = mono_wave
        stream.write(stereo_left.tobytes())
        time.sleep(0.2)

        # Right only
        print("  Right channel only...")
        stereo_right = np.zeros((len(mono_wave), 2), dtype=np.float32)
        stereo_right[:, 1] = mono_wave
        stream.write(stereo_right.tobytes())
        time.sleep(0.2)

        # Both channels
        print("  Both channels...")
        stereo_both = np.zeros((len(mono_wave), 2), dtype=np.float32)
        stereo_both[:, 0] = mono_wave
        stereo_both[:, 1] = mono_wave
        stream.write(stereo_both.tobytes())

        stream.stop_stream()
        stream.close()
        print("Done!")
    except Exception as e:
        print(f"  Stereo test failed (device may be mono): {e}")
    finally:
        p.terminate()

def list_audio_devices():
    """List all available audio devices"""
    p = pyaudio.PyAudio()
    print("\nAvailable Audio Devices:")
    print("-" * 60)
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"Device {i}: {info['name']}")
        print(f"  Max Output Channels: {info['maxOutputChannels']}")
        print(f"  Default Sample Rate: {info['defaultSampleRate']}")
        print()
    p.terminate()

def main():
    """Main test menu"""
    print("=" * 60)
    print("I2S Speaker Test - Raspberry Pi 5")
    print("=" * 60)

    if len(sys.argv) > 1:
        test_type = sys.argv[1]
    else:
        print("\nAvailable Tests:")
        print("  1. Single tone (440Hz)")
        print("  2. Musical scale")
        print("  3. Frequency sweep")
        print("  4. Stereo test")
        print("  5. List audio devices")
        print("  q. Quit")
        print()
        test_type = input("Select test (1-5 or q): ").strip()

    try:
        if test_type == '1':
            test_single_tone()
        elif test_type == '2':
            test_scale()
        elif test_type == '3':
            test_sweep()
        elif test_type == '4':
            test_stereo_pan()
        elif test_type == '5':
            list_audio_devices()
        elif test_type.lower() == 'q':
            print("Exiting...")
            return
        else:
            print("Invalid selection!")
            return
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure:")
        print("  - I2S is enabled in /boot/firmware/config.txt")
        print("  - pyaudio is installed: pip3 install pyaudio")
        print("  - Speaker is properly connected")
        print("  - Run with sudo if permission errors occur")

if __name__ == "__main__":
    main()
