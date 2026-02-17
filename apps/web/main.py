"""
AdaptLight Web Application

Flask-based web interface using the SMgenerator library.
"""

import os
import sys
import json
import time
import uuid
import base64
import threading
import re
from pathlib import Path

# Add parent directories to path for imports
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env file from root directory
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

import yaml
from flask import Flask, request, jsonify, send_from_directory
from brain import SMgenerator

# Add web app directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))
import supabase_client


class VisionRuntime:
    """Web runtime for camera + OpenAI VLM processing."""

    def __init__(self, smgen: SMgenerator, config: dict = None, openai_api_key: str = None):
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
                    'error': analysis['error'],
                    'latency_ms': watcher_latency_ms,
                })
                continue

            detections.append({
                'watcher': watcher.get('name'),
                'engine': engine,
                'cv_detector': detector if engine in ('cv', 'hybrid') else None,
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
            if watcher.get('map_data', True):
                diag = {
                    'watcher': watcher.get('name'),
                    'engine': engine,
                    'key': data_key,
                    'field': data_field,
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
                elif not data_field:
                    diag['mapped'] = False
                    diag['reason'] = 'missing_set_data_field'
                    mapping_diagnostics.append(diag)
                    mapped_data_skips.append({
                        'watcher': watcher.get('name'),
                        'reason': 'missing_set_data_field',
                    })
                elif data_field in fields:
                    value_to_set = fields[data_field]
                    self.state_machine.set_data(data_key, value_to_set)
                    diag['mapped'] = True
                    diag['reason'] = 'mapped_from_fields'
                    diag['value'] = value_to_set
                    mapping_diagnostics.append(diag)
                    mapped_data_updates.append({
                        'watcher': watcher.get('name'),
                        'key': data_key,
                        'field': data_field,
                        'value': value_to_set,
                        'source': 'fields',
                    })
                elif data_field in analysis:
                    value_to_set = analysis.get(data_field)
                    self.state_machine.set_data(data_key, value_to_set)
                    diag['mapped'] = True
                    diag['reason'] = 'mapped_from_top_level'
                    diag['value'] = value_to_set
                    mapping_diagnostics.append(diag)
                    mapped_data_updates.append({
                        'watcher': watcher.get('name'),
                        'key': data_key,
                        'field': data_field,
                        'value': value_to_set,
                        'source': 'top_level',
                    })
                elif str(data_field).strip().lower() == 'hand_distance' and 'no hand' in str(analysis.get('reason', '')).lower():
                    value_to_set = 100
                    self.state_machine.set_data(data_key, value_to_set)
                    diag['mapped'] = True
                    diag['reason'] = 'mapped_from_reason_no_hand_fallback'
                    diag['value'] = value_to_set
                    mapping_diagnostics.append(diag)
                    mapped_data_updates.append({
                        'watcher': watcher.get('name'),
                        'key': data_key,
                        'field': data_field,
                        'value': value_to_set,
                        'source': 'reason_no_hand_fallback',
                    })
                else:
                    diag['mapped'] = False
                    diag['reason'] = 'field_not_returned_by_detector'
                    mapping_diagnostics.append(diag)
                    mapped_data_skips.append({
                        'watcher': watcher.get('name'),
                        'reason': 'field_not_returned_by_detector',
                        'key': data_key,
                        'field': data_field,
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
        v = str(value or 'auto').strip().lower()
        if v in ('vlm', 'openai', 'llm'):
            return 'vlm'
        if v in ('cv', 'opencv', 'posenet'):
            return 'cv'
        if v in ('hybrid', 'both'):
            return 'hybrid'
        return 'auto'

    @staticmethod
    def _looks_cv_friendly(prompt: str) -> bool:
        text = str(prompt or '').strip().lower()
        if not text:
            return True
        simple_patterns = [
            r'\bperson\b', r'\bhuman\b', r'\bface\b', r'\bbody\b', r'\bpose\b',
            r'\bhand\b', r'\bwave\b', r'\bmotion\b', r'\bmovement\b', r'\bpresence\b',
            r'\bempty room\b', r'\bcount people\b', r'\bstanding\b', r'\bsitting\b',
        ]
        complex_markers = [
            r'\bemotion\b', r'\bmood\b', r'\bintention\b', r'\bcontext\b', r'\bstory\b',
            r'\bbrand\b', r'\btext\b', r'\breading\b', r'\bproduct\b', r'\bscene\b',
            r'\bexplain\b', r'\bdescribe\b', r'\bwhy\b',
        ]
        if any(re.search(p, text) for p in complex_markers):
            return False
        return any(re.search(p, text) for p in simple_patterns)

    @staticmethod
    def _cv_supported_fields(detector: str) -> set:
        detector_name = str(detector or '').strip().lower()
        if detector_name in ('hog', 'opencv_hog', 'person'):
            return {'person_count'}
        if detector_name in ('face', 'opencv_face'):
            return {'face_count'}
        if detector_name in ('motion', 'opencv_motion'):
            return {'motion_score'}
        if detector_name in ('posenet', 'pose'):
            return {'pose_landmarks'}
        return set()

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
                self._pose_runtime = mp.solutions.pose.Pose(
                    static_image_mode=False,
                    model_complexity=0,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._pose_runtime.process(rgb)
            landmarks = getattr(result, 'pose_landmarks', None)
            detected = landmarks is not None
            landmark_count = len(landmarks.landmark) if detected else 0
            confidence = 0.85 if detected else 0.0

            return {
                'detected': detected,
                'confidence': confidence,
                'event': expected_event or 'vision_detected',
                'fields': {'pose_landmarks': landmark_count, 'detector': 'posenet'},
                'reason': 'posenet-style pose landmarks detected' if detected else 'no pose landmarks detected',
                'transport': 'cv_posenet_mediapipe',
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


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / 'config.yaml'

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    def expand_env(obj):
        if isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            return os.environ.get(env_var, '')
        elif isinstance(obj, dict):
            return {k: expand_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [expand_env(item) for item in obj]
        return obj

    return expand_env(config)


def load_eval_cases() -> list:
    """Load eval cases from apps/eval/cases/cases.txt."""
    cases_path = ROOT_DIR / 'apps' / 'eval' / 'cases' / 'cases.txt'
    if not cases_path.exists():
        return []

    with open(cases_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]

    return [line for line in lines if line]


def create_app(config_path: str = None) -> Flask:
    """Create and configure the Flask application."""
    config = load_config(config_path)

    # Get representation version from config
    representation_version = config.get('representation', {}).get('version', 'stdlib')

    # Debug: confirm env loading (do not print secret values)
    env_anthropic = os.environ.get('ANTHROPIC_API_KEY', '')
    env_openai = os.environ.get('OPENAI_API_KEY', '')
    print(f"[env] cwd={os.getcwd()}")
    print(f"[env] .env path={ROOT_DIR / '.env'} exists={os.path.exists(ROOT_DIR / '.env')}")
    print(f"[env] ANTHROPIC_API_KEY loaded={bool(env_anthropic)} length={len(env_anthropic)}")
    print(f"[env] OPENAI_API_KEY loaded={bool(env_openai)} length={len(env_openai)}")

    # Trim whitespace from API keys to avoid hidden trailing spaces
    if isinstance(config.get('anthropic', {}).get('api_key'), str):
        config['anthropic']['api_key'] = config['anthropic']['api_key'].strip()
    if isinstance(config.get('openai', {}).get('api_key'), str):
        config['openai']['api_key'] = config['openai']['api_key'].strip()
    if isinstance(config.get('supabase', {}).get('url'), str):
        config['supabase']['url'] = config['supabase']['url'].strip()
    if isinstance(config.get('supabase', {}).get('anon_key'), str):
        config['supabase']['anon_key'] = config['supabase']['anon_key'].strip()

    # Initialize SMgenerator
    smgen_config = {
        'mode': config['brain']['mode'],
        'model': config['brain']['model'],
        'prompt_variant': config['brain']['prompt_variant'],
        'max_turns': config['brain'].get('max_turns', 10),
        'verbose': config['brain'].get('verbose', False),
        'anthropic_api_key': config['anthropic']['api_key'],
        'openai_api_key': config['openai']['api_key'],
        'storage_dir': config.get('storage', {}).get('dir', 'data/storage'),
        'representation_version': representation_version,
    }
    smgen = SMgenerator(smgen_config)

    vision_runtime = VisionRuntime(
        smgen=smgen,
        config=config.get('vision', {}),
        openai_api_key=config.get('openai', {}).get('api_key')
    )

    # Create Flask app
    app = Flask(__name__, static_folder='static')
    app.config['smgen'] = smgen
    app.config['vision_runtime'] = vision_runtime

    # ─────────────────────────────────────────────────────────────
    # Routes
    # ─────────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        """Serve the main page."""
        response = send_from_directory('static', 'index.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/eval')
    def eval_page():
        """Serve the eval page."""
        response = send_from_directory('static', 'eval.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/static/<path:path>')
    def serve_static(path):
        """Serve static files."""
        response = send_from_directory('static', path)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/api/process', methods=['POST'])
    def process():
        """Process user input text."""
        data = request.get_json()
        text = data.get('text', '')
        user_id = data.get('user_id', 'anonymous')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        try:
            result = smgen.process(text)

            # Get full state machine snapshot (all states and rules)
            details = smgen.get_details()

            # Log command session with full snapshot to Supabase
            session_id = supabase_client.log_command_session(
                user_id=user_id,
                command=text,
                response_message=result.message,
                success=result.success,
                current_state=result.state.get('name') if result.state else None,
                current_state_data=result.state,
                all_states=details.get('states', []),
                all_rules=details.get('rules', []),
                tool_calls=result.tool_calls,
                agent_steps=result.agent_steps,
                timing_ms=result.timing.get('total_ms') if result.timing else None,
                run_id=result.run_id
            )

            return jsonify({
                'success': result.success,
                'state': result.state,
                'message': result.message,
                'tool_calls': result.tool_calls,
                'timing': result.timing,
                'run_id': result.run_id,
                'agent_steps': result.agent_steps,
                'session_id': session_id,  # For feedback submission
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/trigger', methods=['POST'])
    def trigger():
        """Trigger a state machine event (button presses - not logged)."""
        data = request.get_json()
        event = data.get('event', 'button_click')

        try:
            state = smgen.trigger(event)
            return jsonify({
                'success': True,
                'state': state,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/state', methods=['GET'])
    def get_state():
        """Get current state."""
        try:
            state = smgen.get_state()
            return jsonify({
                'success': True,
                'state': state,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/summary', methods=['GET'])
    def get_summary():
        """Get SMgenerator summary."""
        try:
            summary = smgen.get_summary()
            return jsonify({
                'success': True,
                'summary': summary,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/details', methods=['GET'])
    def get_details():
        """Get detailed states and rules."""
        try:
            details = smgen.get_details()
            return jsonify({
                'success': True,
                **details,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/reset', methods=['POST'])
    def reset():
        """Reset the state machine generator (not logged)."""
        try:
            smgen.reset()
            state = smgen.get_state()
            return jsonify({
                'success': True,
                'state': state,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/eval/cases', methods=['GET'])
    def get_eval_cases():
        """Return evaluation cases from cases.txt."""
        cases = load_eval_cases()
        return jsonify({
            'success': True,
            'cases': cases,
        })

    @app.route('/api/eval/process', methods=['POST'])
    def eval_process():
        """Process eval input text with a chosen implementation (stubbed)."""
        data = request.get_json()
        text = data.get('text', '')
        implementation = data.get('implementation', 'state_machine')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        try:
            result = smgen.process(text)

            return jsonify({
                'success': result.success,
                'state': result.state,
                'message': result.message,
                'tool_calls': result.tool_calls,
                'timing': result.timing,
                'run_id': result.run_id,
                'implementation': implementation,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'implementation': implementation,
            }), 500

    @app.route('/api/feedback', methods=['POST'])
    def submit_feedback():
        """Submit feedback for a command session."""
        data = request.get_json()
        session_id = data.get('session_id')
        feedback = data.get('feedback', '')
        rating = data.get('rating')  # Optional 1-5

        if not session_id:
            return jsonify({'error': 'No session_id provided'}), 400

        if not feedback:
            return jsonify({'error': 'No feedback provided'}), 400

        try:
            success = supabase_client.submit_feedback(
                session_id=session_id,
                feedback=feedback,
                rating=rating
            )
            return jsonify({
                'success': success,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/quick-feedback', methods=['POST'])
    def submit_quick_feedback():
        """Submit quick feedback (worked/didn't work) for a command session."""
        data = request.get_json()
        session_id = data.get('session_id')
        worked = data.get('worked')

        if not session_id:
            return jsonify({'error': 'No session_id provided'}), 400

        if worked is None:
            return jsonify({'error': 'No worked value provided'}), 400

        try:
            success = supabase_client.submit_quick_feedback(
                session_id=session_id,
                worked=worked
            )
            return jsonify({
                'success': success,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/history', methods=['GET'])
    def get_history():
        """Get command sessions for a user."""
        user_id = request.args.get('user_id', 'anonymous')
        limit = request.args.get('limit', 50, type=int)

        try:
            sessions = supabase_client.get_user_sessions(user_id, limit)
            return jsonify({
                'success': True,
                'sessions': sessions,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/config', methods=['GET'])
    def get_config():
        """Get frontend-relevant config (representation version)."""
        vision_cfg = config.get('vision', {})
        vision_mode = str(vision_cfg.get('mode', 'polling')).lower()
        if vision_mode not in ('polling', 'realtime'):
            vision_mode = 'polling'

        return jsonify({
            'success': True,
            'representation_version': representation_version,
            'vision': {
                'enabled': bool(vision_cfg.get('enabled', False)),
                'mode': vision_mode,
                'latest_frame_only': bool(vision_cfg.get('latest_frame_only', True)),
                'interval_ms': max(1000, int(vision_cfg.get('interval_ms', 2000))),
                'min_confidence': float(vision_cfg.get('min_confidence', 0.55)),
                'max_image_chars': int(vision_cfg.get('max_image_chars', 2_500_000)),
                'cv': {
                    'enabled': bool((vision_cfg.get('cv') or {}).get('enabled', True)),
                    'interval_ms': max(1000, int((vision_cfg.get('cv') or {}).get('interval_ms', 1000))),
                    'detector': str((vision_cfg.get('cv') or {}).get('detector', 'opencv_hog')).lower(),
                },
            },
        })

    @app.route('/api/vision/session/start', methods=['POST'])
    def vision_start_session():
        """Start a vision session for camera frame ingestion."""
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id', 'anonymous')
        runtime: VisionRuntime = app.config['vision_runtime']

        if not runtime.enabled:
            return jsonify({'success': False, 'error': 'vision runtime disabled'}), 400

        session = runtime.start_session(user_id=user_id)
        return jsonify({'success': True, **session})

    @app.route('/api/vision/session/stop', methods=['POST'])
    def vision_stop_session():
        """Stop an active vision session."""
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        runtime: VisionRuntime = app.config['vision_runtime']
        result = runtime.stop_session(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/vision/status', methods=['GET'])
    def vision_status():
        """Get current vision session status."""
        session_id = request.args.get('session_id', '')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        runtime: VisionRuntime = app.config['vision_runtime']
        result = runtime.get_status(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/vision/frame', methods=['POST'])
    def vision_frame():
        """Analyze a camera frame via OpenAI VLM and trigger transitions."""
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        image_data_url = data.get('image')

        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        if not image_data_url:
            return jsonify({'success': False, 'error': 'image required'}), 400

        runtime: VisionRuntime = app.config['vision_runtime']
        result = runtime.process_frame(session_id=session_id, image_data_url=image_data_url)

        if not result.get('success'):
            if result.get('error') in ('session not found',):
                return jsonify(result), 404
            return jsonify(result), 400

        return jsonify(result)

    return app


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='AdaptLight Web Server')
    parser.add_argument('--config', '-c', help='Path to config file')
    parser.add_argument('--port', '-p', type=int, default=3000, help='Port to listen on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    app = create_app(args.config)

    print("=" * 60)
    print("AdaptLight Web Server")
    print("=" * 60)
    print(f"Running on http://{args.host}:{args.port}")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
