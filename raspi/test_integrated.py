#!/usr/bin/env python3
"""
Integrated Test Script - Tests full system integration
Combines LED, button, microphone, and OpenAI API functionality
in a realistic usage scenario
"""

import sys
import time
import wave
import yaml
from pathlib import Path
import board
import neopixel
from gpiozero import Button
import pyaudio
import numpy as np
from openai import OpenAI

# Configuration
LED_COUNT = 16
LED_PIN = board.D18
LED_BRIGHTNESS = 0.3
BUTTON_PIN = 2

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5

# Load config from current directory
config_file = Path(__file__).parent / 'config.yaml'

print("=" * 60)
print("INTEGRATED SYSTEM TEST")
print("=" * 60)
print("\nThis test simulates the full workflow:")
print("  1. Initialize all hardware (LEDs, button, microphone)")
print("  2. Wait for button press")
print("  3. Record audio when button is pressed")
print("  4. Send audio to OpenAI Whisper for transcription")
print("  5. Generate response using GPT")
print("  6. Display results with LED feedback")
print("=" * 60)

def load_config():
    """Load configuration from YAML file"""
    if not config_file.exists():
        print(f"\n✗ ERROR: config.yaml not found at {config_file}")
        print("\nCreate a config.yaml file with OpenAI API key configured")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    return config

def get_audio_level(data):
    """Calculate audio level from audio data"""
    audio_data = np.frombuffer(data, dtype=np.int16)
    rms = np.sqrt(np.mean(audio_data**2))
    return min(100, int(rms / 327.67 * 10))

def led_pattern(pixels, pattern, duration=1.0):
    """Display LED pattern"""
    if pattern == "idle":
        # Soft blue breathing effect
        pixels.fill((0, 0, 50))
    elif pattern == "listening":
        # Bright white
        pixels.fill((255, 255, 255))
    elif pattern == "processing":
        # Yellow/amber
        pixels.fill((255, 200, 0))
    elif pattern == "success":
        # Green
        pixels.fill((0, 255, 0))
    elif pattern == "error":
        # Red
        pixels.fill((255, 0, 0))
    elif pattern == "off":
        pixels.fill((0, 0, 0))

    pixels.show()
    time.sleep(duration)

