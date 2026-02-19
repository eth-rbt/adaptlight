"""
Shared vision runtime implementation.

Extracted from apps.web.main so web and raspi entrypoints can share one runtime.
"""

import base64
import json
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from .vision_shared import (
    normalize_engine,
    looks_cv_friendly,
)

if TYPE_CHECKING:
    from brain import SMgenerator

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class VisionRuntime:
    """Web runtime for camera + OpenAI VLM processing."""

    def __init__(self, smgen: "SMgenerator", config: dict = None, openai_api_key: str = None):
        self.smgen = smgen
        self.state_machine = smgen.state_machine
        self.config = config or {}
        self.enabled = self.config.get('enabled', False)
        self.mode = str(self.config.get('mode', 'polling')).lower()
        self.latest_frame_only = bool(self.config.get('latest_frame_only', True))
        self.default_model = self.config.get('model', 'gpt-4o-mini')
        self.default_interval_ms = max(2000, int(self.config.get('interval_ms', 2000)))
        self.cv_config = self.config.get('cv', {}) if isinstance(self.config.get('cv', {}), dict) else {}
        self.cv_enabled = bool(self.cv_config.get('enabled', True))
        self.cv_default_interval_ms = max(100, int(self.cv_config.get('interval_ms', 200)))  # CV can be fast (100-200ms)
        self.cv_default_detector = str(self.cv_config.get('detector', 'opencv_hog')).lower()
        self.cv_pose_model_asset = str(self.cv_config.get('pose_model_asset', 'data/models/pose_landmarker_lite.task'))
        self.default_cooldown_ms = int(self.config.get('cooldown_ms', 1500))
        self.max_image_chars = int(self.config.get('max_image_chars', 2_500_000))

        self._openai_api_key = openai_api_key
        self._openai_client = None
        self._pose_runtime = None
        self._lock = threading.Lock()
        self._sessions = {}

    def _get_client(self):
        if self._openai_client is not None:
            return self._openai_client

        if not self._openai_api_key:
            raise RuntimeError("OPENAI_API_KEY missing for vision runtime")

        from openai import OpenAI
        self._openai_client = OpenAI(api_key=self._openai_api_key)
        return self._openai_client

    def start_session(self, user_id: str = 'anonymous') -> dict:
        session_id = str(uuid.uuid4())[:12]
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._sessions[session_id] = {
                'session_id': session_id,
                'user_id': user_id,
                'active': True,
                'created_at_ms': now_ms,
                'last_analysis_ms': 0,
                'last_event_ms': {},
                'last_watcher_analysis_ms': {},
                'last_result': None,
                'processing': False,
                'latest_frame': None,
                'latest_frame_received_ms': 0,
                'received_frames': 0,
                'replaced_frames': 0,
                'prev_gray_small': None,
                'cv_signal_cache': {},
            }
        return {'session_id': session_id, 'active': True}

    def stop_session(self, session_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {'success': False, 'error': 'session not found'}
            session['active'] = False
        return {'success': True, 'session_id': session_id, 'active': False}

    def get_status(self, session_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {'success': False, 'error': 'session not found'}
            return {
                'success': True,
                'session_id': session_id,
                'active': session.get('active', False),
                'last_analysis_ms': session.get('last_analysis_ms', 0),
                'last_result': session.get('last_result'),
                'watchers': self._get_active_watchers(),
                'mode': self.mode,
                'latest_frame_only': self.latest_frame_only,
                'received_frames': int(session.get('received_frames', 0)),
                'replaced_frames': int(session.get('replaced_frames', 0)),
                'processing': bool(session.get('processing', False)),
            }

    def process_frame(self, session_id: str, image_data_url: str) -> dict:
        if self.latest_frame_only:
            return self._process_frame_latest_only(session_id=session_id, image_data_url=image_data_url)
        return self._process_frame_direct(session_id=session_id, image_data_url=image_data_url)

    def _process_frame_latest_only(self, session_id: str, image_data_url: str) -> dict:
        frame_received_ms = int(time.time() * 1000)

        if not self.enabled:
            return {'success': False, 'error': 'vision runtime disabled'}

        if not image_data_url or not isinstance(image_data_url, str):
            return {'success': False, 'error': 'image is required'}

        if len(image_data_url) > self.max_image_chars:
            return {'success': False, 'error': 'image payload too large'}

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {'success': False, 'error': 'session not found'}
            if not session.get('active'):
                return {'success': False, 'error': 'session not active'}

            session['received_frames'] = int(session.get('received_frames', 0)) + 1
            had_pending = bool(session.get('latest_frame'))
            session['latest_frame'] = image_data_url
            session['latest_frame_received_ms'] = frame_received_ms
            if had_pending:
                session['replaced_frames'] = int(session.get('replaced_frames', 0)) + 1

            if session.get('processing', False):
                return {
                    'success': True,
                    'processed': False,
                    'reason': 'queued_latest_frame',
                    'state': self.smgen.get_state(),
                    'vision_debug': {
                        'mailbox_mode': 'latest_only',
                        'queued': True,
                        'frame_received_ms': frame_received_ms,
                        'received_frames': int(session.get('received_frames', 0)),
                        'replaced_frames': int(session.get('replaced_frames', 0)),
                    }
                }

            session['processing'] = True

        final_result = None
        try:
            while True:
                with self._lock:
                    session = self._sessions.get(session_id)
                    if not session or not session.get('active'):
                        break
                    frame_to_process = session.get('latest_frame')
                    frame_to_process_ms = int(session.get('latest_frame_received_ms', frame_received_ms))
                    session['latest_frame'] = None

                if not frame_to_process:
                    break

                final_result = self._process_frame_direct(
                    session_id=session_id,
                    image_data_url=frame_to_process,
                    frame_started_ms=frame_to_process_ms,
                )

                with self._lock:
                    session = self._sessions.get(session_id)
                    if not session or not session.get('active'):
                        break
                    has_newer = bool(session.get('latest_frame'))

                if not has_newer:
                    break

            if final_result is None:
                return {
                    'success': True,
                    'processed': False,
                    'reason': 'session_inactive',
                    'state': self.smgen.get_state(),
                    'vision_debug': {
                        'mailbox_mode': 'latest_only',
                        'queued': False,
                    }
                }

            debug = final_result.get('vision_debug') if isinstance(final_result, dict) else None
            if isinstance(debug, dict):
                with self._lock:
                    session = self._sessions.get(session_id) or {}
                    debug['mailbox_mode'] = 'latest_only'
                    debug['received_frames'] = int(session.get('received_frames', 0))
                    debug['replaced_frames'] = int(session.get('replaced_frames', 0))

            return final_result

        finally:
            with self._lock:
                session = self._sessions.get(session_id)
                if session:
                    session['processing'] = False

    def _process_frame_direct(self, session_id: str, image_data_url: str, frame_started_ms: int = None) -> dict:
        """
        Simplified frame processing:
        1. Run CV or VLM watcher
        2. Write raw JSON to state_data['vision']
        3. Emit _event if present (VLM only)
        """
        if frame_started_ms is None:
            frame_started_ms = int(time.time() * 1000)

        if not self.enabled:
            return {'success': False, 'error': 'vision runtime disabled'}

        if not image_data_url or not isinstance(image_data_url, str):
            return {'success': False, 'error': 'image is required'}

        if len(image_data_url) > self.max_image_chars:
            return {'success': False, 'error': 'image payload too large'}

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {'success': False, 'error': 'session not found'}
            if not session.get('active'):
                return {'success': False, 'error': 'session not active'}

        watchers = self._get_active_watchers()
        if not watchers:
            return {
                'success': True,
                'processed': False,
                'reason': 'no_active_vision_watchers',
                'state': self.smgen.get_state(),
            }

        now_ms = int(time.time() * 1000)
        emitted_events = []

        # Process first active watcher (simplified: one watcher at a time)
        for watcher in watchers:
            watcher_key = str(watcher.get('name') or watcher.get('event') or 'watcher')
            engine = self._resolve_engine(watcher)
            interval_ms = self._resolve_interval_ms(watcher, engine)

            # Check throttling
            with self._lock:
                session = self._sessions.get(session_id) or {}
                watcher_history = session.get('last_watcher_analysis_ms', {})
                watcher_last_ms = int(watcher_history.get(watcher_key, 0) or 0)

            if watcher_last_ms and (now_ms - watcher_last_ms) < interval_ms:
                continue  # Throttled, skip this watcher

            # Run the appropriate engine
            detector = watcher.get('cv_detector', self.cv_default_detector)

            if engine == 'cv':
                output = self._analyze_with_cv(
                    session_id=session_id,
                    image_data_url=image_data_url,
                    detector=detector,
                )
            elif engine == 'hybrid':
                # Hybrid: merge CV data with VLM output
                cv_output = self._analyze_with_cv(
                    session_id=session_id,
                    image_data_url=image_data_url,
                    detector=detector,
                )
                vlm_output = self._analyze_with_vlm(
                    image_data_url=image_data_url,
                    prompt=watcher.get('prompt', ''),
                    model=watcher.get('model', self.default_model),
                    expected_event=watcher.get('event'),
                )
                # Merge: CV data + VLM data, VLM _event takes precedence
                output = {**cv_output, **vlm_output}
                output['_detector'] = 'hybrid'
            else:
                # VLM
                output = self._analyze_with_vlm(
                    image_data_url=image_data_url,
                    prompt=watcher.get('prompt', ''),
                    model=watcher.get('model', self.default_model),
                    expected_event=watcher.get('event'),
                )

            # Add timestamp
            output['_timestamp'] = now_ms

            # Write to single 'vision' key in state_data
            self.state_machine.set_data('vision', output)
            print(f"[vision_runtime] wrote to state_data['vision']: {output}")

            # Emit event if _event is present (VLM only emits events)
            if '_event' in output:
                event_name = output['_event']
                # Add vision_ prefix if not present
                if not event_name.startswith('vision_'):
                    event_name = f"vision_{event_name}"

                # Check cooldown
                cooldown_ms = int(watcher.get('cooldown_ms', self.default_cooldown_ms))
                with self._lock:
                    last_event_ms = session.get('last_event_ms', {}).get(event_name, 0)
                    can_emit = (now_ms - last_event_ms) >= cooldown_ms

                if can_emit:
                    self.smgen.trigger(event_name)
                    emitted_events.append(event_name)
                    with self._lock:
                        session.setdefault('last_event_ms', {})[event_name] = now_ms

            # Update last analysis time
            with self._lock:
                session = self._sessions.get(session_id)
                if session is not None:
                    session.setdefault('last_watcher_analysis_ms', {})[watcher_key] = now_ms
                    session['last_analysis_ms'] = now_ms

            # Only process one watcher per frame (simplification)
            break

        frame_finished_ms = int(time.time() * 1000)

        return {
            'success': True,
            'processed': True,
            'vision': self.state_machine.get_data('vision'),
            'emitted_events': emitted_events,
            'state': self.smgen.get_state(),
            'latency_ms': frame_finished_ms - frame_started_ms,
        }

    @staticmethod
    def _coerce_float(value, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _coerce_interval_ms(self, value, default: int = None, min_ms: int = 1000) -> int:
        """Interval guardrail with configurable minimum."""
        fallback = self.default_interval_ms if default is None else int(default)
        try:
            parsed = int(value)
        except Exception:
            parsed = int(fallback)
        return max(int(min_ms), parsed)

    @staticmethod
    def _normalize_engine(value: str) -> str:
        return normalize_engine(value)

    @staticmethod
    def _looks_cv_friendly(prompt: str) -> bool:
        return looks_cv_friendly(prompt)

    @staticmethod
    def _cv_detector_runtime_available(detector: str) -> bool:
        detector_name = str(detector or '').strip().lower()
        if detector_name in ('hog', 'opencv_hog', 'person', 'face', 'opencv_face', 'motion', 'opencv_motion'):
            return True
        if detector_name in ('posenet', 'pose'):
            try:
                import mediapipe as mp
                tasks = getattr(mp, 'tasks', None)
                vision_ns = getattr(tasks, 'vision', None) if tasks is not None else None
                pose_ctor = getattr(vision_ns, 'PoseLandmarker', None) if vision_ns is not None else None
                if callable(pose_ctor):
                    return True
                solutions = getattr(mp, 'solutions', None)
                pose_ns = getattr(solutions, 'pose', None) if solutions is not None else None
                legacy_ctor = getattr(pose_ns, 'Pose', None) if pose_ns is not None else None
                return callable(legacy_ctor)
            except Exception:
                return False
        return False

    def _resolve_pose_model_asset_path(self) -> Path:
        asset = Path(self.cv_pose_model_asset)
        if not asset.is_absolute():
            asset = PROJECT_ROOT / asset
        return asset

    def _smooth_session_signal(self, session_id: str, signal_key: str, raw_value: float, alpha: float = 0.35) -> float:
        """EMA smoothing for continuous CV signals stored per session."""
        try:
            raw_value = float(raw_value)
        except Exception:
            return raw_value

        alpha = max(0.05, min(1.0, float(alpha)))
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return raw_value
            signal_cache = session.setdefault('cv_signal_cache', {})
            prev_value = signal_cache.get(signal_key)
            if prev_value is None:
                smoothed = raw_value
            else:
                try:
                    prev_value = float(prev_value)
                    smoothed = (alpha * raw_value) + ((1.0 - alpha) * prev_value)
                except Exception:
                    smoothed = raw_value
            signal_cache[signal_key] = smoothed
            return smoothed

    def _get_session_signal(self, session_id: str, signal_key: str, default_value=None):
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return default_value
            signal_cache = session.get('cv_signal_cache', {})
            return signal_cache.get(signal_key, default_value)

    def _resolve_engine(self, watcher: dict) -> str:
        """
        Resolve which engine to use (simplified).

        - Explicit engine setting takes precedence
        - Auto: use CV if prompt looks CV-friendly, otherwise VLM
        """
        requested = self._normalize_engine(watcher.get('engine', 'auto'))
        if requested in ('cv', 'vlm', 'hybrid'):
            return requested

        # Auto mode: check if prompt looks CV-friendly
        detector = str(watcher.get('cv_detector') or self.cv_default_detector).lower()
        prompt = watcher.get('prompt', '')

        if detector in ('opencv_hog', 'opencv_face', 'opencv_motion', 'posenet') and self._looks_cv_friendly(prompt):
            return 'cv'
        return 'vlm'

    def _resolve_interval_ms(self, watcher: dict, effective_engine: str) -> int:
        interval_value = watcher.get('interval_ms')
        if effective_engine in ('vlm', 'hybrid'):
            default_interval = self.default_interval_ms
            min_interval = 2000
        else:
            # CV can run much faster since it's local
            default_interval = self.cv_default_interval_ms
            min_interval = 100

        return self._coerce_interval_ms(
            interval_value,
            default=default_interval,
            min_ms=min_interval,
        )

    def _get_active_watchers(self) -> list:
        """
        Get active vision watchers (simplified).

        Returns list of watchers with:
        - name, source, prompt, model, engine, cv_detector, interval_ms, cooldown_ms
        - event (for VLM only - CV doesn't emit events)
        """
        watchers = []
        current_state = self.state_machine.get_state()

        # State-level watcher
        state = self.smgen.get_state() or {}
        state_vis = state.get('vision_reactive') or {}
        state_engine = self._normalize_engine(state_vis.get('engine', state_vis.get('backend', 'auto')))
        state_prompt = state_vis.get('prompt', '')
        state_can_run = bool(state_vis.get('enabled')) and (
            bool(state_prompt) or state_engine in ('cv', 'hybrid', 'auto')
        )
        if state_can_run:
            watchers.append({
                'name': f"state:{current_state}",
                'source': 'state',
                'prompt': state_prompt,
                'model': state_vis.get('model', self.default_model),
                'engine': state_engine,
                'cv_detector': str(state_vis.get('cv_detector', state_vis.get('detector', self.cv_default_detector))).lower(),
                'interval_ms': state_vis.get('interval_ms'),
                'cooldown_ms': int(state_vis.get('cooldown_ms', self.default_cooldown_ms)),
                'event': state_vis.get('event'),  # For VLM to emit
            })

        # Rule-level watcher via trigger_config.vision
        for idx, rule in enumerate(self.state_machine.get_rules()):
            if not rule.enabled:
                continue
            if not self._state_match(rule.state1, current_state):
                continue
            config = rule.trigger_config or {}
            vis = config.get('vision') if isinstance(config, dict) else None
            if not isinstance(vis, dict) or not vis.get('enabled'):
                continue

            rule_engine = self._normalize_engine(vis.get('engine', vis.get('backend', 'auto')))
            rule_prompt = vis.get('prompt', '')

            # VLM requires a prompt
            if not rule_prompt and rule_engine == 'vlm':
                continue

            # Get event name for VLM
            event_name = vis.get('event') or rule.transition
            if event_name and not event_name.startswith('vision_'):
                event_name = f"vision_{event_name}"

            watchers.append({
                'name': f"rule:{idx}",
                'source': 'rule',
                'prompt': rule_prompt,
                'model': vis.get('model', self.default_model),
                'engine': rule_engine,
                'cv_detector': str(vis.get('cv_detector', vis.get('detector', self.cv_default_detector))).lower(),
                'interval_ms': vis.get('interval_ms'),
                'cooldown_ms': int(vis.get('cooldown_ms', self.default_cooldown_ms)),
                'event': event_name,  # For VLM to emit
            })

        return watchers  # No deduplication needed with simplified model

    @staticmethod
    def _state_match(rule_state: str, current_state: str) -> bool:
        if rule_state == '*':
            return True
        if isinstance(rule_state, str) and rule_state.endswith('/*'):
            prefix = rule_state[:-2]
            return current_state.startswith(prefix + '/')
        return rule_state == current_state

    def _analyze_with_vlm(self, image_data_url: str, prompt: str, model: str, expected_event: str = None) -> dict:
        if self.mode == 'realtime':
            return self._analyze_with_realtime_stream(
                image_data_url=image_data_url,
                prompt=prompt,
                model=model,
                expected_event=expected_event,
            )

        return self._analyze_with_responses(
            image_data_url=image_data_url,
            prompt=prompt,
            model=model,
            expected_event=expected_event,
        )

    def _build_instruction(self, expected_event: str = None) -> str:
        event_instruction = ""
        if expected_event:
            event_instruction = f"If the condition in the prompt is met, include '_event': '{expected_event}'. "

        return (
            "Analyze the image based on the user's prompt. "
            "Return only valid JSON with the values you observe. "
            f"{event_instruction}"
            "Always include '_detector': 'vlm' in your response. "
            "No markdown, no explanation, just JSON."
        )

    def _extract_output_text(self, response) -> str:
        text = getattr(response, 'output_text', None)
        if text:
            return text

        text = ''
        for item in getattr(response, 'output', []) or []:
            for content in getattr(item, 'content', []) or []:
                if getattr(content, 'type', '') in ('output_text', 'text'):
                    text += getattr(content, 'text', '')
        return text

    def _normalize_analysis(self, text: str, expected_event: str = None) -> dict:
        """Parse VLM output as raw JSON, ensure _detector is present."""
        parsed = self._parse_json_object(text)
        if not parsed:
            return {
                '_error': 'unable to parse VLM JSON output',
                '_detector': 'vlm',
            }

        # Ensure _detector is set
        if '_detector' not in parsed:
            parsed['_detector'] = 'vlm'

        return parsed

    def _analyze_with_responses(self, image_data_url: str, prompt: str, model: str, expected_event: str = None) -> dict:
        try:
            client = self._get_client()

            instruction = self._build_instruction(expected_event=expected_event)

            response = client.responses.create(
                model=model,
                max_output_tokens=180,
                input=[
                    {
                        'role': 'system',
                        'content': [{'type': 'input_text', 'text': instruction}],
                    },
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'input_text', 'text': prompt},
                            {'type': 'input_image', 'image_url': image_data_url},
                        ],
                    },
                ],
            )

            text = self._extract_output_text(response)
            return self._normalize_analysis(text=text, expected_event=expected_event)

        except Exception as e:
            return {'_error': str(e), '_detector': 'vlm'}

    def _decode_image_for_cv(self, image_data_url: str):
        try:
            import cv2
            import numpy as np

            if ',' in image_data_url:
                encoded = image_data_url.split(',', 1)[1]
            else:
                encoded = image_data_url

            buffer = base64.b64decode(encoded)
            arr = np.frombuffer(buffer, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                print(f"[CV] cv2.imdecode returned None, buffer size={len(buffer)}")
            return frame
        except Exception as e:
            print(f"[CV] decode error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _analyze_with_cv(self, session_id: str, image_data_url: str, detector: str) -> dict:
        """Run CV detector and return raw JSON output."""
        if not self.cv_enabled:
            return {'_error': 'cv runtime disabled', '_detector': 'cv'}

        frame = self._decode_image_for_cv(image_data_url)
        if frame is None:
            return {'_error': 'unable to decode image', '_detector': 'cv'}

        detector_name = str(detector or self.cv_default_detector).lower()
        if detector_name in ('hog', 'opencv_hog', 'person'):
            return self._cv_opencv_hog(frame)
        elif detector_name in ('face', 'opencv_face'):
            return self._cv_opencv_face(frame)
        elif detector_name in ('motion', 'opencv_motion'):
            return self._cv_opencv_motion(session_id, frame)
        elif detector_name in ('posenet', 'pose'):
            return self._cv_posenet(session_id, frame)
        else:
            result = self._cv_opencv_hog(frame)
            result['_fallback'] = f"unknown detector '{detector_name}', used opencv_hog"
            return result

    def _cv_opencv_hog(self, frame) -> dict:
        """Raw JSON output: person_count only."""
        try:
            import cv2

            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            boxes, weights = hog.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
            count = len(boxes)
            return {
                'person_count': count,
                '_detector': 'opencv_hog',
            }
        except Exception as e:
            return {'_error': str(e), '_detector': 'opencv_hog'}

    def _cv_opencv_face(self, frame) -> dict:
        """Raw JSON output: face_count only."""
        try:
            import cv2

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
            count = len(faces)
            return {
                'face_count': count,
                '_detector': 'opencv_face',
            }
        except Exception as e:
            return {'_error': str(e), '_detector': 'opencv_face'}

    def _cv_opencv_motion(self, session_id: str, frame) -> dict:
        """Raw JSON output: motion_score only."""
        try:
            import cv2

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (160, 90))
            small = cv2.GaussianBlur(small, (5, 5), 0)

            with self._lock:
                session = self._sessions.get(session_id) or {}
                prev = session.get('prev_gray_small')
                session['prev_gray_small'] = small

            if prev is None:
                return {
                    'motion_score': 0.0,
                    '_detector': 'opencv_motion',
                }

            diff = cv2.absdiff(prev, small)
            _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
            motion_pixels = float(cv2.countNonZero(thresh))
            total_pixels = float(thresh.shape[0] * thresh.shape[1])
            motion_score = (motion_pixels / total_pixels) if total_pixels > 0 else 0.0

            return {
                'motion_score': round(motion_score, 4),
                '_detector': 'opencv_motion',
            }
        except Exception as e:
            return {'_error': str(e), '_detector': 'opencv_motion'}

    def _cv_posenet(self, session_id: str, frame) -> dict:
        """Raw JSON output: pose_positions, hand_positions, person_count."""
        try:
            import cv2
            import mediapipe as mp

            if self._pose_runtime is None:
                tasks = getattr(mp, 'tasks', None)
                vision_ns = getattr(tasks, 'vision', None) if tasks is not None else None
                if tasks is not None and vision_ns is not None:
                    model_path = self._resolve_pose_model_asset_path()
                    if not model_path.exists():
                        return {
                            '_error': f'missing MediaPipe model at {model_path}',
                            '_detector': 'posenet',
                        }

                    base_options = mp.tasks.BaseOptions(model_asset_path=str(model_path))
                    options = vision_ns.PoseLandmarkerOptions(
                        base_options=base_options,
                        running_mode=vision_ns.RunningMode.IMAGE,
                        num_poses=1,
                        min_pose_detection_confidence=0.5,
                        min_pose_presence_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self._pose_runtime = vision_ns.PoseLandmarker.create_from_options(options)
                else:
                    solutions = getattr(mp, 'solutions', None)
                    pose_ns = getattr(solutions, 'pose', None) if solutions is not None else None
                    pose_ctor = getattr(pose_ns, 'Pose', None) if pose_ns is not None else None
                    if pose_ctor is None:
                        return {
                            '_error': 'MediaPipe runtime missing',
                            '_detector': 'posenet',
                        }
                    self._pose_runtime = pose_ctor(
                        static_image_mode=False,
                        model_complexity=0,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            pose_landmarks = None

            if hasattr(self._pose_runtime, 'detect'):
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = self._pose_runtime.detect(mp_image)
                pose_list = getattr(result, 'pose_landmarks', None) or []
                pose_landmarks = pose_list[0] if len(pose_list) > 0 else None
            else:
                result = self._pose_runtime.process(rgb)
                landmarks_obj = getattr(result, 'pose_landmarks', None)
                pose_landmarks = landmarks_obj.landmark if landmarks_obj is not None else None

            detected = pose_landmarks is not None

            pose_positions = []
            hand_positions = []
            hand_landmark_indices = {
                15: 'left_wrist',
                17: 'left_pinky',
                19: 'left_index',
                21: 'left_thumb',
                16: 'right_wrist',
                18: 'right_pinky',
                20: 'right_index',
                22: 'right_thumb',
            }

            if pose_landmarks:
                for index, landmark in enumerate(pose_landmarks):
                    x = getattr(landmark, 'x', None)
                    y = getattr(landmark, 'y', None)
                    if x is None or y is None:
                        continue
                    confidence_value = getattr(landmark, 'visibility', None)
                    if confidence_value is None:
                        confidence_value = getattr(landmark, 'presence', 0.0)
                    confidence_value = max(0.0, min(1.0, float(confidence_value or 0.0)))
                    point = {
                        'index': int(index),
                        'x': round(float(x), 4),
                        'y': round(float(y), 4),
                        'confidence': round(confidence_value, 4),
                    }
                    pose_positions.append(point)
                    hand_name = hand_landmark_indices.get(index)
                    if hand_name is not None:
                        hand_positions.append({
                            **point,
                            'name': hand_name,
                        })

            return {
                'person_count': 1 if detected else 0,
                'pose_positions': pose_positions,
                'hand_positions': hand_positions,
                '_detector': 'posenet',
            }
        except Exception as e:
            import traceback
            print(f"[posenet] Error: {e}")
            traceback.print_exc()
            return {'_error': str(e), '_detector': 'posenet'}

    def _analyze_with_realtime_stream(self, image_data_url: str, prompt: str, model: str, expected_event: str = None) -> dict:
        """
        Realtime mode using streaming output where available.
        Falls back to regular responses API when stream transport is unavailable.
        """
        try:
            client = self._get_client()
            instruction = self._build_instruction(expected_event=expected_event)
            stream_text = ''

            input_payload = [
                {
                    'role': 'system',
                    'content': [{'type': 'input_text', 'text': instruction}],
                },
                {
                    'role': 'user',
                    'content': [
                        {'type': 'input_text', 'text': prompt},
                        {'type': 'input_image', 'image_url': image_data_url},
                    ],
                },
            ]

            try:
                stream_method = getattr(getattr(client, 'responses', None), 'stream', None)
                if not callable(stream_method):
                    raise RuntimeError('OpenAI SDK stream method unavailable')

                chunks = []
                with stream_method(model=model, max_output_tokens=180, input=input_payload) as stream:
                    for event in stream:
                        event_type = getattr(event, 'type', '')
                        if event_type == 'response.output_text.delta':
                            delta = getattr(event, 'delta', '')
                            if isinstance(delta, str):
                                chunks.append(delta)
                    final_response = stream.get_final_response()

                stream_text = ''.join(chunks).strip()
                if not stream_text:
                    stream_text = self._extract_output_text(final_response)

                return self._normalize_analysis(text=stream_text, expected_event=expected_event)

            except Exception:
                pass

            # Fallback to non-stream response if stream path fails
            response = client.responses.create(
                model=model,
                max_output_tokens=180,
                input=input_payload,
            )
            text = self._extract_output_text(response)
            return self._normalize_analysis(text=text, expected_event=expected_event)

        except Exception as e:
            return {'_error': str(e), '_detector': 'vlm'}

    @staticmethod
    def _parse_json_object(text: str):
        if not text:
            return None

        stripped = text.strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass

        start = stripped.find('{')
        end = stripped.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None

        candidate = stripped[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
