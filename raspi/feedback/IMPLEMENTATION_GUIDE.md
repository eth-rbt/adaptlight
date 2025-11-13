# Feedback System Implementation Guide

## ✅ What's Already Done

### 1. Volume-Reactive LED
**File**: `raspi/feedback/volume_reactive_led.py`
- Reads microphone volume in real-time
- Maps volume to LED brightness (louder = brighter)
- Uses existing `pyaudio` and `numpy` libraries
- Configurable sensitivity settings

**Usage**:
```python
from feedback.volume_reactive_led import VolumeReactiveLED

# Initialize
volume_led = VolumeReactiveLED(led_controller, audio_settings)

# Start volume-reactive mode (green)
volume_led.start(color=(0, 255, 0))

# Stop and clear
volume_led.stop()

# Adjust sensitivity if needed
volume_led.set_sensitivity(min_brightness=0.1, max_brightness=1.0, threshold=500, scale=5000)
```

### 2. LED Feedback for Commands
**Already exists** in `led_controller.py`:
- `flash_success(flashes=3, duration=0.2)` - Green blink for rule changes
- `flash_error(flashes=3, duration=0.3)` - Red blink for no changes

### 3. Audio Playback
**Already exists**: `AudioPlayer` in `voice/audio_player.py`
- Uses `pygame` for WAV playback
- `play_sound(sound_path, blocking=False)`

### 4. WAV Files Folder
**Created**: `raspi/wav/` with README
- Need to record: `prompt_negative.wav` and `prompt_positive.wav`
- Format: 44.1kHz, 16-bit, mono WAV

### 5. AWS Upload Infrastructure
**Already exists**: `AWSUploader` in `event_logging/aws_uploader.py`
- S3 client initialized
- Upload methods available

---

## 🔧 What Needs to Be Implemented

### Step 1: Add Feedback Upload Method to AWSUploader

**File**: `raspi/event_logging/aws_uploader.py`

Add this method:
```python
def upload_feedback(self, audio_file_path, feedback_type, metadata):
    """
    Upload user feedback audio to S3.

    Args:
        audio_file_path: Path to recorded audio file
        feedback_type: "positive" or "negative"
        metadata: Dict with context (timestamp, rules, state, etc.)

    Returns:
        True if upload succeeded, False otherwise
    """
    if not self.s3_client:
        print("S3 client not available")
        return False

    try:
        # Create S3 key with feedback type and timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        s3_key = f"feedback/{feedback_type}/{timestamp}.wav"

        # Upload audio file
        self.s3_client.upload_file(
            audio_file_path,
            self.s3_bucket,
            s3_key
        )

        # Upload metadata JSON
        import json
        metadata_key = f"feedback/{feedback_type}/{timestamp}_metadata.json"
        metadata_json = json.dumps(metadata, indent=2)
        self.s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=metadata_key,
            Body=metadata_json.encode('utf-8')
        )

        print(f"  ✅ Uploaded feedback to s3://{self.s3_bucket}/{s3_key}")
        return True

    except Exception as e:
        print(f"  ❌ Failed to upload feedback: {e}")
        return False
```

### Step 2: Add Change Detection to CommandParser

**File**: `raspi/voice/command_parser.py` or create new file

Add this method:
```python
def detect_changes(before_rules, after_rules, tool_calls):
    """
    Detect if rules were actually changed.

    Args:
        before_rules: Rules before parsing
        after_rules: Rules after tool calls
        tool_calls: List of tool calls executed

    Returns:
        Dict: {"changed": bool, "feedback_color": "red"|"green"}
    """
    # No tool calls = nothing happened
    if not tool_calls:
        return {"changed": False, "feedback_color": "red"}

    # Compare rules
    if before_rules == after_rules:
        return {"changed": False, "feedback_color": "red"}

    # Rules changed
    return {"changed": True, "feedback_color": "green"}
```

### Step 3: Create Feedback Button Listener

**File**: `raspi/feedback/button_listener.py` (NEW)