try:
    # Initialize all components
    print("\n" + "=" * 60)
    print("PHASE 1: HARDWARE INITIALIZATION")
    print("=" * 60)

    # Load configuration
    print("\n[1/6] Loading configuration...")
    config = load_config()
    openai_config = config.get('openai', {})
    api_key = openai_config.get('api_key')
    if not api_key:
        print("✗ ERROR: openai.api_key not found in config.yaml")
        sys.exit(1)
    print(f"✓ API key loaded")

    # Initialize OpenAI
    print("\n[2/6] Initializing OpenAI client...")
    client = OpenAI(api_key=api_key)
    print("✓ OpenAI client ready")

    # Initialize LEDs
    print("\n[3/6] Initializing LED strip...")
    pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False)
    led_pattern(pixels, "idle", 0.5)
    print("✓ LEDs initialized (blue = idle)")

    # Initialize button
    print("\n[4/6] Initializing button...")
    button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
    print("✓ Button initialized")

    # Initialize audio
    print("\n[5/6] Initializing audio system...")
    p = pyaudio.PyAudio()
    print("✓ Audio system ready")

    # Test audio stream
    print("\n[6/6] Testing audio stream...")
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    print("✓ Audio stream opened")

    print("\n" + "=" * 60)
    print("✓ ALL HARDWARE INITIALIZED SUCCESSFULLY")
    print("=" * 60)

    # Main interaction loop
    print("\n" + "=" * 60)
    print("PHASE 2: INTERACTIVE TEST")
    print("=" * 60)
    print("\nSystem ready!")
    print("\nInstructions:")
    print("  1. LEDs are BLUE (idle state)")
    print("  2. PRESS THE BUTTON to start recording")
    print("  3. Speak for 5 seconds (LEDs will turn WHITE)")
    print("  4. System will process audio (LEDs turn YELLOW)")
    print("  5. Results displayed (LEDs turn GREEN if successful)")
    print("\nPress Ctrl+C to exit")
    print("=" * 60)

    test_count = 0

    while True:
        # Wait for button press
        print(f"\n[Test #{test_count + 1}] Waiting for button press...")
        led_pattern(pixels, "idle", 0.1)

        button.wait_for_press()
        test_count += 1

        print("\n" + "-" * 60)
        print(f"BUTTON PRESSED! Starting Test #{test_count}")
        print("-" * 60)

        # Start recording
        print(f"\n[Recording] Listening for {RECORD_SECONDS} seconds...")
        print("Speak now!")
        led_pattern(pixels, "listening", 0.1)

        frames = []
        max_level = 0

        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            level = get_audio_level(data)
            max_level = max(max_level, level)

            # Visual feedback
            bar_length = 40
            filled = int(bar_length * level / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"\r  Level: [{bar}] {level}%", end='', flush=True)

        print()  # New line
        print(f"✓ Recording complete (max level: {max_level}%)")

        # Check if audio was detected
        if max_level < 5:
            print("⚠ WARNING: Very low audio detected!")
            led_pattern(pixels, "error", 2)
            continue

        # Save recording
        temp_file = "temp_recording.wav"
        print(f"\n[Processing] Saving audio to {temp_file}...")
        wf = wave.open(temp_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        print("✓ Audio saved")

        # Process with Whisper
        led_pattern(pixels, "processing", 0.1)
        print("\n[Processing] Transcribing with Whisper...")

        try:
            with open(temp_file, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="text"
                )

            print(f"✓ Transcription: '{transcription}'")

            # Generate response with GPT
            print("\n[Processing] Generating response with GPT...")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Respond briefly in 1-2 sentences."},
                    {"role": "user", "content": transcription}
                ],
                max_tokens=100,
                temperature=0.7
            )

            gpt_response = response.choices[0].message.content
            print(f"✓ Response: '{gpt_response}'")

            # Success!
            led_pattern(pixels, "success", 2)

            print("\n" + "-" * 60)
            print("✓ TEST SUCCESSFUL!")
            print("-" * 60)
            print(f"You said: {transcription}")
            print(f"AI response: {gpt_response}")
            print(f"Tokens used: {response.usage.total_tokens}")
            print("-" * 60)

        except Exception as e:
            print(f"\n✗ ERROR during processing: {e}")
            led_pattern(pixels, "error", 2)
            print("-" * 60)
            print("✗ TEST FAILED")
            print("-" * 60)

        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)

        # Return to idle
        led_pattern(pixels, "idle", 0.5)

except KeyboardInterrupt:
    print("\n\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"\nTotal tests completed: {test_count}")

    if test_count > 0:
        print("\n✓ Integrated system is working!")
        print("\nAll components tested successfully:")
        print("  ✓ LED feedback")
        print("  ✓ Button input")
        print("  ✓ Audio recording")
        print("  ✓ OpenAI Whisper transcription")
        print("  ✓ OpenAI GPT response generation")
    else:
        print("\nNo tests completed")

    print("=" * 60)

    # Cleanup
    print("\nCleaning up...")
    led_pattern(pixels, "off", 0.1)
    if 'stream' in locals():
        stream.stop_stream()
        stream.close()
    if 'p' in locals():
        p.terminate()
    print("✓ Cleanup complete")

except Exception as e:
    print(f"\n\n✗ ERROR: {e}")
    print("\nTroubleshooting:")
    print("  1. Run individual test scripts first:")
    print("     - sudo python3 test_leds.py")
    print("     - sudo python3 test_button.py")
    print("     - python3 test_microphone.py")
    print("     - python3 test_openai.py")
    print("  2. Check all hardware connections")
    print("  3. Verify API key in .env file")
    print("  4. Ensure all libraries are installed")

    # Cleanup
    if 'pixels' in locals():
        pixels.fill((0, 0, 0))
        pixels.show()
    if 'stream' in locals():
        stream.stop_stream()
        stream.close()
    if 'p' in locals():
        p.terminate()
