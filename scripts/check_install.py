"""Check a ZÆNIA install: every listed Python package, the external tools, and the local models.

Run from the project folder with ZAE's Python:

    .venv\\Scripts\\python.exe scripts\\check_install.py

It only looks; it never downloads or installs anything. Exit code 0 means everything required is there.
"""
from __future__ import annotations

import importlib.metadata as metadata
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ("requirements.txt", "requirements-module1.txt", "requirements-operator.txt")
MODELS = {
    "Speech recognition (Vosk)": "data/models/vosk-model-small-en-us-0.15",
    "Kokoro voice model": "data/voices/kokoro/kokoro-v1.0.onnx",
    "Kokoro voice bank": "data/voices/kokoro/voices-v1.0.bin",
    "Piper fallback voice": "data/voices/piper/en_US-hfc_female-medium.onnx",
    "Speaker verification (ECAPA)": "data/models/speaker_verification/ecapa_voxceleb",
}
OLLAMA_MODELS = ("qwen3.5:4b", "qwen3.5:9b", "qwen3:14b", "qwen3:1.7b", "nomic-embed-text")


def requirements(root: Path = ROOT) -> list[tuple[str, str]]:
    """(name, pinned version or '') for every package line in the requirements files."""
    found = []
    for name in REQUIREMENTS:
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            match = re.match(r"([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(?:==\s*([^\s;]+))?", line)
            if match:
                found.append((match.group(1), match.group(2) or ""))
    return found


def check_packages(root: Path = ROOT) -> list[str]:
    problems = []
    for name, pinned in requirements(root):
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            problems.append(f"missing package {name}")
            continue
        if pinned and installed.split("+")[0] != pinned:
            problems.append(f"{name} is {installed}, requirements say {pinned}")
    return problems


def check_tools() -> list[str]:
    problems = [f"{tool} not found on PATH ({why})" for tool, why in
                (("node", "desktop and web builds, JavaScript playground"), ("npm", "desktop and web builds"),
                 ("cargo", "Windows app build"), ("ollama", "ZAE's local brain")) if not shutil.which(tool)]
    if shutil.which("ollama"):
        try:
            listed = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=20).stdout
            problems += [f"Ollama model {model} not pulled (ollama pull {model})" for model in OLLAMA_MODELS
                         if not re.search(r"^" + re.escape(model if ":" in model else model + ":") , listed, re.M)]
        except (OSError, subprocess.SubprocessError):
            problems.append("Ollama is installed but not answering (start Ollama)")
    return problems


def check_models(root: Path = ROOT) -> list[str]:
    return [f"{label} missing at {path}" for label, path in MODELS.items() if not (root / path).exists()]


def main() -> int:
    if sys.version_info < (3, 11):
        print(f"✕ Python {sys.version.split()[0]}: ZÆNIA needs 3.11 or newer (3.13 is what's tested).")
        return 1
    sections = {"Python packages": check_packages(), "Tools": check_tools(), "Local models": check_models()}
    for title, problems in sections.items():
        print(f"{'✓' if not problems else '✕'} {title}")
        for problem in problems:
            print(f"    - {problem}")
    ok = not any(sections.values())
    print("\nEverything ZÆNIA needs is installed." if ok else "\nSee docs/INSTALL.md for how to fix each item.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
