# AdaptLight - Raspberry Pi 5

Voice-controlled adaptive lighting system with AI-powered natural language processing.

Features:
- WS2812 LED strip control (16 LEDs)
- Push button input with pattern detection
- USB microphone for voice commands
- OpenAI Whisper speech-to-text
- GPT-powered command parsing
- AWS S3 logging (optional)

---

## Deploying to Raspberry Pi

### Prerequisites

- Raspberry Pi 5 with Raspberry Pi OS installed
- Network connection (WiFi or Ethernet)
- SSH enabled on Raspberry Pi
- Your development machine and Raspberry Pi on the same network

### Step 1: Find Your Raspberry Pi's IP Address

On the Raspberry Pi, run:
```bash
hostname -I
```

Or from your development machine:
```bash
# Scan network for Raspberry Pi
ping raspberrypi.local
# Or use: arp -a | grep -i "b8:27:eb\|dc:a6:32\|e4:5f:01"
```

### Step 2: Enable SSH on Raspberry Pi

If SSH is not already enabled:
```bash
# On Raspberry Pi directly:
sudo systemctl enable ssh
sudo systemctl start ssh

# Or enable via raspi-config:
sudo raspi-config
# Navigate to: Interfacing Options → SSH → Enable
```

### Step 3: Sync Files to Raspberry Pi

**Method 1: Using rsync (Recommended)**

From your development machine, in the `adaptlight` directory:

```bash
# Sync entire raspi folder to Raspberry Pi
rsync -avz --progress worktree/raspi/ pi@<PI_IP_ADDRESS>:~/adaptlight/

# Example:
# rsync -avz --progress worktree/raspi/ pi@192.168.1.100:~/adaptlight/

# Exclude test files if desired:
# rsync -avz --progress --exclude 'test_*.py' --exclude '*.wav' worktree/raspi/ pi@<PI_IP_ADDRESS>:~/adaptlight/
```

**Method 2: Using scp**

```bash
# Copy entire folder
scp -r worktree/raspi pi@<PI_IP_ADDRESS>:~/adaptlight

# Example:
# scp -r worktree/raspi pi@192.168.1.100:~/adaptlight
```

**Method 3: Using Git (if you have a remote repository)**

On Raspberry Pi:
```bash
# Clone repository
git clone <your-repo-url> ~/adaptlight
cd ~/adaptlight

# Checkout worktree branch
git worktree add raspi
cd raspi
```

**Method 4: Using USB Drive**

1. Copy `worktree/raspi/` folder to USB drive
2. Plug USB drive into Raspberry Pi
3. Mount and copy:
```bash
# Find USB device
lsblk

# Mount USB (assuming /dev/sda1)
sudo mount /dev/sda1 /mnt/usb

# Copy files
cp -r /mnt/usb/raspi ~/adaptlight

# Unmount
sudo umount /mnt/usb
```

### Step 4: Copy .env File

The .env file (with your OpenAI API key) is in the parent directory. Copy it separately:

```bash
# From your development machine
scp .env pi@<PI_IP_ADDRESS>:~/

# Or include in rsync
rsync -avz --progress .env pi@<PI_IP_ADDRESS>:~/
```

### Step 5: Automated Sync Script

Create a sync script on your development machine for easy updates:

**sync-to-pi.sh:**
```bash
#!/bin/bash
PI_IP="192.168.1.100"  # Change this to your Pi's IP
PI_USER="pi"
PI_PATH="~/adaptlight"

echo "Syncing to Raspberry Pi at $PI_IP..."

# Sync raspi folder
rsync -avz --progress \
  --exclude '*.pyc' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude 'test_recording.wav' \
  --exclude 'temp_recording.wav' \
  worktree/raspi/ $PI_USER@$PI_IP:$PI_PATH/

# Sync .env file
rsync -avz .env $PI_USER@$PI_IP:~/

echo "✓ Sync complete!"
```

Make it executable:
```bash
chmod +x sync-to-pi.sh
./sync-to-pi.sh
```

