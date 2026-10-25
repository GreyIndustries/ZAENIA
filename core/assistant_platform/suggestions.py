"""Suggestions: ZAE's own ideas for Grey's day, for upgrading her system and for new features.

When he asks, her brain looks at what she can see and proposes a few specific
ideas of three kinds:
- "day": his calendar, tasks, reminders and game-coach notes (planning,
  preparation, health, a reminder worth setting);
- "upgrade": her own system, from real data: installed versions of Python, her
  key packages and Ollama against the latest releases, her local models, the
  PC's RAM, GPU and disk, and her health checks;
- "feature": a new capability that isn't already in the app (the list of what
  exists is given so she doesn't repeat it).
Upgrade and feature ideas carry how to do it and the effort. Approving a "day"
idea that names a reminder sets it; approved upgrades and features go on her
upgrade plan for Grey, Claude or Codex to build. Nothing is done without his
approval. Stored in data/suggestions.json; version checks are cached for 12
hours in data/ui/upgrade_check.json.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUGGESTIONS_FILE = PROJECT_ROOT / "data" / "suggestions.json"
CHECK_FILE = PROJECT_ROOT / "data" / "ui" / "upgrade_check.json"
KINDS = ("day", "upgrade", "feature")
PACKAGES = ("fastapi", "uvicorn", "pydantic", "requests", "cryptography", "torch", "speechbrain", "kokoro-onnx",
            "onnxruntime", "vosk", "sounddevice", "numpy", "pypdf", "argon2-cffi")
FEATURES = ("Overview with the glowing core; Status (health, protocols, self-sustain, reminders); Security tab with passkey "
            "unlock; Tasks & Calendar (Google two-way sync, reminders); Notes; Workbench (projects, science tools, chemistry "
            "and physics labs); Music; Fitness & Health; News (16 feeds, world search, reader); Research (historical "
            "connections, notebook, library, scripture with Hebrew/Greek and Jewish texts and the Quran, translation); Code "
            "Doctor; Suggestions; Arena (compare local models); Assistant (memory, learning library, what she has learned, "
            "follow-through); Files with source search; Settings (35 accent colours, per-tab looks, Vault). Voice: Kokoro voice, "
            "Vosk listening, speaker verification, barge-in, adaptive speaking style. Game mode and game coach, screen watch, "
            "web lookups, phone line (Twilio), Gmail summaries, nightly backups, watchdog, self-service maintenance script "
            "(status, test, update, build, restart, rollback).")
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
    try:
        from core.research.agent import watch
        latest = watch().latest()
        if latest:
            lines.append("Watch-list news: " + " | ".join(latest))
    except Exception:
        pass
    lines.append("Local time: " + datetime.now().astimezone().strftime("%A %d %B, %I:%M %p"))
    return "\n".join(lines)


def _cached_check(compute: Callable[[], dict[str, Any]], path: Path = CHECK_FILE, hours: float = 12) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(data.get("at", 0)) < hours * 3600:
            return data
    except (OSError, ValueError):
        pass
    data = compute()
    data["at"] = time.time()
    try:
        from core.foundation.security.io import atomic_write
        atomic_write(path, json.dumps(data, indent=1).encode("utf-8"))
    except Exception:
        pass
    return data


def check_versions(get: Callable | None = None) -> dict[str, Any]:
    """Installed versus latest: Python, her key packages (PyPI) and Ollama (GitHub releases). Public data only."""
    from concurrent.futures import ThreadPoolExecutor
    from importlib import metadata
    if get is None:
        from core.research.web import get_json as get
    installed = {}
    for name in PACKAGES:
        try:
            installed[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue

    def latest(name: str) -> tuple[str, str]:
        try:
            return name, str(get(f"https://pypi.org/pypi/{name}/json", timeout=8)["info"]["version"])
        except Exception:
            return name, ""
    with ThreadPoolExecutor(max_workers=6) as pool:
        newest = dict(pool.map(latest, installed))
    ollama = {"installed": "", "latest": ""}
    try:
        import requests
        ollama["installed"] = str(requests.get("http://127.0.0.1:11434/api/version", timeout=3).json().get("version", ""))
    except Exception:
        pass
    try:
        ollama["latest"] = str(get("https://api.github.com/repos/ollama/ollama/releases/latest", timeout=8).get("tag_name", "")).lstrip("v")
    except Exception:
        pass
    return {"python": sys.version.split()[0], "packages": [{"name": n, "installed": v, "latest": newest.get(n, "")} for n, v in installed.items()],
            "ollama": ollama}


def gather_system_context(versions: Callable[[], dict[str, Any]] | None = None) -> str:
    """Her own system as short plain lines: versions, models, hardware and health (no secrets, no file contents)."""
    lines: list[str] = []
    try:
        data = versions() if versions else _cached_check(check_versions)
        lines.append(f"Python {data.get('python')}.")
        behind = [f"{p['name']} {p['installed']} (latest {p['latest']})" for p in data.get("packages", []) if p.get("latest") and p["latest"] != p["installed"].split("+")[0]]
        current = [p["name"] for p in data.get("packages", []) if p.get("latest") == p["installed"].split("+")[0]]
        lines.append("Packages with newer releases: " + ("; ".join(behind) if behind else "none") + ".")
        if current:
            lines.append("Packages up to date: " + ", ".join(current) + ".")
        ollama = data.get("ollama") or {}
        if ollama.get("installed"):
            lines.append(f"Ollama {ollama['installed']}" + (f" (latest {ollama['latest']})" if ollama.get("latest") and ollama["latest"] != ollama["installed"] else " (up to date)") + ".")
    except Exception:
        pass
    try:
        import requests
        models = requests.get("http://127.0.0.1:11434/api/tags", timeout=3).json().get("models") or []
        lines.append("Local models: " + "; ".join(f"{m.get('name')} ({round((m.get('size') or 0) / 1e9, 1)} GB, {str(m.get('modified_at', ''))[:10]})" for m in models[:12]) + ".")
    except Exception:
        pass
    try:
        from core.brain.local_llm import active_model, get_brain_settings
        settings = get_brain_settings()
        lines.append(f"Brain model in use: {active_model(settings)}, context window {settings.get('context_window')}.")
    except Exception:
        pass
    try:
        from core.api.status_bar import status_bar
        bar = status_bar()
        gpu = bar.get("gpu") or {}
        lines.append(f"PC: RAM {bar.get('ramUsedGb')}/{bar.get('ramTotalGb')} GB used, GPU memory {gpu.get('memoryUsedGb', '?')}/{gpu.get('memoryTotalGb', '?')} GB, "
                     f"disk {bar.get('diskFreeGb')} GB free, voice {bar.get('voice')}, server mode {bar.get('mode')}.")
    except Exception:
        pass
    try:
        node = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
        if node:
            lines.append(f"Node {node}.")
    except Exception:
        pass
    try:
        from core.assistant_platform.selfcare import health
        issues = health().get("issues") or []
        lines.append("Health issues: " + ("; ".join(issues) if issues else "none") + ".")
    except Exception:
        pass
    lines.append("WHAT THE APP ALREADY HAS: " + FEATURES)
    return "\n".join(lines)


RULES = {
    "day": "DAY (his planning, preparation, health, focus, or a reminder worth setting)",
    "upgrade": ("UPGRADE (updating or replacing part of your own system: a package, Python, Ollama, a better or newer local "
                "model for this PC's GPU and RAM, a setting, or fixing a health issue; base it on the versions and numbers "
                "given, never invent a version)"),
    "feature": "FEATURE (a new capability for you that is NOT already in the list of what the app has)",
}
FOCUS = {"all": ("day", "upgrade", "feature"), "day": ("day",), "system": ("upgrade", "feature")}


def build_prompt(focus: str, context: str, earlier: list[str]) -> str:
    kinds = FOCUS.get(focus, FOCUS["all"])
    return ("You are ZAE, Grey's personal assistant. From what you can see below, suggest up to "
            f"{5 if len(kinds) < 3 else 6} specific, useful ideas. Each idea is one of: "
            + "; ".join(RULES[k] for k in kinds) + ". No generic advice. "
            + ("Don't repeat these earlier ideas: " + "; ".join(earlier[:30]) + ". " if earlier else "")
            + "Reply with JSON only: {\"suggestions\": [{\"for\": " + " or ".join(f'\"{k}\"' for k in kinds)
            + ", \"title\": \"short\", \"why\": \"one sentence\""
            + (", \"remind\": \"optional: when|text, e.g. 6pm|pack gym bag\"" if "day" in kinds else "")
            + (", \"how\": \"for upgrades and features: one or two sentences on how to do it\", \"effort\": \"small, medium or large\""
               if "upgrade" in kinds else "")
            + "}]}\n\nWHAT YOU CAN SEE:\n" + context)


def _kind(value: Any, focus: str) -> str:
    text = str(value or "").lower()
    if text.startswith(("upgrade", "update")):
        return "upgrade"
    if text.startswith(("feature", "zae", "new")):
        return "feature"
    if text.startswith(("day", "his", "you")):
        return "day"
    return "day" if focus != "system" else "feature"


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

    def think(self, ask: Callable[[str], str], context: Callable[[], str] | None = None, focus: str = "all") -> list[dict[str, Any]]:
        if focus not in FOCUS:
            raise ValueError("Unknown focus.")
        if context is None:
            parts = []
            if focus in ("all", "day"):
                parts.append(gather_context())
            if focus in ("all", "system"):
                parts.append(gather_system_context())
            seen_text = "\n".join(parts)
        else:
            seen_text = context()
        earlier = [item["title"] for item in self.list()[::-1] if item.get("for") != "day"]
        raw = ask(build_prompt(focus, seen_text, earlier))
        match = re.search(r"\{.*\}", raw, re.S)
        try:
            ideas = json.loads(match.group(0) if match else raw).get("suggestions") or []
        except (ValueError, AttributeError):
            ideas = []
        fresh = []
        with _LOCK:
            items = self.list()
            seen = {item["title"].casefold() for item in items if item["status"] != "dismissed"}
            for idea in ideas[:6]:
                title = " ".join(str(idea.get("title", "")).split())[:140]
                if not title or title.casefold() in seen:
                    continue
                seen.add(title.casefold())
                kind = _kind(idea.get("for"), focus)
                if kind not in FOCUS[focus]:
                    continue
                remind = str(idea.get("remind") or "") if kind == "day" else ""
                effort = str(idea.get("effort") or "").lower().strip()
                fresh.append({"id": uuid.uuid4().hex, "for": kind,
                              "title": title, "why": " ".join(str(idea.get("why", "")).split())[:300],
                              "how": " ".join(str(idea.get("how") or "").split())[:500] if kind != "day" else "",
                              "effort": effort if effort in ("small", "medium", "large") else "",
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
            elif approve and item["for"] in ("zae", "upgrade", "feature"):
                item["outcome"] = "Added to ZAE's upgrade plan."
            self._save(items)
        return item


def upgrade_plan(items: list[dict[str, Any]]) -> str:
    """Approved upgrades and features as a plain list to hand to Claude or Codex (or to do himself)."""
    lines = []
    for item in items:
        if item.get("status") == "approved" and item.get("for") in ("zae", "upgrade", "feature"):
            kind = "Upgrade" if item["for"] == "upgrade" else "Feature"
            effort = f" [{item['effort']}]" if item.get("effort") else ""
            lines.append(f"- {kind}{effort}: {item['title']}. {item.get('why', '')}" + (f" How: {item['how']}" if item.get("how") else ""))
    return "ZAE upgrade plan (approved by Grey):\n" + "\n".join(lines) if lines else ""


_SUGGESTIONS: Suggestions | None = None


def suggestions() -> Suggestions:
    global _SUGGESTIONS
    if _SUGGESTIONS is None:
        _SUGGESTIONS = Suggestions()
    return _SUGGESTIONS
