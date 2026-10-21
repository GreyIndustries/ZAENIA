from __future__ import annotations

import json
import queue
import time
from pathlib import Path
from typing import Any

import sounddevice as sd
import yaml
from rich.console import Console
from vosk import KaldiRecognizer, Model

from core.behavior.behavior_engine import log_behavior_event
from core.brain.dialogue_manager import (
    converse,
    return_to_background,
)
from core.console.zaenia_console import handle_command
from core.conversation.conversation_state import (
    activate_conversation,
    is_conversation_active,
    record_user_speech,
)
from core.voice_listener.cognitive_filter import filter_utterance
from core.voice_output.speaker import speak


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "voice_listener"
    / "voice_listener_config.yaml"
)

console = Console()

audio_queue: queue.Queue[bytes] = queue.Queue()

assistant_speaking = False


def load_listener_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing listener config: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        return yaml.safe_load(f) or {}


def get_model_path() -> Path:
    config = load_listener_config()

    relative_path = (
        config
        .get("voice_listener", {})
        .get("speech", {})
        .get(
            "model_path",
            "data/models/vosk-model-small-en-us-0.15",
        )
    )

    path = PROJECT_ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"Vosk model not found: {path}"
        )

    return path


def list_input_devices() -> list[dict[str, Any]]:
    devices = sd.query_devices()
    results = []

    for index, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            results.append(
                {
                    "index": index,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                    "sample_rate": device["default_samplerate"],
                }
            )

    return results


def find_approved_input_device() -> tuple[int, dict[str, Any]]:
    """
    Use Zack's approved microphone route only.

    Never silently fall back to another microphone.
    """
    config = load_listener_config()

    speech_config = (
        config
        .get("voice_listener", {})
        .get("speech", {})
    )

    configured_index = speech_config.get(
        "device_index"
    )

    configured_name = speech_config.get(
        "device_name_contains"
    )

    devices = list_input_devices()

    if configured_index is not None:
        for device in devices:
            if device["index"] == int(configured_index):
                return device["index"], device

        raise RuntimeError(
            f"Configured microphone index "
            f"{configured_index} is not available."
        )

    search_terms = []

    if configured_name:
        search_terms.append(
            str(configured_name).lower()
        )

    search_terms.extend(
        [
            "steelseries sonar",
            "sonar",
        ]
    )

    for search_term in search_terms:
        for device in devices:
            if search_term in device["name"].lower():
                return device["index"], device

    available = "\n".join(
        f"{device['index']}: {device['name']}"
        for device in devices
    )

    raise RuntimeError(
        "Approved Sonar microphone route was not found.\n"
        "ZÆNIA will not automatically use another microphone.\n\n"
        f"Available inputs:\n{available}"
    )


def clear_audio_queue() -> None:
    """
    Remove queued microphone audio.

    Used after ZÆNIA speaks so her own voice does not
    become the next recognized user utterance.
    """
    while True:
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


def speak_without_feedback(
    text: str,
) -> None:
    """
    Speak through Piper while temporarily preventing
    microphone audio from entering the recognition queue.
    """
    global assistant_speaking

    if not text.strip():
        return

    assistant_speaking = True

    clear_audio_queue()

    try:
        speak(text)

    finally:
        # Give speaker output a moment to disappear from the
        # microphone route before listening again.
        time.sleep(0.20)

        clear_audio_queue()

        assistant_speaking = False


def microphone_callback(
    indata: bytes,
    frames: int,
    time_info: Any,
    status: Any,
) -> None:
    if status:
        console.print(
            f"[yellow]Mic status: {status}[/yellow]"
        )

    if assistant_speaking:
        return

    audio_queue.put(
        bytes(indata)
    )


def normalize_voice_command(
    command_text: str,
) -> str | None:
    """
    Map explicitly authorized speech into ZÆNIA's
    restricted command vocabulary.

    This function cannot create arbitrary shell commands.
    """
    text = command_text.lower().strip()

    if not text:
        return None

    if "fix evening" in text:
        return "fix evening"

    if (
        "1840" in text
        or "evening status" in text
    ):
        return "1840"

    if "carplay" in text:
        return "carplay"

    if "traffic" in text:
        return "traffic"

    if "weather" in text:
        return "weather say"

    if "calendar" in text:
        if (
            "sync" in text
            or "update" in text
        ):
            return "sync"

        return "calendar"

    if "sync" in text:
        return "sync"

    if "briefing" in text:
        return "briefing say"

    if (
        "drive" in text
        or "commute" in text
    ):
        return "drive"

    if "audio" in text:
        if "force" in text:
            return "audio force"

        return "audio"

    if "status" in text:
        return "status"

    return None


