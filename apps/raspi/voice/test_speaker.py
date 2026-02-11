#!/usr/bin/env python3
"""
Speaker test script for I2S DAC (MAX98357A or similar).

Tests audio output through I2S speaker.

Run with: python -m raspi.voice.test_speaker
"""

import subprocess
import tempfile
import wave
import struct
import math
import argparse
from pathlib import Path


def generate_test_tone(frequency=440, duration=1.0, sample_rate=44100, volume=0.5):
    """Generate a sine wave test tone as WAV file."""
    n_samples = int(sample_rate * duration)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name

    with wave.open(temp_path, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        for i in range(n_samples):
            value = volume * math.sin(2 * math.pi * frequency * i / sample_rate)
            packed = struct.pack('<h', int(value * 32767))
            wav_file.writeframes(packed)

    return temp_path


def play_audio(file_path, device=None):
    """Play audio file using aplay."""
    cmd = ["aplay"]
    if device:
        cmd.extend(["-D", device])
    cmd.append(file_path)

    print(f"  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            return False
        return True
    except FileNotFoundError:
        print("  Error: aplay not found. Install alsa-utils.")
        return False
    except subprocess.TimeoutExpired:
        print("  Error: Playback timed out")
        return False


def list_audio_devices():
    """List available ALSA audio devices."""
    print("\n" + "=" * 50)
    print("Available Audio Devices")
    print("=" * 50)

    try:
        # List playback devices
        result = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
        print("\nPlayback devices (aplay -l):")
        print(result.stdout if result.stdout else "  No devices found")

        # List PCM devices
        result = subprocess.run(["aplay", "-L"], capture_output=True, text=True)
        print("\nPCM devices (aplay -L):")
        lines = result.stdout.split('\n')[:20]  # First 20 lines
        print('\n'.join(lines))
        if len(result.stdout.split('\n')) > 20:
            print("  ... (truncated)")

    except FileNotFoundError:
        print("  aplay not found. Install alsa-utils: sudo apt install alsa-utils")


def test_speaker(device="hw:0,0"):
    """Test I2S speaker with a tone."""
    print("\n" + "=" * 50)
    print(f"Testing I2S Speaker (device: {device})")
    print("=" * 50)

    # Generate test tone
    print("\n1. Generating 440Hz test tone (1 second)...")
    tone_file = generate_test_tone(frequency=440, duration=1.0)
    print(f"   Created: {tone_file}")

    # Play the tone
    print("\n2. Playing test tone...")
    success = play_audio(tone_file, device)

    # Cleanup
    Path(tone_file).unlink(missing_ok=True)

    if success:
        print("\n[OK] Speaker test completed!")
    else:
        print("\n[FAIL] Speaker test failed")
        print("\nTroubleshooting:")
        print("  1. Check I2S overlay is enabled in /boot/config.txt")
        print("  2. Verify wiring: BCLK=GPIO18, LRCLK=GPIO19, DIN=GPIO21")
        print("  3. Run 'sudo dmesg | grep -i i2s' to check driver")
        print("  4. Try different device: hw:1,0 or plughw:0,0")

    return success


def test_frequency_sweep(device="hw:0,0"):
    """Play a frequency sweep to test speaker range."""
    print("\n" + "=" * 50)
    print("Frequency Sweep Test")
    print("=" * 50)

    frequencies = [200, 440, 880, 1760, 3520]

    for freq in frequencies:
        print(f"\n  Playing {freq}Hz...")
        tone_file = generate_test_tone(frequency=freq, duration=0.5)
        play_audio(tone_file, device)
        Path(tone_file).unlink(missing_ok=True)

    print("\n[OK] Frequency sweep completed!")


def main():
    parser = argparse.ArgumentParser(description="Test I2S speaker")
    parser.add_argument("--device", "-d", default="hw:0,0",
                        help="ALSA device (default: hw:0,0)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List available audio devices")
    parser.add_argument("--sweep", "-s", action="store_true",
                        help="Run frequency sweep test")
    parser.add_argument("--frequency", "-f", type=int, default=440,
                        help="Test tone frequency in Hz (default: 440)")
    parser.add_argument("--duration", "-t", type=float, default=1.0,
                        help="Test tone duration in seconds (default: 1.0)")
    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("I2S Speaker Test")
    print("=" * 50)

    if args.list:
        list_audio_devices()
        return

    if args.sweep:
        test_frequency_sweep(args.device)
        return

    # Single tone test
    print(f"\nDevice: {args.device}")
    print(f"Frequency: {args.frequency}Hz")
    print(f"Duration: {args.duration}s")

    print("\nGenerating test tone...")
    tone_file = generate_test_tone(
        frequency=args.frequency,
        duration=args.duration
    )

    print("Playing...")
    success = play_audio(tone_file, args.device)
    Path(tone_file).unlink(missing_ok=True)

    if success:
        print("\n[OK] Test completed!")
    else:
        print("\n[FAIL] Test failed")
        list_audio_devices()


if __name__ == "__main__":
    main()
