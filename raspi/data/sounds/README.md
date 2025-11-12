# Audio Feedback Sounds

This directory contains WAV audio files for AdaptLight feedback sounds.

## Required Sound Files

### error.wav
Played when:
- Voice command parsing fails
- No changes are detected after voice command processing
- Any error occurs during voice command execution

### success.wav (Optional)
Played when:
- Rules are successfully added or modified
- State changes successfully applied
- Any successful operation

## File Format Requirements

- Format: WAV (Waveform Audio File Format)
- Sample rate: 22050 Hz or higher recommended
- Channels: Mono or Stereo
- Bit depth: 16-bit recommended

## How to Add Sound Files

1. Create or download short WAV sound files (0.5-2 seconds recommended)
2. Name them `error.wav` and/or `success.wav`
3. Place them in this directory
4. Restart AdaptLight for changes to take effect

## Sound Sources

You can create custom sounds using:
- Online sound effect generators (freesound.org, zapsplat.com)
- Text-to-speech tools for voice feedback
- Audio editing software (Audacity, etc.)
- Pre-made sound libraries

## Example Commands to Generate Simple Beep Sounds

Using `sox` (Sound eXchange) on Linux/macOS:

```bash
# Install sox if needed
# macOS: brew install sox
# Linux: sudo apt-get install sox

# Generate error sound (descending tone)
sox -n error.wav synth 0.3 sine 800 fade 0 0.3 0.1 : synth 0.3 sine 400 fade 0.1 0.3 0

# Generate success sound (ascending tone)
sox -n success.wav synth 0.2 sine 600 fade 0 0.2 0.05 : synth 0.2 sine 900 fade 0.05 0.2 0
```

Using Python (if you want to generate programmatically):

```python
import numpy as np
import wave

def generate_beep(filename, frequency=440, duration=0.5, sample_rate=22050):
    """Generate a simple beep sound."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t)

    # Apply fade in/out to avoid clicks
    fade_samples = int(sample_rate * 0.05)
    audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
    audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

    # Convert to 16-bit PCM
    audio = (audio * 32767).astype(np.int16)

    # Write WAV file
    with wave.open(filename, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio.tobytes())

# Generate sounds
generate_beep('error.wav', frequency=300, duration=0.4)
generate_beep('success.wav', frequency=800, duration=0.3)
```
