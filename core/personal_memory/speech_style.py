"""How Zack talks, so ZAE can answer (and speak) the same way.

Only running averages are kept: message length, how casual the writing is,
the shorthand he uses, and how fast he speaks. No message text is stored.
The file is data/personal_memory/speech_style.json, on this PC only, and it is
updated only after a turn is saved with memory.write (see brain_service).
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STYLE_PATH = PROJECT_ROOT / "data" / "personal_memory" / "speech_style.json"
WEIGHT = 0.15          # how quickly the averages follow recent turns
MIN_TURNS = 5          # before this, ZAE keeps her default style
TYPICAL_WPM = 150.0    # an average English speaking pace

# Casual spellings worth mirroring when he uses them himself.
SHORTHAND = ("u", "ur", "ya", "yeah", "yep", "nah", "lets", "gonna", "wanna", "gotta", "kinda", "dont", "cant",
             "wont", "im", "thx", "pls", "ok", "okay", "bro", "dude", "lol", "btw", "rn", "idk")
_WORD = re.compile(r"[a-z']+")
_LOCK = threading.Lock()
# App-mic transcripts arrive as ordinary chat text, in lowercase without
# punctuation; remember them briefly (memory only) so they aren't read as typing.
_SPOKEN: list[tuple[float, str]] = []
SPOKEN_SECONDS = 180.0


def _key(text: str) -> str:
    return " ".join(_WORD.findall(str(text).casefold()))


def mark_spoken(text: str) -> None:
    import time
    now = time.monotonic()
    key = _key(text)
    with _LOCK:
        _SPOKEN[:] = [(at, k) for at, k in _SPOKEN if now - at < SPOKEN_SECONDS][-7:]
        if key:
            _SPOKEN.append((now, key))


def _was_spoken(text: str) -> bool:
    import time
    now = time.monotonic()
    key = _key(text)
    return bool(key) and any(now - at < SPOKEN_SECONDS and (key in k or k in key) for at, k in _SPOKEN)


def _blank() -> dict[str, Any]:
    return {"turns": 0, "spokenTurns": 0, "words": 0.0, "lowercase": 0.0, "noEndPunct": 0.0,
            "questions": 0.0, "shorthand": {}, "wpm": None, "speechSamples": 0}


class SpeechStyle:
    def __init__(self, path: Path = STYLE_PATH) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {**_blank(), **data} if isinstance(data, dict) else _blank()
        except (OSError, ValueError):
            return _blank()

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def observe_text(self, text: str, *, spoken: bool = False) -> None:
        """Fold one of Zack's own messages into the averages."""
        clean = " ".join(str(text).split())
        words = _WORD.findall(clean.casefold())
        if not words:
            return
        letters = [c for c in clean if c.isalpha()]
        spoken = spoken or _was_spoken(clean)
        with _LOCK:
            data = self.load()
            first = data["turns"] == 0
            ease = lambda old, new: new if first else old + WEIGHT * (new - old)
            data["words"] = round(ease(float(data["words"]), float(len(words))), 2)
            if not spoken:
                # Capitals and punctuation only mean something when he typed it.
                lower = 1.0 if letters and not any(c.isupper() for c in letters) else 0.0
                data["lowercase"] = round(ease(float(data["lowercase"]), lower), 3)
                data["noEndPunct"] = round(ease(float(data["noEndPunct"]), 0.0 if clean[-1] in ".!?" else 1.0), 3)
            data["questions"] = round(ease(float(data["questions"]), 1.0 if "?" in clean or words[0] in
                                           ("what", "why", "how", "when", "where", "who", "can", "is", "are", "do", "does") else 0.0), 3)
            counts = dict(data.get("shorthand") or {})
            for word in set(words):
                if word in SHORTHAND:
                    counts[word] = int(counts.get(word, 0)) + 1
            data["shorthand"] = counts
            data["turns"] = int(data["turns"]) + 1
            data["spokenTurns"] = int(data["spokenTurns"]) + (1 if spoken else 0)
            self._save(data)

    def observe_speech(self, words: int, seconds: float) -> None:
        """His speaking pace from one recognised voice clip."""
        if words < 4 or seconds < 1.5:
            return
        wpm = min(260.0, max(70.0, words * 60.0 / seconds))
        with _LOCK:
            data = self.load()
            old = data.get("wpm")
            data["wpm"] = round(wpm if old is None else float(old) + WEIGHT * (wpm - float(old)), 1)
            data["speechSamples"] = int(data.get("speechSamples", 0)) + 1
            self._save(data)

    def voice_speed(self) -> float:
        """Kokoro speed factor: a little quicker if he talks fast, calmer if he's slow."""
        data = self.load()
        if data.get("wpm") is None or int(data.get("speechSamples", 0)) < MIN_TURNS:
            return 1.0
        return round(min(1.12, max(0.92, 1.0 + (float(data["wpm"]) / TYPICAL_WPM - 1.0) * 0.5)), 3)

    def hint(self) -> str | None:
        """One short paragraph for the model on how to sound like a match for him."""
        data = self.load()
        if int(data["turns"]) < MIN_TURNS:
            return None
        notes: list[str] = []
        words = float(data["words"])
        if words <= 12:
            notes.append(f"He writes short messages (about {round(words)} words), so keep replies tight")
        elif words >= 35:
            notes.append(f"He writes in detail (about {round(words)} words a message); a little more context is welcome")
        casual = float(data["lowercase"]) >= 0.6 or float(data["noEndPunct"]) >= 0.6
        if casual:
            notes.append("he types casually (lowercase, little punctuation), so be relaxed and plain, never stiff")
        used = sorted(((n, w) for w, n in (data.get("shorthand") or {}).items() if n >= 3), reverse=True)[:5]
        if used:
            notes.append("words he uses himself and that you may use naturally: " + ", ".join(w for _, w in used))
        if float(data["questions"]) >= 0.6:
            notes.append("he mostly asks questions: answer first, no preamble")
        if not notes:
            return None
        return "HOW ZACK TALKS (learned from his own messages): " + "; ".join(notes) + "."


_STYLE: SpeechStyle | None = None


def speech_style() -> SpeechStyle:
    global _STYLE
    if _STYLE is None:
        _STYLE = SpeechStyle()
    return _STYLE
