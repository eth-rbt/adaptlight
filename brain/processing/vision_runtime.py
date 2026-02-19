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
    cv_supported_fields,
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
        self.cv_default_interval_ms = max(1000, int(self.cv_config.get('interval_ms', 1000)))
        self.cv_default_detector = str(self.cv_config.get('detector', 'opencv_hog')).lower()
        self.cv_pose_model_asset = str(self.cv_config.get('pose_model_asset', 'data/models/pose_landmarker_lite.task'))
        self.default_cooldown_ms = int(self.config.get('cooldown_ms', 1500))
        self.default_min_confidence = float(self.config.get('min_confidence', 0.55))
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
                'vision_debug': {
                    'frame_started_ms': frame_started_ms,
                    'frame_finished_ms': int(time.time() * 1000),
                    'backend_latency_ms': int(time.time() * 1000) - frame_started_ms,
                    'watcher_count': 0,
                }
            }

        now_ms = int(time.time() * 1000)

        detections = []
        emitted_events = []
        processed_watchers = 0
        mapped_data_updates = []
        mapped_data_skips = []
        mapping_diagnostics = []

        prepared_watchers = []
        for watcher in watchers:
            effective_engine = self._resolve_engine(watcher)
            effective_interval_ms = self._resolve_interval_ms(watcher, effective_engine)
            prepared = dict(watcher)
            prepared['effective_engine'] = effective_engine
            prepared['effective_interval_ms'] = effective_interval_ms
            prepared_watchers.append(prepared)

        for watcher in prepared_watchers:
            watcher_key = str(watcher.get('name') or watcher.get('event') or 'watcher')
            watcher_interval_ms = int(watcher.get('effective_interval_ms', self.default_interval_ms))

            with self._lock:
                session = self._sessions.get(session_id) or {}
                watcher_history = session.get('last_watcher_analysis_ms', {})
                watcher_last_ms = int(watcher_history.get(watcher_key, 0) or 0)

            if watcher_last_ms and (now_ms - watcher_last_ms) < watcher_interval_ms:
                detections.append({
                    'watcher': watcher.get('name'),
                    'engine': watcher.get('effective_engine', 'vlm'),
                    'skipped': True,
                    'reason': 'throttled',
                    'next_in_ms': watcher_interval_ms - (now_ms - watcher_last_ms),
                })
                continue

            watcher_started = time.perf_counter()
            engine = watcher.get('effective_engine', 'vlm')
            detector = watcher.get('cv_detector', self.cv_default_detector)
            if engine in ('vlm', 'hybrid') and watcher_interval_ms < 2000:
                watcher_interval_ms = 2000

            if engine == 'cv':
                analysis = self._analyze_with_cv(
                    session_id=session_id,
                    image_data_url=image_data_url,
                    detector=detector,
                    prompt=watcher.get('prompt', ''),
                    expected_event=watcher.get('event')
                )
            elif engine == 'hybrid':
                cv_result = self._analyze_with_cv(
                    session_id=session_id,
                    image_data_url=image_data_url,
                    detector=detector,
                    prompt=watcher.get('prompt', ''),
                    expected_event=watcher.get('event')
                )
                vlm_result = self._analyze_with_vlm(
                    image_data_url=image_data_url,
                    prompt=watcher.get('prompt', ''),
                    model=watcher.get('model', self.default_model),
                    expected_event=watcher.get('event')
                )
                if not vlm_result.get('error'):
                    merged_reason = (
                        f"VLM: {vlm_result.get('reason', '')} | "
                        f"CV({detector}): {cv_result.get('reason', '')}"
                    )
                    analysis = {
                        **vlm_result,
                        'confidence': max(
                            self._coerce_float(vlm_result.get('confidence'), 0.0),
                            self._coerce_float(cv_result.get('confidence'), 0.0),
                        ),
                        'fields': {
                            **(cv_result.get('fields') if isinstance(cv_result.get('fields'), dict) else {}),
                            **(vlm_result.get('fields') if isinstance(vlm_result.get('fields'), dict) else {}),
                        },
                        'reason': merged_reason.strip(' |'),
                        'transport': 'hybrid_vlm_cv',
                        'engine': 'hybrid',
                        'cv_detector': detector,
                    }
                else:
                    analysis = dict(cv_result)
                    analysis['transport'] = 'hybrid_cv_fallback'
                    analysis['engine'] = 'hybrid'
                    analysis['cv_detector'] = detector
                    analysis['fallback_reason'] = vlm_result.get('error')
            else:
                analysis = self._analyze_with_vlm(
                    image_data_url=image_data_url,
                    prompt=watcher.get('prompt', ''),
                    model=watcher.get('model', self.default_model),
                    expected_event=watcher.get('event')
                )

            watcher_latency_ms = int((time.perf_counter() - watcher_started) * 1000)

            with self._lock:
                session = self._sessions.get(session_id)
                if session is not None:
                    session.setdefault('last_watcher_analysis_ms', {})[watcher_key] = now_ms

            processed_watchers += 1

            if analysis.get('error'):
                detections.append({
                    'watcher': watcher.get('name'),
                    'engine': engine,
                    'cv_detector': detector if engine in ('cv', 'hybrid') else None,
                    'supported_fields': sorted(list(self._cv_supported_fields(detector))) if engine in ('cv', 'hybrid') else [],
                    'error': analysis['error'],
                    'latency_ms': watcher_latency_ms,
                })
                continue

            detections.append({
                'watcher': watcher.get('name'),
                'engine': engine,
                'cv_detector': detector if engine in ('cv', 'hybrid') else None,
                'supported_fields': sorted(list(self._cv_supported_fields(detector))) if engine in ('cv', 'hybrid') else [],
                **analysis,
                'latency_ms': watcher_latency_ms,
            })

            confidence = self._coerce_float(analysis.get('confidence'), 0.0)
            min_confidence = self._coerce_float(
                watcher.get('min_confidence'),
                self.default_min_confidence
            )
            detection_positive = bool(analysis.get('detected')) and confidence >= min_confidence

            # Optional continuous numeric mapping into state_data
            # Data mapping is independent from event emission (pure plumbing)
            data_key = watcher.get('set_data_key')
            data_field = watcher.get('set_data_field')
            fields = analysis.get('fields') or {}

            if engine == 'cv':
                if not data_field:
                    if 'hand_pose' in fields:
                        data_field = 'hand_pose'
                    elif 'hand_positions' in fields:
                        data_field = 'hand_positions'
                    elif 'pose_positions' in fields:
                        data_field = 'pose_positions'
                if not data_key and data_field:
                    if data_field in ('hand_pose', 'hand_positions'):
                        data_key = 'hand_pose'
                    elif data_field == 'pose_positions':
                        data_key = 'pose_positions'
                    else:
                        data_key = str(data_field)

            if watcher.get('map_data', True):
                inferred_field = None
                if not data_field and data_key:
                    key_name = str(data_key).strip()
                    if key_name in fields:
                        inferred_field = key_name
                    else:
                        preferred_fields = [
                            'hand_pose',
                            'hand_positions',
                            'pose_positions',
                            'person_count',
                            'face_count',
                            'motion_score',
                            'pose_landmarks',
                        ]
                        for candidate in preferred_fields:
                            if candidate in fields:
                                inferred_field = candidate
                                break
                        if inferred_field is None:
                            for field_name, field_value in fields.items():
                                if field_name == 'detector':
                                    continue
                                if isinstance(field_value, (int, float, bool)):
                                    inferred_field = field_name
                                    break
                resolved_data_field = data_field or inferred_field

                diag = {
                    'watcher': watcher.get('name'),
                    'engine': engine,
                    'key': data_key,
                    'field': resolved_data_field,
                    'requested_field': data_field,
                    'available_fields': sorted(list(fields.keys())),
                }
                if not data_key:
                    diag['mapped'] = False
                    diag['reason'] = 'missing_set_data_key'
                    mapping_diagnostics.append(diag)
                    mapped_data_skips.append({
                        'watcher': watcher.get('name'),
                        'reason': 'missing_set_data_key',
                    })
                elif not resolved_data_field:
                    diag['mapped'] = False
                    diag['reason'] = 'missing_set_data_field'
                    mapping_diagnostics.append(diag)
                    mapped_data_skips.append({
                        'watcher': watcher.get('name'),
                        'reason': 'missing_set_data_field',
                    })
                elif resolved_data_field in fields:
                    value_to_set = fields[resolved_data_field]
                    self.state_machine.set_data(data_key, value_to_set)
                    diag['mapped'] = True
                    diag['reason'] = 'mapped_from_fields_inferred' if (not data_field and inferred_field) else 'mapped_from_fields'
                    diag['value'] = value_to_set
                    mapping_diagnostics.append(diag)
                    mapped_data_updates.append({
                        'watcher': watcher.get('name'),
                        'key': data_key,
                        'field': resolved_data_field,
                        'value': value_to_set,
                        'source': 'fields',
                    })
                elif resolved_data_field in analysis:
                    value_to_set = analysis.get(resolved_data_field)
                    self.state_machine.set_data(data_key, value_to_set)
                    diag['mapped'] = True
                    diag['reason'] = 'mapped_from_top_level'
                    diag['value'] = value_to_set
                    mapping_diagnostics.append(diag)
                    mapped_data_updates.append({
                        'watcher': watcher.get('name'),
                        'key': data_key,
                        'field': resolved_data_field,
                        'value': value_to_set,
                        'source': 'top_level',
                    })
                else:
                    diag['mapped'] = False
                    diag['reason'] = 'field_not_returned_by_detector'
                    mapping_diagnostics.append(diag)
                    mapped_data_skips.append({
                        'watcher': watcher.get('name'),
                        'reason': 'field_not_returned_by_detector',
                        'key': data_key,
                        'field': resolved_data_field,
                        'available_fields': sorted(list(fields.keys())),
                    })

            # Emit transition event if positive detection and not in cooldown
            if watcher.get('emit_event', True) and detection_positive and watcher.get('event'):
                event = watcher['event']
                cooldown_ms = int(watcher.get('cooldown_ms', self.default_cooldown_ms))

                with self._lock:
                    last_event_ms = session.get('last_event_ms', {}).get(event, 0)
                    can_emit = (now_ms - last_event_ms) >= cooldown_ms

                if can_emit:
                    self.smgen.trigger(event)
                    emitted_events.append(event)
                    with self._lock:
                        session['last_event_ms'][event] = now_ms

        state = self.smgen.get_state()
        frame_finished_ms = int(time.time() * 1000)
        best_detection = None
        for detection in detections:
            if detection.get('error'):
                continue
            if best_detection is None:
                best_detection = detection
                continue
            if self._coerce_float(detection.get('confidence'), 0.0) > self._coerce_float(best_detection.get('confidence'), 0.0):
                best_detection = detection

        vision_debug = {
            'frame_started_ms': frame_started_ms,
            'frame_finished_ms': frame_finished_ms,
            'backend_latency_ms': frame_finished_ms - frame_started_ms,
            'watcher_count': len(watchers),
            'best_detection': best_detection,
            'mapped_data': mapped_data_updates,
            'mapped_data_skips': mapped_data_skips,
            'mapping_diagnostics': mapping_diagnostics,
        }
        result_payload = {
            'detections': detections,
            'emitted_events': emitted_events,
            'state_name': state.get('name') if isinstance(state, dict) else None,
            'processed_at_ms': now_ms,
            'vision_debug': vision_debug,
        }

        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session['last_analysis_ms'] = now_ms
                session['last_result'] = result_payload

        if processed_watchers == 0:
            return {
                'success': True,
                'processed': False,
                'reason': 'throttled_all_watchers',
                'state': state,
                'watchers': prepared_watchers,
                'detections': detections,
                'emitted_events': emitted_events,
                'vision_debug': {
                    **vision_debug,
                    'processed_watcher_count': 0,
                },
            }

        return {
            'success': True,
            'processed': True,
            'watchers': prepared_watchers,
            'detections': detections,
            'emitted_events': emitted_events,
            'state': state,
            'vision_debug': {
                **vision_debug,
                'processed_watcher_count': processed_watchers,
            },
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
    def _cv_supported_fields(detector: str) -> set:
        return cv_supported_fields(detector)

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
        requested = self._normalize_engine(watcher.get('engine', 'auto'))
        if requested == 'cv':
            return 'cv'
        if requested == 'vlm':
            return 'vlm'
        if requested == 'hybrid':
            return 'hybrid'

        detector = str(watcher.get('cv_detector') or self.cv_default_detector).lower()
        detector_explicit = bool(watcher.get('cv_detector_explicit', False))
        prompt = watcher.get('prompt', '')

        mapping_requested = bool(watcher.get('map_data', True)) and bool(watcher.get('set_data_key')) and bool(watcher.get('set_data_field'))
        if mapping_requested:
            target_field = str(watcher.get('set_data_field', '')).strip()
            supported_cv_fields = self._cv_supported_fields(detector)
            if detector_explicit and target_field in supported_cv_fields:
                return 'cv'
            # Guardrail: arbitrary mapped fields in auto mode should use VLM
            return 'vlm'

        if detector in ('opencv_hog', 'opencv_face', 'opencv_motion', 'posenet') and self._looks_cv_friendly(prompt):
            return 'cv'
        return 'vlm'

    def _resolve_interval_ms(self, watcher: dict, effective_engine: str) -> int:
        interval_value = watcher.get('interval_ms')
        if effective_engine in ('vlm', 'hybrid'):
            default_interval = self.default_interval_ms
            min_interval = 2000
        else:
            default_interval = self.cv_default_interval_ms
            min_interval = 1000

        return self._coerce_interval_ms(
            interval_value,
            default=default_interval,
            min_ms=min_interval,
        )

    @staticmethod
    def _dedupe_watchers(watchers: list) -> list:
        """Deduplicate equivalent watchers to avoid duplicate VLM calls."""
        unique = {}
        for watcher in watchers:
            key = (
                watcher.get('source'),
                watcher.get('prompt'),
                watcher.get('event'),
                watcher.get('model'),
                watcher.get('engine'),
                watcher.get('cv_detector'),
                watcher.get('set_data_key'),
                watcher.get('set_data_field'),
                bool(watcher.get('emit_event', True)),
                bool(watcher.get('map_data', True)),
            )
            existing = unique.get(key)
            if existing is None:
                unique[key] = watcher
                continue

            existing['interval_ms'] = min(
                int(existing.get('interval_ms', 10_000)),
                int(watcher.get('interval_ms', 10_000))
            )
            existing['cooldown_ms'] = max(
                int(existing.get('cooldown_ms', 0)),
                int(watcher.get('cooldown_ms', 0))
            )
            existing['min_confidence'] = max(
                VisionRuntime._coerce_float(existing.get('min_confidence'), 0.0),
                VisionRuntime._coerce_float(watcher.get('min_confidence'), 0.0)
            )

        return list(unique.values())

    def _get_active_watchers(self) -> list:
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
            mode = str(state_vis.get('mode', 'both')).lower()
            watchers.append({
                'name': f"state:{current_state}",
                'source': 'state',
                'event': state_vis.get('event', 'vision_detected'),
                'prompt': state_prompt,
                'model': state_vis.get('model', self.default_model),
                'engine': state_engine,
                'cv_detector': str(state_vis.get('cv_detector', state_vis.get('detector', self.cv_default_detector))).lower(),
                'cv_detector_explicit': ('cv_detector' in state_vis) or ('detector' in state_vis),
                'interval_ms': state_vis.get('interval_ms'),
                'cooldown_ms': int(state_vis.get('cooldown_ms', self.default_cooldown_ms)),
                'min_confidence': self._coerce_float(state_vis.get('min_confidence'), self.default_min_confidence),
                'set_data_key': state_vis.get('set_data_key') or state_vis.get('set_data_field'),
                'set_data_field': state_vis.get('set_data_field'),
                'emit_event': mode in ('both', 'event_only', 'event'),
                'map_data': mode in ('both', 'data_only', 'data'),
            })

        # Rule-level watcher via trigger_config.vision
        for idx, rule in enumerate(self.state_machine.get_rules()):
            if not rule.enabled:
                continue
            if not self._state_match(rule.state1, current_state):
                continue
            config = rule.trigger_config or {}
            vis = config.get('vision') if isinstance(config, dict) else None
            if not isinstance(vis, dict) or not vis.get('enabled') or not vis.get('prompt'):
                continue

            # Rule watcher must target an explicit vision event.
            # Accept either vis.event or a rule.transition prefixed with "vision_".
            event_name = vis.get('event') or rule.transition
            if not isinstance(event_name, str) or not event_name.startswith('vision_'):
                continue

            mode = str(vis.get('mode', 'event_only')).lower()
            rule_engine = self._normalize_engine(vis.get('engine', vis.get('backend', 'auto')))
            rule_prompt = vis.get('prompt', '')
            if not rule_prompt and rule_engine == 'vlm':
                continue

            watchers.append({
                'name': f"rule:{idx}",
                'source': 'rule',
                'event': event_name,
                'prompt': rule_prompt,
                'model': vis.get('model', self.default_model),
                'engine': rule_engine,
                'cv_detector': str(vis.get('cv_detector', vis.get('detector', self.cv_default_detector))).lower(),
                'cv_detector_explicit': ('cv_detector' in vis) or ('detector' in vis),
                'interval_ms': vis.get('interval_ms'),
                'cooldown_ms': int(vis.get('cooldown_ms', self.default_cooldown_ms)),
                'min_confidence': self._coerce_float(vis.get('min_confidence'), self.default_min_confidence),
                'set_data_key': vis.get('set_data_key') or vis.get('set_data_field'),
                'set_data_field': vis.get('set_data_field'),
                'emit_event': mode in ('both', 'event_only', 'event'),
                'map_data': mode in ('both', 'data_only', 'data'),
            })

        return self._dedupe_watchers(watchers)

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
        return (
            "You are a strict vision detector. "
            "Return JSON only with keys: detected (boolean), confidence (0..1), event (string), fields (object), reason (string). "
            "Interpret 'person' broadly: visible face, head/shoulders, or any human body part counts as person present. "
            f"Use event='{expected_event or 'vision_detected'}' when detected is true. "
            "Do not include markdown."
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

    def _normalize_analysis(self, text: str, expected_event: str = None, transport: str = 'responses', fallback_reason: str = None) -> dict:
        parsed = self._parse_json_object(text)
        if not parsed:
            return {
                'detected': False,
                'confidence': 0.0,
                'event': expected_event or 'vision_detected',
                'fields': {},
                'reason': 'unable to parse VLM JSON output',
                'transport': transport,
                'fallback_reason': fallback_reason,
            }

        fields_obj = parsed.get('fields') if isinstance(parsed.get('fields'), dict) else {}
        for key, value in parsed.items():
            if key in ('detected', 'confidence', 'event', 'reason', 'fields'):
                continue
            if key not in fields_obj and isinstance(value, (str, int, float, bool)):
                fields_obj[key] = value

        reason_text = str(parsed.get('reason', '')).strip()
        if not reason_text:
            if bool(parsed.get('detected', False)):
                reason_text = 'Target condition detected in the frame.'
            else:
                reason_text = 'Target condition not detected in the frame.'

        return {
            'detected': bool(parsed.get('detected', False)),
            'confidence': float(parsed.get('confidence', 0.0) or 0.0),
            'event': parsed.get('event') or expected_event or 'vision_detected',
            'fields': fields_obj,
            'reason': reason_text,
            'transport': transport,
            'fallback_reason': fallback_reason,
        }

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
            return self._normalize_analysis(text=text, expected_event=expected_event, transport='responses')

        except Exception as e:
            return {'error': str(e), 'detected': False, 'confidence': 0.0, 'fields': {}}

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
            return frame
        except Exception:
            return None

    def _analyze_with_cv(self, session_id: str, image_data_url: str, detector: str, prompt: str, expected_event: str = None) -> dict:
        if not self.cv_enabled:
            return {
                'detected': False,
                'confidence': 0.0,
                'event': expected_event or 'vision_detected',
                'fields': {},
                'reason': 'cv runtime disabled',
                'transport': 'cv_disabled',
                'engine': 'cv',
                'cv_detector': detector,
            }

        frame = self._decode_image_for_cv(image_data_url)
        if frame is None:
            return {'error': 'unable to decode image for cv', 'detected': False, 'confidence': 0.0, 'fields': {}}

        detector_name = str(detector or self.cv_default_detector).lower()
        if detector_name in ('hog', 'opencv_hog', 'person'):
            result = self._cv_opencv_hog(frame, expected_event)
        elif detector_name in ('face', 'opencv_face'):
            result = self._cv_opencv_face(frame, expected_event)
        elif detector_name in ('motion', 'opencv_motion'):
            result = self._cv_opencv_motion(session_id, frame, expected_event)
        elif detector_name in ('posenet', 'pose'):
            result = self._cv_posenet(session_id, frame, expected_event)
        else:
            result = self._cv_opencv_hog(frame, expected_event)
            result['reason'] = f"unknown detector '{detector_name}', fell back to opencv_hog"

        result['engine'] = 'cv'
        result['cv_detector'] = detector_name
        if prompt and not result.get('reason'):
            result['reason'] = f"cv detector {detector_name} evaluated prompt-driven signal"
        return result

    def _cv_opencv_hog(self, frame, expected_event: str = None) -> dict:
        try:
            import cv2

            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            boxes, weights = hog.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
            count = len(boxes)
            max_weight = max([float(w) for w in weights], default=0.0)
            confidence = min(1.0, max(0.0, max_weight / 2.5)) if count > 0 else 0.0
            return {
                'detected': count > 0,
                'confidence': confidence,
                'event': expected_event or 'vision_detected',
                'fields': {'person_count': count, 'detector': 'opencv_hog'},
                'reason': f"opencv_hog detected {count} person-like regions",
                'transport': 'cv_opencv_hog',
            }
        except Exception as e:
            return {'error': f'opencv_hog error: {e}', 'detected': False, 'confidence': 0.0, 'fields': {}}

    def _cv_opencv_face(self, frame, expected_event: str = None) -> dict:
        try:
            import cv2

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
            count = len(faces)
            confidence = min(1.0, 0.5 + 0.15 * count) if count > 0 else 0.0
            return {
                'detected': count > 0,
                'confidence': confidence,
                'event': expected_event or 'vision_detected',
                'fields': {'face_count': count, 'detector': 'opencv_face'},
                'reason': f"opencv_face detected {count} face(s)",
                'transport': 'cv_opencv_face',
            }
        except Exception as e:
            return {'error': f'opencv_face error: {e}', 'detected': False, 'confidence': 0.0, 'fields': {}}

    def _cv_opencv_motion(self, session_id: str, frame, expected_event: str = None) -> dict:
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
                    'detected': False,
                    'confidence': 0.0,
                    'event': expected_event or 'vision_detected',
                    'fields': {'motion_score': 0.0, 'detector': 'opencv_motion'},
                    'reason': 'opencv_motion warming up previous frame reference',
                    'transport': 'cv_opencv_motion',
                }

            diff = cv2.absdiff(prev, small)
            _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
            motion_pixels = float(cv2.countNonZero(thresh))
            total_pixels = float(thresh.shape[0] * thresh.shape[1])
            motion_score = (motion_pixels / total_pixels) if total_pixels > 0 else 0.0
            detected = motion_score > 0.02
            confidence = min(1.0, motion_score * 8.0)

            return {
                'detected': detected,
                'confidence': confidence,
                'event': expected_event or 'vision_detected',
                'fields': {'motion_score': round(motion_score, 4), 'detector': 'opencv_motion'},
                'reason': f"opencv_motion score={motion_score:.4f}",
                'transport': 'cv_opencv_motion',
            }
        except Exception as e:
            return {'error': f'opencv_motion error: {e}', 'detected': False, 'confidence': 0.0, 'fields': {}}

    def _cv_posenet(self, session_id: str, frame, expected_event: str = None) -> dict:
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
                            'error': (
                                f'posenet detector error: missing MediaPipe Tasks model asset at {model_path}. '
                                'Set vision.cv.pose_model_asset in config.yaml to a valid .task file path.'
                            ),
                            'detected': False,
                            'confidence': 0.0,
                            'fields': {},
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
                            'error': 'posenet detector error: MediaPipe runtime missing both Tasks PoseLandmarker and legacy solutions.pose.Pose APIs',
                            'detected': False,
                            'confidence': 0.0,
                            'fields': {},
                        }
                    self._pose_runtime = pose_ctor(
                        static_image_mode=False,
                        model_complexity=0,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            pose_landmarks = None
            visibility_values = []
            transport = 'cv_posenet_mediapipe_tasks'

            if hasattr(self._pose_runtime, 'detect'):
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = self._pose_runtime.detect(mp_image)
                pose_list = getattr(result, 'pose_landmarks', None) or []
                pose_landmarks = pose_list[0] if len(pose_list) > 0 else None
                if pose_landmarks:
                    visibility_values = [float(getattr(lm, 'visibility', 0.0) or 0.0) for lm in pose_landmarks]
            else:
                result = self._pose_runtime.process(rgb)
                landmarks_obj = getattr(result, 'pose_landmarks', None)
                pose_landmarks = landmarks_obj.landmark if landmarks_obj is not None else None
                if pose_landmarks:
                    visibility_values = [float(getattr(lm, 'visibility', 0.0) or 0.0) for lm in pose_landmarks]
                transport = 'cv_posenet_mediapipe_solutions'

            detected = pose_landmarks is not None
            landmark_count = len(pose_landmarks) if detected else 0
            if visibility_values:
                confidence = max(0.0, min(1.0, sum(visibility_values) / max(1, len(visibility_values))))
            else:
                confidence = 0.85 if detected else 0.0

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
                        'x': round(float(x), 6),
                        'y': round(float(y), 6),
                        'confidence': round(confidence_value, 6),
                    }
                    pose_positions.append(point)
                    hand_name = hand_landmark_indices.get(index)
                    if hand_name is not None:
                        hand_positions.append({
                            **point,
                            'name': hand_name,
                        })

            fields = {
                'pose_landmarks': landmark_count,
                'person_count': 1 if detected else 0,
                'pose_positions': pose_positions,
                'hand_positions': hand_positions,
                'hand_pose': hand_positions,
                'pose_detected': 1 if detected else 0,
                'detector': 'posenet',
            }

            reason_text = (
                f"posenet pose detected; pose_positions={len(pose_positions)}; hand_positions={len(hand_positions)}"
            ) if detected else 'no pose landmarks detected'

            return {
                'detected': detected,
                'confidence': confidence,
                'event': expected_event or 'vision_detected',
                'fields': fields,
                'reason': reason_text,
                'transport': transport,
            }
        except Exception as e:
            return {'error': f'posenet detector error: {e}', 'detected': False, 'confidence': 0.0, 'fields': {}}

    def _analyze_with_realtime_stream(self, image_data_url: str, prompt: str, model: str, expected_event: str = None) -> dict:
        """
        Realtime mode using streaming output where available.
        Falls back to regular responses API when stream transport is unavailable.
        """
        try:
            client = self._get_client()
            instruction = self._build_instruction(expected_event=expected_event)
            stream_fallback_reason = None
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

                return self._normalize_analysis(
                    text=stream_text,
                    expected_event=expected_event,
                    transport='realtime_stream',
                )

            except Exception as stream_err:
                stream_fallback_reason = str(stream_err)

            # Fallback to non-stream response if stream path fails
            response = client.responses.create(
                model=model,
                max_output_tokens=180,
                input=input_payload,
            )
            text = self._extract_output_text(response)
            return self._normalize_analysis(
                text=text,
                expected_event=expected_event,
                transport='responses_fallback',
                fallback_reason=stream_fallback_reason,
            )

        except Exception as e:
            return {'error': str(e), 'detected': False, 'confidence': 0.0, 'fields': {}}

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
