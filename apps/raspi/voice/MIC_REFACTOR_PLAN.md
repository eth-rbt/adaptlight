# MicController Refactor: On-Demand Architecture

## Problem Statement

Current MicController keeps PyAudio stream always open, constantly processing frames even when not needed. This causes:
- Watchdog false positives and unnecessary restarts
- CPU usage processing frames just to discard them
- Complex mode state machine (IDLE/LISTENING/RECORDING)
- Race conditions and edge cases

## New Design: On-Demand

### Core Principle
Stream is only open when actively needed. No watchdog, no queue, no background processing.

### States

```
OFF        - No stream open, mic idle
LISTENING  - Stream open, feeding volume/audio watchers
RECORDING  - Stream open, saving for transcription (button held)
```

### State Transitions

```
                    button_press
         OFF ──────────────────────► RECORDING
          │                              │
          │ watchers_active              │ button_release
          ▼                              ▼
     LISTENING ◄─────────────────── check_watchers()
          │                              │
          │ watchers_inactive            │ no watchers
          ▼                              ▼
         OFF ◄─────────────────────── OFF
```

### Audio Frame Consumers

| Consumer | Trigger | Frame Handling |
|----------|---------|----------------|
| Recording buffer | Button held | Save all frames |
| VoiceReactive LED | Button held + callback | Feed to callback |
| VolumeRuntime | `volume_reactive.enabled` | Compute RMS, ingest |
| AudioRuntime | `audio_reactive.enabled` | Accumulate, process periodically |

### Frame Routing Logic

```python
IF mode == RECORDING:
    frames → recording_buffer
    frames → voice_reactive_callback (if provided)
    # Watchers paused during recording

ELIF mode == LISTENING:
    IF volume_watchers_active:
        frames → VolumeRuntime.ingest_frame(rms)

    IF audio_watchers_active:
        frames → audio_buffer
        IF interval_elapsed:
            process_audio_buffer()  # transcribe or direct
```

## Implementation

### New MicController Class

```python
class MicController:
    """On-demand microphone controller."""

    def __init__(self, config, volume_runtime, audio_runtime, ...):
        # Config
        self.config = config
        self.volume_runtime = volume_runtime
        self.audio_runtime = audio_runtime

        # PyAudio (initialized but not opened)
        self._pyaudio: Optional[PyAudio] = None
        self._stream: Optional[Stream] = None
        self._device_index: Optional[int] = None
        self._sample_rate: int = 44100

        # State
        self._mode: str = "off"  # "off" | "listening" | "recording"

        # Recording state
        self._recording_buffer: bytearray = bytearray()
        self._recording_callback: Optional[Callable] = None

        # Listening state (audio accumulation)
        self._audio_buffer: list = []
        self._last_audio_process_ms: int = 0

        # Sessions
        self._volume_session_id: Optional[str] = None
        self._audio_session_id: Optional[str] = None

        # Callbacks
        self._on_state_change: Optional[Callable] = None

    # ─────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Initialize PyAudio and find device. Does NOT open stream."""
        # Init PyAudio
        # Find USB device
        # Start runtime sessions
        # Return True if ready

    def stop(self):
        """Close stream if open, cleanup PyAudio."""
        # Close stream
        # Stop sessions
        # Terminate PyAudio

    # ─────────────────────────────────────────────────────────────
    # Recording (button-triggered)
    # ─────────────────────────────────────────────────────────────

    def start_recording(self, on_audio_data: Callable = None):
        """Open stream if needed, switch to RECORDING mode."""
        # If stream not open, open it
        # Set mode = "recording"
        # Clear recording buffer
        # Store callback
        # Lock state machine transitions

    def stop_recording(self) -> bytes:
        """Stop recording, return audio, check watchers for next mode."""
        # Capture buffer
        # Clear recording state
        # Unlock state machine
        # Check watchers → LISTENING or OFF
        # Return audio bytes

    # ─────────────────────────────────────────────────────────────
    # Tick (called from main loop)
    # ─────────────────────────────────────────────────────────────

    def tick(self):
        """
        Called from main loop (~100ms interval).
        Manages stream based on watcher state.
        Processes frames when in LISTENING mode.
        """
        # If RECORDING, do nothing (button has priority)
        if self._mode == "recording":
            return

        # Check if watchers need the mic
        has_volume = self._has_volume_watchers()
        has_audio = self._has_audio_watchers()
        need_stream = has_volume or has_audio

        # Open/close stream as needed
        if need_stream and self._stream is None:
            self._open_stream()
            self._mode = "listening"
        elif not need_stream and self._stream is not None:
            self._close_stream()
            self._mode = "off"
            return

        # Process frames if listening
        if self._mode == "listening":
            self._process_listening_frames(has_volume, has_audio)

    # ─────────────────────────────────────────────────────────────
    # Stream Management
    # ─────────────────────────────────────────────────────────────

    def _open_stream(self) -> bool:
        """Open PyAudio stream (blocking read mode)."""
        # Open stream with blocking reads (no callback)
        # Log open event

    def _close_stream(self):
        """Close PyAudio stream."""
        # Stop and close stream
        # Small delay for ALSA settling
        # Log close event

    def _read_frames(self, num_chunks: int = 1) -> list[bytes]:
        """Read available frames from stream (non-blocking)."""
        # Read with exception_on_overflow=False
        # Return list of frame bytes

    # ─────────────────────────────────────────────────────────────
    # Frame Processing
    # ─────────────────────────────────────────────────────────────

    def _process_listening_frames(self, has_volume: bool, has_audio: bool):
        """Process frames for volume and/or audio watchers."""
        frames = self._read_frames()

        for frame in frames:
            if has_volume:
                level = self._compute_rms(frame)
                self.volume_runtime.ingest_frame(
                    session_id=self._volume_session_id,
                    level=level
                )

            if has_audio:
                self._audio_buffer.append(frame)

        # Process audio buffer periodically
        if has_audio:
            now_ms = int(time.time() * 1000)
            interval = self.config.get('audio', {}).get('interval_ms', 3000)
            if (now_ms - self._last_audio_process_ms) >= interval:
                self._process_audio_buffer()
                self._last_audio_process_ms = now_ms

    def _process_recording_frame(self, frame: bytes):
        """Process a frame during recording."""
        self._recording_buffer.extend(frame)
        if self._recording_callback:
            self._recording_callback(frame)

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _has_volume_watchers(self) -> bool:
        if not self.volume_runtime or not self._volume_session_id:
            return False
        return bool(self.volume_runtime._get_active_watchers())

    def _has_audio_watchers(self) -> bool:
        if not self.audio_runtime or not self._audio_session_id:
            return False
        return bool(self.audio_runtime._get_active_watchers())

    def _compute_rms(self, frame: bytes) -> float:
        """Compute RMS level from frame."""
        audio = np.frombuffer(frame, dtype=np.int16)
        rms = np.sqrt(np.mean(np.square(audio.astype(np.float32))))
        return min(1.0, rms / 32768.0)

    @staticmethod
    def _compute_rms(frame: bytes) -> float:
        audio = np.frombuffer(frame, dtype=np.int16)
        rms = np.sqrt(np.mean(np.square(audio.astype(np.float32))))
        return min(1.0, rms / 32768.0)
```

