from __future__ import annotations

import json
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERSONALITY_PATH = PROJECT_ROOT / "core" / "console" / "console_personality.yaml"
ALIASES_PATH = PROJECT_ROOT / "core" / "console" / "console_aliases.yaml"
HISTORY_PATH = PROJECT_ROOT / "data" / "console_history.jsonl"

console = Console()
from core.foundation.console_gate import console_gate


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_personality() -> dict[str, Any]:
    if not PERSONALITY_PATH.exists():
        raise FileNotFoundError(f"Missing console personality file: {PERSONALITY_PATH}")

    return load_yaml(PERSONALITY_PATH)


def load_aliases() -> dict[str, Any]:
    data = load_yaml(ALIASES_PATH)
    raw_aliases = data.get("aliases", {}) or {}

    # [comment omitted from source review]
    return {
        str(key).lower().strip(): value
        for key, value in raw_aliases.items()
    }


def pick(options: list[str], fallback: str = "") -> str:
    if not options:
        return fallback
    return random.choice(options)


def personality_section(*keys: str) -> Any:
    data = load_personality()
    current: Any = data

    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current


def say(text: str, style: str = "cyan") -> None:
    console.print(f"[{style}]{text}[/{style}]")


def zaenia_success(text: str | None = None) -> None:
    confirmations = personality_section("console_personality", "confirmations", "success") or []
    prefix = pick(confirmations, "Done, Sir.")
    say(f"{prefix} {text or ''}".strip(), "green")


def zaenia_error(text: str) -> None:
    prefixes = personality_section("console_personality", "error_style", "prefixes") or []
    guidance = personality_section("console_personality", "error_style", "guidance") or []

    prefix = pick(prefixes, "I see the issue.")
    guide = pick(guidance, "We fix one thing at a time.")

    say(f"{prefix} {text}", "red")
    say(guide, "yellow")


def log_command(command: str) -> None:
    # Do not retain raw text, accidentally entered credentials, or model prompts.
    from core.foundation.security.audit import audit
    audit("console.command_received", reason_code="owner_console_input")


def run_module(module: str, args: list[str] | None = None) -> int:
    return console_gate.run(module, args)


def run_powershell(command_text: str) -> int:
    raise PermissionError("Raw PowerShell execution is disabled. Use a separately registered management action.")


def show_help() -> None:
    help_text = """
Commands:
  help                Show this command list
  briefing            Show current drive briefing
  briefing say        Speak current drive briefing on Windows
  commute / drive     Briefing with forced I-5 traffic
  weather             Show current weather
  weather say         Speak current weather
  traffic             Check I-5 traffic now
  calendar            Show today's ZÆNIA calendar
  sync                Sync Google Calendar iCal feed into ZÆNIA
  audio               Generate CarPlay MP3
  audio force         Generate CarPlay MP3 with forced traffic
  carplay             Sync calendar, then generate CarPlay MP3
  1840                Check evening task + OneDrive file timestamps
  status              Show quick system status
  history             Show recent console commands
  clear               Clear the screen
  goodnight / exit    Close console
""".strip()

    console.print(Panel(help_text, title="ZÆNIA Console Help", border_style="cyan"))


def show_status() -> None:
    onedrive_audio = Path.home() / "OneDrive" / "CarStartupAudio.mp3"

    checks = [
        ("Console personality", PERSONALITY_PATH.exists()),
        ("Console aliases", ALIASES_PATH.exists()),
        ("Console history", HISTORY_PATH.exists()),
        ("Google iCal URL", (PROJECT_ROOT / "data" / "google_calendar" / "google_calendar_ics_url.txt").exists()),
        ("CarPlay audio script", (PROJECT_ROOT / "scripts" / "generate_carplay_audio.ps1").exists()),
        ("OneDrive audio", onedrive_audio.exists()),
        ("Local calendar", (PROJECT_ROOT / "core" / "calendar_context" / "zaenia_calendar.yaml").exists()),
    ]

    lines = []
    for name, ok in checks:
        status = "OK" if ok else "Missing"
        lines.append(f"{name}: {status}")

    console.print(Panel("\n".join(lines), title="ZÆNIA Quick Status", border_style="green"))


def show_history(limit: int = 8) -> None:
    if not HISTORY_PATH.exists():
        say("No console history yet.", "yellow")
        return

    lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    recent = lines[-limit:]

    if not recent:
        say("No console history yet.", "yellow")
        return

    output = []
    for line in recent:
        try:
            item = json.loads(line)
            output.append(f"{item.get('timestamp')} — {item.get('command')}")
        except json.JSONDecodeError:
            output.append(line)

    console.print(Panel("\n".join(output), title="Recent Console Commands", border_style="cyan"))


def repair_evening_task() -> None:
    zaenia_success("Repairing the evening CarPlay scheduled task.")

    command_text = r'''
Write-Host "`n--- Recreating Evening Scheduled Task ---"

schtasks /Delete /TN "ZAENIA CarPlay Evening Audio" /F 2>$null

schtasks /Create /TN "ZAENIA CarPlay Evening Audio" /TR "powershell.exe -ExecutionPolicy Bypass -File C:\Projects\ZAENIA\scripts\generate_carplay_audio.ps1" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:46 /F

Write-Host "`n--- Running Auto Script Once Now ---"
powershell.exe -ExecutionPolicy Bypass -File C:\Projects\ZAENIA\scripts\generate_carplay_audio.ps1

Write-Host "`n--- Evening Scheduled Task Status ---"
schtasks /Query /TN "ZAENIA CarPlay Evening Audio" /V /FO LIST

Write-Host "`n--- OneDrive CarPlay Files ---"
Get-Item "$env:OneDrive\CarStartupAudio.mp3" | Select-Object Name, LastWriteTime, Length | Format-List
Get-Item "$env:OneDrive\CarStartupAudio.txt" | Select-Object Name, LastWriteTime, Length | Format-List
'''

    run_powershell(command_text)

