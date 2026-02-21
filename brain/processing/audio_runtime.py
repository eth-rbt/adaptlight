"""
Audio Runtime for AdaptLight.

Processes microphone chunks for LLM-based audio watchers, writes parsed output to
state_data['audio'], and optionally emits audio_* events.

Supports two modes:
- transcript: Whisper transcription → GPT-4o-mini text analysis (default)
- direct: Send audio directly to GPT-4o audio model (faster, no transcription step)
"""

import base64
import json
import os
import threading
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brain import SMgenerator


class AudioRuntime:
    """Runtime for LLM audio-reactive behavior."""

    def __init__(self, smgen: "SMgenerator", config: dict = None, openai_api_key: str = None):
        self.smgen = smgen
        self.state_machine = smgen.state_machine
        self.config = config or {}
        self.enabled = bool(self.config.get("enabled", True))
        self.default_model = str(self.config.get("model", "gpt-4o-mini"))
        self.default_interval_ms = max(1000, int(self.config.get("interval_ms", 3000)))
        self.default_cooldown_ms = max(0, int(self.config.get("cooldown_ms", 1500)))
        self.max_transcript_chars = int(self.config.get("max_transcript_chars", 20_000))
        self.max_audio_bytes = int(self.config.get("max_audio_bytes", 5_000_000))  # 5MB max
        self.debug_llm_output = bool(self.config.get("debug_llm_output", False)) or os.getenv(
            "ADAPTLIGHT_DEBUG_AUDIO_LLM", ""
        ).strip().lower() in {"1", "true", "yes", "on"}

        # Mode: "transcript" (Whisper → GPT text) or "direct" (audio → GPT-4o audio)
        self.mode = str(self.config.get("mode", "transcript")).lower()
        # Model for direct audio mode (must support audio input)
        self.direct_audio_model = str(self.config.get("direct_audio_model", "gpt-4o-audio-preview-2024-12-17"))

        self._openai_api_key = openai_api_key
        self._openai_client = None
        self._lock = threading.Lock()
        self._sessions = {}

    def _get_client(self):
        if self._openai_client is not None:
            return self._openai_client
        if not self._openai_api_key:
            raise RuntimeError("OPENAI_API_KEY missing for audio runtime")
        from openai import OpenAI
        self._openai_client = OpenAI(api_key=self._openai_api_key)
        return self._openai_client

    def start_session(self, user_id: str = "anonymous") -> dict:
        session_id = str(uuid.uuid4())[:12]
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._sessions[session_id] = {
                "session_id": session_id,
                "user_id": user_id,
                "active": True,
                "created_at_ms": now_ms,
                "last_analysis_ms": 0,
                "last_event_ms": {},
                "last_watcher_analysis_ms": {},
                "last_result": None,
            }
        return {"session_id": session_id, "active": True}

    def stop_session(self, session_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {"success": False, "error": "session not found"}
            session["active"] = False
        return {"success": True, "session_id": session_id, "active": False}

    def get_status(self, session_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {"success": False, "error": "session not found"}
            return {
                "success": True,
                "session_id": session_id,
                "active": bool(session.get("active", False)),
                "last_analysis_ms": int(session.get("last_analysis_ms", 0)),
                "last_result": session.get("last_result"),
                "watchers": self._get_active_watchers(),
            }

    def process_audio_direct(self, session_id: str, audio_bytes: bytes, chunk_meta: dict = None) -> dict:
        """Process raw audio bytes directly with GPT-4o audio model (no Whisper transcription)."""
        if not self.enabled:
            return {"success": False, "error": "audio runtime disabled"}
        if not isinstance(audio_bytes, bytes) or len(audio_bytes) == 0:
            return {"success": False, "error": "audio_bytes is required"}
        if len(audio_bytes) > self.max_audio_bytes:
            return {"success": False, "error": "audio_bytes too large"}

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {"success": False, "error": "session not found"}
            if not session.get("active"):
                return {"success": False, "error": "session not active"}

        watchers = self._get_active_watchers()
        if not watchers:
            return {
                "success": True,
                "processed": False,
                "reason": "no_active_audio_watchers",
                "state": self.smgen.get_state(),
                "watchers": [],
            }

        now_ms = int(time.time() * 1000)
        emitted_events = []
        processed = False

        for watcher in watchers:
            watcher_key = str(watcher.get("name") or watcher.get("event") or "audio_watcher")
            interval_ms = max(1000, int(watcher.get("interval_ms", self.default_interval_ms)))
            cooldown_ms = max(0, int(watcher.get("cooldown_ms", self.default_cooldown_ms)))

            with self._lock:
                session = self._sessions.get(session_id) or {}
                watcher_last_ms = int(session.get("last_watcher_analysis_ms", {}).get(watcher_key, 0) or 0)

            if watcher_last_ms and (now_ms - watcher_last_ms) < interval_ms:
                continue

            output = self._analyze_with_llm_audio(
                audio_bytes=audio_bytes,
                prompt=str(watcher.get("prompt", "")).strip(),
                model=str(watcher.get("model", self.direct_audio_model)),
                expected_event=watcher.get("event"),
                chunk_meta=chunk_meta or {},
            )

            if self.debug_llm_output:
                print(
                    "[audio_llm_direct] watcher="
                    f"{watcher_key} expected_event={watcher.get('event')} "
                    f"audio_size={len(audio_bytes)} output={json.dumps(output, ensure_ascii=False)}"
                )

            output["_timestamp"] = now_ms
            self.state_machine.set_data("audio", output)
            processed = True

            if "_event" in output:
                event_name = str(output["_event"])
                if not event_name.startswith("audio_"):
                    event_name = f"audio_{event_name}"
                with self._lock:
                    last_event_ms = int(session.get("last_event_ms", {}).get(event_name, 0) or 0)
                    can_emit = (now_ms - last_event_ms) >= cooldown_ms
                if can_emit:
                    from_state = self.state_machine.get_state()
                    next_state = self.smgen.trigger(event_name)
                    emitted_events.append(event_name)
                    if self.debug_llm_output:
                        print(
                            "[audio_llm_direct] emitted_event="
                            f"{event_name} watcher={watcher_key} source={(chunk_meta or {}).get('source')} "
                            f"from={from_state} to={next_state.get('name') if isinstance(next_state, dict) else None}"
                        )
                    with self._lock:
                        session.setdefault("last_event_ms", {})[event_name] = now_ms

            with self._lock:
                session = self._sessions.get(session_id)
                if session is not None:
                    session.setdefault("last_watcher_analysis_ms", {})[watcher_key] = now_ms
                    session["last_analysis_ms"] = now_ms
                    session["last_result"] = output
            break

        return {
            "success": True,
            "processed": processed,
            "audio": self.state_machine.get_data("audio"),
            "emitted_events": emitted_events,
            "state": self.smgen.get_state(),
            "watchers": watchers,
        }

    def process_chunk(self, session_id: str, transcript: str, chunk_meta: dict = None) -> dict:
        if not self.enabled:
            return {"success": False, "error": "audio runtime disabled"}
        if not isinstance(transcript, str) or not transcript.strip():
            return {"success": False, "error": "transcript is required"}
        if len(transcript) > self.max_transcript_chars:
            return {"success": False, "error": "transcript too large"}

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {"success": False, "error": "session not found"}
            if not session.get("active"):
                return {"success": False, "error": "session not active"}

        watchers = self._get_active_watchers()
        if not watchers:
            return {
                "success": True,
                "processed": False,
                "reason": "no_active_audio_watchers",
                "state": self.smgen.get_state(),
                "watchers": [],
            }

        now_ms = int(time.time() * 1000)
        emitted_events = []
        processed = False

        for watcher in watchers:
            watcher_key = str(watcher.get("name") or watcher.get("event") or "audio_watcher")
            interval_ms = max(1000, int(watcher.get("interval_ms", self.default_interval_ms)))
            cooldown_ms = max(0, int(watcher.get("cooldown_ms", self.default_cooldown_ms)))

            with self._lock:
                session = self._sessions.get(session_id) or {}
                watcher_last_ms = int(session.get("last_watcher_analysis_ms", {}).get(watcher_key, 0) or 0)

            if watcher_last_ms and (now_ms - watcher_last_ms) < interval_ms:
                continue

            output = self._analyze_with_llm(
                transcript=transcript,
                prompt=str(watcher.get("prompt", "")).strip(),
                model=str(watcher.get("model", self.default_model)),
                expected_event=watcher.get("event"),
                chunk_meta=chunk_meta or {},
            )

            if self.debug_llm_output:
                print(
                    "[audio_llm] watcher="
                    f"{watcher_key} expected_event={watcher.get('event')} "
                    f"transcript={transcript[:120]!r} output={json.dumps(output, ensure_ascii=False)}"
                )

            output["_timestamp"] = now_ms
            self.state_machine.set_data("audio", output)
            processed = True

            if "_event" in output:
                event_name = str(output["_event"])
                if not event_name.startswith("audio_"):
                    event_name = f"audio_{event_name}"
                with self._lock:
                    last_event_ms = int(session.get("last_event_ms", {}).get(event_name, 0) or 0)
                    can_emit = (now_ms - last_event_ms) >= cooldown_ms
                if can_emit:
                    from_state = self.state_machine.get_state()
                    next_state = self.smgen.trigger(event_name)
                    emitted_events.append(event_name)
                    if self.debug_llm_output:
                        print(
                            "[audio_llm] emitted_event="
                            f"{event_name} watcher={watcher_key} source={(chunk_meta or {}).get('source')} "
                            f"from={from_state} to={next_state.get('name') if isinstance(next_state, dict) else None}"
                        )
                    with self._lock:
                        session.setdefault("last_event_ms", {})[event_name] = now_ms

            with self._lock:
                session = self._sessions.get(session_id)
                if session is not None:
                    session.setdefault("last_watcher_analysis_ms", {})[watcher_key] = now_ms
                    session["last_analysis_ms"] = now_ms
                    session["last_result"] = output
            break

        return {
            "success": True,
            "processed": processed,
            "audio": self.state_machine.get_data("audio"),
            "emitted_events": emitted_events,
            "state": self.smgen.get_state(),
            "watchers": watchers,
        }

    def _get_active_watchers(self) -> list:
        watchers = []
        current_state = self.state_machine.get_state()
        state = self.smgen.get_state() or {}

        state_audio = state.get("audio_reactive") or {}
        if isinstance(state_audio, dict) and state_audio.get("enabled"):
            watchers.append({
                "name": f"state:{current_state}",
                "source": "state",
                "prompt": state_audio.get("prompt", ""),
                "model": state_audio.get("model", self.default_model),
                "interval_ms": state_audio.get("interval_ms", self.default_interval_ms),
                "cooldown_ms": state_audio.get("cooldown_ms", self.default_cooldown_ms),
                "event": state_audio.get("event"),
            })

        for idx, rule in enumerate(self.state_machine.get_rules()):
            if not rule.enabled:
                continue
            if not self._state_match(rule.state1, current_state):
                continue
            config = rule.trigger_config or {}
            audio_cfg = config.get("audio") if isinstance(config, dict) else None
            if not isinstance(audio_cfg, dict) or not audio_cfg.get("enabled"):
                continue

            event_name = audio_cfg.get("event") or rule.transition
            if event_name and not str(event_name).startswith("audio_"):
                event_name = f"audio_{event_name}"

            watchers.append({
                "name": f"rule:{idx}",
                "source": "rule",
                "prompt": audio_cfg.get("prompt", ""),
                "model": audio_cfg.get("model", self.default_model),
                "interval_ms": audio_cfg.get("interval_ms", self.default_interval_ms),
                "cooldown_ms": audio_cfg.get("cooldown_ms", self.default_cooldown_ms),
                "event": event_name,
            })

        return watchers

    @staticmethod
    def _state_match(rule_state: str, current_state: str) -> bool:
        if rule_state == "*":
            return True
        if isinstance(rule_state, str) and rule_state.endswith("/*"):
            prefix = rule_state[:-2]
            return current_state.startswith(prefix + "/")
        return rule_state == current_state

    def _build_instruction(self, expected_event: str = None) -> str:
        event_instruction = ""
        if expected_event:
            event_instruction = (
                f"If the condition in the prompt is met, include '_event': '{expected_event}'. "
            )
        return (
            "Analyze microphone transcript based on the user's prompt. "
            "Return only valid JSON with observed fields. "
            f"{event_instruction}"
            "Always include '_detector': 'audio_llm'. "
            "No markdown, no explanation, only JSON."
        )

    def _analyze_with_llm(self, transcript: str, prompt: str, model: str, expected_event: str = None, chunk_meta: dict = None) -> dict:
        chunk_meta = chunk_meta or {}
        try:
            client = self._get_client()
            instruction = self._build_instruction(expected_event=expected_event)
            user_payload = (
                f"Prompt: {prompt or 'Analyze this transcript.'}\n"
                f"Transcript: {transcript}\n"
                f"Chunk meta: {json.dumps(chunk_meta)}"
            )
            response = client.responses.create(
                model=model,
                max_output_tokens=180,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": instruction}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_payload}]},
                ],
            )
            text = getattr(response, "output_text", "") or ""
            parsed = self._parse_json_object(text)

            if self.debug_llm_output:
                print(f"[audio_llm] raw_output={text!r}")

            if not parsed:
                return {"_error": "unable to parse audio LLM JSON output", "_detector": "audio_llm"}
            if "_detector" not in parsed:
                parsed["_detector"] = "audio_llm"
            if self.debug_llm_output:
                parsed["_raw_output"] = text
            return parsed
        except Exception as e:
            return {"_error": str(e), "_detector": "audio_llm"}

    def _analyze_with_llm_audio(self, audio_bytes: bytes, prompt: str, model: str, expected_event: str = None, chunk_meta: dict = None) -> dict:
        """Send raw audio directly to GPT-4o audio model for analysis."""
        chunk_meta = chunk_meta or {}
        try:
            client = self._get_client()

            # Build instruction for audio analysis
            event_instruction = ""
            if expected_event:
                event_instruction = f"If the condition in the prompt is met, include '_event': '{expected_event}'. "
            instruction = (
                "Analyze this audio based on the user's prompt. "
                "Listen to what is being said or played and extract relevant information. "
                "Return only valid JSON with observed fields. "
                f"{event_instruction}"
                "Always include '_detector': 'audio_llm_direct'. "
                "No markdown, no explanation, only JSON."
            )

            # Encode audio as base64
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            # Determine audio format from chunk_meta or default to wav
            audio_format = chunk_meta.get("format", "wav")

            user_payload = f"Prompt: {prompt or 'Analyze this audio.'}\nChunk meta: {json.dumps(chunk_meta)}"

            if self.debug_llm_output:
                duration_sec = len(audio_bytes) / (44100 * 2) if len(audio_bytes) > 0 else 0  # Assume 44100Hz 16-bit
                print(f"[audio_llm_direct] SENDING to {model}: {len(audio_bytes)} bytes ({duration_sec:.1f}s), format={audio_format}")
                print(f"[audio_llm_direct] prompt={prompt!r} expected_event={expected_event}")

            # Use Chat Completions API for audio input (not Responses API)
            response = client.chat.completions.create(
                model=model,
                modalities=["text"],  # We only need text output
                max_completion_tokens=180,
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": [
                        {"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}},
                        {"type": "text", "text": user_payload},
                    ]},
                ],
            )
            text = response.choices[0].message.content if response.choices else ""
            parsed = self._parse_json_object(text)

            if self.debug_llm_output:
                print(f"[audio_llm_direct] RESPONSE raw_output={text!r}")

            if not parsed:
                return {"_error": "unable to parse audio LLM JSON output", "_detector": "audio_llm_direct"}
            if "_detector" not in parsed:
                parsed["_detector"] = "audio_llm_direct"
            if self.debug_llm_output:
                parsed["_raw_output"] = text
            return parsed
        except Exception as e:
            return {"_error": str(e), "_detector": "audio_llm_direct"}

    @staticmethod
    def _parse_json_object(text: str):
        if not text:
            return None
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = stripped[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
