#!/usr/bin/env python3
"""
Test script for Text-to-Speech.

Tests TTS with different providers and voices.

Run with: python -m raspi.voice.test_tts
"""

import sys
import os
from pathlib import Path

# Add parent directories to path (works for both apps/raspi and flattened raspi)
ROOT_DIR = Path(__file__).parent.parent.parent
if (ROOT_DIR / 'apps').exists():
    ROOT_DIR = ROOT_DIR.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env file
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')


def get_tts_class():
    """Import TextToSpeech from the right location."""
    try:
        from raspi.voice.tts import TextToSpeech
    except ImportError:
        TextToSpeech = get_tts_class()
    return TextToSpeech


def test_openai():
    """Test OpenAI TTS."""
    print("=" * 50)
    print("Test 1: OpenAI TTS")
    print("=" * 50)

    try:
        TextToSpeech = get_tts_class()

        tts = TextToSpeech(provider="openai", voice="nova")
        print(f"  Provider: openai")
        print(f"  Voice: nova")
        print(f"  Speaking...")

        tts.speak("Hello! I've set your light to a warm orange color.")
        print("  [OK] OpenAI TTS works")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_edge():
    """Test Edge TTS (free)."""
    print("\n" + "=" * 50)
    print("Test 2: Edge TTS (Microsoft, free)")
    print("=" * 50)

    try:
        TextToSpeech = get_tts_class()

        tts = TextToSpeech(provider="edge", voice="en-US-AriaNeural")
        print(f"  Provider: edge")
        print(f"  Voice: en-US-AriaNeural")
        print(f"  Speaking...")

        tts.speak("Sure, party mode is now on. The lights will cycle through colors.")
        print("  [OK] Edge TTS works")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_voices():
    """Test different OpenAI voices."""
    print("\n" + "=" * 50)
    print("Test 3: OpenAI Voice Comparison")
    print("=" * 50)

    TextToSpeech = get_tts_class()

    voices = ["alloy", "echo", "nova", "shimmer"]
    text = "Done, I've updated the light."

    for voice in voices:
        try:
            print(f"\n  Testing voice: {voice}")
            tts = TextToSpeech(provider="openai", voice=voice)
            tts.speak(text)
            print(f"  [OK] {voice}")
        except Exception as e:
            print(f"  [FAIL] {voice}: {e}")


def main():
    print("\n" + "=" * 50)
    print("Text-to-Speech Test Suite")
    print("=" * 50)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", "-p", choices=["openai", "edge", "all"], default="openai")
    parser.add_argument("--voice", "-v", help="Voice name")
    parser.add_argument("--text", "-t", default="Hello, this is a test of the text to speech system.")
    parser.add_argument("--compare", action="store_true", help="Compare all OpenAI voices")
    args = parser.parse_args()

    if args.compare:
        test_voices()
        return

    if args.provider == "all":
        test_openai()
        test_edge()
    elif args.provider == "openai":
        TextToSpeech = get_tts_class()
        voice = args.voice or "nova"
        print(f"\nProvider: openai, Voice: {voice}")
        tts = TextToSpeech(provider="openai", voice=voice)
        tts.speak(args.text)
    elif args.provider == "edge":
        TextToSpeech = get_tts_class()
        voice = args.voice or "en-US-AriaNeural"
        print(f"\nProvider: edge, Voice: {voice}")
        tts = TextToSpeech(provider="edge", voice=voice)
        tts.speak(args.text)


if __name__ == "__main__":
    main()
