# AdaptLight Raspberry Pi Testing Guide

## Overview

This document outlines the testing strategy for AdaptLight on Raspberry Pi. Tests are organized into:
- **Hardware Verification Scripts** (standalone, practical testing)
- **Unit tests** (individual components with pytest)
- **Integration tests** (combined functionality)

---

## Hardware Verification Scripts

These are standalone scripts for practical hardware testing. Run these FIRST to verify your hardware setup before running the automated test suite.

### Quick Start Hardware Tests

**Pin Connections Required:**
- **LED Strip (WS2812)**: Data → GPIO 18, Power → 5V, Ground → GND
- **Button**: Terminal 1 → GPIO 2, Terminal 2 → GND
- **USB Microphone**: Plug into any USB port

**Test Order:**

1. **LED Test** - `sudo python3 test_leds.py`
   - Verifies LED strip connection on GPIO 18
   - Tests all colors: OFF → RED → GREEN → BLUE → WHITE → Rainbow
   - Each color displays for 2 seconds

2. **Button Test** - `sudo python3 test_button.py`
   - Verifies button connection on GPIO 2
   - Counts and times each button press
   - Tests debouncing (50ms)
   - Press Ctrl+C to see results

3. **Microphone Test** - `python3 test_microphone.py`
   - Lists available audio devices
   - Tests audio levels (5 seconds)
   - Records test file: test_recording.wav
   - Play with: `aplay test_recording.wav`

4. **OpenAI API Test** - `python3 test_openai.py`
   - Loads config.yaml from current directory
   - Tests GPT text completion
   - Tests Whisper speech-to-text (if test_recording.wav exists)
   - Verifies API connectivity

5. **Integrated System Test** - `sudo python3 test_integrated.py`
   - Tests full workflow: button → record → transcribe → respond → LED feedback
   - LED colors: BLUE (idle), WHITE (listening), YELLOW (processing), GREEN (success), RED (error)
   - Press button, speak for 5 seconds, see results
   - Can run multiple test cycles

**Troubleshooting:**
- LEDs not working? Check power, connect data to MOSI (GPIO 10), run with sudo
- Enable SPI: `sudo raspi-config` → Interface Options → SPI → Enable
- Raspberry Pi 5: Use `pip install adafruit-circuitpython-neopixel-spi adafruit-blinka`
- Button not responding? Check GPIO 2 and GND connections
- No audio? Run `arecord -l`, check USB connection
- API errors? Verify openai.api_key in config.yaml

---

## Unit Tests

### 1. LED Control Test (`test_led_control.py`)

**Purpose**: Verify NeoPixel LED strip control

**Test Cases**:
- ✅ Initialize LED controller
- ✅ Set color to red (255, 0, 0)
- ✅ Set color to green (0, 255, 0)
- ✅ Set color to blue (0, 0, 255)
- ✅ Set color to white (255, 255, 255)
- ✅ Turn LEDs off (0, 0, 0)
- ✅ Set brightness levels (0.1, 0.5, 1.0)
- ✅ Fill all LEDs with same color
- ✅ Cleanup and verify LEDs off

**Hardware Required**:
- NeoPixel LED strip (16 LEDs)
- GPIO 18 connection

**Run**:
```bash
cd raspi
python test_led_control.py
```

---

### 2. Button Input Test (`test_button_input.py`)

**Purpose**: Verify button press pattern detection

**Test Cases**:
- ✅ Single click detection
- ✅ Double click detection (within 200ms window)
- ✅ Hold detection (500ms threshold)
- ✅ Release after hold detection
- ✅ Debouncing (50ms)
- ✅ Callback execution for each event type

**Hardware Required**:
- Push button connected to GPIO 2
- Ground connection

**Run**:
```bash
cd raspi
python test_button_input.py
```

**Expected Output**:
```
Testing button controller...
Press button for SINGLE CLICK... <wait for input>
✓ Single click detected
Press button for DOUBLE CLICK... <wait for input>
✓ Double click detected
Press and HOLD button... <wait for input>
✓ Hold detected
Release button... <wait for input>
✓ Release detected
```

---

### 3. Voice Recording Test (`test_voice_recording.py`)

**Purpose**: Verify audio recording from microphone

**Test Cases**:
- ✅ Detect USB microphone
- ✅ Record audio when button held
- ✅ Save to MP3 format
- ✅ Stop recording on button release
- ✅ Verify audio file created
- ✅ Play back recorded audio
- ✅ Check audio duration matches recording time

**Hardware Required**:
- USB microphone
- Recording button (GPIO 3 or configurable)

**Recording Flow**:
1. Hold recording button → Start recording
2. Speak into microphone
3. Release button → Stop recording
4. Save as MP3 file (`recordings/test_TIMESTAMP.mp3`)

