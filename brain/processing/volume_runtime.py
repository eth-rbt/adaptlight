"""
Volume Runtime for AdaptLight.

Ingests microphone meter payloads and writes smoothed values to state_data['volume'].
"""

import threading
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brain import SMgenerator


class VolumeRuntime:
    """Runtime for volume-reactive behavior."""

    def __init__(self, smgen: "SMgenerator", config: dict = None):
        self.smgen = smgen
        self.state_machine = smgen.state_machine
        self.config = config or {}
        self.enabled = bool(self.config.get("enabled", True))
        self.default_interval_ms = max(30, int(self.config.get("interval_ms", 80)))
        self.default_smoothing_alpha = float(self.config.get("smoothing_alpha", 0.35))
        self.default_floor = float(self.config.get("floor", 0.0))
        self.default_ceiling = float(self.config.get("ceiling", 1.0))

        self._lock = threading.Lock()
        self._sessions = {}

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
                "last_result": None,
                "last_watcher_analysis_ms": {},
                "signal_cache": {},
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

    def ingest_frame(self, session_id: str, level: float = None, rms: float = None, peak: float = None, speaking: bool = None) -> dict:
        if not self.enabled:
            return {"success": False, "error": "volume runtime disabled"}

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
                "reason": "no_active_volume_watchers",
                "state": self.smgen.get_state(),
                "watchers": [],
            }

        raw_level = self._coerce_level(level=level, rms=rms, peak=peak)
        now_ms = int(time.time() * 1000)
        processed = False

        for watcher in watchers:
            watcher_key = str(watcher.get("name") or "volume_watcher")
            interval_ms = max(30, int(watcher.get("interval_ms", self.default_interval_ms)))
            alpha = self._coerce_alpha(watcher.get("smoothing_alpha", self.default_smoothing_alpha))
            floor = float(watcher.get("floor", self.default_floor))
            ceiling = float(watcher.get("ceiling", self.default_ceiling))

            with self._lock:
                session = self._sessions.get(session_id) or {}
                watcher_last_ms = int(session.get("last_watcher_analysis_ms", {}).get(watcher_key, 0) or 0)
            if watcher_last_ms and (now_ms - watcher_last_ms) < interval_ms:
                continue

            clamped_level = max(floor, min(ceiling, raw_level))
            normalized = 0.0
            if ceiling > floor:
                normalized = (clamped_level - floor) / (ceiling - floor)

            smoothed = self._smooth_session_signal(
                session_id=session_id,
                signal_key=f"{watcher_key}:smoothed_level",
                raw_value=normalized,
                alpha=alpha,
            )

            output = {
                "level": round(normalized, 4),
                "rms": self._coerce_float(rms, normalized),
                "peak": self._coerce_float(peak, normalized),
                "smoothed_level": round(smoothed, 4),
                "speaking": bool(speaking) if speaking is not None else normalized > 0.02,
                "_timestamp": now_ms,
                "_detector": "volume_meter",
            }
            self.state_machine.set_data("volume", output)
            processed = True

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
            "volume": self.state_machine.get_data("volume"),
            "state": self.smgen.get_state(),
            "watchers": watchers,
        }

    def _get_active_watchers(self) -> list:
        watchers = []
        current_state = self.state_machine.get_state()
        state = self.smgen.get_state() or {}

        state_volume = state.get("volume_reactive") or {}
        if isinstance(state_volume, dict) and state_volume.get("enabled"):
            watchers.append({
                "name": f"state:{current_state}",
                "source": "state",
                "interval_ms": state_volume.get("interval_ms", self.default_interval_ms),
                "smoothing_alpha": state_volume.get("smoothing_alpha", self.default_smoothing_alpha),
                "floor": state_volume.get("floor", self.default_floor),
                "ceiling": state_volume.get("ceiling", self.default_ceiling),
            })

        for idx, rule in enumerate(self.state_machine.get_rules()):
            if not rule.enabled:
                continue
            if not self._state_match(rule.state1, current_state):
                continue
            config = rule.trigger_config or {}
            volume_cfg = config.get("volume") if isinstance(config, dict) else None
            if not isinstance(volume_cfg, dict) or not volume_cfg.get("enabled"):
                continue

            watchers.append({
                "name": f"rule:{idx}",
                "source": "rule",
                "interval_ms": volume_cfg.get("interval_ms", self.default_interval_ms),
                "smoothing_alpha": volume_cfg.get("smoothing_alpha", self.default_smoothing_alpha),
                "floor": volume_cfg.get("floor", self.default_floor),
                "ceiling": volume_cfg.get("ceiling", self.default_ceiling),
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

    @staticmethod
    def _coerce_float(value, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _coerce_alpha(value) -> float:
        try:
            parsed = float(value)
        except Exception:
            parsed = 0.35
        return max(0.05, min(1.0, parsed))

    def _coerce_level(self, level, rms, peak) -> float:
        if level is not None:
            return max(0.0, self._coerce_float(level, 0.0))
        rms_v = max(0.0, self._coerce_float(rms, 0.0))
        peak_v = max(0.0, self._coerce_float(peak, rms_v))
        return max(rms_v, peak_v)

    def _smooth_session_signal(self, session_id: str, signal_key: str, raw_value: float, alpha: float = 0.35) -> float:
        raw_value = self._coerce_float(raw_value, 0.0)
        alpha = self._coerce_alpha(alpha)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return raw_value
            signal_cache = session.setdefault("signal_cache", {})
            prev = signal_cache.get(signal_key)
            if prev is None:
                smoothed = raw_value
            else:
                smoothed = (alpha * raw_value) + ((1.0 - alpha) * self._coerce_float(prev, raw_value))
            signal_cache[signal_key] = smoothed
            return smoothed
