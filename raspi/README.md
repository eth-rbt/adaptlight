# Raspberry Pi LED Control

Simple GPIO button to LED control for Raspberry Pi with WS2812 LEDs.

Logs button press events to AWS S3 with timestamps in daily JSON Lines files.

## Hardware Setup

- **Button**: Connect to GPIO 2 with pull-up (button to GND when pressed)
- **LEDs**: WS2812 data line to GPIO 18 (PWM pin)
- **LED Count**: 16 LEDs

## Installation

1. Install system dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-dev
```

2. Install Python packages:
```bash
pip3 install -r requirements.txt
```

## AWS S3 Logging Setup (Optional)

If you want to log button presses to AWS S3:

1. **Create IAM User**: Follow the instructions in [AWS_SETUP.md](AWS_SETUP.md) to create an IAM user with S3 write permissions.

2. **Configure credentials**:
   ```bash
   cp config.example.yaml config.yaml
   nano config.yaml
   ```

3. **Edit config.yaml** with your AWS credentials:
   ```yaml
   aws:
     access_key_id: YOUR_ACCESS_KEY_ID
     secret_access_key: YOUR_SECRET_ACCESS_KEY
     region: us-east-1
     s3_bucket: YOUR_BUCKET_NAME

   logging:
     enabled: true
     log_prefix: button-logs/
     timezone: UTC
   ```

4. **Log format**: Logs are stored as JSON Lines (`.jsonl`) files, one file per day:
   - Filename: `button-logs/button-logs-2025-11-04.jsonl`
   - Each line is a JSON object:
     ```json
     {"timestamp": "2025-11-04T15:30:45.123456+00:00", "event": "button_press", "led_state": "on"}
     ```

**Note**: If S3 logging fails (network issues, credentials, etc.), the script will continue to work and control the LEDs. Errors are printed to the console.

## Usage

Run the script with sudo (required for GPIO access):
```bash
sudo python3 led_control.py
```

Press the button to toggle LEDs on/off.

Press Ctrl+C to exit.

## Configuration

Edit `led_control.py` to modify:
- `LED_COUNT`: Number of LEDs (default: 16)
- `LED_PIN`: GPIO pin for LED data (default: GPIO 18)
- `BUTTON_PIN`: GPIO pin for button (default: GPIO 2)
- `LED_BRIGHTNESS`: Brightness level 0.0-1.0 (default: 0.3)
- `LED_COLOR`: RGB color tuple (default: white 255,255,255)