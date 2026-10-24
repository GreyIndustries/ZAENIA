"""System brief: what is working, what needs attention and what to improve.

Built from the live status feed plus a few read-only checks on the PC. It
reads no secrets and changes nothing.
"""
from __future__ import annotations

import importlib.util
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACIFIC = ZoneInfo("America/Los_Angeles")

# How to fix each module when it isn't ready, in plain words.
FIXES: dict[str, str] = {
    "security": "At the PC, run ZÆNIA's security setup to create the passkey and API token.",
    "brain": "Start Ollama on the PC, then download the model in brain_config.yaml (ollama pull).",
    "voice": "Check the Piper voice files in data/voices/piper and voice_config.yaml.",
    "calendar": "Link Google Calendar again so briefs can read it live.",
    "traffic": "Set WSDOT_API_KEY as a Windows user variable, then restart the ZÆNIA server.",
    "weather": "Check the PC's internet connection.",
    "carplay": "Start the car once, or check that the CarPlay shortcut reaches the PC.",
}


def _item(level: str, area: str, title: str, detail: str = "", fix: str = "", action: str = "") -> dict[str, str]:
    # action: a fix the desktop app can run itself ("Fix it" button or by voice).
    return {"level": level, "area": area, "title": title, "detail": detail, "fix": fix, "action": action}


def _hours_since(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=PACIFIC)
    return (datetime.now(timezone.utc) - moment).total_seconds() / 3600


def _overdue_tasks() -> int:
    try:
        from core.api.ui_tasks import list_tasks
        now = datetime.now(timezone.utc)
        return sum(
            1 for task in list_tasks()
            if not task.get("archived") and task.get("status") != "Completed" and task.get("deadline")
            and datetime.fromisoformat(str(task["deadline"]).replace("Z", "+00:00")) < now
        )
    except Exception:
        return 0


