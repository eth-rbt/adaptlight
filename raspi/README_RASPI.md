# AdaptLight - Voice-Controlled Smart Lamp for Raspberry Pi

AdaptLight is an intelligent lamp system that combines voice commands, physical button interactions, and AI-powered rule learning. The lamp learns from user interactions and can be controlled via natural language voice commands or button presses.

## Features

- **Voice Commands**: Control the lamp using natural language (e.g., "turn on the light", "make it blue")
- **Button Control**: Single click, double click, hold, and release patterns
- **State Machine**: Flexible rule-based behavior system
- **Animations**: Expression-based LED animations
- **Event Logging**: All interactions are logged (voice commands, button presses, state changes)
- **AWS Integration**: Automatic log uploads to S3 every 6 hours
- **NeoPixel Support**: Full RGB LED control for WS2812B strips

## Hardware Requirements

- Raspberry Pi (any model with GPIO)
- WS2812B NeoPixel LED strip (16 LEDs by default)
- Push button
- USB microphone (for voice commands)
- Power supply for LEDs

## Installation

### 1. Clone and Setup

```bash
cd /path/to/adaptlight/worktree
```

### 2. Setup Python Virtual Environment

```bash
# Create venv outside the project folder
cd /path/to/adaptlight
python -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
cd worktree/raspi
pip install -r requirements.txt
```

### 4. Configuration

Copy the example configuration file:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` to configure your setup:
- GPIO pin numbers
- LED count
- Voice settings
- OpenAI API key
- AWS credentials (if using cloud logging)

### 5. Hardware Connections

**LED Strip (via SPI):**
- Data pin → MOSI (GPIO 10 / Physical Pin 19)
- 5V → 5V power supply
- GND → Ground
- **Note:** Enable SPI in `sudo raspi-config` → Interface Options → SPI

**COB RGB (PWM) - optional:**
- Default pins: Red → GPIO 23, Green → GPIO 27, Blue → GPIO 22
- Configure `hardware.led_type: cob` and set `cob_max_duty_cycle` to cap brightness (0.0-1.0)
- Duty cycles are clamped to the configured max to protect the COB package

**Control Button (GPIO 2):**
- One side → GPIO 2
- Other side → Ground
- Pull-up resistor enabled in software
- Function: Toggle light on/off (default)

**Record Button (GPIO 17):**
- One side → GPIO 17
- Other side → Ground
- Pull-up resistor enabled in software
- Function: Press to start/stop voice recording

**Microphone:**
- USB microphone → USB port

## Usage

### Run the Application

```bash
python main.py
```

Or make it executable:

```bash
chmod +x main.py
./main.py
```

### Voice Commands

Examples:
- "Turn on the light"
- "Turn off the light"
- "Make it red"
- "Set the color to blue"
- "Pulse slowly"
- "Rainbow animation"

### Button Controls

**Control Button (GPIO 2):**
- **Single Click**: Toggle on/off (default rule)
- **Double Click**: Customizable via voice commands
- **Hold**: Customizable via voice commands
- **Release**: Triggered after hold

**Record Button (GPIO 17):**
- **Press once**: Start recording
- **Press again**: Stop recording and process voice command

## Directory Structure

```
worktree/
├── main.py                   # Main entry point
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
│
├── core/                    # State machine core
│   ├── state_machine.py
│   ├── state.py
│   └── rule.py
│
├── hardware/                # Hardware interfaces
│   ├── led_controller.py
│   ├── button_controller.py
│   └── hardware_config.py
│
├── voice/                   # Voice processing
│   ├── voice_input.py
│   ├── command_parser.py
│   └── audio_utils.py
│
├── logging/                 # Event logging
│   ├── event_logger.py
│   ├── log_manager.py
│   └── aws_uploader.py
│
├── states/                  # State behaviors
│   ├── light_states.py
│   ├── color_utils.py
│   └── animation_engine.py
│
├── utils/                   # Utilities
│   ├── expression_evaluator.py
│   └── time_utils.py
│
├── prompts/                 # AI prompts
│   └── parsing_prompt.py
│
└── data/                    # Runtime data
    └── logs/                # Log files
```

## Migration from JavaScript Version

This is a Python port of the JavaScript/browser version, with key differences:

| Feature | JavaScript | Python (Raspi) |
|---------|-----------|----------------|
| Input | Web textbox | Voice STT |
| Display | DOM/CSS | NeoPixel LEDs |
| Hardware | WebSerial to Arduino | Direct GPIO |
| Logging | None | Voice/button/state → S3 |

Core state machine logic remains identical.

