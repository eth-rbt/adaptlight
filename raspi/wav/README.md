# Audio Prompt Files

This folder contains pre-recorded WAV files for audio feedback prompts.

## Required Files:

### Feedback Prompts
- `prompt_negative.wav` - "Can you please describe the problem?"
- `prompt_positive.wav` - "Please tell us what you like"

## Recording Instructions:

1. Record audio at 44.1kHz, 16-bit, mono WAV format
2. Keep prompts short and clear (2-3 seconds)
3. Use consistent volume levels
4. Test on actual hardware speaker

## Placeholder Files:

Until real recordings are made, you can:
- Use text-to-speech services (Google TTS, Amazon Polly, etc.)
- Record using a phone or computer microphone
- Use professional voice recording if needed

## Usage:

These files are played by `AudioPlayer` when feedback buttons are pressed.
