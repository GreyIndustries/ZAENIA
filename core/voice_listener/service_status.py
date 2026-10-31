"""Heartbeat for the PC voice service, so the desktop and phone UI can show
whether ZÆNIA is listening on the PC microphone.

State only ("listening", "hearing", "replying", "off") and timestamps: no
transcripts and no audio. Writing it never interrupts the voice runtime.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_FILE = PROJECT_ROOT / "data" / "ui" / "voice_service.json"
REFRESH_SECONDS = 2.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Heartbeat:
    def __init__(self) -> None:
        self.started_at = _now()
        self.state: str | None = None
        self.last = 0.0

    def report(self, state: str, *, force: bool = False, recognising: bool = True) -> None:
        now = time.monotonic()
        if not force and state == self.state and recognising == getattr(self, "recognising", True) and now - self.last < REFRESH_SECONDS:
            return
        self.state, self.last, self.recognising = state, now, recognising
        # recognising: False after several turns in a row failed the owner
        # voice check, so the app can listen with its own mic meanwhile.
        record = {"state": state, "startedAt": self.started_at, "updatedAt": _now(), "pid": os.getpid(),
                  "recognising": recognising}
        from core.assistant_platform.performance import COORDINATOR
        record["timing"] = COORDINATOR.snapshot()
        try:
            from core.foundation.security.io import atomic_write
            atomic_write(STATUS_FILE, json.dumps(record).encode("utf-8"))
        except Exception:
            pass  # the UI just shows the service as off


# ---- One answer per spoken turn ------------------------------------------
# The PC voice service and the app mic can both hear the same sentence. Each
# claims a turn before answering; whichever claims second drops it, so ZAE
# answers once. A claim holds hashed words and a time only, never the text.
TURN_FILE = PROJECT_ROOT / "data" / "ui" / "voice_turn.json"
# The PC checks and transcribes a whole sentence after it ends (a few seconds for a long one), and its
# transcriber words things differently from the app's, so the app waits longer and matches loosely.
SAME_TURN_SECONDS = 12.0
PC_HEARING_WAIT = 6.0
SIMILAR = 0.34


def _hashes(text: str) -> list[str]:
    import hashlib
    import re
    words = sorted(set(re.findall(r"[a-z0-9']+", str(text).casefold())))
    return [hashlib.sha256(word.encode("utf-8")).hexdigest()[:10] for word in words]


def _similar(left: list[str], right: list[str]) -> bool:
    a, b = set(left), set(right)
    return bool(a and b) and len(a & b) / len(a | b) >= SIMILAR


def _read_turn() -> dict:
    try:
        data = json.loads(TURN_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _pc_hearing() -> bool:
    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        fresh = (datetime.now(timezone.utc) - datetime.fromisoformat(str(data.get("updatedAt")))).total_seconds() <= 8.0
        return fresh and data.get("state") == "hearing"
    except (OSError, ValueError, TypeError):
        return False


def claim_turn(source: str, text: str, *, wait_for_pc: bool = False, record: bool = True,
               clock=time.time, sleep=time.sleep) -> bool:
    """True if `source` ("pc" or "app") should answer `text`; False if the other already is.

    record=False only checks (for words that may not be meant for ZAE).
    The app mic waits briefly while the PC service is still hearing, since the
    PC usually finishes the same sentence a moment later and answers it.
    """
    mine = _hashes(text)
    if not mine:
        return True
    deadline = clock() + (PC_HEARING_WAIT if wait_for_pc else 0.0)
    while True:
        other = _read_turn()
        if other.get("source") not in (None, source) and clock() - float(other.get("at", 0)) <= SAME_TURN_SECONDS \
                and _similar(mine, list(other.get("words") or [])):
            return False
        if not (wait_for_pc and _pc_hearing() and clock() < deadline):
            break
        sleep(0.15)
    if not record:
        return True
    try:
        from core.foundation.security.io import atomic_write
        atomic_write(TURN_FILE, json.dumps({"source": source, "at": clock(), "words": mine}).encode("utf-8"))
    except Exception:
        pass
    return True
