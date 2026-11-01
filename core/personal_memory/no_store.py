"""Off the record (Phase 3 "no-store", 2026-11-01).

Grey can keep a turn, or a stretch of conversation, out of ZAE's memory:

* one turn: a sentence that starts or ends with "off the record", "don't remember this", "don't save this",
  "between us" (and close wording) is answered as usual but not written to the conversation log and not
  learned from;
* a stretch: "go off the record" starts it, "back on the record" (or 30 minutes) ends it. While it lasts, no turn
  is logged or learned from.

The state is in memory only (a restart ends it), so nothing about what was said is kept anywhere.
"""
from __future__ import annotations

import re
import threading
import time

OFF_MINUTES = 30
_TURN = re.compile(r"^\s*(?:(?:hey\s+)?zae[,\s]+)?(?:(?:this\s+is\s+)?off\s+the\s+record|don'?t\s+(?:remember|save|store|log|keep)\s+(?:this|that|any\s+of\s+this)|"
                   r"between\s+(?:us|you\s+and\s+me)|just\s+between\s+us)\b"
                   r"|\b(?:off\s+the\s+record|don'?t\s+(?:remember|save|store|log|keep)\s+(?:this|that|any\s+of\s+this)|just\s+between\s+us)[.!?]*\s*$", re.I)
_START = re.compile(r"^\s*(?:(?:hey\s+)?zae[,\s]+)?(?:let'?s\s+)?(?:go|going|we'?re\s+going|stay)\s+off\s+the\s+record\b", re.I)
_STOP = re.compile(r"^\s*(?:(?:hey\s+)?zae[,\s]+)?(?:(?:we'?re|go|going|let'?s\s+go)\s+)?back\s+on\s+the\s+record\b|^\s*(?:you\s+can\s+)?(?:remember|save)\s+again\b", re.I)

_lock = threading.Lock()
_until = 0.0


def check(text: str, *, now: float | None = None) -> bool:
    """True when this turn must not be stored or learned from. Also starts/stops an off-the-record stretch."""
    global _until
    now = time.time() if now is None else now
    words = " ".join(str(text or "").split())
    with _lock:
        if _STOP.search(words):
            _until = 0.0
            return True          # the "back on the record" sentence itself isn't worth storing
        if _START.search(words):
            _until = now + OFF_MINUTES * 60
            return True
        if _until > now:
            return True
        return bool(_TURN.search(words))


def active(*, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    with _lock:
        return _until > now


def reset() -> None:
    global _until
    with _lock:
        _until = 0.0