def record_passive_signals(
    signals: dict[str, Any],
) -> None:
    """
    Save derived behavioral observations.

    Raw microphone conversation is not written here.
    """
    if not signals:
        return

    log_behavior_event(
        "voice_context",
        "Passive behavioral context detected.",
        {
            "signals": list(
                signals.keys()
            ),
            "source": "microphone",
        },
    )


def converse_locally(
    text: str,
    *,
    signals: dict[str, Any] | None = None,
    attention_called: bool = False,
) -> None:
    """
    Send natural conversation to ZÆNIA's local Qwen brain.

    This path has no command execution authority.
    """
    signals = signals or {}

    if signals:
        record_passive_signals(
            signals
        )

    record_user_speech(
        signals=list(
            signals.keys()
        )
    )

    console.print(
        "[dim]Thinking locally...[/dim]"
    )

    try:
        result = converse(
            text,
            speak_response=False,
            attention_called=attention_called,
        )

    except Exception as error:
        console.print(
            f"[red]Local brain error: "
            f"{error}[/red]"
        )
        return

    reply = (
        result
        .get("reply", "")
        .strip()
    )

    if not reply:
        return

    console.print(
        f"[cyan]ZÆNIA → {reply}[/cyan]"
    )

    speak_without_feedback(
        reply
    )


def handle_attention(
    spoken_text: str,
    signals: dict[str, Any],
) -> None:
    """
    Process speech that explicitly addressed ZÆNIA.
    """
    if not spoken_text:
        activate_conversation()

        response = "Yes, Sir?"

        console.print(
            f"[cyan]ZÆNIA → "
            f"{response}[/cyan]"
        )

        speak_without_feedback(
            response
        )

        return

    approved_command = normalize_voice_command(
        spoken_text
    )

    if approved_command is not None:
        activate_conversation(
            task=approved_command,
        )

        console.print(
            f"[green]"
            f"Authorized command → "
            f"{approved_command}"
            f"[/green]"
        )

        handle_command(
            approved_command
        )

        return

    # ZÆNIA was explicitly addressed, but the utterance
    # is not an executable command.
    #
    # Send it to the conversational brain instead.
    converse_locally(
        spoken_text,
        signals=signals,
        attention_called=True,
    )


def handle_background_request(
    text: str,
    signals: dict[str, Any],
) -> None:
    """
    Return an active conversation to background mode.

    If ZÆNIA was already backgrounded, remain silent.
    """
    record_passive_signals(
        signals
    )

    if not is_conversation_active():
        return

    # Give the brain the final statement so it can respond
    # naturally rather than using a hard-coded sign-off.
    try:
        result = converse(
            text,
            speak_response=False,
            attention_called=False,
        )

        reply = (
            result
            .get("reply", "")
            .strip()
        )

    except Exception:
        reply = ""

    return_to_background(
        reason="contextual_wrap_up"
    )

    if reply:
        console.print(
            f"[blue]ZÆNIA → "
            f"{reply}[/blue]"
        )

        speak_without_feedback(
            reply
        )

    console.print(
        "[dim]"
        "Conversation backgrounded. "
        "Approved background tasks continue."
        "[/dim]"
    )


def process_recognized_text(text: str) -> None:
    raise PermissionError("Text-only voice authorization is retired; use the verified PCM runtime.")

    # Background speech with no meaningful learned
    # context is ignored completely.


def run_listener() -> None:
    from core.voice_security.runtime import run
    run()


def stop_cleanly() -> None:
    console.print(
        "\n[yellow]"
        "ZÆNIA listener stopped cleanly."
        "[/yellow]"
    )


if __name__ == "__main__":
    try:
        run_listener()

    except KeyboardInterrupt:
        stop_cleanly()