### Step 6: Verify Files on Raspberry Pi

SSH into your Raspberry Pi and verify:
```bash
ssh pi@<PI_IP_ADDRESS>

# Check files
ls -la ~/adaptlight/
ls -la ~/.env

# Verify structure
tree ~/adaptlight/ -L 2
```

---

## Hardware Setup

**Pin Connections:**

| Component | Connection | GPIO Pin | Physical Pin |
|-----------|------------|----------|--------------|
| LED Strip Data | WS2812 Data | GPIO 18 | Pin 12 |
| LED Strip Power | 5V | 5V | Pin 2 or 4 |
| LED Strip Ground | GND | GND | Pin 6 |
| Button Terminal 1 | Input | GPIO 2 | Pin 3 |
| Button Terminal 2 | Ground | GND | Pin 9 |
| USB Microphone | USB Port | Any USB | - |

**Notes:**
- LED strip: 16 WS2812 LEDs (configurable)
- Button: Momentary push button (NO - Normally Open)
- Internal pull-up resistor enabled on GPIO 2
- USB microphone auto-detected by system

---

## Installation on Raspberry Pi

**After syncing files to Raspberry Pi, SSH in and run:**

### 1. Install System Dependencies

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and build tools
sudo apt-get install -y python3-pip python3-dev python3-venv

# Install audio libraries
sudo apt-get install -y portaudio19-dev

# Install optional tools
sudo apt-get install -y git vim tree
```

### 2. Set Up Python Environment

```bash
cd ~/adaptlight

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Or install globally:
pip3 install -r requirements.txt
```

### 3. Install Python Packages

```bash
# Activate virtual environment first (if using)
source venv/bin/activate

# Install all requirements
pip3 install -r requirements.txt

# Verify installations
python3 -c "import board; import neopixel; import gpiozero; print('✓ Hardware libraries OK')"
python3 -c "import openai; import pyaudio; print('✓ API libraries OK')"
```

### 4. Configure Environment Variables

```bash
# Copy .env file from home directory
cp ~/.env ~/adaptlight/.env

# Or create new .env file
nano ~/adaptlight/.env
```

Add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 5. Configure GPIO Permissions (Optional)

Add your user to the gpio group to avoid using sudo:
```bash
sudo usermod -a -G gpio $USER
sudo usermod -a -G audio $USER

# Reboot for changes to take effect
sudo reboot
```

### 6. Test Hardware

Run the hardware verification tests:
```bash
cd ~/adaptlight

# Test LEDs (requires sudo)
sudo python3 test_leds.py

# Test button (requires sudo)
sudo python3 test_button.py

# Test microphone (no sudo needed)
python3 test_microphone.py

# Test OpenAI API
python3 test_openai.py

# Full integration test
sudo python3 test_integrated.py
```

See [TESTING.md](TESTING.md) for detailed testing instructions.

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

### Running the Application

**Main Application (Voice-controlled):**
```bash
cd ~/adaptlight
sudo python3 main.py
```

**Simple LED Control (Button only):**
```bash
sudo python3 led_control.py
```

**Test Scripts:**
```bash
# Individual tests
sudo python3 test_leds.py
sudo python3 test_button.py
python3 test_microphone.py
python3 test_openai.py

# Full integration test
sudo python3 test_integrated.py
```

### Using the System

**Voice Commands:**
1. Press and hold the button
2. Speak your command (e.g., "make it blue", "pulse slowly", "turn it off")
3. Release the button
4. System transcribes, processes, and executes command

**Button-Only Mode (led_control.py):**
- Single press: Toggle LEDs on/off
- LEDs default to white when on

### Running as a Service (Auto-start on boot)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/adaptlight.service
```

Add this content:
```ini
[Unit]
Description=AdaptLight Voice-Controlled LED System
After=network.target sound.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/adaptlight
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/pi/adaptlight/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
# Enable service (start on boot)
sudo systemctl enable adaptlight.service

# Start service now
sudo systemctl start adaptlight.service

# Check status
sudo systemctl status adaptlight.service

# View logs
sudo journalctl -u adaptlight.service -f

# Stop service
sudo systemctl stop adaptlight.service

# Restart service
sudo systemctl restart adaptlight.service
```