def build_system_brief(mode: str) -> dict[str, Any]:
    from core.api.status_feed import build_status

    status = build_status(mode)
    system = status.get("system") or {}
    brief_age = _hours_since(system.get("last_brief_at"))
    items: list[dict[str, str]] = []
    ready: list[str] = []
    for module in status["modules"]:
        if module["phase"] in ("ready",):
            ready.append(module["name"])
            continue
        if module["id"] == "carplay" and brief_age is not None and brief_age > 30:
            continue  # reported once below, with how long it has been
        level = "attention" if module["phase"] in ("error", "pending") else "improve"
        items.append(_item(level, module["id"], f"{module['name']}: {module['detail']}", fix=FIXES.get(module["id"], "")))

    if mode == "unattended":
        items.append(_item("info", "security", "Running in token mode",
                           "The brief, chat, status, tasks, calendar and file proposals work. Owner features stay locked.",
                           "Start the server with the passkey at the PC when you need owner features.", "start_passkey"))
    if brief_age is not None and brief_age > 30:
        items.append(_item("attention", "carplay", f"No CarPlay brief for {int(brief_age // 24)} day(s)",
                           "The last brief is older than a day.", FIXES["carplay"]))
    cpu, memory = system.get("cpu"), system.get("memory")
    if isinstance(cpu, int) and cpu >= 85:
        items.append(_item("attention", "pc", f"The PC's processor is busy ({cpu}%)", "Replies and briefs may be slow."))
    if isinstance(memory, int) and memory >= 90:
        items.append(_item("attention", "pc", f"The PC's memory is nearly full ({memory}%)", "Close unused programs."))
    try:
        disk = shutil.disk_usage(PROJECT_ROOT)
        free_gb = disk.free / 1024 ** 3
        if free_gb < 10 or disk.free / disk.total < 0.08:
            items.append(_item("attention", "pc", f"Low disk space ({free_gb:.0f} GB free)", "Free up space on the ZÆNIA drive."))
    except OSError:
        pass

    try:
        from core.api.ui_files import pending_count
        waiting = pending_count()
    except Exception:
        waiting = 0
    if waiting:
        items.append(_item("attention", "files", f"{waiting} file change(s) waiting for approval",
                           "Changes proposed from the phone apply only after you approve them.",
                           "Open Files in the desktop app and review Pending changes.", "open_files"))
    overdue = _overdue_tasks()
    if overdue:
        items.append(_item("attention", "tasks", f"{overdue} overdue task(s)", fix="Open Tasks to update or complete them.", action="open_tasks"))

    try:
        from core.api.security_check import list_reports
        latest = (list_reports(1) or [None])[0]
    except Exception:
        latest = None
    if latest is None or (_hours_since(latest.get("at")) or 0) > 7 * 24:
        items.append(_item("improve", "security", "Run a security self-check",
                           "No check in the last week." if latest else "ZAE hasn't checked her own security yet.",
                           "Press Fix it, or open Status & Security and run one. It also runs daily while the server is on.",
                           "run_security_check"))
    elif latest["status"] == "fail":
        items.append(_item("attention", "security", f"Security self-check: {latest['headline']}",
                           "Open Status & Security to see which checks failed and how to fix them.", action="open_status"))

    # Improvements for ZÆNIA itself.
    from core.api.desktop_key import is_paired
    if not is_paired():
        items.append(_item("improve", "files", "Pair the desktop app for file approvals",
                           "Without it, file changes can be proposed but not applied.",
                           "At the PC run: python -m core.api.server pair-desktop"))
    try:
        from core.api.ui_voice import VOICE_SCRIPT, service_status
        if not service_status()["running"]:
            items.append(_item("improve", "voice", "PC voice service is off",
                               "ZÆNIA isn't listening on the PC microphone. The app's own listening still works while it's open.",
                               f"Start it from the desktop app, or run {VOICE_SCRIPT} and enter your passkey.", "start_voice"))
    except Exception:
        pass
    try:
        from core.google_calendar_sync.google_calendar_api import status as google_write
        google = google_write()
    except Exception:
        google = {"clientFile": False, "connected": False}
    if not google["connected"]:
        items.append(_item("improve", "calendar", "Two-way Google Calendar",
                           "Events added in ZÆNIA stay in ZÆNIA; Google is read-only.",
                           "Sign in to Google once (you click Allow) so new events also go to Google."
                           if google["clientFile"] else
                           "Create a Google OAuth client (Desktop app), save it as data\\google_calendar\\credentials.json, then press Fix it.",
                           "connect_google"))
    try:
        from core.api.ui_voice import voice_check_status
        check = voice_check_status()
    except Exception:
        check = {"required": False}
    if check.get("required") and not check.get("setUp"):
        items.append(_item("attention", "voice", "Voice check for the app mic",
                           "The app mic now needs your voice, but voice checking isn't set up, so spoken turns are ignored.",
                           "Press Fix it to run voice training (passkey needed), or type to ZAE meanwhile.", "voice_training"))
    elif check.get("needsTraining"):
        items.append(_item("attention", "voice", "ZAE isn't recognising your voice well",
                           f"Only {int((check.get('recognisedRate') or 0) * 100)}% of your recent app-mic turns were recognised.",
                           "Press Fix it to retrain your voice on the approved mic (passkey needed).", "voice_training"))
    try:
        from core.email_watch.gmail import status as gmail_status
        mail = gmail_status()
    except Exception:
        mail = {"clientFile": False, "connected": False}
    if not mail["connected"]:
        items.append(_item("improve", "email", "Important email summaries",
                           "ZAE can't see your email yet.",
                           "In Google Cloud Console enable the Gmail API and add the gmail.readonly scope, then press Fix it and click Allow."
                           if mail["clientFile"] else
                           "Create a Google OAuth client (Desktop app) as for Calendar, then press Fix it.",
                           "connect_gmail"))
    try:
        from core.voice_output.neural_voice import settings as kokoro_settings
        kokoro = kokoro_settings()
        kokoro_ready = (kokoro["active"] and kokoro["model_path"].is_file()
                        and importlib.util.find_spec("kokoro_onnx") is not None)
    except Exception:
        kokoro_ready = False
    if not kokoro_ready:
        items.append(_item("improve", "voice", "More natural voice with Kokoro",
                           "Kokoro is free and sounds more natural than Piper.",
                           "Install Kokoro, then switch the brief and replies to it."))
    memory_file = PROJECT_ROOT / "data" / "conversation_memory.jsonl"
    try:
        tail = memory_file.read_bytes()[-200_000:] if memory_file.is_file() else b""
        # Only the newest saves matter: older entries are cleaned when they're read back.
        recent = b"\n".join(tail.splitlines()[-20:])
        if "[ZÆNIA owner moral compass]".encode("utf-8") in recent:
            items.append(_item("improve", "brain", "Lighter chat memory",
                               "Typed chats save the full moral-compass guidance with every message, which repeats it in "
                               "ZÆNIA's recent memory and slows replies.",
                               "Save only your words to memory and add the guidance once per reply."))
        if memory_file.is_file() and memory_file.stat().st_size > 5 * 1024 * 1024:
            items.append(_item("improve", "brain", "Conversation memory is large",
                               f"{memory_file.stat().st_size / 1024 ** 2:.0f} MB", "Archive older conversation memory."))
    except OSError:
        pass

    attention = [i for i in items if i["level"] == "attention"]
    improve = [i for i in items if i["level"] == "improve"]
    headline = ("Everything ZÆNIA checks is working." if not attention
                else f"{len(attention)} thing{'s' if len(attention) != 1 else ''} need{'s' if len(attention) == 1 else ''} attention.")
    spoken = [f"System brief. {len(ready)} of {len(status['modules'])} modules are ready."]
    if attention:
        spoken.append("Needs attention: " + "; ".join(i["title"] for i in attention[:4]) + ".")
    else:
        spoken.append("Nothing needs attention right now.")
    if improve:
        spoken.append("Next improvements: " + "; ".join(i["title"] for i in improve[:3]) + ".")
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "headline": headline,
        "ready": ready,
        "items": items,
        "counts": {"attention": len(attention), "improve": len(improve), "ready": len(ready)},
        "spoken": " ".join(spoken),
    }