### Changes to main.py

```python
# In main loop, add tick call:
def run(self):
    while self.running:
        # Existing: tick API runtime
        self._tick_api_runtime()

        # NEW: tick mic controller
        if self.mic_controller:
            self.mic_controller.tick()

        time.sleep(0.1)
```

### Recording Flow (button press)

```python
def _handle_record_button(self):
    if self.is_recording:
        # STOP
        self.is_recording = False
        if self.voice_reactive:
            self.voice_reactive.stop()

        audio_bytes = self.mic_controller.stop_recording()
        transcript = self._transcribe_audio(audio_bytes)
        # ... process transcript ...
    else:
        # START
        self.is_recording = True
        callback = self.voice_reactive.process_audio_data if self.voice_reactive else None
        self.mic_controller.start_recording(on_audio_data=callback)
```

## What Gets Removed

1. **Watchdog thread** - No longer needed, stream opens/closes cleanly
2. **Queue-based buffering** - Use blocking reads instead
3. **Processor thread** - tick() handles processing synchronously
4. **IDLE mode** - Replaced by "off" with no stream
5. **Complex restart logic** - Simple open/close
6. **Stream gate/locks** - No concurrent access

## What Gets Simplified

1. **Mode state** - Just 3 states: off, listening, recording
2. **Frame routing** - Clear priority: recording > listening
3. **Error handling** - If open fails, log and return False
4. **Lifecycle** - start() inits, tick() runs, stop() cleans up

## Testing Plan

1. **No watchers** - Mic should stay off, tick() does nothing
2. **Volume watcher active** - Stream opens, RMS computed
3. **Audio watcher active** - Stream opens, audio accumulated
4. **Both watchers** - Both consumers fed
5. **Button press** - Stream opens (or stays open), recording starts
6. **Button release with watchers** - Recording stops, stays in listening
7. **Button release no watchers** - Recording stops, stream closes
8. **State change removes watchers** - Stream closes
9. **State change adds watchers** - Stream opens

## Risk Mitigation

1. **ALSA settling** - 100ms delay after close before reopen
2. **Open failures** - Catch exception, log, return False
3. **Frame read errors** - Catch overflow, continue
4. **Graceful degradation** - If mic fails, app continues without audio features

---

## Codex Review Feedback (Incorporated)

### Issue 1: Recording Mode Frame Reading
**Problem:** tick() is skipped during recording, so frames won't be read.
**Solution:** Recording uses a separate blocking loop that runs while button is held. When start_recording() is called, it enters a read loop that feeds frames to recording_buffer and voice_reactive callback. This loop runs until stop_recording() is called.

Actually, better approach: Use a callback-based stream (like current implementation) but ONLY during recording. For listening mode, use blocking reads in tick().