def full_auto_chain() -> None:
    zaenia_success("Syncing calendar first, then generating the latest CarPlay voice file.")
    run_module("core.google_calendar_sync.google_calendar_sync_main", ["sync", "--days", "2"])
    run_module("core.carplay_audio.carplay_audio_main", ["generate"])


def run_action(action: str) -> bool:
    console_gate.require_owner()
    action = action.strip().lower()

    if action == "exit":
        console_gate.close()
        response = personality_section("console_personality", "command_responses", "exit")
        say(response or "Console closing. Rest if you need it, Sir.", "cyan")
        return False

    if action == "briefing":
        zaenia_success("Pulling the current drive briefing.")
        run_module("core.briefing.drive_briefing_main", ["now"])
        return True

    if action == "briefing_say":
        zaenia_success("Speaking the current drive briefing.")
        run_module("core.briefing.drive_briefing_main", ["now", "--say"])
        return True

    if action == "commute":
        zaenia_success("Building the commute briefing with traffic included.")
        run_module("core.briefing.drive_briefing_main", ["now", "--force-traffic"])
        return True

    if action == "weather":
        zaenia_success("Checking weather.")
        run_module("core.weather.weather_main", ["now"])
        return True

    if action == "weather_say":
        zaenia_success("Speaking weather.")
        run_module("core.weather.weather_main", ["now", "--say"])
        return True

    if action == "traffic":
        zaenia_success("Checking I-5 traffic now.")
        run_module("core.traffic.traffic_main", ["now", "--force"])
        return True

    if action == "calendar":
        zaenia_success("Reading today's calendar context.")
        run_module("core.calendar_context.calendar_context_main", ["today"])
        return True

    if action == "sync":
        zaenia_success("Syncing Google Calendar into ZÆNIA.")
        run_module("core.google_calendar_sync.google_calendar_sync_main", ["sync", "--days", "2"])
        return True

    if action == "audio":
        zaenia_success("Generating CarPlay audio.")
        run_module("core.carplay_audio.carplay_audio_main", ["generate"])
        return True

    if action == "audio_force":
        zaenia_success("Generating CarPlay audio with traffic forced.")
        run_module("core.carplay_audio.carplay_audio_main", ["generate", "--force-traffic"])
        return True

    if action == "full_auto":
        full_auto_chain()
        return True

    if action == "evening_check":
        evening_check()
        return True

    if action == "morning_preview":
        say("Use this for a morning preview:", "cyan")
        say("python -m core.briefing.drive_briefing_main now --calendar-date YYYY-MM-DD --force-traffic", "green")
        return True

    zaenia_error(f"Unknown action in aliases file: {action}")
    return True


def handle_command(raw_command: str) -> bool:
    command = raw_command.strip()
    lowered = command.lower()

    if not command:
        return True

    console_gate.require_owner()
    log_command(command)

    aliases = load_aliases()
    if lowered in aliases:
        alias = aliases[lowered] or {}
        response = alias.get("response")
        action = alias.get("action")

        if response:
            say(response, "cyan")

        if action:
            return run_action(str(action))

    if lowered in {"exit", "quit", "close", "goodnight"}:
        return run_action("exit")

    if lowered in {"help", "commands", "?"}:
        show_help()
        return True

    if lowered in {"clear", "cls"}:
        console.clear()
        return True

    if lowered == "status":
        show_status()
        return True

    if lowered == "history":
        show_history()
        return True

    if lowered == "briefing":
        return run_action("briefing")

    if lowered == "briefing say":
        return run_action("briefing_say")

    if lowered in {"commute", "drive", "traffic briefing"}:
        return run_action("commute")

    if lowered == "weather":
        return run_action("weather")

    if lowered == "weather say":
        return run_action("weather_say")

    if lowered == "traffic":
        return run_action("traffic")

    if lowered == "calendar":
        return run_action("calendar")

    if lowered == "sync":
        return run_action("sync")

    if lowered == "audio":
        return run_action("audio")

    if lowered == "audio force":
        return run_action("audio_force")

    if lowered == "carplay":
        return run_action("full_auto")

    if lowered == "1840":
        return run_action("evening_check")

    if lowered == "tomorrow":
        return run_action("morning_preview")

    unknown = personality_section("console_personality", "command_responses", "unknown")
    zaenia_error(unknown or "I do not recognize that command yet. Type help.")
    return True


def main() -> None:
    startup_options = personality_section("console_personality", "greetings", "startup") or []
    startup = pick(startup_options, "ZÆNIA online. Console ready, Sir.")

    console.print(Panel(startup, title="ZÆNIA Console", border_style="cyan"))
    show_help()

    keep_running = True

    while keep_running:
        try:
            raw_command = console.input("\n[bold cyan]ZÆNIA > [/bold cyan]")
            keep_running = handle_command(raw_command)
        except KeyboardInterrupt:
            say("\nConsole interrupted. Closing cleanly, Sir.", "yellow")
            break
        except Exception as error:
            zaenia_error(str(error))


if __name__ == "__main__":
    main()