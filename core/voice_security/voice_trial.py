"""Owner / other-speaker voice trial (multi-brain plan, section 8.1).

Grey starts a round from the app ("me" or "someone else"), then talks to ZAE
through the app microphone as usual. Every app-mic voice check during the
round is noted here: who was speaking, whether the gate accepted the turn, why,
and the speaker score. Nothing else is kept: no audio and no words.

The trial only watches. The gate, its threshold and what happens to a rejected
turn are unchanged. Starting a round clears the 45-second "short reply" window
so a quick "yes" from someone else can't ride on Grey's last sentence; a short
reply that is still accepted during a round is counted as "accepted without a
check" so it shows up in the results.

Results are kept in data/voice_trial.json on this PC.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRIAL_FILE = PROJECT_ROOT / "data" / "voice_trial.json"
WHO = ("owner", "other")
MAX_ATTEMPTS = 400


class VoiceTrial:
    """The round lives in the file too (2026-11-01), so the PC voice service, a separate process that has the mic
    whenever it runs, records its checks into the same round as the app mic."""

    def __init__(self, path: Path = TRIAL_FILE, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.lock = threading.Lock()

    def _data(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _load(self) -> list[dict[str, Any]]:
        return [a for a in self._data().get("attempts", []) if isinstance(a, dict)]

    @property
    def round(self) -> dict[str, Any] | None:
        current = self._data().get("round")
        # A round left open for more than 30 minutes is over.
        if isinstance(current, dict) and self.clock() - float(current.get("started", 0)) <= 1800:
            return current
        return None

    def _save(self, attempts: list[dict[str, Any]], round_: dict[str, Any] | None | bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        current = self._data().get("round") if round_ is False else round_
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"attempts": attempts[-MAX_ATTEMPTS:], "round": current}, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def start(self, who: str, target: int = 10) -> dict[str, Any]:
        if who not in WHO:
            raise ValueError("Pick who is speaking: owner or other.")
        target = max(1, min(int(target), 50))
        with self.lock:
            self._save(self._load(), {"who": who, "target": target, "count": 0, "started": self.clock()})
        try:
            from core.voice_security.app_mic import app_mic_gate
            app_mic_gate().last_verified = -1e9
        except Exception:
            pass
        return self.view()

    def stop(self) -> dict[str, Any]:
        with self.lock:
            self._save(self._load(), None)
        return self.view()

    def clear(self) -> dict[str, Any]:
        with self.lock:
            self._save([], None)
        return self.view()

    def note(self, accepted: bool, reason: str, score: float | None) -> None:
        """Called for every voice check (app mic or PC voice); does nothing outside a round."""
        with self.lock:
            current = self.round
            if current is None:
                return
            attempts = self._load()
            attempts.append({"who": current["who"], "accepted": bool(accepted), "reason": str(reason)[:40],
                             "score": None if score is None else round(float(score), 4), "at": round(self.clock(), 1)})
            current["count"] = int(current.get("count", 0)) + 1
            self._save(attempts, None if current["count"] >= int(current.get("target", 10)) else current)

    def view(self) -> dict[str, Any]:
        with self.lock:
            attempts = self._load()
            current = dict(self.round) if self.round else None
        threshold = None
        try:
            from core.voice_security.app_mic import app_mic_gate
            threshold = app_mic_gate().stats().get("threshold")
        except Exception:
            pass
        summary = {}
        for who in WHO:
            mine = [a for a in attempts if a["who"] == who]
            checked = [a for a in mine if a["reason"] in ("recognised", "not_recognised")]
            scores = [a["score"] for a in checked if a["score"] is not None]
            summary[who] = {
                "tries": len(mine), "checked": len(checked),
                "accepted": sum(1 for a in checked if a["accepted"]),
                "acceptedWithoutCheck": sum(1 for a in mine if a["accepted"] and a["reason"] == "short_reply_in_conversation"),
                "tooShort": sum(1 for a in mine if a["reason"] == "too_short"),
                "failed": sum(1 for a in mine if a["reason"] in ("check_failed", "not_set_up")),
                "scoreMin": min(scores) if scores else None, "scoreMax": max(scores) if scores else None,
                "scoreAverage": round(sum(scores) / len(scores), 4) if scores else None,
            }
        owner, other = summary["owner"], summary["other"]
        verdict = "not_run"
        if owner["checked"] >= 5 and other["checked"] >= 5:
            owner_rate = owner["accepted"] / owner["checked"]
            passed = other["accepted"] == 0 and other["acceptedWithoutCheck"] == 0 and owner_rate >= 0.8
            verdict = "pass" if passed else "fail"
        elif attempts:
            verdict = "in_progress"
        return {"round": current, "threshold": threshold, "summary": summary, "verdict": verdict,
                "attempts": attempts[-60:][::-1]}


_TRIAL: VoiceTrial | None = None
_TRIAL_LOCK = threading.Lock()


def voice_trial() -> VoiceTrial:
    global _TRIAL
    with _TRIAL_LOCK:
        if _TRIAL is None:
            _TRIAL = VoiceTrial()
        return _TRIAL
