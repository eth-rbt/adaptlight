#!/usr/bin/env python3
"""
I2S Mic + Speaker Loopback Test
Records audio from I2S microphone and plays it back through I2S speaker
"""

import pyaudio
import wave
import sys

# Audio configuration
RATE = 48000  # Sample rate (Hz) - 48kHz standard for I2S
CHANNELS = 2  # Stereo (I2S devices usually require 2 channels)
CHUNK = 1024  # Buffer size
FORMAT = pyaudio.paInt16  # 16-bit audio
RECORD_SECONDS = 3  # Recording duration

def test_loopback():
    """Record from mic and play back through speaker"""

    p = pyaudio.PyAudio()

    print("=" * 60)
    print("I2S Microphone + Speaker Loopback Test")
    print("=" * 60)

    # Find the I2S device
    device_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if 'googlevoicehat' in info['name'].lower() or 'voicehat' in info['name'].lower():
            device_index = i
            print(f"\nUsing device: {info['name']}")
            print(f"  Channels: {info['maxInputChannels']} in, {info['maxOutputChannels']} out")
            break

    if device_index is None:
        print("\nError: I2S device not found!")
        print("Make sure your I2S mic and speaker are connected.")
        p.terminate()
        return

    # Record audio
    print(f"\nRecording for {RECORD_SECONDS} seconds...")
    print("Speak now!")

    try:
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       input_device_index=device_index,
                       frames_per_buffer=CHUNK)

        frames = []
        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)
            # Simple progress indicator
            if i % 10 == 0:
                print(".", end="", flush=True)

        print("\nRecording complete!")

        stream.stop_stream()
        stream.close()

        # Play back the recording
        print("Playing back...")

        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       output=True,
                       output_device_index=device_index,
                       frames_per_buffer=CHUNK)

        for frame in frames:
            stream.write(frame)

        print("Playback complete!")

        stream.stop_stream()
        stream.close()

    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("  - Check mic and speaker wiring")
        print("  - Ensure I2S is enabled in /boot/firmware/config.txt")
        print("  - Try running with: sudo python3 loopback_test.py")
    finally:
        p.terminate()

def test_realtime_loopback():
    """Real-time loopback - hear yourself with slight delay"""

    p = pyaudio.PyAudio()

    print("=" * 60)
    print("Real-time Loopback - Press Ctrl+C to stop")
    print("=" * 60)

    # Find the I2S device
    device_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if 'googlevoicehat' in info['name'].lower() or 'voicehat' in info['name'].lower():
            device_index = i
            print(f"\nUsing device: {info['name']}")
            break

    if device_index is None:
        print("\nError: I2S device not found!")
        p.terminate()
        return

    print("\nStarting real-time loopback...")
    print("You should hear yourself with a slight delay.")
    print("Press Ctrl+C to stop.\n")

    try:
        stream_in = p.open(format=FORMAT,
                          channels=CHANNELS,
                          rate=RATE,
                          input=True,
                          input_device_index=device_index,
                          frames_per_buffer=CHUNK)

        stream_out = p.open(format=FORMAT,
                           channels=CHANNELS,
                           rate=RATE,
                           output=True,
                           output_device_index=device_index,
                           frames_per_buffer=CHUNK)

        while True:
            data = stream_in.read(CHUNK)
            stream_out.write(data)

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        stream_in.stop_stream()
        stream_in.close()
        stream_out.stop_stream()
        stream_out.close()
        p.terminate()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "realtime":
        test_realtime_loopback()
    else:
        print("\nChoose test mode:")
        print("  1. Record and playback (default)")
        print("  2. Real-time loopback")
        choice = input("\nSelect (1 or 2): ").strip()

        if choice == "2":
            test_realtime_loopback()
        else:
            test_loopback()
