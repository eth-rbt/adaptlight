#!/usr/bin/env python3
"""
OpenAI API Test Script - Tests OpenAI API connectivity and functionality
Tests both text generation and speech-to-text (Whisper) capabilities
"""

import sys
import yaml
from pathlib import Path
from openai import OpenAI

# Load config from current directory
config_file = Path(__file__).parent / 'config.yaml'

print("=" * 50)
print("OPENAI API TEST SCRIPT")
print("=" * 50)
print(f"\nConfiguration:")
print(f"  config.yaml location: {config_file}")
print("\nThis script tests:")
print("  1. API key configuration")
print("  2. Text completion (GPT model)")
print("  3. Speech-to-text (Whisper model) - if audio file exists")
print("=" * 50)

def load_config():
    """Load configuration from YAML file"""
    if not config_file.exists():
        print(f"\n✗ ERROR: config.yaml not found at {config_file}")
        print("\nCreate a config.yaml file with OpenAI API key configured")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    print(f"\n[1/4] Loading config.yaml...")
    print(f"✓ config.yaml loaded from {config_file}")
    return config

def test_api_key(config):
    """Test if API key is configured"""
    print("\n[2/4] Checking API key configuration...")

    openai_config = config.get('openai', {})
    api_key = openai_config.get('api_key')

    if not api_key:
        print("✗ ERROR: openai.api_key not found in config.yaml")
        print("\nAdd OpenAI API key to config.yaml:")
        sys.exit(1)

    # Check if key looks valid (starts with sk-)
    if not api_key.startswith('sk-'):
        print("⚠ WARNING: API key doesn't start with 'sk-'")
        print("  This might not be a valid OpenAI API key")
    else:
        print(f"✓ API key found (length: {len(api_key)} chars)")
        print(f"  Key prefix: {api_key[:20]}...")

    return api_key

def test_text_completion(client):
    """Test text completion with GPT model"""
    print("\n[3/4] Testing text completion (GPT model)...")
    print("  Sending test prompt to OpenAI...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant testing API connectivity."},
                {"role": "user", "content": "Say 'API test successful' if you can read this."}
            ],
            max_tokens=50,
            temperature=0.7
        )

        result = response.choices[0].message.content
        print(f"✓ Text completion successful!")
        print(f"\n  Prompt: 'Say API test successful if you can read this.'")
        print(f"  Response: '{result}'")
        print(f"\n  Model used: {response.model}")
        print(f"  Tokens used: {response.usage.total_tokens}")

        return True

    except Exception as e:
        print(f"✗ ERROR: Text completion failed")
        print(f"  {type(e).__name__}: {e}")
        return False

def test_whisper_transcription(client):
    """Test speech-to-text with Whisper model"""
    print("\n[4/4] Testing speech-to-text (Transcription model)...")

    # Look for test audio file
    audio_file = Path(__file__).parent / "test_recording.wav"

    if not audio_file.exists():
        print(f"⚠ Skipping transcription test: No audio file found")
        print(f"  Expected file: {audio_file}")
        print(f"  Run test_microphone.py first to create test_recording.wav")
        return None

    print(f"  Audio file: {audio_file}")
    print(f"  Sending audio to transcription API...")

    try:
        with open(audio_file, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=f
            )

        response_text = transcription.text
        print(f"✓ Speech-to-text successful!")
        print(f"\n  Transcription: '{response_text}'")

        if len(response_text.strip()) == 0:
            print(f"\n  ⚠ WARNING: Empty transcription")
            print(f"    The audio file might be silent or unclear")
        elif len(response_text.strip()) < 5:
            print(f"\n  ⚠ WARNING: Very short transcription")
            print(f"    Check audio quality and volume")
        else:
            print(f"\n  ✓ Good transcription length")

        return True

    except Exception as e:
        print(f"✗ ERROR: Speech-to-text failed")
        print(f"  {type(e).__name__}: {e}")
        return False

try:
    # Load configuration
    config = load_config()

    # Test API key
    api_key = test_api_key(config)

    # Initialize OpenAI client
    print("\nInitializing OpenAI client...")
    client = OpenAI(api_key=api_key)
    print("✓ OpenAI client initialized")

    # Run tests
    text_success = test_text_completion(client)
    whisper_success = test_whisper_transcription(client)

    # Print results
    print("\n" + "=" * 50)
    print("OPENAI API TEST RESULTS")
    print("=" * 50)
    print(f"\nAPI Key Configuration: ✓ PASS")
    print(f"Text Completion (GPT): {'✓ PASS' if text_success else '✗ FAIL'}")

    if whisper_success is None:
        print(f"Speech-to-Text (Whisper): ⚠ SKIPPED (no audio file)")
    elif whisper_success:
        print(f"Speech-to-Text (Whisper): ✓ PASS")
    else:
        print(f"Speech-to-Text (Whisper): ✗ FAIL")

    # Overall result
    if text_success and (whisper_success is None or whisper_success):
        print("\n✓ OVERALL: OpenAI API is working correctly!")
        if whisper_success is None:
            print("  Note: Run test_microphone.py to test Whisper")
    else:
        print("\n✗ OVERALL: Some tests failed")
        print("  Check error messages above for details")

    print("=" * 50)

except KeyboardInterrupt:
    print("\n\nTest interrupted by user")

except Exception as e:
    print(f"\n✗ UNEXPECTED ERROR: {e}")
    print("\nTroubleshooting:")
    print("  1. Install OpenAI library: pip3 install openai")
    print("  2. Check .env file exists in parent directory")
    print("  3. Verify OPENAI_API_KEY in .env file")
    print("  4. Check internet connectivity")
    print("  5. Verify API key at: https://platform.openai.com/api-keys")
    sys.exit(1)