**Revised approach:**
- LISTENING mode: Blocking reads in tick() (simple, main loop driven)
- RECORDING mode: Callback-based stream (doesn't block main loop, captures all frames)

### Issue 2: Blocking Read in tick()
**Problem:** Blocking stream.read() could stall the 100ms main loop.
**Solution:**
- Use `stream.get_read_available()` to check how many frames are ready
- Only read what's available (non-blocking)
- Set a time budget per tick (e.g., max 50ms of reading)

```python
def _read_available_frames(self, max_chunks: int = 10) -> list[bytes]:
    """Read available frames without blocking."""
    frames = []
    try:
        available = self._stream.get_read_available()
        chunks_to_read = min(available // self._chunk_size, max_chunks)
        for _ in range(chunks_to_read):
            frame = self._stream.read(self._chunk_size, exception_on_overflow=False)
            frames.append(frame)
    except Exception:
        pass
    return frames
```

### Issue 3: Buffer Clearing
**Problem:** Stale data in buffers after transitions.
**Solution:**
- Clear `_audio_buffer` when entering OFF or RECORDING
- Clear `_recording_buffer` in start_recording()
- Discard initial frames after stream open (pop/junk)

### Issue 4: Hysteresis for Watcher Flapping
**Problem:** Rapid watcher enable/disable causes open/close churn.
**Solution:**
- Minimum dwell time: once opened, stay open for at least 1 second
- Close delay: require N consecutive ticks (e.g., 5 = 500ms) with no watchers before closing

```python
self._stream_opened_at: float = 0
self._no_watchers_since: float = 0
MIN_OPEN_DURATION = 1.0  # seconds
CLOSE_DELAY = 0.5  # seconds

def tick(self):
    ...
    # Don't close too quickly after opening
    if time.monotonic() - self._stream_opened_at < MIN_OPEN_DURATION:
        return

    # Require sustained no-watchers before closing
    if not need_stream:
        if self._no_watchers_since == 0:
            self._no_watchers_since = time.monotonic()
        elif time.monotonic() - self._no_watchers_since >= CLOSE_DELAY:
            self._close_stream()
    else:
        self._no_watchers_since = 0
```

### Issue 5: Initial Junk Frames
**Problem:** First frames after open contain pops/junk.
**Solution:** After opening stream, discard first 5-10 chunks before processing.

```python
def _open_stream(self):
    ...
    # Discard initial junk frames
    for _ in range(5):
        try:
            self._stream.read(self._chunk_size, exception_on_overflow=False)
        except:
            pass
```

### Issue 6: Open Failure Backoff
**Problem:** If open fails, don't retry every tick.
**Solution:** Track last failure time, backoff for 5 seconds before retry.

```python
self._last_open_failure: float = 0
OPEN_RETRY_DELAY = 5.0  # seconds

def _open_stream(self) -> bool:
    if time.monotonic() - self._last_open_failure < OPEN_RETRY_DELAY:
        return False  # Still in backoff

    try:
        # ... open logic ...
        return True
    except Exception as e:
        self._last_open_failure = time.monotonic()
        print(f"[Mic] Open failed, retry in {OPEN_RETRY_DELAY}s: {e}")
        return False
```

---

## Revised Architecture

### Recording Mode Strategy

Since recording needs to capture ALL frames without gaps (main loop might be busy), use callback mode for recording:

```
LISTENING mode:
  - Blocking stream (no callback)
  - tick() reads available frames
  - Simple, main-loop driven

RECORDING mode:
  - Callback stream
  - Callback writes to buffer + voice_reactive
  - Captures all frames even if main loop is slow
```

**Transition:** When button pressed, close blocking stream, open callback stream. When released, close callback stream, optionally reopen blocking stream.

**Simpler alternative:** Just use callback mode always, but only process in tick() when LISTENING. This avoids stream reopening on mode change.

### Final Decision: Callback Mode Always

Keep using callback mode (like current implementation) but simplify:
- No watchdog
- No processor thread
- Callback just puts frames in a bounded deque
- tick() pulls from deque and processes

This gives us:
- No frame loss during recording (callback captures all)
- No blocking in tick() (just deque.pop)
- Simpler than switching stream modes

```python
from collections import deque

class MicController:
    def __init__(self, ...):
        self._frame_buffer = deque(maxlen=100)  # ~2.3s at 1024/44100
        ...

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - just buffer the frame."""
        self._frame_buffer.append(in_data)
        return (None, pyaudio.paContinue)

    def tick(self):
        """Process buffered frames based on mode."""
        while self._frame_buffer:
            frame = self._frame_buffer.popleft()

            if self._mode == "recording":
                self._recording_buffer.extend(frame)
                if self._recording_callback:
                    self._recording_callback(frame)

            elif self._mode == "listening":
                # Feed to watchers
                ...
```

This is actually closer to current design but much simpler:
- No queue with blocking get
- No processor thread
- No watchdog
- tick() is synchronous and fast (just deque operations)
