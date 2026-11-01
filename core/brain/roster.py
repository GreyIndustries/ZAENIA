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


def brains() -> list[dict[str, Any]]:
    from core.brain.conductor import SEEK_MODEL, TALK_KEEP_ALIVE, TALK_MODEL
    return [
        {"id": "talk", "name": "Talk", "model": TALK_MODEL, "where": "Graphics card",
         "role": "Answers you. Kept loaded all day so replies start fast; freed while you game.", "keepAlive": TALK_KEEP_ALIVE},
        {"id": "seek", "name": "Seek", "model": SEEK_MODEL, "where": "Graphics card",
         "role": "Web questions with sources, and takes over if Talk goes quiet.", "keepAlive": "as needed"},
        {"id": "study", "name": "Study", "model": "qwen3:14b", "where": "Graphics card",
         "role": "Research jobs, nightly fix ideas and Aider's local coding. Unloaded after each job.", "keepAlive": "unloads after each job"},
        {"id": "keep", "name": "Keep", "model": "qwen3:1.7b", "where": "Processor",
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
    roles.setdefault("qwen3:14b", []).append("Aider")
    roles.setdefault("zae-code:14b", []).append("OpenCode")
    for model in installed:
        model["usedBy"] = roles.get(model["name"], [])
    return {"ollama": {"running": version is not None, "version": version, "address": OLLAMA}, "brains": rows,
            "tools": coding_tools(), "models": sorted(installed, key=lambda m: (not m["usedBy"], m["name"]))}
