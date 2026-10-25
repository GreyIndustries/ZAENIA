"""Suggestions: ZAE's own ideas for Grey's day and for herself, which he approves or dismisses.

Once a day (or when he asks) her brain looks at what she can see: today's and
tomorrow's calendar and tasks, open reminders, her health and security
status, and recent game-coach notes. She proposes a few specific ideas, each
either for "your day" or "ZAE herself". Approving a "your day" idea that
names a reminder sets it; an approved "ZAE herself" idea goes on the
improvement list for Claude or Codex to build. Nothing is done without his
approval. Stored in data/suggestions.json.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUGGESTIONS_FILE = PROJECT_ROOT / "data" / "suggestions.json"
KEEP = 300
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def gather_context() -> str:
    """What ZAE can see right now, as short plain lines (no secrets)."""
    lines: list[str] = []
    try:
        from core.assistant_followthrough.service import local_calendar_snapshot, local_task_snapshot
        events = local_calendar_snapshot() or []
        lines.append("Calendar (next days): " + "; ".join(f"{e.get('date', '')} {e.get('time', '')} {e.get('title', '')}".strip() for e in list(events)[:12]) if events else "Calendar: nothing coming up.")
        tasks = [t for t in (local_task_snapshot() or []) if not t.get("archived") and t.get("status") != "Completed"]
        lines.append("Open tasks: " + "; ".join(f"{t.get('title')} ({t.get('priority')}, due {t.get('deadline') or 'no deadline'})" for t in tasks[:12]) if tasks else "No open tasks.")
    except Exception:
        pass
    try:
        from core.assistant_platform.reminders import reminders
        upcoming = reminders().list()[:6]
        if upcoming:
            lines.append("Reminders: " + "; ".join(f"{r['text']} at {r['due']}" for r in upcoming))
    except Exception:
        pass
    try:
        from core.assistant_platform.selfcare import health
        issues = health().get("issues") or []
        lines.append("ZAE health: " + ("; ".join(issues) if issues else "all good"))
    except Exception:
        pass
    try:
        from core.assistant_platform.game_coach import game_coach
        last = game_coach().status().get("lastReview")
        if last:
            lines.append(f"Last game review ({last.get('game')}): {last.get('style', '')} Tips: {'; '.join(last.get('tips') or [])}")
    except Exception:
        pass
    lines.append("Local time: " + datetime.now().astimezone().strftime("%A %d %B, %I:%M %p"))
    return "\n".join(lines)


PROMPT = ("You are ZAE, Grey's personal assistant. From what you can see below, suggest up to 5 specific, useful ideas. "
          "Each is either for HIS DAY (planning, preparation, health, focus, a reminder worth setting) or for ZAE HERSELF "
          "(a feature or fix that would make you more useful to him). No generic advice. Reply with JSON only: "
          '{"suggestions": [{"for": "day" or "zae", "title": "short", "why": "one sentence", '
          '"remind": "optional: when|text, e.g. 6pm|pack gym bag"}]}\n\nWHAT YOU CAN SEE:\n')


class Suggestions:
    def __init__(self, path: Path = SUGGESTIONS_FILE):
        self.path = Path(path)

    def list(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        from core.foundation.security.io import atomic_write
        atomic_write(self.path, json.dumps(items[-KEEP:], indent=1).encode("utf-8"))

    def think(self, ask: Callable[[str], str], context: Callable[[], str] = gather_context) -> list[dict[str, Any]]:
        raw = ask(PROMPT + context())
        match = re.search(r"\{.*\}", raw, re.S)
        try:
            ideas = json.loads(match.group(0) if match else raw).get("suggestions") or []
        except (ValueError, AttributeError):
            ideas = []
        fresh = []
        with _LOCK:
            items = self.list()
            seen = {item["title"].casefold() for item in items if item["status"] != "dismissed"}
            for idea in ideas[:5]:
                title = " ".join(str(idea.get("title", "")).split())[:140]
                if not title or title.casefold() in seen:
                    continue
                seen.add(title.casefold())
                remind = str(idea.get("remind") or "")
                fresh.append({"id": uuid.uuid4().hex, "for": "zae" if str(idea.get("for", "")).lower().startswith("zae") else "day",
                              "title": title, "why": " ".join(str(idea.get("why", "")).split())[:300],
                              "remind": remind[:120] if "|" in remind else "", "status": "new", "created": _now()})
            self._save(items + fresh)
        return fresh

    def decide(self, suggestion_id: str, approve: bool, set_reminder: Callable[[str, str], str] | None = None) -> dict[str, Any]:
        with _LOCK:
            items = self.list()
            item = next((entry for entry in items if entry["id"] == suggestion_id), None)
            if item is None:
                raise KeyError("That suggestion no longer exists.")
            item["status"], item["decided"] = ("approved" if approve else "dismissed"), _now()
            if approve and item.get("remind") and set_reminder is not None:
                when, text = item["remind"].split("|", 1)
                item["outcome"] = set_reminder(when.strip(), text.strip())
            elif approve and item["for"] == "zae":
                item["outcome"] = "Added to ZAE's improvement list."
            self._save(items)
        return item


_SUGGESTIONS: Suggestions | None = None


def suggestions() -> Suggestions:
    global _SUGGESTIONS
    if _SUGGESTIONS is None:
        _SUGGESTIONS = Suggestions()
    return _SUGGESTIONS