**Run**:
```bash
cd raspi
python test_voice_recording.py
```

**Expected Output**:
```
Testing voice recording...
Hold recording button to start...
🔴 Recording... (speak now)
Release button to stop...
⏹️  Recording stopped
✓ Saved: recordings/test_20250106_103045.mp3
✓ Duration: 3.2s
✓ File size: 52KB
```

---

### 4. Speech-to-Text Test (`test_speech_to_text.py`)

**Purpose**: Verify STT API integration (Whisper/Google/Vosk)

**Test Cases**:
- ✅ Load audio file (MP3/WAV)
- ✅ Send to Whisper API
- ✅ Receive transcribed text
- ✅ Handle API errors
- ✅ Test with sample phrases:
  - "Turn on the light"
  - "Make it red"
  - "Pulse slowly"
  - "Turn it off"
- ✅ Verify text accuracy

**Prerequisites**:
- OpenAI API key in `config.yaml`
- Sample audio files in `test_audio/`

**Run**:
```bash
cd raspi
python test_speech_to_text.py
```

**Expected Output**:
```
Testing speech-to-text...

Test 1: test_audio/turn_on.mp3
Audio: [plays audio]
Transcription: "turn on the light"
✓ Match expected

Test 2: test_audio/make_red.mp3
Audio: [plays audio]
Transcription: "make it red"
✓ Match expected

All STT tests passed!
```

---

## Integration Tests

### Level 1: API Call Test (`test_api_basic.py`)

**Purpose**: Test OpenAI API for command parsing (no hardware)

**Test Cases**:
- ✅ Send text command to parsing API
- ✅ Receive JSON rules array
- ✅ Validate rule structure
- ✅ Test various commands:
  - "turn on the light"
  - "make it blue"
  - "pulse slowly"

**No Hardware Required** - API only

**Run**:
```bash
cd raspi
python test_api_basic.py
```

**Expected Output**:
```
Testing OpenAI API parsing...

Input: "turn on the light"
Current state: "off"
Response: [
  {
    "state1": "off",
    "transition": "voice_command",
    "state2": "on",
    "state2_param": null
  }
]
✓ Valid JSON
✓ Rule structure correct

Input: "make it blue"
Current state: "on"
Response: [
  {
    "state1": "on",
    "transition": "voice_command",
    "state2": "color",
    "state2_param": {"r": 0, "g": 0, "b": 255}
  }
]
✓ Valid JSON
✓ State-aware (uses current state)

All API tests passed!
```

---

### Level 2: API + State Manipulation Test (`test_api_state.py`)

**Purpose**: Test command parsing with state machine logic

**Test Cases**:
- ✅ Initialize state machine
- ✅ Parse command into rules
- ✅ Add rules to state machine
- ✅ Execute transitions
- ✅ Verify state changes
- ✅ Test prompt matching:
  - From "off" → "turn it red" → should go to "color"
  - From "color" → "make it pulse" → should go to "animation"
  - From "animation" → "turn it off" → should go to "off"

**No Hardware Required** - State machine only

**Run**:
```bash
cd raspi
python test_api_state.py
```

**Expected Output**:
```
Testing API + State Machine...

Test 1: off → "turn it red" → color
Current state: off
Parsed rules: [{state1: "off", transition: "voice_command", state2: "color", ...}]
Added 1 rule(s)
Executing transition: voice_command
New state: color
✓ Correct state transition
✓ Color params: r=255, g=0, b=0

Test 2: color → "make it pulse" → animation
Current state: color
Parsed rules: [{state1: "color", transition: "voice_command", state2: "animation", ...}]
Added 1 rule(s)
Executing transition: voice_command
New state: animation
✓ Correct state transition
✓ Animation params present

All state tests passed!
```

---

### Level 3: Full Integration Test (`test_full_integration.py`)

**Purpose**: End-to-end test with all components (hardware + software)

**Test Cases**:
- ✅ Initialize all components (LEDs, buttons, state machine, voice)
- ✅ Test button → LED response
- ✅ Test voice recording → transcription → parsing → LED change
- ✅ Test logging (voice commands, button events, state changes)
- ✅ Verify log files created
- ✅ Test complete workflow:
  1. Click button → LED turns on
  2. Hold recording button → Record "make it red"
  3. Release → Transcribe → Parse → LED turns red
  4. Click button → LED turns off

**Hardware Required**:
- ALL hardware (LEDs, buttons, microphone)
- Internet connection (for API calls)

**Run**:
```bash
cd raspi
sudo python test_full_integration.py
```

