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
HANDOFF_FILE = UI_DIR / "voice_handoff.json"
APP_ONLINE_SECONDS = 20.0
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


# Grey, 2026-10-31: "wake up calls and sleep calls will not be word for word but be more flexible. The only thing
# zae is actually looking for is my authentic voice." Only turns already verified as his voice get here, so:
# * while calm, any sentence he says to ZAE wakes her (her name, or Talk judges it's meant for her; if Talk can't
#   be asked, his voice is enough);
# * while awake, a sentence with a rest/sleep cue puts her into Calm view when Talk agrees that's what he means.
SLEEP_CUE = re.compile(r"\b(?:sleep|bed|good ?night|nap|background|rest|calm|pin in|call it a (?:day|night)|that'?s (?:all|it) for (?:now|today|tonight)|take a break|signing off|done for (?:the day|today|tonight)|stand ?by|power down|shut ?down for)\b", re.I)


def _ask_talk(system: str, text: str, timeout: float = 4.0) -> dict[str, Any] | None:
    try:
        import requests
        from core.brain.conductor import TALK_KEEP_ALIVE, TALK_MODEL
        from core.brain.local_llm import _game_keep_alive, get_brain_settings
        settings = get_brain_settings()
        reply = requests.post(settings["endpoint"], timeout=timeout, json={
            "model": TALK_MODEL, "stream": False, "format": "json", "think": False, "keep_alive": _game_keep_alive(TALK_KEEP_ALIVE),
            "options": {"temperature": 0, "num_predict": 16, "num_ctx": settings["context_window"]},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": text[:400]}]})
        reply.raise_for_status()
        data = json.loads(reply.json().get("message", {}).get("content", "") or "{}")
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def intent(text: str, calm: bool, *, ask=None) -> dict[str, Any] | None:
    """{"kind": "wake"|"sleep", ...} for a verified sentence, flexibly; None when it's neither."""
    ask = ask or _ask_talk
    found = match(text)
    if found:
        return found if found["kind"] == ("wake" if calm else "sleep") else None
    said = normalize(text)
    if not said:
        return None
    if calm:
        if _NAMES.search(said):
            return {"kind": "wake", "id": 1, "phrase": "flexible"}
        # His voice is the gate: wake unless the sentence is plainly for another person.
        verdict = ask("Grey's assistant is resting and hears Grey say the sentence below. Decide only whether he is plainly "
                      "speaking to ANOTHER PERSON (he names or addresses someone else, like 'hey mom', 'babe', 'hold on, "
                      "I'm on a call', or answers someone in the room). Anything else, including greetings, 'let's get "
                      "back to work', 'you awake?', questions or requests, is for the assistant.\n"
                      "Reply only with JSON: {\"other_person\": true} or {\"other_person\": false}.", said)
        if verdict is None or verdict.get("other_person") is not True:
            return {"kind": "wake", "id": 1, "phrase": "flexible"}
        return None
    if not SLEEP_CUE.search(said):
        return None
    verdict = ask("Grey says the sentence below to his assistant. Is he wrapping up or saying goodnight, so the assistant "
                  "should go quiet and rest until he's back? Yes for things like 'I'm heading to bed', 'let's call it a "
                  "night', 'that's it for today', 'take everything to the background'. No for questions "
                  "or requests about sleep or rest, like 'how much sleep do I need' or 'plan the rest of the week'.\n"
                  "Reply only with JSON: {\"rest\": true} or {\"rest\": false}.", said)
    if verdict and verdict.get("rest") is True:
        return {"kind": "sleep", "id": 1, "phrase": "flexible"}
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
    found = intent(text, calm)
    if found:
        _write(EVENT_FILE, {**found, "at": now})
        return True
    return calm


def app_online(*, now: float | None = None) -> bool:
    """The desktop app is open and reporting (it posts its state at least every 8 s)."""
    now = now if now is not None else time.time()
    try:
        return now - float(_read(CALM_FILE).get("at", 0)) <= APP_ONLINE_SECONDS
    except (TypeError, ValueError):
        return False


def hand_to_app(text: str, *, now: float | None = None) -> bool:
    """While the app is open, a verified PC-voice request goes to the app's own chat, so it runs exactly like a
    typed or app-mic request: logging, saving and every other in-app action, with the result shown on screen
    (Grey, 2026-10-31). False when the app isn't open; the PC voice then answers by itself."""
    now = now if now is not None else time.time()
    text = " ".join(str(text).split())[:2000]
    if not text or not app_online(now=now):
        return False
    queue = [t for t in _read(HANDOFF_FILE).get("turns", []) if isinstance(t, dict) and now - float(t.get("at", 0)) <= 30][-4:]
    queue.append({"text": text, "at": now})
    _write(HANDOFF_FILE, {"turns": queue})
    return True


def take_voice_turns(*, now: float | None = None) -> list[str]:
    """PC-voice requests waiting for the app, once each (called from /api/remote/collect)."""
    data = _read(HANDOFF_FILE)
    if not data:
        return []
    try:
        HANDOFF_FILE.unlink()
    except OSError:
        pass
    now = now if now is not None else time.time()
    out = []
    for turn in data.get("turns", []):
        try:
            if isinstance(turn, dict) and now - float(turn.get("at", 0)) <= 30 and str(turn.get("text", "")).strip():
                out.append(str(turn["text"])[:2000])
        except (TypeError, ValueError):
            continue
    return out


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