```python
"""
Feedback button listener for user feedback collection.
Handles red (negative) and green (positive) feedback buttons.
"""

import threading
try:
    import gpiozero
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: gpiozero not available")


class FeedbackButtonListener:
    """Listens for feedback button presses and triggers recording flow."""

    def __init__(self, led_controller, voice_input, audio_player, aws_uploader, config):
        """
        Initialize feedback button listener.

        Args:
            led_controller: LEDController instance
            voice_input: VoiceInput instance
            audio_player: AudioPlayer instance
            aws_uploader: AWSUploader instance
            config: Hardware config with GPIO pins
        """
        self.led_controller = led_controller
        self.voice_input = voice_input
        self.audio_player = audio_player
        self.aws_uploader = aws_uploader
        self.config = config

        self.feedback_state = "IDLE"  # IDLE, RECORDING_NEGATIVE, RECORDING_POSITIVE
        self.current_recording = None

        # Initialize buttons if GPIO available
        if GPIO_AVAILABLE:
            # TODO: Get pin numbers from config
            # self.red_button = gpiozero.Button(config['feedback_button_red'])
            # self.green_button = gpiozero.Button(config['feedback_button_green'])
            # self.red_button.when_pressed = self.on_red_button
            # self.green_button.when_pressed = self.on_green_button
            pass

    def on_red_button(self):
        """Handle red (negative) feedback button press."""
        if self.feedback_state != "IDLE":
            return

        print("🔴 Negative feedback button pressed")
        self.feedback_state = "RECORDING_NEGATIVE"

        # Play prompt
        self.audio_player.play_sound("wav/prompt_negative.wav", blocking=True)

        # Start recording
        self.voice_input.start_recording()
        print("  Recording negative feedback... press voice button to finish")

    def on_green_button(self):
        """Handle green (positive) feedback button press."""
        if self.feedback_state != "IDLE":
            return

        print("🟢 Positive feedback button pressed")
        self.feedback_state = "RECORDING_POSITIVE"

        # Play prompt
        self.audio_player.play_sound("wav/prompt_positive.wav", blocking=True)

        # Start recording
        self.voice_input.start_recording()
        print("  Recording positive feedback... press voice button to finish")

    def on_voice_button_in_feedback_mode(self):
        """
        Handle voice button press when in feedback recording mode.
        This should be called by the main voice button handler.

        Returns:
            True if handled (was in feedback mode), False if not
        """
        if self.feedback_state == "IDLE":
            return False  # Not in feedback mode

        # Stop recording
        audio_file = self.voice_input.stop_recording()

        if audio_file:
            # Determine feedback type
            feedback_type = "negative" if self.feedback_state == "RECORDING_NEGATIVE" else "positive"

            # Create metadata
            metadata = {
                "type": feedback_type,
                "timestamp": str(datetime.now(timezone.utc)),
                "current_rules": [],  # TODO: Get from state machine
                "current_state": "",  # TODO: Get from state machine
            }

            # Upload to AWS
            print(f"  Uploading {feedback_type} feedback...")
            self.aws_uploader.upload_feedback(audio_file, feedback_type, metadata)

        # Reset state
        self.feedback_state = "IDLE"
        return True  # Handled in feedback mode
```

### Step 4: Integrate into main.py

**File**: `raspi/main.py`

Add to initialization:
```python
from feedback.volume_reactive_led import VolumeReactiveLED
from feedback.button_listener import FeedbackButtonListener

# Initialize volume-reactive LED
self.volume_reactive_led = VolumeReactiveLED(
    self.led_controller,
    audio_settings={'chunk': 1024, 'rate': 44100, 'channels': 1}
)

# Initialize feedback button listener
self.feedback_listener = FeedbackButtonListener(
    self.led_controller,
    self.voice_input,
    self.audio_player,
    self.aws_uploader,
    self.hardware_config
)
```

Modify voice button handler:
```python
def on_voice_button_press(self):
    # Check if in feedback mode first
    if self.feedback_listener.on_voice_button_in_feedback_mode():
        return  # Handled by feedback system

    if not self.is_recording:
        # Start recording with volume-reactive LED
        self.is_recording = True
        self.volume_reactive_led.start(color=(0, 255, 0))
        self.voice_input.start_recording()
    else:
        # Stop recording
        self.volume_reactive_led.stop()
        text = self.voice_input.stop_recording()
        self.is_recording = False

        # Parse command
        result = self.command_parser.parse_command(...)

        # Detect changes for LED feedback
        changes = detect_changes(before_rules, after_rules, result['toolCalls'])
        if changes['changed']:
            self.led_controller.flash_success()
        else:
            self.led_controller.flash_error()
```

---

## 📝 Configuration Needed

Add to `config.yaml`:
```yaml
feedback:
  gpio:
    button_red: 22      # GPIO pin for negative feedback button
    button_green: 23    # GPIO pin for positive feedback button

  wav_files:
    prompt_negative: "wav/prompt_negative.wav"
    prompt_positive: "wav/prompt_positive.wav"
```

---

## 🎤 Record WAV Files

Use online TTS or record yourself:
1. "Can you please describe the problem?"
2. "Please tell us what you like"

Save as 44.1kHz, 16-bit, mono WAV format.

---

## 🧪 Testing Without Hardware

For development without GPIO buttons:
- Use keyboard input to simulate button presses
- Mock GPIO with print statements
- Test audio playback with computer speakers
- Test volume-reactive LED in simulation mode

---

## ✅ Next Steps

1. ✅ Volume-reactive LED created
2. ✅ WAV folder created
3. ⏳ Record WAV prompt files
4. ⏳ Add `upload_feedback()` to AWSUploader
5. ⏳ Create `button_listener.py`
6. ⏳ Integrate into `main.py`
7. ⏳ Configure GPIO pins
8. ⏳ Test on hardware