**Expected Output**:
```
AdaptLight Full Integration Test
================================

✓ LED Controller initialized
✓ Button Controller initialized
✓ State Machine initialized
✓ Voice Input initialized
✓ Command Parser initialized
✓ Event Logger initialized

Test 1: Button Click → LED On
Press button now...
✓ Button click detected
✓ State changed: off → on
✓ LED turned on (white)
✓ Event logged

Test 2: Voice Command → LED Color Change
Hold recording button and say "make it red"...
🔴 Recording...
✓ Recording complete
✓ Transcribed: "make it red"
✓ Parsed 1 rule(s)
✓ State changed: on → color
✓ LED color: RGB(255, 0, 0)
✓ Voice command logged

Test 3: Verify Logs
✓ Log file created: data/logs/button_events/log-2025-01-06.jsonl
✓ Log file created: data/logs/voice_commands/log-2025-01-06.jsonl
✓ Log file created: data/logs/state_changes/log-2025-01-06.jsonl

All integration tests passed! 🎉
```

---

## Test File Structure

```
raspi/
├── HARDWARE VERIFICATION SCRIPTS (run first):
├── test_leds.py                 # Hardware: LED strip verification
├── test_button.py               # Hardware: Button input verification
├── test_microphone.py           # Hardware: USB mic verification
├── test_openai.py               # Hardware: API connectivity test
├── test_integrated.py           # Hardware: Full system workflow test
│
├── UNIT TESTS (pytest):
├── test_led_control.py          # Unit test: LED control
├── test_button_input.py         # Unit test: Button patterns
├── test_voice_recording.py      # Unit test: Audio recording
├── test_speech_to_text.py       # Unit test: STT API
│
├── INTEGRATION TESTS (pytest):
├── test_api_basic.py            # Integration Level 1: API only
├── test_api_state.py            # Integration Level 2: API + State
├── test_full_integration.py     # Integration Level 3: Full E2E
│
├── TEST DATA:
├── test_audio/                  # Sample audio files for STT tests
│   ├── turn_on.mp3
│   ├── make_red.mp3
│   └── pulse.mp3
├── recordings/                  # Recorded audio output
│   └── test_*.mp3
└── test_recording.wav           # Generated by test_microphone.py
```

---

## Running All Tests

### Step 1: Hardware Verification (Run First!)
```bash
cd worktree/raspi

# Test LEDs
sudo python3 test_leds.py

# Test Button
sudo python3 test_button.py

# Test Microphone
python3 test_microphone.py

# Test OpenAI API
python3 test_openai.py

# Test Full Integration
sudo python3 test_integrated.py
```

### Step 2: Run Unit Tests (pytest)
```bash
cd worktree/raspi
python -m pytest test_led_control.py test_button_input.py test_voice_recording.py test_speech_to_text.py
```

### Step 3: Run Integration Tests (pytest)
```bash
cd worktree/raspi
python -m pytest test_api_basic.py test_api_state.py
```

### Step 4: Run Full E2E Test (requires hardware)
```bash
cd worktree/raspi
sudo python test_full_integration.py
```

### Run All Tests
```bash
cd worktree/raspi
./run_all_tests.sh
```

---

## Test Results Log

Results will be logged to `test_results.log`:

```
[2025-01-06 10:30:00] test_led_control.py: PASSED (8/8 tests)
[2025-01-06 10:30:15] test_button_input.py: PASSED (6/6 tests)
[2025-01-06 10:30:45] test_voice_recording.py: PASSED (7/7 tests)
[2025-01-06 10:31:20] test_speech_to_text.py: PASSED (5/5 tests)
[2025-01-06 10:31:45] test_api_basic.py: PASSED (3/3 tests)
[2025-01-06 10:32:10] test_api_state.py: PASSED (3/3 tests)
[2025-01-06 10:33:00] test_full_integration.py: PASSED (3/3 tests)
```

---

## Troubleshooting

### LED not working
- Check GPIO 18 connection
- Run with `sudo` for GPIO permissions
- Verify power supply to LED strip

### Button not responding
- Check GPIO 2 connection and ground
- Adjust debounce time in config
- Test with multimeter

### Audio recording fails
- Check USB microphone: `arecord -l`
- Verify permissions: `sudo usermod -a -G audio $USER`
- Test microphone: `arecord -d 3 test.wav`

### STT API errors
- Verify API key in `config.yaml`
- Check internet connection
- Test API manually: `curl https://api.openai.com/v1/audio/transcriptions`

---

## Next Steps

After all tests pass:
1. Run full system: `python main.py`
2. Monitor logs: `tail -f data/logs/**/*.jsonl`
3. Test voice commands in real environment
4. Deploy as systemd service for auto-start
