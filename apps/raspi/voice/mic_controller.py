"""
MicController - On-Demand Microphone Controller for AdaptLight.

Simple design:
- Stream opens when needed (recording OR watchers active)
- Stream closes when not needed (not recording AND no watchers)
- Button just toggles recording flag, doesn't control stream lifecycle
- Frame routing based on current state (recording vs listening)

No watchdog, no processor thread, no complex state machine.
"""

import os
import time
from collections import deque
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


class MicController:
    """
    On-demand microphone controller.

    Usage:
        mic = MicController(config, volume_runtime, audio_runtime)
        mic.start()  # Init only, no stream yet

        # Main loop calls tick() to manage stream and process frames
        while running:
            mic.tick()
            time.sleep(0.1)

        # Button press toggles recording
        mic.toggle_recording(callback=voice_reactive.process_audio_data)

        # When done recording, get audio
        if not mic.is_recording:
            audio = mic.get_recording()

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
        self.config = config or {}
        self.mic_config = self.config.get('mic', {})
        self.volume_runtime = volume_runtime
        self.audio_runtime = audio_runtime
        self.state_machine = state_machine
        self.replicate_token = replicate_token
        self.device_id = device_id
        self.verbose = verbose

        # Audio settings
        self._chunk_size = self.mic_config.get('chunk_size', 1024)
        self._buffer_max_chunks = self.mic_config.get('buffer_max_chunks', 200)  # ~4.6s

        # Audio runtime config
        audio_config = self.config.get('audio', {})
        self._audio_interval_ms = audio_config.get('interval_ms', 3000)

        # PyAudio state
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream = None
        self._device_index: Optional[int] = None
        self._sample_rate: int = 44100

        # Frame buffer (callback appends, tick() processes)
        self._frame_buffer: deque = deque(maxlen=self._buffer_max_chunks)
        self._overflow_count: int = 0

        # Recording state
        self._is_recording: bool = False
        self._recording_buffer: bytearray = bytearray()
        self._recording_callback: Optional[Callable] = None
        self._recording_ready: bool = False  # True when recording finished, audio ready

        # Listening state (audio accumulation for watchers)
        self._audio_watcher_buffer: list = []
        self._last_audio_process_ms: int = 0

        # Stream lifecycle
        self._stream_open: bool = False
        self._last_open_failure: float = 0
        self._open_retry_delay: float = 5.0  # seconds

        # Hysteresis to avoid open/close churn
        self._stream_opened_at: float = 0
        self._no_need_since: float = 0
        self._min_open_duration: float = 1.0  # seconds
        self._close_delay: float = 0.5  # seconds

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
        Initialize PyAudio and find device. Does NOT open stream yet.

        Returns:
            True if ready to use, False otherwise.
        """
        if not PYAUDIO_AVAILABLE:
            if self.verbose:
                print("[Mic] PyAudio not available")
            return False

        try:
            # Initialize PyAudio (suppress ALSA errors)
            if not self._init_pyaudio():
                return False

            # Find USB microphone
            self._device_index = self._find_usb_device()
            if self._device_index is None:
                if self.verbose:
                    print("[Mic] No USB microphone found")
                self._cleanup_pyaudio()
                return False

            # Start runtime sessions
            self._start_sessions()

            if self.verbose:
                print(f"[Mic] Ready ({self._sample_rate}Hz, chunk={self._chunk_size})")
            return True

        except Exception as e:
            if self.verbose:
                print(f"[Mic] Start failed: {e}")
            self._cleanup_pyaudio()
            return False

    def stop(self):
        """Close stream and cleanup PyAudio."""
        if self.verbose:
            print("[Mic] Stopping...")

        # Close stream if open
        if self._stream_open:
            self._close_stream()

        # Stop sessions
        self._stop_sessions()

        # Cleanup PyAudio
        self._cleanup_pyaudio()

        if self.verbose:
            print(f"[Mic] Stopped. Overflows: {self._overflow_count}")

    # =========================================================================
    # Recording (button-triggered)
    # =========================================================================

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def start_recording(self, on_audio_data: Callable = None):
        """
        Start recording. Just sets flag - stream managed by tick().

        Args:
            on_audio_data: Optional callback for real-time audio (VoiceReactive LED)
        """
        if self._is_recording:
            if self.verbose:
                print("[Mic] Already recording")
            return

        self._is_recording = True
        self._recording_buffer = bytearray()
        self._recording_callback = on_audio_data
        self._recording_ready = False

        # Lock state machine transitions during recording
        if self.state_machine:
            self.state_machine.lock_transitions = True

        if self.verbose:
            print("[Mic] Recording started")

    def stop_recording(self) -> bytes:
        """
        Stop recording and return audio bytes.

        Returns:
            Raw audio bytes (16-bit mono PCM)
        """
        if not self._is_recording:
            if self.verbose:
                print("[Mic] Not recording")
            return b''

        # Drain remaining frames from buffer BEFORE clearing recording flag
        # This ensures we don't lose the tail end of the recording
        frames_drained = 0
        while self._frame_buffer:
            try:
                frame = self._frame_buffer.popleft()
                self._recording_buffer.extend(frame)
                frames_drained += 1
                if self._recording_callback:
                    try:
                        self._recording_callback(frame)
                    except Exception:
                        pass
            except IndexError:
                break

        if self.verbose and frames_drained > 0:
            print(f"[Mic] Drained {frames_drained} final frames")

        self._is_recording = False
        self._recording_callback = None

        # Capture audio
        audio_bytes = bytes(self._recording_buffer)
        self._recording_buffer = bytearray()
        self._recording_ready = True

        # Unlock state machine
        if self.state_machine:
            self.state_machine.lock_transitions = False

        if self.verbose:
            duration = len(audio_bytes) / (self._sample_rate * 2)
            print(f"[Mic] Recording stopped: {len(audio_bytes)} bytes ({duration:.1f}s)")

        return audio_bytes

    def toggle_recording(self, on_audio_data: Callable = None) -> Optional[bytes]:
        """
        Toggle recording state. Returns audio if stopping.

        Args:
            on_audio_data: Callback for voice reactive (only used when starting)

        Returns:
            Audio bytes if stopping recording, None if starting
        """
        if self._is_recording:
            return self.stop_recording()
        else:
            self.start_recording(on_audio_data)
            return None

    def get_sample_rate(self) -> int:
        """Get the microphone sample rate."""
        return self._sample_rate

    # =========================================================================
    # Tick (called from main loop)
    # =========================================================================

    def tick(self):
        """
        Called from main loop (~100ms interval).

        Manages stream lifecycle and processes buffered frames.
        """
        # Determine if we need the stream
        has_watchers = self._has_watchers()
        need_stream = self._is_recording or has_watchers

        # Manage stream lifecycle
        self._manage_stream(need_stream)

        # Process buffered frames
        if self._stream_open:
            self._process_frames(has_watchers)

    def _manage_stream(self, need_stream: bool):
        """Open or close stream based on need."""
        now = time.monotonic()

        if need_stream and not self._stream_open:
            # Need stream but not open - try to open
            if now - self._last_open_failure >= self._open_retry_delay:
                if self._open_stream():
                    self._stream_opened_at = now
                    self._no_need_since = 0

        elif not need_stream and self._stream_open:
            # Stream open but not needed - check hysteresis before closing
            # Don't close too quickly after opening
            if now - self._stream_opened_at < self._min_open_duration:
                return

            # Track how long we haven't needed the stream
            if self._no_need_since == 0:
                self._no_need_since = now
            elif now - self._no_need_since >= self._close_delay:
                self._close_stream()
                self._no_need_since = 0

        elif need_stream:
            # Stream is open and needed - reset no-need timer
            self._no_need_since = 0

    def _process_frames(self, has_watchers: bool):
        """Process all buffered frames."""
        frames_processed = 0
        max_frames = 50  # Limit per tick to avoid stalling

        while self._frame_buffer and frames_processed < max_frames:
            try:
                frame = self._frame_buffer.popleft()
            except IndexError:
                break  # Race condition, buffer emptied

            frames_processed += 1

            if self._is_recording:
                # Recording mode: save to buffer + callback
                self._recording_buffer.extend(frame)
                if self._recording_callback:
                    try:
                        self._recording_callback(frame)
                    except Exception as e:
                        if self.verbose:
                            print(f"[Mic] Recording callback error: {e}")

            elif has_watchers:
                # Listening mode: feed to watchers
                self._process_watcher_frame(frame)

    def _process_watcher_frame(self, frame: bytes):
        """Process a frame for volume/audio watchers."""
        # Compute RMS for volume
        try:
            audio = np.frombuffer(frame, dtype=np.int16)
            rms = float(np.sqrt(np.mean(np.square(audio.astype(np.float32)))))
            level = min(1.0, rms / 32768.0)
        except Exception:
            level = 0.0

        # Feed to VolumeRuntime
        if self._has_volume_watchers():
            try:
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

        # Accumulate for AudioRuntime
        if self._has_audio_watchers():
            self._audio_watcher_buffer.append(frame)

            # Process periodically
            now_ms = int(time.time() * 1000)
            if (now_ms - self._last_audio_process_ms) >= self._audio_interval_ms:
                self._process_audio_buffer()
                self._last_audio_process_ms = now_ms

    def _process_audio_buffer(self):
        """Process accumulated audio for AudioRuntime."""
        if not self._audio_watcher_buffer:
            return

        try:
            # Combine audio
            audio_data = b''.join(self._audio_watcher_buffer)
            self._audio_watcher_buffer = []

            # Skip if too short (< 0.5s)
            min_bytes = int(self._sample_rate * 0.5 * 2)
            if len(audio_data) < min_bytes:
                return

            # Check audio runtime mode
            audio_mode = getattr(self.audio_runtime, 'mode', 'transcript')
            duration_sec = len(audio_data) / (self._sample_rate * 2)

            if self.verbose:
                print(f"[Mic] Processing {duration_sec:.1f}s audio in '{audio_mode}' mode")

            if audio_mode == 'direct':
                result = self._process_audio_direct(audio_data)
            else:
                result = self._process_audio_transcript(audio_data)

            if result and result.get('emitted_events') and self._on_state_change:
                if self.verbose:
                    print(f"[Mic] Events: {result.get('emitted_events')}")
                self._on_state_change()

        except Exception as e:
            if self.verbose:
                print(f"[Mic] Audio buffer error: {e}")

    def _process_audio_transcript(self, audio_data: bytes) -> dict:
        """Process audio via transcription mode (Whisper → GPT text)."""
        transcript = self._transcribe_audio(audio_data)
        if not transcript:
            return {}

        if self.verbose:
            print(f"[Mic] Transcript: {transcript}")

        return self.audio_runtime.process_chunk(
            session_id=self._audio_session_id,
            transcript=transcript,
            chunk_meta={'source': 'mic_controller'}
        )

    def _process_audio_direct(self, audio_data: bytes) -> dict:
        """Process audio via direct mode (raw audio → GPT-4o audio)."""
        if self.verbose:
            duration_sec = len(audio_data) / (self._sample_rate * 2)
            print(f"[Mic] Direct audio: {len(audio_data)} bytes ({duration_sec:.1f}s)")

        wav_bytes = self._pcm_to_wav(audio_data)

        if self.verbose:
            print(f"[Mic] WAV encoded: {len(wav_bytes)} bytes")

        result = self.audio_runtime.process_audio_direct(
            session_id=self._audio_session_id,
            audio_bytes=wav_bytes,
            chunk_meta={'source': 'mic_controller', 'format': 'wav'}
        )

        if self.verbose:
            audio_data = result.get('audio', {})
            print(f"[Mic] Direct response: success={result.get('success')} processed={result.get('processed')}")
            if audio_data:
                print(f"[Mic] Audio data: {audio_data}")

        return result

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Convert raw PCM data to WAV format bytes."""
        import io
        import wave

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._sample_rate)
            wav_file.writeframes(pcm_data)

        return wav_buffer.getvalue()

    def _transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using Replicate Whisper."""
        if not self.replicate_token:
            if self.verbose:
                print("[Mic] No Replicate token for transcription")
            return ""

        try:
            import wave
            import tempfile
            import replicate

            if self.verbose:
                duration = len(audio_data) / (self._sample_rate * 2)
                print(f"[Mic] Transcribing {duration:.1f}s...")

            # Write temp WAV
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            with wave.open(tmp_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self._sample_rate)
                wav.writeframes(audio_data)

            try:
                os.environ['REPLICATE_API_TOKEN'] = self.replicate_token

                with open(tmp_path, 'rb') as f:
                    output = replicate.run(
                        "openai/whisper:4d50797290df275329f202e48c76360b3f22b08d28c196cbc54600319435f8d2",
                        input={
                            "audio": f,
                            "model": "large-v3",
                            "translate": False,
                            "temperature": 0,
                            "transcription": "plain text",
                        }
                    )

                if isinstance(output, dict):
                    return output.get('transcription', '').strip()
                return str(output).strip() if output else ""

            finally:
                os.unlink(tmp_path)

        except Exception as e:
            if self.verbose:
                print(f"[Mic] Transcription error: {e}")
            return ""

    # =========================================================================
    # Watcher Helpers
    # =========================================================================

    def _has_watchers(self) -> bool:
        """Check if any watchers are active."""
        return self._has_volume_watchers() or self._has_audio_watchers()

    def _has_volume_watchers(self) -> bool:
        """Check if volume watchers are active."""
        if not self.volume_runtime or not self._volume_session_id:
            return False
        try:
            return bool(self.volume_runtime._get_active_watchers())
        except Exception:
            return False

    def _has_audio_watchers(self) -> bool:
        """Check if audio watchers are active."""
        if not self.audio_runtime or not self._audio_session_id:
            return False
        try:
            return bool(self.audio_runtime._get_active_watchers())
        except Exception:
            return False

    # =========================================================================
    # Stream Management
    # =========================================================================

    def _open_stream(self) -> bool:
        """Open PyAudio stream with callback."""
        if self._stream_open:
            return True

        try:
            # Suppress ALSA errors
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_stderr = os.dup(2)
            os.dup2(devnull, 2)
            os.close(devnull)

            try:
                self._stream = self._pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self._sample_rate,
                    input=True,
                    input_device_index=self._device_index,
                    frames_per_buffer=self._chunk_size,
                    stream_callback=self._audio_callback,
                )
            finally:
                os.dup2(old_stderr, 2)
                os.close(old_stderr)

            self._stream_open = True

            # Discard initial junk frames
            time.sleep(0.1)
            self._frame_buffer.clear()

            if self.verbose:
                print("[Mic] Stream opened")

            return True

        except Exception as e:
            self._last_open_failure = time.monotonic()
            if self.verbose:
                print(f"[Mic] Stream open failed: {e}")
            return False

    def _close_stream(self):
        """Close PyAudio stream."""
        if not self._stream_open:
            return

        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
        except Exception as e:
            if self.verbose:
                print(f"[Mic] Stream close error: {e}")

        self._stream_open = False
        self._frame_buffer.clear()
        self._audio_watcher_buffer = []

        # Small delay for ALSA settling
        time.sleep(0.1)

        if self.verbose:
            print("[Mic] Stream closed")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - just buffer the frame."""
        if len(self._frame_buffer) >= self._frame_buffer.maxlen:
            self._overflow_count += 1
        self._frame_buffer.append(in_data)
        return (None, pyaudio.paContinue)

    # =========================================================================
    # PyAudio Initialization
    # =========================================================================

    def _init_pyaudio(self) -> bool:
        """Initialize PyAudio with ALSA error suppression."""
        try:
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
            if self.verbose:
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
        """Find USB audio input device."""
        if not self._pyaudio:
            return None

        try:
            # Look for USB device
            for i in range(self._pyaudio.get_device_count()):
                info = self._pyaudio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) <= 0:
                    continue

                name = str(info.get('name', '')).lower()
                if 'usb' in name:
                    self._sample_rate = int(info.get('defaultSampleRate', 44100))
                    if self.verbose:
                        print(f"[Mic] Found USB: [{i}] {info['name']} @ {self._sample_rate}Hz")
                    return i

            # Fallback: PnP device
            for i in range(self._pyaudio.get_device_count()):
                info = self._pyaudio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) <= 0:
                    continue

                name = str(info.get('name', '')).lower()
                if 'pnp' in name:
                    self._sample_rate = int(info.get('defaultSampleRate', 44100))
                    if self.verbose:
                        print(f"[Mic] Found PnP: [{i}] {info['name']} @ {self._sample_rate}Hz")
                    return i

            return None

        except Exception as e:
            if self.verbose:
                print(f"[Mic] Device search failed: {e}")
            return None

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
                if self.verbose:
                    print(f"[Mic] Volume session failed: {e}")

        if self.audio_runtime:
            try:
                session = self.audio_runtime.start_session(user_id=self.device_id)
                self._audio_session_id = session.get('session_id')
                if self.verbose:
                    print(f"[Mic] Audio session: {self._audio_session_id}")
            except Exception as e:
                if self.verbose:
                    print(f"[Mic] Audio session failed: {e}")

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
