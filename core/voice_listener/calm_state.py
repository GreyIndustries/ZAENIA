"""Calm view and ZAE's PC voice (2026-10-31).

When the PC voice service has the microphone, the app's own mic is off, so the
app never heard Grey's wake-up calls while Calm view was up (and Calm said "the
mic is off"). The two run in different processes, so they share two small files:

* data/ui/calm.json: the app reports whether Calm view is up (through
  /api/remote/state, every 8 s at most). It counts only while fresh, so a
  closed or crashed app can't leave the PC voice deaf.
* data/ui/calm_event.json: the PC voice service notes a wake-up call (while
  calm) or a sleep phrase (while not), and the app picks it up through
  /api/remote/collect.

Only turns already verified as Grey's voice reach `calm_turn`. While calm,
every other sentence is ignored, the same rule as the app mic.
The phrase lists match desktop/src/core/calmPhrases.ts; keep them in step.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

UI_DIR = Path(__file__).resolve().parents[2] / "data" / "ui"
CALM_FILE = UI_DIR / "calm.json"
EVENT_FILE = UI_DIR / "calm_event.json"
FRESH_SECONDS = 30.0

WAKE_CALLS = [
    ["wake up sleepy we have work to do", "wake up sleepy we got work to do", "wake up sleepy"],
    ["sleeping on the job"],
    ["the boss is here", "boss is here"],
    ["zae you're still there", "zae are you still there", "you still there zae"],
    ["day is not yet over", "the day is not over yet", "the night is still young", "night is still young"],
]
SLEEP_PHRASES = [
    ["take everything to the background", "take it all to the background"],
    ["i'm going to sleep", "i am going to sleep", "going to sleep"],
    ["let's put a pin in this and continue tomorrow", "put a pin in this and continue tomorrow", "let's put a pin in this"],
    ["calm view", "go to calm view", "calm mode"],
]
_NAMES = re.compile(r"\b(?:zae|zay|zai|zeh|zaenia|xenia|zania)\b")
_FILLER = re.compile(r"\b(?:hey|ok|okay|so|well|um|uh|yo)\b")


def normalize(text: str) -> str:
    text = str(text).lower().replace("’", "'")
    text = re.sub(r"\bi am\b", "i'm", text)
    text = re.sub(r"\blet us\b", "let's", text)
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _close(said: str, phrase: str) -> bool:
    words = [w for w in _FILLER.sub(" ", _NAMES.sub(" ", said)).split() if w]
    target = [w for w in _NAMES.sub(" ", phrase).split() if w]
    if not target or len(words) > len(target) + 3:
        return False
    have = set(words)
    hits = sum(1 for w in target if w in have)
    return hits / len(target) >= (1 if len(target) <= 3 else 0.8)


def match(text: str) -> dict[str, Any] | None:
    said = normalize(text)
    if not said:
        return None
    for kind, table in (("wake", WAKE_CALLS), ("sleep", SLEEP_PHRASES)):
        for index, phrases in enumerate(table):
            if any(_close(said, normalize(p)) for p in phrases):
                return {"kind": kind, "id": index + 1, "phrase": phrases[0]}
    return None


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def report(calm: bool, *, now: float | None = None) -> None:
    """The app's Calm view state (called from /api/remote/state)."""
    _write(CALM_FILE, {"calm": bool(calm), "at": now if now is not None else time.time()})


def is_calm(*, now: float | None = None) -> bool:
    data = _read(CALM_FILE)
    now = now if now is not None else time.time()
    try:
        return bool(data.get("calm")) and now - float(data.get("at", 0)) <= FRESH_SECONDS
    except (TypeError, ValueError):
        return False


def calm_turn(text: str, *, now: float | None = None) -> bool:
    """For a verified PC-voice turn: True when Calm view handles it (a wake-up call or sleep phrase, or any
    speech while calm, which is ignored). False lets the turn go on as usual."""
    now = now if now is not None else time.time()
    calm = is_calm(now=now)
    found = match(text)
    if found and found["kind"] == ("wake" if calm else "sleep"):
        _write(EVENT_FILE, {**found, "at": now})
        return True
    return calm


def take_event(*, now: float | None = None, max_age: float = 20.0) -> dict[str, Any] | None:
    """The newest wake-up call / sleep phrase from the PC voice, once (called from /api/remote/collect)."""
    data = _read(EVENT_FILE)
    if not data:
        return None
    try:
        EVENT_FILE.unlink()
    except OSError:
        pass
    now = now if now is not None else time.time()
    try:
        fresh = now - float(data.get("at", 0)) <= max_age
    except (TypeError, ValueError):
        return None
    if not fresh or data.get("kind") not in ("wake", "sleep"):
        return None
    return {"kind": data["kind"], "id": int(data.get("id", 0)), "phrase": str(data.get("phrase", ""))[:80]}
