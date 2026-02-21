# MicController v2 - Implementation Plan

## Overview

A unified microphone controller that keeps the audio stream always open and dispatches frames to different consumers based on mode.

## Architecture

```
USB Microphone
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│                    MicController                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  PyAudio    │───►│ FrameQueue  │───►│  Processor  │      │
│  │  Callback   │    │  (1000 max) │    │   Thread    │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│        ▲                                      │              │
│        │                          ┌───────────┴───────────┐  │
│  ┌─────────────┐                  ▼           ▼           ▼  │
│  │  Watchdog   │              IDLE      LISTENING    RECORDING│
│  │   Thread    │            (discard)   (analyze)   (save+LED)│
│  └─────────────┘                                             │
└─────────────────────────────────────────────────────────────┘
```

## File Location

`apps/raspi/voice/mic_controller.py`

## Class Structure

```python
class MicMode(Enum):
    IDLE = "idle"           # Discard frames
    LISTENING = "listening" # Feed to VolumeRuntime/AudioRuntime
    RECORDING = "recording" # Save for transcription + VoiceReactive

class MicController:
    # === Init ===
    def __init__(self, config, volume_runtime, audio_runtime, ...)

    # === Lifecycle ===
    def start(self) -> bool
    def stop(self)

    # === Recording (button-triggered) ===
    def start_recording(self, on_audio_data: Callable = None)
    def stop_recording(self) -> bytes

    # === Internal ===
    def _init_pyaudio(self)
    def _find_usb_device(self) -> int
    def _open_stream(self) -> Stream
    def _audio_callback(self, in_data, frame_count, time_info, status)
    def _processor_loop(self)
    def _watchdog_loop(self)
    def _restart_stream(self)
    def _handle_idle(self, audio_data)
    def _handle_listening(self, audio_data)
    def _handle_recording(self, audio_data)
    def _has_active_watchers(self) -> bool
    def _compute_rms(self, audio_data) -> float
```

## Configuration

From `config.yaml`:
```yaml
mic:
  chunk_size: 1024          # Samples per frame
  queue_size: 1000          # Max frames in queue
  watchdog_grace_sec: 3.0   # Wait before monitoring
  watchdog_stall_sec: 5.0   # Silence threshold
  max_restarts: 3           # Give up after N restarts
  restart_cooldown_sec: 0.5 # Wait between restarts
```

## Implementation Phases

### Phase 1: Core Infrastructure

**Files:** `mic_controller.py`

1. Create `MicMode` enum
2. Create `MicController.__init__()` with:
   - Config parsing
   - State variables (mode, running, etc.)
   - Runtime references (volume, audio)
   - Threading primitives (lock, queue, events)

3. Implement `_init_pyaudio()`:
   - Suppress ALSA stderr
   - Create PyAudio instance
   - Find USB device

4. Implement `_find_usb_device()`:
   - Iterate devices
   - Match "usb" in name
   - Return index and sample rate

5. Implement `_open_stream()`:
   - Open with callback
   - Return stream object

6. Implement `_audio_callback()`:
   - Check `_accepting_frames` flag
   - Put in queue (handle full)
   - Update `_last_frame_time`
   - Return paContinue

### Phase 2: Processor Thread

1. Implement `start()`:
   - Call `_init_pyaudio()`
   - Open stream
   - Start processor thread
   - Start watchdog thread
   - Return success

2. Implement `stop()`:
   - Set `_running = False`
   - Join threads
   - Close stream
   - Terminate PyAudio

3. Implement `_processor_loop()`:
   ```python
   while self._running:
       try:
           frame = self._queue.get(timeout=0.1)
       except Empty:
           continue

       mode = self._get_mode()

       if mode == RECORDING:
           self._handle_recording(frame)
       elif mode == LISTENING:
           self._handle_listening(frame)
       else:
           self._handle_idle(frame)
   ```

### Phase 3: Recording Mode

1. Implement `start_recording()`:
   - Lock transitions
   - Set mode to RECORDING
   - Clear recording buffer
   - Set voice reactive callback

2. Implement `stop_recording()`:
   - Set mode to IDLE
   - Unlock transitions
   - Return accumulated bytes
   - Clear callback

3. Implement `_handle_recording()`:
   - Append to buffer
   - Call voice reactive callback
   - Log progress periodically

### Phase 4: Listening Mode

1. Implement `_has_active_watchers()`:
   - Check VolumeRuntime watchers
   - Check AudioRuntime watchers

2. Implement `_handle_listening()`:
   - Compute RMS
   - Feed VolumeRuntime.ingest_frame()
   - Accumulate for AudioRuntime
   - Transcribe periodically

3. Implement `_handle_idle()`:
   - Just discard (pass)
   - Optionally check for watchers to auto-switch

### Phase 5: Watchdog

1. Implement `_watchdog_loop()`:
   ```python
   # Grace period
   time.sleep(GRACE_SEC)

   while self._running:
       if not self._stream_healthy:
           time.sleep(1)
           continue

       silence = time.time() - self._last_frame_time
       if silence > STALL_SEC:
           self._restart_stream()

       time.sleep(0.5)
   ```

2. Implement `_restart_stream()`:
   - Increment restart count
   - Check max restarts
   - Set `_accepting_frames = False`
   - Close old stream
   - Drain queue
   - Wait cooldown
   - Open new stream
   - Set `_accepting_frames = True`
   - Reset frame time

### Phase 6: Integration

**Files:** `apps/raspi/main.py`, `brain/core/state_machine.py`

1. Add `lock_transitions` to StateMachine:
   ```python
   self.lock_transitions = False

   def execute_transition(self, action):
       if self.lock_transitions:
           print(f"Transition '{action}' blocked - locked")
           return False
       # ... rest of method
   ```

2. Update `main.py`:
   - Import MicController
   - Create in `__init__`
   - Start in `run()`
   - Use for recording instead of VoiceInput
   - Pass state change callback

3. Update `_handle_record_button()`:
   - Call `mic_controller.start_recording()`
   - Call `mic_controller.stop_recording()`
   - Transcribe returned bytes

## Error Handling

| Error | Detection | Response |
|-------|-----------|----------|
| Queue full | `queue.Full` exception | Log warning, drop frame |
| ALSA error | `-9999` in error string | Restart stream |
| No frames | `time - last_frame > 5s` | Restart stream |
| Max restarts | `restart_count >= 3` | Set unhealthy, stop trying |
| Device gone | Stream open fails | Log, retry in watchdog |

## Testing Plan

1. **Basic recording**: Press button, speak, release → transcription works
2. **Double recording**: Record twice in a row → both work
3. **Rapid toggle**: Press/release quickly 10x → no crash
4. **Long recording**: Record for 60s → no frame drops
5. **Listening mode**: Set volume_reactive state → RMS values flow
6. **Mode switching**: Record while listening → recording takes priority
7. **Watchdog**: Simulate stall → auto-restart
8. **Unplug mic**: Remove USB → graceful error, no crash

## Success Criteria

- [ ] Second recording works (main bug fix)
- [ ] No frame drops in 60s recording
- [ ] VoiceReactive LED works during recording
- [ ] VolumeRuntime receives data in listening mode
- [ ] Watchdog recovers from stalls
- [ ] Clean shutdown with no errors
