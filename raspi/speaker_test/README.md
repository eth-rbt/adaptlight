# I2S Speaker Testing on Raspberry Pi 5

## Overview
This folder contains resources for testing I2S (Inter-IC Sound) speakers with the Raspberry Pi 5.

## I2S Pinout on Raspberry Pi 5

The Raspberry Pi 5 uses the following GPIO pins for I2S audio:

| Signal | GPIO Pin | Physical Pin | Description |
|--------|----------|--------------|-------------|
| PCM_CLK (BCK) | GPIO 18 | Pin 12 | Bit Clock (Serial Clock) |
| PCM_FS (LRCLK) | GPIO 19 | Pin 35 | Frame Select (Left/Right Clock) |
| PCM_DIN | GPIO 20 | Pin 38 | Data In (for recording) |
| PCM_DOUT | GPIO 21 | Pin 40 | Data Out (for playback) |
| GND | GND | Pin 6, 9, 14, 20, 25, 30, 34, 39 | Ground |
| 3.3V or 5V | - | Pin 1 (3.3V) or Pin 2/4 (5V) | Power (check your speaker module) |

## Common I2S Wiring

For most I2S speaker modules (like MAX98357A, UDA1334A, etc.):

```
Speaker Module    →    Raspberry Pi 5
--------------------------------------------
VIN               →    3.3V or 5V (check module specs)
GND               →    GND
DIN/SD            →    GPIO 21 (Pin 40)
BCLK              →    GPIO 18 (Pin 12)
LRCLK/LRC         →    GPIO 19 (Pin 35)
```

## Setup Instructions

### 1. Enable I2S Interface

Edit the boot configuration:
```bash
sudo nano /boot/firmware/config.txt
```

Add or uncomment:
```
dtparam=i2s=on
```

For specific DAC/speaker modules, you may need a device tree overlay:
```
# For generic I2S devices
dtoverlay=hifiberry-dac

# Or for MAX98357A
dtoverlay=googlevoicehat-soundcard

# Or for other devices

```

Reboot:
```bash
sudo reboot
```

### 2. Verify I2S Interface

Check if I2S device is detected:
```bash
aplay -l
```

You should see an I2S device listed (e.g., "bcm2835 I2S").

### 3. Install Required Packages

```bash
sudo apt-get update
sudo apt-get install -y python3-pyaudio alsa-utils
```

### 4. Test Audio Playback

Generate a test tone:
```bash
speaker-test -t wav -c 2
```

Or play a WAV file:
```bash
aplay /usr/share/sounds/alsa/Front_Center.wav
```

### 5. Adjust Volume

```bash
alsamixer
```

Or via command line:
```bash
amixer set 'PCM' 80%
```

## Python Example

```python
import pyaudio
import numpy as np

# Audio parameters
RATE = 44100
DURATION = 2  # seconds
FREQUENCY = 440  # Hz (A4 note)

# Generate sine wave
samples = (np.sin(2 * np.pi * np.arange(RATE * DURATION) * FREQUENCY / RATE)).astype(np.float32)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open stream
stream = p.open(format=pyaudio.paFloat32,
                channels=1,
                rate=RATE,
                output=True)

# Play audio
stream.write(samples.tobytes())

# Clean up
stream.stop_stream()
stream.close()
p.terminate()
```

## Troubleshooting

### No Sound Output
- Check wiring connections
- Verify I2S is enabled in config.txt
- Check volume levels with `alsamixer`
- Ensure correct device tree overlay

### Device Not Found
```bash
# List all sound devices
aplay -L

# Check I2S is loaded
lsmod | grep snd
```

### Permissions
If you get permission errors:
```bash
sudo usermod -a -G audio $USER
```
Then log out and back in.

## Common I2S Speaker Modules

- **MAX98357A**: 3W Class D amplifier, mono
- **UDA1334A**: Stereo DAC breakout
- **PCM5102**: High-quality stereo DAC
- **HiFiBerry DAC**: Various models available

## References

- [Raspberry Pi I2S Documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
- [Device Tree Overlays](https://github.com/raspberrypi/firmware/tree/master/boot/overlays)
