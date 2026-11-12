"""Phone as a remote for the PC (Grey, 2026-10-30).

The phone (any signed-in app or browser session) queues a small set of screen commands; the paired desktop app on
the PC (it holds the desktop key) collects them, runs only the ones on the list, and reports what is open. Nothing
here can save files, launch programs, apply code or approve anything: those stay behind the desktop-only routes
until the "phone near the PC" approval is designed with Grey.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from collections import deque
from typing import Any

ACTIONS = {
    "arrange_2": "Arrange two app windows",
    "arrange_3": "Arrange three app windows",
    "arrange_4": "Arrange four app windows",
    "undo_arrange": "Undo the last app-window arrangement",
    "open": "Open a tab on the PC",
    "close": "Close a tab on the PC",
    "minimize": "Minimise a tab on the PC",
    "show_desktop": "Minimise every tab (show the dashboard)",
    "restore_all": "Bring every minimised tab back",
    "calm": "Switch the PC to Calm view",
    "wake": "Leave Calm view on the PC (goes to the dashboard)",
}
TAB = re.compile(r"^[a-z]{2,20}$")
MAX_QUEUE = 50
TTL_SECONDS = 120          # a command not collected within 2 minutes is dropped, so a stale tap never fires later
ONLINE_SECONDS = 15         # the PC counts as connected if it reported within this many seconds

_lock = threading.Lock()
_queue: deque[dict[str, Any]] = deque(maxlen=MAX_QUEUE)
_state: dict[str, Any] = {"windows": [], "active": None, "calm": False, "section": "overview", "at": 0.0}


def queue_command(action: str, target: str = "", *, now: float | None = None) -> dict[str, Any]:
    if action not in ACTIONS:
        raise ValueError("That isn't something the remote can do.")
    target = str(target or "").strip().lower()
    if action in ("open", "close", "minimize") and not TAB.match(target):
        raise ValueError("Pick a tab first.")
    if action.startswith("arrange_") and target:
        targets = target.split(",")
        known = {"tasks", "notes", "workbench", "music", "research", "codedoctor", "arena", "warroom", "assistant", "system"}
        if len(targets) != int(action[-1]) or len(set(targets)) != len(targets) or not all(item in known for item in targets):
            raise ValueError("Pick distinct supported app windows for this layout.")
    command = {"id": uuid.uuid4().hex, "action": action, "target": target if action in ("open", "close", "minimize") or action.startswith("arrange_") else "",
               "at": now if now is not None else time.time()}
    with _lock:
        _queue.append(command)
    return {"queued": command["id"], "pcOnline": pc_online(now)}


_seen = {"at": 0.0}


def last_collect() -> float:
    """When the desktop app last checked in (Status → Uptime counts it as running)."""
    return _seen["at"]


def collect(*, now: float | None = None) -> list[dict[str, Any]]:
    """For the desktop app: every fresh command, oldest first; each is handed out once."""
    now = now if now is not None else time.time()
    _seen["at"] = now
    with _lock:
        fresh = [c for c in _queue if now - c["at"] <= TTL_SECONDS]
        _queue.clear()
    return fresh


def report_state(windows: list[dict[str, Any]], active: str | None, calm: bool, section: str, *, now: float | None = None) -> dict[str, Any]:
    clean = []
    for w in windows[:30]:
        tab = str(w.get("id", "")).lower()
        if TAB.match(tab):
            clean.append({"id": tab, "title": str(w.get("title", tab))[:40], "minimized": bool(w.get("minimized"))})
    with _lock:
        _state.update({"windows": clean, "active": str(active or "")[:20] or None, "calm": bool(calm),
                       "section": str(section or "")[:20], "at": now if now is not None else time.time()})
        return dict(_state)


def pc_online(now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    with _lock:
        return now - _state["at"] <= ONLINE_SECONDS


def state(*, now: float | None = None) -> dict[str, Any]:
    now = now if now is not None else time.time()
    with _lock:
        copy = dict(_state)
        pending = sum(1 for c in _queue if now - c["at"] <= TTL_SECONDS)
    copy["online"] = now - copy["at"] <= ONLINE_SECONDS
    copy["lastSeenSeconds"] = round(now - copy["at"]) if copy["at"] else None
    copy["pending"] = pending
    copy["actions"] = ACTIONS
    copy.pop("at", None)
    return copy
