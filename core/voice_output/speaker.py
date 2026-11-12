from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from core.voice_output.quiet_pygame import pygame
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

VOICE_CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "voice_output"
    / "voice_config.yaml"
)


def load_voice_config() -> dict[str, Any]:
    if not VOICE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Voice config not found: {VOICE_CONFIG_PATH}"
        )

    with VOICE_CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        return yaml.safe_load(f) or {}


def resolve_project_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def play_audio_hidden(audio_path: Path) -> None:
    """
    Play local audio without opening Media Player.
    """
    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    pygame.mixer.init()

    try:
        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.05)

    finally:
        pygame.mixer.music.stop()
        pygame.mixer.quit()


def speak_piper(text: str) -> Path:
    """
    Generate and play ZÆNIA's local Piper voice.

    Works without internet once the model files are installed.
    """
    config = load_voice_config()
    piper = config.get("piper", {}) or {}

    model_path = resolve_project_path(
        piper.get(
            "model_path",
            "data/voices/piper/en_US-hfc_female-medium.onnx",
        )
    )

    config_path = resolve_project_path(
        piper.get(
            "config_path",
            "data/voices/piper/en_US-hfc_female-medium.onnx.json",
        )
    )

    output_path = resolve_project_path(
        piper.get(
            "output_file",
            "data/audio/zaenia_local.wav",
        )
    )

    if not model_path.exists():
        raise FileNotFoundError(
            f"Piper voice model missing: {model_path}"
        )

    if not config_path.exists():
        raise FileNotFoundError(
            f"Piper voice config missing: {config_path}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        sys.executable,
        "-m",
        "piper",
        "--model",
        str(model_path),
        "--config",
        str(config_path),
        "--output_file",
        str(output_path),
    ]

    creation_flags = 0

    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW

    result = subprocess.run(
        command,
        input=text,
        text=True,
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        creationflags=creation_flags,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Piper failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )

    play_audio_hidden(output_path)

    return output_path


def speak_windows(text: str) -> None:
    """
    Offline Windows TTS fallback.
    """
    escaped = (
        text
        .replace("'", "''")
    )

    command = (
        "Add-Type -AssemblyName System.Speech; "
        "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$voice.Speak('{escaped}');"
    )

    creation_flags = 0

    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW

    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            command,
        ],
        cwd=str(PROJECT_ROOT),
        creationflags=creation_flags,
        check=True,
    )


def speak_linux(text: str) -> None:
    """
    Offline Linux fallback: espeak-ng or speech-dispatcher, if present.
    """
    import shutil

    for command in (
        ["espeak-ng", text],
        ["spd-say", "--wait", text],
    ):
        if shutil.which(command[0]):
            subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                check=True,
            )
            return

    raise RuntimeError(
        "No system voice found (install espeak-ng)."
    )


def speak(text: str) -> None:
    """
    Main ZÆNIA speech entry point.

    Primary:
        Piper local/offline voice.

    Fallback:
        Windows offline TTS.
    """
    text = " ".join(text.split()).strip()

    if not text:
        return

    config = load_voice_config()

    voice_output = (
        config.get("voice_output", {})
        or {}
    )

    if not voice_output.get(
        "enabled",
        True,
    ):
        return

    fallback_order = voice_output.get(
        "fallback_order",
        ["piper", "windows"],
    )

    errors: list[str] = []

    for provider in fallback_order:
        provider = str(provider).lower()

        try:
            if provider == "piper":
                speak_piper(text)
                return

            if provider == "windows":
                # The built-in system voice: Windows speech, or on Linux
                # espeak-ng / speech-dispatcher when installed.
                if os.name == "nt":
                    speak_windows(text)
                else:
                    speak_linux(text)
                return

        except Exception as error:
            errors.append(
                f"{provider}: {error}"
            )

    raise RuntimeError(
        "All voice providers failed. "
        + " | ".join(errors)
    )