---

## Configuration

### Hardware Configuration

Edit configuration in Python files:

**main.py or led_control.py:**
- `LED_COUNT`: Number of LEDs (default: 16)
- `LED_PIN`: GPIO pin for LED data (default: GPIO 18)
- `BUTTON_PIN`: GPIO pin for button (default: GPIO 2)
- `LED_BRIGHTNESS`: Brightness level 0.0-1.0 (default: 0.3)

### Audio Configuration

**test_microphone.py and test_integrated.py:**
- `RATE`: Sample rate in Hz (default: 16000)
- `CHANNELS`: Audio channels (default: 1 - mono)
- `CHUNK`: Samples per buffer (default: 1024)

### API Configuration

**.env file:**
```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

---

## Updating Your Code

When you make changes on your development machine, sync again:

```bash
# From development machine
./sync-to-pi.sh

# Or manually:
rsync -avz --progress worktree/raspi/ pi@<PI_IP>:~/adaptlight/

# Then restart service on Pi
ssh pi@<PI_IP> "sudo systemctl restart adaptlight.service"
```

---

## Troubleshooting

### Permission Errors
```bash
# Add user to groups
sudo usermod -a -G gpio,audio $USER
sudo reboot
```

### LEDs Not Working
```bash
# Check GPIO permissions
sudo chmod 666 /dev/gpiomem

# Verify wiring
# Data line must be on GPIO 18 (PWM pin)
# Power: 5V, Ground: GND
```

### Button Not Responding
```bash
# Check wiring: GPIO 2 to button, button to GND
# Test with: sudo python3 test_button.py
```

### Microphone Not Found
```bash
# List audio devices
arecord -l

# Check USB connection
lsusb

# Install audio packages
sudo apt-get install portaudio19-dev pulseaudio
```

### API Errors
```bash
# Verify .env file
cat ~/.env

# Test connectivity
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check internet
ping -c 4 google.com
```

### Service Won't Start
```bash
# Check logs
sudo journalctl -u adaptlight.service -n 50

# Check file permissions
ls -la ~/adaptlight/main.py

# Test manually first
cd ~/adaptlight
sudo python3 main.py
```

---

## Project Structure

```
adaptlight/
├── main.py                    # Main voice-controlled application
├── led_control.py             # Simple button-toggle LED control
│
├── Test Scripts:
├── test_leds.py               # Hardware test: LED strip
├── test_button.py             # Hardware test: Button input
├── test_microphone.py         # Hardware test: USB microphone
├── test_openai.py             # API test: OpenAI connectivity
├── test_integrated.py         # Integration test: Full workflow
│
├── Configuration:
├── .env                       # Environment variables (API keys)
├── config.yaml                # AWS S3 configuration (optional)
├── config.example.yaml        # Example config file
├── requirements.txt           # Python dependencies
│
├── Documentation:
├── README.md                  # This file
├── README_RASPI.md            # Raspberry Pi specific info
├── TESTING.md                 # Testing guide
├── AWS_SETUP.md               # AWS S3 setup instructions
│
├── Core Modules:
├── core/                      # Core application logic
├── hardware/                  # Hardware control modules
├── states/                    # State machine implementation
├── voice/                     # Voice input/processing
├── utils/                     # Utility functions
└── logging/                   # Logging modules
```

---

## Additional Resources

- [TESTING.md](TESTING.md) - Comprehensive testing guide
- [AWS_SETUP.md](AWS_SETUP.md) - AWS S3 logging setup
- [README_RASPI.md](README_RASPI.md) - Raspberry Pi specific documentation

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review [TESTING.md](TESTING.md) for hardware tests
3. Check logs: `sudo journalctl -u adaptlight.service`
4. Verify hardware connections match pin table

---