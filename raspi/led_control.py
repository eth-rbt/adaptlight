#!/usr/bin/env python3
"""
Simple GPIO button to LED control for Raspberry Pi
Detects button press and toggles 16 WS2812 LEDs on/off
Logs button presses to AWS S3 with timestamps
"""

import time
import json
from datetime import datetime, timezone
import board
import neopixel
from gpiozero import Button
from signal import pause
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import yaml

# Load configuration
def load_config():
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Warning: config.yaml not found. S3 logging will be disabled.")
        print("Copy config.example.yaml to config.yaml and add your AWS credentials.")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        return None

config = load_config()

# Configuration
LED_COUNT = 16          # Number of LEDs
LED_PIN = board.D18     # GPIO pin for LED data (GPIO 18)
BUTTON_PIN = 2          # GPIO pin for button (GPIO 2)

# LED settings
LED_BRIGHTNESS = 0.3    # Brightness (0.0 to 1.0)
LED_COLOR = (255, 255, 255)  # Default color (white)

# Initialize S3 client if config is available
s3_client = None
logging_enabled = False

if config and config.get('logging', {}).get('enabled', False):
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=config['aws']['access_key_id'],
            aws_secret_access_key=config['aws']['secret_access_key'],
            region_name=config['aws']['region']
        )
        logging_enabled = True
        print("S3 logging enabled")
    except (KeyError, NoCredentialsError) as e:
        print(f"Warning: Could not initialize S3 client: {e}")
        print("S3 logging will be disabled.")
else:
    print("S3 logging disabled in config")

# Initialize NeoPixel strip
pixels = neopixel.NeoPixel(
    LED_PIN,
    LED_COUNT,
    brightness=LED_BRIGHTNESS,
    auto_write=False
)

# Initialize button (pull_up=True means pressed = LOW)
button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)

# LED state
leds_on = False

def log_to_s3(event_type, led_state):
    """Log button press event to S3 with timestamp in daily files"""
    if not logging_enabled or not s3_client:
        return

    try:
        # Get current timestamp
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        date_str = now.strftime('%Y-%m-%d')

        # Create log entry
        log_entry = {
            'timestamp': timestamp,
            'event': event_type,
            'led_state': led_state
        }

        # S3 bucket and file details
        bucket = config['aws']['s3_bucket']
        prefix = config['logging'].get('log_prefix', 'button-logs/')
        filename = f"{prefix}button-logs-{date_str}.jsonl"

        # Try to download existing file content
        existing_content = ""
        try:
            response = s3_client.get_object(Bucket=bucket, Key=filename)
            existing_content = response['Body'].read().decode('utf-8')
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # File doesn't exist yet, that's okay
                pass
            else:
                # Other error, re-raise
                raise

        # Append new log entry
        new_content = existing_content + json.dumps(log_entry) + '\n'

        # Upload updated file
        s3_client.put_object(
            Bucket=bucket,
            Key=filename,
            Body=new_content.encode('utf-8'),
            ContentType='application/x-ndjson'
        )

        print(f"Logged to S3: {filename}")

    except ClientError as e:
        print(f"Error logging to S3: {e}")
    except Exception as e:
        print(f"Unexpected error logging to S3: {e}")

def toggle_leds():
    """Toggle LEDs on/off when button is pressed"""
    global leds_on

    leds_on = not leds_on

    if leds_on:
        # Turn all LEDs on with white color
        pixels.fill(LED_COLOR)
        print("LEDs: ON")
    else:
        # Turn all LEDs off
        pixels.fill((0, 0, 0))
        print("LEDs: OFF")

    pixels.show()

    # Log the button press to S3
    log_to_s3('button_press', 'on' if leds_on else 'off')

# Attach button press handler
button.when_pressed = toggle_leds

print("LED Control Started")
print(f"Button Pin: GPIO {BUTTON_PIN}")
print(f"LED Pin: GPIO {LED_PIN}")
print(f"LED Count: {LED_COUNT}")
print("Press button to toggle LEDs on/off")
print("Press Ctrl+C to exit")

try:
    # Initialize LEDs to off
    pixels.fill((0, 0, 0))
    pixels.show()

    # Wait for button presses
    pause()
except KeyboardInterrupt:
    print("\nExiting...")
    # Turn off all LEDs before exiting
    pixels.fill((0, 0, 0))
    pixels.show()