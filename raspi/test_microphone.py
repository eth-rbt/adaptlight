#!/usr/bin/env python3
"""
Microphone Test Script - Tests USB microphone functionality
Records audio and displays input levels
"""

import pyaudio
import wave
import numpy as np
import time
import sys

# Configuration
CHUNK = 1024            # Samples per frame
FORMAT = pyaudio.paInt16  # Audio format
CHANNELS = 1            # Mono audio
RATE = 16000           # Sample rate (16kHz, good for speech)
RECORD_SECONDS = 5     # Duration for test recording
TEST_FILENAME = "test_recording.wav"

print("=" * 50)
print("MICROPHONE TEST SCRIPT")
print("=" * 50)
print(f"\nConfiguration:")
print(f"  Sample Rate: {RATE} Hz")
print(f"  Channels: {CHANNELS} (Mono)")
print(f"  Chunk Size: {CHUNK} samples")
print(f"  Format: 16-bit PCM")
print("\nHardware Setup:")
print("  - Plug USB microphone into Raspberry Pi 5 USB port")
print("  - No additional wiring needed")
print("  - Microphone should be auto-detected")
print("=" * 50)

def list_audio_devices(p):
    """List all available audio devices"""
    print("\nAll Audio Devices:")
    print("-" * 50)
    device_count = p.get_device_count()
    input_devices = []

    for i in range(device_count):
        info = p.get_device_info_by_index(i)
        device_type = []
        if info['maxInputChannels'] > 0:
            device_type.append("INPUT")
            input_devices.append(i)
        if info['maxOutputChannels'] > 0:
            device_type.append("OUTPUT")

        type_str = "/".join(device_type) if device_type else "NONE"
        print(f"  [{i}] {info['name']}")
        print(f"      Type: {type_str}")
        print(f"      Input Channels: {info['maxInputChannels']}")
        print(f"      Output Channels: {info['maxOutputChannels']}")
        print(f"      Sample Rate: {int(info['defaultSampleRate'])} Hz")
        print()

    return input_devices

def get_audio_level(data):
    """Calculate audio level (RMS) from audio data"""
    try:
        audio_data = np.frombuffer(data, dtype=np.int16)
        if len(audio_data) == 0:
            return 0
        rms = np.sqrt(np.mean(audio_data**2))
        # Check for NaN or inf
        if not np.isfinite(rms):
            return 0
        # Normalize to 0-100 scale
        level = min(100, int(rms / 327.67 * 10))  # 32767 is max for int16
        return level
    except Exception:
        return 0

def print_level_bar(level):
    """Print a visual level meter"""
    bar_length = 50
    filled = int(bar_length * level / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    print(f"\rLevel: [{bar}] {level}%", end='', flush=True)

try:
    # Initialize PyAudio
    print("\n[1/5] Initializing audio system...")
    p = pyaudio.PyAudio()
    print("✓ PyAudio initialized")

    # List available devices
    print("\n[2/5] Detecting audio devices...")
    input_devices = list_audio_devices(p)

    if not input_devices:
        print("✗ ERROR: No input devices found!")
        print("\nTroubleshooting:")
        print("  1. Check if USB microphone is plugged in")
        print("  2. Run: arecord -l (to list audio devices)")
        print("  3. Try: sudo apt-get install pulseaudio")
        sys.exit(1)

    print(f"✓ Found {len(input_devices)} input device(s)")

    # Auto-select USB device if available
    selected_device = None
    device_info = None
    for dev_idx in input_devices:
        info = p.get_device_info_by_index(dev_idx)
        device_name = info['name'].lower()
        if 'usb' in device_name or 'pnp' in device_name:
            selected_device = dev_idx
            device_info = info
            print(f"\n✓ Auto-selected USB device: [{dev_idx}] {info['name']}")
            break

    if selected_device is None:
        selected_device = input_devices[0]
        device_info = p.get_device_info_by_index(selected_device)
        print(f"\n✓ Using device: [{selected_device}] {device_info['name']}")

    # Use device's native sample rate
    device_rate = int(device_info['defaultSampleRate'])
    print(f"  Using sample rate: {device_rate} Hz (device native)")

    # Open audio stream
    print("\n[3/5] Opening audio stream...")
    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=device_rate,
            input=True,
            input_device_index=selected_device,
            frames_per_buffer=CHUNK
        )
        print("✓ Audio stream opened successfully")
    except Exception as e:
        print(f"✗ ERROR opening stream: {e}")
        print("\nTry specifying a device manually:")
        print("Edit this script and add 'input_device_index=X' to p.open()")
        raise

    time.sleep(1)

    # Test audio levels
    print("\n[4/5] Testing audio levels (5 seconds)...")
    print("Make some noise to test the microphone!")
    print()

    max_level = 0
    samples = []

    for i in range(0, int(device_rate / CHUNK * 5)):  # 5 seconds
        data = stream.read(CHUNK, exception_on_overflow=False)
        level = get_audio_level(data)
        max_level = max(max_level, level)
        samples.append(data)
        print_level_bar(level)
        time.sleep(0.01)

    print()  # New line after level meter
    print(f"\n✓ Audio level test complete")
    print(f"  Maximum level detected: {max_level}%")

    if max_level < 5:
        print("\n⚠ WARNING: Very low audio levels detected!")
        print("  1. Try speaking louder or moving closer to mic")
        print("  2. Check microphone volume settings")
        print("  3. Use: alsamixer (to adjust input levels)")
    elif max_level < 30:
        print("\n✓ Audio detected, but levels are low")
        print("  Consider increasing microphone gain")
    else:
        print("\n✓ Good audio levels detected!")

    # Record a test file
    print(f"\n[5/5] Recording test file ({RECORD_SECONDS} seconds)...")
    print("Speak now to test recording quality!")

    frames = []
    for i in range(0, int(device_rate / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        level = get_audio_level(data)
        print_level_bar(level)

    print()  # New line
    print(f"✓ Recording complete")

    # Save test recording
    print(f"\nSaving recording to: {TEST_FILENAME}")
    wf = wave.open(TEST_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(device_rate)
    wf.writeframes(b''.join(frames))
    wf.close()
    print(f"✓ Test recording saved")
    print(f"  You can play it with: aplay {TEST_FILENAME}")

    # Cleanup
    stream.stop_stream()
    stream.close()
    p.terminate()

    print("\n" + "=" * 50)
    print("MICROPHONE TEST COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print("\nResults:")
    print(f"  ✓ Microphone detected and working")
    print(f"  ✓ Maximum level: {max_level}%")
    print(f"  ✓ Test recording saved: {TEST_FILENAME}")
    print("\nNext steps:")
    print("  - Play recording: aplay test_recording.wav")
    print("  - Verify audio quality")
    print("  - Adjust mic position/gain if needed")
    print("=" * 50)

except KeyboardInterrupt:
    print("\n\nTest interrupted by user")
    if 'stream' in locals():
        stream.stop_stream()
        stream.close()
    if 'p' in locals():
        p.terminate()

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    print("\nTroubleshooting:")
    print("  1. Install PyAudio: pip3 install pyaudio")
    print("  2. Install system audio: sudo apt-get install portaudio19-dev")
    print("  3. Check USB mic connection")
    print("  4. List devices: arecord -l")
    print("  5. Test with: arecord -d 5 test.wav && aplay test.wav")

    if 'p' in locals():
        p.terminate()
