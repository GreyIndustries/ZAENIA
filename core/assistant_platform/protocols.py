"""Protocols: saved routines Grey starts with a phrase ("goodnight", "I'm heading out", "game time").

A protocol is a short list of fixed, safe steps. ZAE runs it when a message is
one of its phrases (by voice or typing):

  say       ZAE says this
  open      open a tab (status, tasks, research, news, notes, ...)
  remind    set a reminder: "<minutes or time>|<text>", e.g. "30|stretch" or "7am tomorrow|gym"
  ask       ask her brain and say the answer, e.g. "what's on my calendar tomorrow?"
  headlines read the top three headlines
  coach     game coach "on" or "off"
  watch     "off" stops screen watching

Steps never run commands, change security or send messages: they only use
things ZAE already does. Stored in data/protocols.json.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_FILE = PROJECT_ROOT / "data" / "protocols.json"
KINDS = ("say", "open", "remind", "ask", "headlines", "coach", "watch")
TABS = ("overview", "status", "security", "tasks", "notes", "news", "research", "assistant", "files", "system", "workbench", "music", "fitness")
MAX_STEPS = 12
_LOCK = threading.Lock()

EXAMPLES = [
    {"name": "Goodnight", "phrases": ["goodnight", "good night zae"],
     "steps": [{"kind": "ask", "value": "Briefly, what's on my calendar and task list tomorrow?"},
               {"kind": "remind", "value": "7am tomorrow|Good morning. Time to get up."},
               {"kind": "say", "value": "Good night, sir."}]},
    {"name": "Game time", "phrases": ["game time", "gaming time"],
     "steps": [{"kind": "coach", "value": "on"}, {"kind": "say", "value": "Coach is on. Good luck, boss."}]},
]


def _norm(text: str) -> str:
    clean = re.sub(r"[^\w\s']", " ", str(text).casefold())
    clean = re.sub(r"^(?:hey |ok |okay )?(?:zae|zay|zaenia)\s+", "", " ".join(clean.split()))
    return re.sub(r"\s+(?:zae|zay|zaenia)$", "", clean).strip()


def validate(body: dict[str, Any]) -> dict[str, Any]:
    name = " ".join(str(body.get("name", "")).split())[:80]
    phrases = [_norm(p)[:80] for p in body.get("phrases") or [] if _norm(p)][:8]
    steps = []
    for step in (body.get("steps") or [])[:MAX_STEPS]:
        kind, value = str(step.get("kind", "")), " ".join(str(step.get("value", "")).split())[:300]
        if kind not in KINDS:
            raise ValueError(f"Unknown step: {kind}")
        if kind == "open" and value not in TABS:
            raise ValueError(f"There's no tab called {value}.")
        if kind in ("coach",) and value not in ("on", "off"):
            raise ValueError("Coach steps are on or off.")
        if kind == "watch" and value != "off":
            raise ValueError("The screen step can only stop watching.")
        if kind == "remind" and "|" not in value:
            raise ValueError("Reminder steps look like: 30|stretch or 7am tomorrow|gym")
        steps.append({"kind": kind, "value": value})
    if not name or not phrases or not steps:
        raise ValueError("A protocol needs a name, at least one phrase and at least one step.")
    return {"name": name, "phrases": phrases, "steps": steps, "enabled": body.get("enabled", True) is not False}


class Protocols:
    def __init__(self, path: Path = PROTOCOLS_FILE):
        self.path = Path(path)

    def list(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        from core.foundation.security.io import atomic_write
        atomic_write(self.path, json.dumps(items, indent=1).encode("utf-8"))

    def save(self, body: dict[str, Any], protocol_id: str | None = None) -> dict[str, Any]:
        record = validate(body)
        with _LOCK:
            items = self.list()
            taken = {p for item in items if item["id"] != protocol_id for p in item["phrases"]}
            clash = taken & set(record["phrases"])
            if clash:
                raise ValueError(f"Another protocol already uses: {', '.join(sorted(clash))}")
            if protocol_id:
                if not any(item["id"] == protocol_id for item in items):
                    raise KeyError("That protocol no longer exists.")
                items = [{**record, "id": protocol_id} if item["id"] == protocol_id else item for item in items]
                record["id"] = protocol_id
            else:
                record["id"] = uuid.uuid4().hex
                items.append(record)
            self._save(items)
        return record

    def delete(self, protocol_id: str) -> None:
        with _LOCK:
            self._save([item for item in self.list() if item["id"] != protocol_id])

    def match(self, message: str) -> dict[str, Any] | None:
        said = _norm(message)
        if not said or len(said) > 80:
            return None
        return next((item for item in self.list() if item.get("enabled", True) and said in item["phrases"]), None)


def run(protocol: dict[str, Any], *, ask: Callable[[str], str], set_reminder: Callable[[str, str], str],
        headlines: Callable[[], list[str]], coach: Callable[[bool], None], stop_watch: Callable[[], None]) -> dict[str, Any]:
    """Carry out each step; returns what to say and which tabs to open. A failed step is skipped and mentioned."""
    lines: list[str] = []
    tabs: list[str] = []
    for step in protocol["steps"]:
        kind, value = step["kind"], step["value"]
        try:
            if kind == "say":
                lines.append(value)
            elif kind == "open":
                tabs.append(value)
            elif kind == "remind":
                when, text = value.split("|", 1)
                lines.append(set_reminder(when.strip(), text.strip()))
            elif kind == "ask":
                lines.append(ask(value))
            elif kind == "headlines":
                top = headlines()[:3]
                lines.append("Top headlines: " + "; ".join(top) + "." if top else "No headlines right now.")
            elif kind == "coach":
                coach(value == "on")
            elif kind == "watch":
                stop_watch()
        except Exception as error:
            lines.append(f"(Couldn't do the {kind} step: {str(error)[:80]})")
    return {"reply": " ".join(line for line in lines if line) or "Done.", "open": tabs}


_PROTOCOLS: Protocols | None = None


def protocols() -> Protocols:
    global _PROTOCOLS
    if _PROTOCOLS is None:
        _PROTOCOLS = Protocols()
    return _PROTOCOLS
