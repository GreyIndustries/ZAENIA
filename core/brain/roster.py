"""Her brains and coding tools as one list for the app (Arena > Brains & tools), checked live.

The brains are fixed roles (conductor.py, research/agent.py): Talk answers, Seek handles web questions, Study does
research and nightly ideas, Keep writes small summaries on the processor, and the embedder tracks topics. The coding
tools are what Build requests and Grey use: Claude Code, Aider (local) and OpenCode (local). Nothing here can change
a model or a permission; it only reports.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

TOOLS_ROOT = Path(__file__).resolve().parents[2].parent / "ZAENIA-Tools"
OLLAMA = "http://127.0.0.1:11434"
_VERSIONS: dict[str, tuple[float, str | None]] = {}


# The four brains and what each is for, in a few words (Settings diagnostics and the bottom bar).
FOUR = (("talk", "Talk", "Answers you"), ("seek", "Seek", "Web questions"), ("study", "Study", "Research and coding"),
        ("keep", "Keep", "Small summaries"))


def brain_modules(installed: set[str] | None, loaded: set[str]) -> list[dict[str, str]]:
    """One diagnostics module per brain: ready when its model is downloaded; the detail says its job and if it's loaded."""
    rows = {b["id"]: b for b in brains()}
    out = []
    for brain_id, name, job in FOUR:
        brain = rows[brain_id]
        model = brain["model"]
        # The app accepts at most 100 characters per detail, so it's the job and the state only (the role is in Arena).
        if installed is None:
            phase, state = "error", "Ollama isn't running"
        elif model not in installed:
            phase, state = "working", f"not downloaded (ollama pull {model})"
        else:
            phase, state = "ready", ("loaded now on the " if model in loaded else "loads when needed, on the ") + brain["where"].lower()
        out.append({"id": f"brain_{brain_id}", "name": f"{name} · {model}", "phase": phase, "detail": f"{job}. {state[0].upper() + state[1:]}."})
    return out


def brains() -> list[dict[str, Any]]:
    from core.brain.conductor import KEEP_MODEL, SEEK_MODEL, STUDY_MODEL, TALK_KEEP_ALIVE, TALK_MODEL
    return [
        {"id": "talk", "name": "Talk", "model": TALK_MODEL, "where": "Graphics card",
         "role": "The only brain that speaks or writes to you, including progress notes while others work. Kept loaded all day; freed while you game.", "keepAlive": TALK_KEEP_ALIVE},
        {"id": "seek", "name": "Seek", "model": SEEK_MODEL, "where": "Graphics card",
         "role": "Reads shared files part by part, finds facts in web pages, works out which app action you meant, checks answers about ZAE herself, and writes web answers where accuracy matters most.", "keepAlive": "as needed"},
        {"id": "study", "name": "Study", "model": STUDY_MODEL, "where": "Graphics card",
         "role": "Thinks, never speaks: research jobs, Code Doctor, Suggestions, nightly fix ideas and Aider's local coding. Unloaded after each research job.", "keepAlive": "10m after Code Doctor; unloads after research"},
        {"id": "keep", "name": "Keep", "model": KEEP_MODEL, "where": "Processor",
         "role": "Small watch-list summaries, on the processor so the graphics card stays free.", "keepAlive": "30m"},
        {"id": "topics", "name": "Topic tracker", "model": "nomic-embed-text", "where": "Graphics card",
         "role": "Keeps track of which conversation topic you're on.", "keepAlive": "10m"},
    ]


def _version(key: str, command: list[str]) -> str | None:
    """A tool's version, cached for 10 minutes (starting some tools takes a second)."""
    cached = _VERSIONS.get(key)
    if cached and time.monotonic() - cached[0] < 600:
        return cached[1]
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace",
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        found = re.search(r"\d+\.\d+(?:\.\d+)?", out or "")
        value = found.group(0) if found else None
    except (OSError, subprocess.SubprocessError):
        value = None
    _VERSIONS[key] = (time.monotonic(), value)
    return value


def coding_tools() -> list[dict[str, Any]]:
    from core.assistant_platform.build_helper import AIDER_MODEL, aider_exe, claude_exe
    claude, aider = claude_exe(), aider_exe()
    opencode = TOOLS_ROOT / "opencode" / "node_modules" / ".bin" / "opencode.cmd"
    model = None
    try:
        model = json.loads((TOOLS_ROOT / "opencode" / "opencode.json").read_text(encoding="utf-8")).get("model")
    except (OSError, ValueError):
        pass
    return [
        {"id": "claude", "name": "Claude Code", "installed": bool(claude), "version": _version("claude", [claude, "--version"]) if claude else None,
         "model": "Your Claude plan (online)", "use": "Build requests: real features. Works in a copy with no shell or web."},
        {"id": "aider", "name": "Aider", "installed": bool(aider), "version": _version("aider", [aider, "--version"]) if aider else None,
         "model": f"{AIDER_MODEL} on this PC", "use": "Build requests: small changes, and anything when you're offline."},
        {"id": "opencode", "name": "OpenCode", "installed": opencode.exists(), "version": _version("opencode", [str(opencode), "--version"]) if opencode.exists() else None,
         "model": (model or "").replace("ollama/", "") + " on this PC" if model else None,
         "use": "For you, in a terminal: zae-opencode.cmd in ZAENIA-Tools\\opencode. Ollama on this PC only."},
    ]


def turn_summary() -> dict[str, Any]:
    from core.brain.turn_log import summary
    return summary()


def roster() -> dict[str, Any]:
    import requests
    loaded: dict[str, dict[str, Any]] = {}
    installed: list[dict[str, Any]] = []
    version = None
    try:
        version = requests.get(f"{OLLAMA}/api/version", timeout=3).json().get("version")
        for item in requests.get(f"{OLLAMA}/api/ps", timeout=3).json().get("models") or []:
            loaded[item["name"]] = {"vramGb": round((item.get("size_vram") or 0) / 2**30, 1), "sizeGb": round((item.get("size") or 0) / 2**30, 1),
                                    "context": item.get("context_length"), "until": item.get("expires_at")}
        for item in requests.get(f"{OLLAMA}/api/tags", timeout=3).json().get("models") or []:
            details = item.get("details") or {}
            installed.append({"name": item["name"], "sizeGb": round((item.get("size") or 0) / 2**30, 1),
                              "parameters": details.get("parameter_size", ""), "loaded": item["name"] in loaded})
    except Exception:
        pass
    names = {m["name"] for m in installed}
    roles: dict[str, list[str]] = {}
    rows = []
    for brain in brains():
        model = brain["model"] if brain["model"] in names or ":" in brain["model"] else brain["model"] + ":latest"
        roles.setdefault(model, []).append(brain["name"])
        rows.append({**brain, "installed": model in names, "loaded": loaded.get(model)})
    from core.assistant_platform.build_helper import AIDER_MODEL
    roles.setdefault(AIDER_MODEL, []).append("Aider")
    roles.setdefault("zae-code:14b", []).append("OpenCode")
    from core.brain.conductor import OVERNIGHT_MODEL
    roles.setdefault(OVERNIGHT_MODEL, []).append("Nightly ideas")
    for model in installed:
        model["usedBy"] = roles.get(model["name"], [])
    return {"ollama": {"running": version is not None, "version": version, "address": OLLAMA}, "brains": rows,
            "tools": coding_tools(), "turns": turn_summary(), "models": sorted(installed, key=lambda m: (not m["usedBy"], m["name"]))}
