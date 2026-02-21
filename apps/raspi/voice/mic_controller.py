"""
MicController v2 - Unified Microphone Controller for AdaptLight.

Keeps PyAudio stream always open and dispatches frames to consumers based on mode:
- IDLE: Discard frames (no active consumers)
- LISTENING: Feed to VolumeRuntime/AudioRuntime for reactive states
- RECORDING: Save for transcription + feed to VoiceReactive LED

Key design decisions:
- Stream always open (ALSA hates open/close cycles)
- Callback-based capture (non-blocking, driven by ALSA)
- Separate processor thread pulls from queue
- Watchdog monitors for stalls and restarts stream
- Uses threading.Event to gate callback during restarts
"""

import os
import queue
import threading
import time
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

try:
    import pyaudio
    import numpy as np
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

if TYPE_CHECKING:
    from brain.processing.volume_runtime import VolumeRuntime
    from brain.processing.audio_runtime import AudioRuntime
    from brain.core.state_machine import StateMachine


class MicMode(Enum):
    """Microphone operating modes."""
    IDLE = "idle"           # Discard frames, no active consumers
    LISTENING = "listening" # Feed to VolumeRuntime/AudioRuntime
    RECORDING = "recording" # Save for transcription + VoiceReactive


class MicController:
    """
    Unified microphone controller.

    Usage:
        mic = MicController(config, volume_runtime, audio_runtime)
        mic.start()

        # When button pressed:
        mic.start_recording(on_audio_data=voice_reactive.process_audio_data)

        # When button released:
        audio_bytes = mic.stop_recording()
        transcript = transcribe(audio_bytes)

        # Cleanup:
        mic.stop()
    """

    def __init__(
        self,
        config: dict = None,
        volume_runtime: Optional["VolumeRuntime"] = None,
        audio_runtime: Optional["AudioRuntime"] = None,
        state_machine: Optional["StateMachine"] = None,
        replicate_token: str = None,
        device_id: str = "lamp1",
        verbose: bool = False,
    ):
        """
        Initialize the mic controller.

        Args:
            config: Configuration dict with 'mic' section
            volume_runtime: VolumeRuntime for volume-reactive states
            audio_runtime: AudioRuntime for audio-reactive states
            state_machine: StateMachine for transition locking
            replicate_token: Replicate API token for transcription
            device_id: Device identifier for sessions
            verbose: Enable verbose logging
        """
        self.config = config or {}
        self.mic_config = self.config.get('mic', {})
        self.volume_runtime = volume_runtime
        self.audio_runtime = audio_runtime
        self.state_machine = state_machine
        self.replicate_token = replicate_token
        self.device_id = device_id
        self.verbose = verbose

        # Audio config
        self._chunk_size = self.mic_config.get('chunk_size', 1024)
        self._queue_size = self.mic_config.get('queue_size', 1000)

        # Watchdog config
        self._watchdog_grace_sec = self.mic_config.get('watchdog_grace_sec', 3.0)
        self._watchdog_stall_sec = self.mic_config.get('watchdog_stall_sec', 5.0)
        self._max_restarts = self.mic_config.get('max_restarts', 3)
        self._restart_cooldown_sec = self.mic_config.get('restart_cooldown_sec', 0.5)

        # Audio runtime config
        audio_config = self.config.get('audio', {})
        self._transcription_interval_ms = audio_config.get('interval_ms', 3000)

        # PyAudio state
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream = None
        self._device_index: Optional[int] = None
        self._sample_rate: int = 44100

        # Threading primitives
        self._lock = threading.Lock()
        self._stream_gate = threading.Event()  # Gates callback writes
        self._restart_lock = threading.Lock()  # Prevents concurrent restarts
        self._queue: queue.Queue = queue.Queue(maxsize=self._queue_size)

        # Threads
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None

        # State
        self._mode = MicMode.IDLE
        self._stream_healthy = False
        self._restart_count = 0

        # Timing (use monotonic for reliability)
        self._last_frame_time = time.monotonic()
        self._stream_start_time = 0.0

        # Metrics
        self._frames_in = 0
        self._frames_out = 0
        self._drops = 0
        self._overflows = 0

        # Recording mode state
        self._recording_buffer: bytearray = bytearray()
        self._recording_callback: Optional[Callable] = None

        # Listening mode state
        self._audio_buffer: list = []
        self._last_transcription_ms = 0

        # Sessions
        self._volume_session_id: Optional[str] = None
        self._audio_session_id: Optional[str] = None

        # Callbacks
        self._on_state_change: Optional[Callable] = None

    def set_on_state_change(self, callback: Callable):
        """Set callback for when audio events trigger state changes."""
        self._on_state_change = callback

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self) -> bool:
        """
        Start the mic controller.

        Returns:
            True if started successfully, False otherwise.
        """
        if not PYAUDIO_AVAILABLE:
            print("[Mic] PyAudio not available")
            return False

        if self._running:
            print("[Mic] Already running")
            return True

        try:
            # Initialize PyAudio
            if not self._init_pyaudio():
                return False

            # Find USB device
            self._device_index = self._find_usb_device()
            if self._device_index is None:
                print("[Mic] No USB microphone found")
                self._cleanup_pyaudio()
                return False

            # Start sessions
            self._start_sessions()

            # Open stream
            self._stream = self._open_stream()
            if self._stream is None:
                print("[Mic] Failed to open stream")
                self._cleanup_pyaudio()
                return False

            # Mark as running
            self._running = True
            self._stream_healthy = True
            self._stream_gate.set()  # Allow callback to write
            self._last_frame_time = time.monotonic()
            self._stream_start_time = time.monotonic()

            # Start stream
            self._stream.start_stream()

            # Start threads
            self._processor_thread = threading.Thread(
                target=self._processor_loop,
                name="MicProcessor",
                daemon=True
            )
            self._processor_thread.start()

            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                name="MicWatchdog",
                daemon=True
            )
            self._watchdog_thread.start()

            print(f"[Mic] Started ({self._sample_rate}Hz, chunk={self._chunk_size})")
            return True

        except Exception as e:
            print(f"[Mic] Start failed: {e}")
            import traceback
            traceback.print_exc()
            self._cleanup_pyaudio()
            return False

    def stop(self):
        """Stop the mic controller and clean up resources."""
        if not self._running:
            return

        print("[Mic] Stopping...")
        self._running = False
        self._stream_gate.clear()

        # Send sentinel to unblock processor
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

        # Wait for threads
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=2.0)

        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=2.0)

        # Stop sessions
        self._stop_sessions()

        # Close stream
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                if self.verbose:
                    print(f"[Mic] Stream close error: {e}")
            self._stream = None

        # Cleanup PyAudio
        self._cleanup_pyaudio()

        # Log metrics
        print(f"[Mic] Stopped. Frames in={self._frames_in}, out={self._frames_out}, "
              f"drops={self._drops}, overflows={self._overflows}")

    # =========================================================================
    # Recording Mode (button-triggered)
    # =========================================================================

    def start_recording(self, on_audio_data: Callable = None):
        """
        Switch to recording mode (button pressed).

        Args:
            on_audio_data: Callback for real-time audio (VoiceReactive LED)
        """
        if not self._running:
            print("[Mic] Not running, cannot start recording")
            return

        with self._lock:
            # Flush stale frames from queue
            flushed = 0
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    flushed += 1
                except queue.Empty:
                    break

            # Switch mode
            self._mode = MicMode.RECORDING
            self._recording_buffer = bytearray()
            self._recording_callback = on_audio_data

            print(f"[Mic] RECORDING started (flushed {flushed} stale frames, frames_in={self._frames_in})")

        # Lock state machine transitions
        if self.state_machine:
            self.state_machine.lock_transitions = True

    def stop_recording(self) -> bytes:
        """
        Stop recording and return accumulated audio bytes.

        Returns:
            Raw audio bytes (16-bit mono PCM)
        """
        try:
            with self._lock:
                # Capture buffer
                audio_bytes = bytes(self._recording_buffer)
                buffer_chunks = len(self._recording_buffer) // (self._chunk_size * 2)

                # Reset state
                self._recording_buffer = bytearray()
                self._recording_callback = None
                self._mode = MicMode.IDLE

                # Reset transcription timer
                self._last_transcription_ms = int(time.time() * 1000)

            print(f"[Mic] RECORDING stopped: {len(audio_bytes)} bytes ({buffer_chunks} chunks)")
            return audio_bytes

        finally:
            # Always unlock transitions
            if self.state_machine:
                self.state_machine.lock_transitions = False

    def get_sample_rate(self) -> int:
        """Get the microphone sample rate."""
        return self._sample_rate

    def is_recording(self) -> bool:
        """Check if currently in recording mode."""
        with self._lock:
            return self._mode == MicMode.RECORDING

    def is_healthy(self) -> bool:
        """Check if the mic stream is healthy."""
        return self._stream_healthy and self._running

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return {
            'frames_in': self._frames_in,
            'frames_out': self._frames_out,
            'drops': self._drops,
            'overflows': self._overflows,
            'restart_count': self._restart_count,
            'healthy': self._stream_healthy,
            'mode': self._mode.value,
        }

    # =========================================================================
    # PyAudio Initialization
    # =========================================================================

    def _init_pyaudio(self) -> bool:
        """Initialize PyAudio with ALSA error suppression."""
        try:
            # Suppress ALSA errors to stderr
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_stderr = os.dup(2)
            os.dup2(devnull, 2)
            os.close(devnull)

            try:
                self._pyaudio = pyaudio.PyAudio()
            finally:
                os.dup2(old_stderr, 2)
                os.close(old_stderr)

            return True

        except Exception as e:
            print(f"[Mic] PyAudio init failed: {e}")
            return False

    def _cleanup_pyaudio(self):
        """Clean up PyAudio resources."""
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass
            self._pyaudio = None

    def _find_usb_device(self) -> Optional[int]:
        """
        Find USB audio input device.

        Returns:
            Device index or None if not found.
        """
        if not self._pyaudio:
            return None

        try:
            for i in range(self._pyaudio.get_device_count()):
                info = self._pyaudio.get_device_info_by_index(i)

                # Must have input channels
                if info.get('maxInputChannels', 0) <= 0:
                    continue

                name = str(info.get('name', '')).lower()

                # Look for USB device
                if 'usb' in name:
                    self._sample_rate = int(info.get('defaultSampleRate', 44100))
                    print(f"[Mic] Found USB device: [{i}] {info['name']} @ {self._sample_rate}Hz")
                    return i

            # Fallback: any input device with "pnp" in name
            for i in range(self._pyaudio.get_device_count()):
                info = self._pyaudio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) <= 0:
                    continue
                name = str(info.get('name', '')).lower()
                if 'pnp' in name:
                    self._sample_rate = int(info.get('defaultSampleRate', 44100))
                    print(f"[Mic] Found PnP device: [{i}] {info['name']} @ {self._sample_rate}Hz")
                    return i

            return None

        except Exception as e:
            print(f"[Mic] Device search failed: {e}")
            return None

    def _open_stream(self):
        """
        Open audio stream with callback.

        Returns:
            PyAudio stream or None on failure.
        """
        if not self._pyaudio or self._device_index is None:
            return None

        try:
            # Suppress ALSA errors
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_stderr = os.dup(2)
            os.dup2(devnull, 2)
            os.close(devnull)

            try:
                stream = self._pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self._sample_rate,
                    input=True,
                    input_device_index=self._device_index,
                    frames_per_buffer=self._chunk_size,
                    stream_callback=self._audio_callback,
                    start=False  # Don't start yet, we'll call start_stream()
                )
                return stream

            finally:
                os.dup2(old_stderr, 2)
                os.close(old_stderr)

        except Exception as e:
            print(f"[Mic] Stream open failed: {e}")
            return None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        PyAudio callback - runs in separate thread.

        IMPORTANT: Keep this fast, no blocking operations or logging.
        """
        # Check for overflow
        if status:
            if status & pyaudio.paInputOverflow:
                self._overflows += 1

        # Gate check (blocks during restart)
        if not self._stream_gate.is_set():
            return (None, pyaudio.paContinue)

        # Put in queue
        try:
            self._queue.put_nowait(in_data)
            self._last_frame_time = time.monotonic()
            self._frames_in += 1
        except queue.Full:
            self._drops += 1

        return (None, pyaudio.paContinue)

    # =========================================================================
    # Session Management
    # =========================================================================

    def _start_sessions(self):
        """Start VolumeRuntime and AudioRuntime sessions."""
        if self.volume_runtime:
            try:
                session = self.volume_runtime.start_session(user_id=self.device_id)
                self._volume_session_id = session.get('session_id')
                if self.verbose:
                    print(f"[Mic] Volume session: {self._volume_session_id}")
            except Exception as e:
                print(f"[Mic] Volume session start failed: {e}")

        if self.audio_runtime:
            try:
                session = self.audio_runtime.start_session(user_id=self.device_id)
                self._audio_session_id = session.get('session_id')
                if self.verbose:
                    print(f"[Mic] Audio session: {self._audio_session_id}")
            except Exception as e:
                print(f"[Mic] Audio session start failed: {e}")

    def _stop_sessions(self):
        """Stop VolumeRuntime and AudioRuntime sessions."""
        if self.volume_runtime and self._volume_session_id:
            try:
                self.volume_runtime.stop_session(self._volume_session_id)
            except Exception:
                pass
            self._volume_session_id = None

        if self.audio_runtime and self._audio_session_id:
            try:
                self.audio_runtime.stop_session(self._audio_session_id)
            except Exception:
                pass
            self._audio_session_id = None

    # =========================================================================
    # Processor Thread
    # =========================================================================

    def _processor_loop(self):
        """Main processing loop - pulls frames from queue and dispatches."""
        print("[Mic] Processor thread started")

        last_mode = None
        frame_log_interval = 100  # Log every N frames

        while self._running:
            try:
                # Get frame from queue with timeout
                try:
                    frame = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Check for sentinel (shutdown signal)
                if frame is None:
                    break

                self._frames_out += 1

                # Get current mode (snapshot)
                with self._lock:
                    mode = self._mode
                    recording_callback = self._recording_callback

                # Log mode changes
                if mode != last_mode:
                    print(f"[Mic] Mode changed: {last_mode.value if last_mode else 'None'} -> {mode.value}")
                    last_mode = mode

                # Periodic frame count log
                if self._frames_out % frame_log_interval == 0:
                    print(f"[Mic] Processor: {self._frames_out} frames processed, mode={mode.value}")

                # Dispatch based on mode
                if mode == MicMode.RECORDING:
                    self._handle_recording(frame, recording_callback)
                elif mode == MicMode.LISTENING:
                    self._handle_listening(frame)
                else:
                    # IDLE - check if we should switch to LISTENING
                    if self._has_active_watchers():
                        with self._lock:
                            if self._mode == MicMode.IDLE:
                                self._mode = MicMode.LISTENING
                                print("[Mic] Watchers active -> LISTENING")
                    # Otherwise discard frame (IDLE mode)

            except Exception as e:
                print(f"[Mic] Processor error: {e}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()

        print("[Mic] Processor thread stopped")

    def _handle_recording(self, frame: bytes, callback: Callable = None):
        """Handle frame in recording mode."""
        # Append to buffer
        self._recording_buffer.extend(frame)

        # Call voice reactive callback
        if callback:
            try:
                callback(frame)
            except Exception as e:
                print(f"[Mic] Recording callback error: {e}")

        # Log progress periodically (~every second)
        buffer_chunks = len(self._recording_buffer) // (self._chunk_size * 2)
        if buffer_chunks > 0 and buffer_chunks % 43 == 0:  # ~1s at 44100Hz/1024
            duration_sec = len(self._recording_buffer) / (self._sample_rate * 2)
            print(f"[Mic] Recording: {len(self._recording_buffer)} bytes ({duration_sec:.1f}s)")

    def _handle_listening(self, frame: bytes):
        """Handle frame in listening mode."""
        # Compute RMS
        try:
            audio_array = np.frombuffer(frame, dtype=np.int16)
            rms = float(np.sqrt(np.mean(np.square(audio_array.astype(np.float32)))))
            level = min(1.0, rms / 32768.0)
        except Exception:
            level = 0.0

        # Feed to VolumeRuntime
        if self.volume_runtime and self._volume_session_id:
            try:
                watchers = self.volume_runtime._get_active_watchers()
                if watchers:
                    result = self.volume_runtime.ingest_frame(
                        session_id=self._volume_session_id,
                        level=level,
                        rms=level,
                        peak=level
                    )
                    if result.get('processed') and self._on_state_change:
                        self._on_state_change()
            except Exception as e:
                if self.verbose:
                    print(f"[Mic] Volume ingest error: {e}")

        # Feed to AudioRuntime (accumulate and transcribe periodically)
        if self.audio_runtime and self._audio_session_id:
            try:
                watchers = self.audio_runtime._get_active_watchers()
                if watchers:
                    self._audio_buffer.append(frame)

                    now_ms = int(time.time() * 1000)
                    if (now_ms - self._last_transcription_ms) >= self._transcription_interval_ms:
                        self._process_audio_buffer()
                        self._last_transcription_ms = now_ms
                        self._audio_buffer = []
                else:
                    # No watchers, clear buffer
                    self._audio_buffer = []
            except Exception as e:
                if self.verbose:
                    print(f"[Mic] Audio processing error: {e}")

        # Check if watchers are gone -> switch to IDLE
        if not self._has_active_watchers():
            with self._lock:
                if self._mode == MicMode.LISTENING:
                    self._mode = MicMode.IDLE
                    self._audio_buffer = []
                    if self.verbose:
                        print("[Mic] No watchers -> IDLE")

    def _has_active_watchers(self) -> bool:
        """Check if any volume or audio watchers are active."""
        if self.volume_runtime and self._volume_session_id:
            try:
                if self.volume_runtime._get_active_watchers():
                    return True
            except Exception:
                pass

        if self.audio_runtime and self._audio_session_id:
            try:
                if self.audio_runtime._get_active_watchers():
                    return True
            except Exception:
                pass

        return False

    def _process_audio_buffer(self):
        """Transcribe accumulated audio and send to AudioRuntime."""
        if not self._audio_buffer:
            return

        try:
            # Combine audio
            audio_data = b''.join(self._audio_buffer)

            # Skip if too short (< 0.5s)
            min_bytes = int(self._sample_rate * 0.5 * 2)
            if len(audio_data) < min_bytes:
                return

            # Transcribe
            transcript = self._transcribe_audio(audio_data)
            if not transcript:
                return

            if self.verbose:
                print(f"[Mic] Transcript: {transcript}")

            # Send to AudioRuntime
            result = self.audio_runtime.process_chunk(
                session_id=self._audio_session_id,
                transcript=transcript,
                chunk_meta={'source': 'mic_controller'}
            )

            if result.get('emitted_events') and self._on_state_change:
                if self.verbose:
                    print(f"[Mic] Events: {result.get('emitted_events')}")
                self._on_state_change()

        except Exception as e:
            if self.verbose:
                print(f"[Mic] Audio buffer processing error: {e}")

    def _transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using Replicate Whisper."""
        if not self.replicate_token:
            if self.verbose:
                print("[Mic] Transcription skipped: no Replicate token")
            return ""

        try:
            import wave
            import tempfile
            import replicate

            if self.verbose:
                duration_sec = len(audio_data) / (self._sample_rate * 2)
                print(f"[Mic] Transcribing {len(audio_data)} bytes ({duration_sec:.1f}s)...")

            # Write to temp WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            with wave.open(tmp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self._sample_rate)
                wav_file.writeframes(audio_data)

            try:
                os.environ['REPLICATE_API_TOKEN'] = self.replicate_token

                with open(tmp_path, 'rb') as audio_file:
                    output = replicate.run(
                        "openai/whisper:4d50797290df275329f202e48c76360b3f22b08d28c196cbc54600319435f8d2",
                        input={
                            "audio": audio_file,
                            "model": "large-v3",
                            "translate": False,
                            "temperature": 0,
                            "transcription": "plain text",
                        }
                    )

                if isinstance(output, dict):
                    result = output.get('transcription', '').strip()
                elif isinstance(output, str):
                    result = output.strip()
                else:
                    result = str(output).strip()

                if self.verbose:
                    print(f"[Mic] Transcription complete: '{result}'")
                return result

            finally:
                os.unlink(tmp_path)

        except Exception as e:
            if self.verbose:
                print(f"[Mic] Transcription error: {e}")
            return ""

    # =========================================================================
    # Watchdog Thread
    # =========================================================================

    def _watchdog_loop(self):
        """Monitor stream health and restart on stalls."""
        print("[Mic] Watchdog thread started")

        # Grace period - wait for stream to stabilize
        grace_end = time.monotonic() + self._watchdog_grace_sec
        while self._running and time.monotonic() < grace_end:
            time.sleep(0.5)

        print(f"[Mic] Watchdog active (stall threshold: {self._watchdog_stall_sec}s)")

        tick_count = 0
        while self._running:
            try:
                tick_count += 1

                # Skip if unhealthy (already gave up)
                if not self._stream_healthy:
                    if tick_count % 10 == 0:  # Log every 5s
                        print(f"[Mic] Watchdog: stream unhealthy, waiting...")
                    time.sleep(1.0)
                    continue

                # Check if stream is active
                stream_active = self._stream.is_active() if self._stream else False
                if self._stream and not stream_active:
                    print("[Mic] Watchdog: stream not active, restarting...")
                    self._restart_stream()
                    continue

                # Check for stall
                silence_sec = time.monotonic() - self._last_frame_time

                # Debug log every 5 seconds
                if tick_count % 10 == 0:
                    with self._lock:
                        mode = self._mode
                    print(f"[Mic] Watchdog: mode={mode.value}, silence={silence_sec:.1f}s, "
                          f"frames_in={self._frames_in}, frames_out={self._frames_out}, "
                          f"drops={self._drops}, healthy={self._stream_healthy}")

                if silence_sec > self._watchdog_stall_sec:
                    print(f"[Mic] Watchdog: {silence_sec:.1f}s stall detected, restarting...")
                    self._restart_stream()

                time.sleep(0.5)

            except Exception as e:
                print(f"[Mic] Watchdog error: {e}")
                time.sleep(1.0)

        print("[Mic] Watchdog thread stopped")

    def _restart_stream(self):
        """Restart the audio stream after a stall or error."""
        with self._restart_lock:
            # Check restart limit
            self._restart_count += 1
            if self._restart_count > self._max_restarts:
                print(f"[Mic] Max restarts ({self._max_restarts}) reached, giving up")
                self._stream_healthy = False
                return

            print(f"[Mic] Restarting stream (attempt {self._restart_count}/{self._max_restarts})")

            # 1. Gate callback (stop writes)
            self._stream_gate.clear()

            # 2. Stop and close old stream
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception as e:
                    if self.verbose:
                        print(f"[Mic] Old stream close error: {e}")
                self._stream = None

            # 3. Drain queue
            drained = 0
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    drained += 1
                except queue.Empty:
                    break

            # 4. Cooldown
            time.sleep(self._restart_cooldown_sec)

            # 5. Open new stream
            self._stream = self._open_stream()
            if self._stream is None:
                print("[Mic] Restart failed: could not open stream")
                self._stream_healthy = False
                return

            # 6. Start stream
            try:
                self._stream.start_stream()
            except Exception as e:
                print(f"[Mic] Restart failed: could not start stream: {e}")
                self._stream_healthy = False
                return

            # 7. Reset state and ungate
            self._last_frame_time = time.monotonic()
            self._stream_start_time = time.monotonic()
            self._stream_gate.set()

            print(f"[Mic] Stream restarted (drained {drained} frames)")
