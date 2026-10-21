"""Voice for the ZÆNIA UI: local speech-to-text and the PC voice service status.

The desktop and phone apps send short clips (16 kHz mono PCM) after you speak.
They are transcribed on this PC with the same Vosk model as ZÆNIA's voice
runtime, then dropped: audio is never written to disk and transcripts are not
logged. Wake words come from voice_listener_config.yaml, so "Zay" and "ZÆNIA"
work the same as on the PC microphone.

The PC voice service (core.voice_security.runtime) writes a heartbeat to
data/ui/voice_service.json; this module only reads it.
"""
from __future__ import annotations

import base64
import os
import binascii
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VOSK_MODEL = PROJECT_ROOT / "data" / "models" / "vosk-model-small-en-us-0.15"
STATUS_FILE = PROJECT_ROOT / "data" / "ui" / "voice_service.json"
SAMPLE_RATE = 16000
MIN_BYTES = SAMPLE_RATE * 2 // 4          # a quarter second
MAX_BYTES = SAMPLE_RATE * 2 * 20          # twenty seconds
STATUS_FRESH_SECONDS = 8.0

_MODEL_LOCK = threading.Lock()
_MODEL: Any = None


class VoiceError(ValueError):
    """A clip the server can't use; the message is safe to show."""


class VoiceUnavailable(RuntimeError):
    """Speech recognition isn't installed or its model is missing."""


def _model() -> Any:
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            try:
                from vosk import Model, SetLogLevel
            except ImportError as error:
                raise VoiceUnavailable("Speech recognition (Vosk) isn't installed on the PC.") from error
            if not VOSK_MODEL.is_dir():
                raise VoiceUnavailable("The Vosk speech model is missing from data/models.")
            SetLogLevel(-1)
            _MODEL = Model(str(VOSK_MODEL))
        return _MODEL


def recognize(pcm: bytes) -> str:
    """Final text for one clip, recognized locally."""
    model = _model()
    from vosk import KaldiRecognizer
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    step = SAMPLE_RATE  # half-second chunks of 16-bit audio
    for start in range(0, len(pcm), step):
        recognizer.AcceptWaveform(pcm[start:start + step])
    return str(json.loads(recognizer.FinalResult()).get("text", "")).strip()


def _decode(audio: Any) -> bytes:
    if not isinstance(audio, str) or not audio:
        raise VoiceError("No audio was received.")
    try:
        pcm = base64.b64decode(audio, validate=True)
    except (binascii.Error, ValueError) as error:
        raise VoiceError("The audio couldn't be read.") from error
    if len(pcm) % 2:
        raise VoiceError("The audio couldn't be read.")
    if len(pcm) < MIN_BYTES:
        raise VoiceError("That was too short to understand.")
    if len(pcm) > MAX_BYTES:
        raise VoiceError("Keep each request under 20 seconds.")
    return pcm


def _for_zae(text: str) -> tuple[bool, bool]:
    """(no wake word in use, the brain judged these words are meant for ZAE)."""
    from core.voice_listener.ambient import AmbientJudge, AmbientSettings
    from core.voice_listener.cognitive_filter import load_config
    settings = AmbientSettings.from_config(load_config().get("ambient", {}))
    if not settings.enabled or settings.require_name:
        return False, False
    # The brain decides: a request for her, or a moment where speaking up helps.
    return True, AmbientJudge(settings).decide(text, [])["action"] in ("direct", "respond")


def interpret(text: str, wake: bool) -> dict[str, Any]:
    """Whether the words are meant for ZÆNIA, and the request without the wake word."""
    from core.voice_listener.cognitive_filter import contains_attention_call, detect_background_intent, strip_attention_call
    from core.voice_listener.attention import is_conversational_follow_up, is_quiet_acknowledgement
    clean = " ".join(text.split())
    addressed = bool(clean) and contains_attention_call(clean)
    command = strip_attention_call(clean) if addressed else clean
    if addressed:
        # "Hey Zay, ..." leaves "hey" in front of the request.
        command = re.sub(r"^(?:hey|hi|ok|okay|yo|so)\b\s*", "", command).strip()
    dismiss = detect_background_intent(clean) if clean else False
    open_mic, for_zae = (False, False)
    if clean and not addressed and not dismiss:
        open_mic, for_zae = _for_zae(clean)
    return {
        "text": clean,
        "addressed": addressed,
        "command": command,
        "dismiss": dismiss,
        "wake": wake,
        # A routing cue only. The UI must also have its own live conversation
        # window; this stateless endpoint never activates a conversation itself.
        "conversational": is_conversational_follow_up(command),
        "acknowledgement": is_quiet_acknowledgement(command),
        # No wake word: the local brain judged these words were meant for ZAE.
        "forZae": addressed or for_zae,
        "nameRequired": not open_mic if clean and not addressed and not dismiss else None,
    }


from core.assistant_platform.performance import measure

@measure("transcription_and_intent")
def transcribe(audio: Any, wake: bool = False) -> dict[str, Any]:
    pcm = _decode(audio)
    try:
        text = recognize(pcm)
    except VoiceUnavailable:
        raise
    except Exception as error:
        raise VoiceUnavailable(f"Speech recognition failed ({type(error).__name__}).") from error
    return interpret(text, bool(wake))


# How to start the PC voice service by hand on this OS.
VOICE_SCRIPT = "scripts\\start_zaenia_voice.ps1" if os.name == "nt" else "scripts/linux/start_zaenia_voice.sh"


def name_required() -> bool:
    """False when ZAE listens without a wake word (ambient.require_name: false)."""
    from core.voice_listener.ambient import AmbientSettings
    from core.voice_listener.cognitive_filter import load_config
    try:
        settings = AmbientSettings.from_config(load_config().get("ambient", {}))
    except Exception:
        return True
    return not settings.enabled or settings.require_name


def service_status() -> dict[str, Any]:
    """The PC voice service, as reported by its own heartbeat."""
    result = _service_status()
    result["nameRequired"] = name_required()
    return result


AUDIT_FILE = Path(__file__).resolve().parents[2] / "data" / "secure" / "audit.log"


def _recently_recognising(window_seconds: float = 600.0) -> bool:
    """For a PC voice service started before it reported this itself: False
    when the owner voice check failed 3+ times in the last 10 minutes."""
    try:
        with AUDIT_FILE.open("rb") as handle:
            handle.seek(max(0, AUDIT_FILE.stat().st_size - 400_000))
            lines = handle.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return True
    now = datetime.now(timezone.utc)
    misses = 0
    for line in lines:
        if '"voice.turn_rejected"' not in line or not ('"speaker_rejected"' in line or '"verification_failed"' in line):
            continue
        try:
            moment = datetime.fromisoformat(json.loads(line)["timestamp"])
        except (ValueError, KeyError, TypeError):
            continue
        if (now - moment).total_seconds() <= window_seconds:
            misses += 1
    return misses < 3


def _service_status() -> dict[str, Any]:
    hint = f"At the PC run {VOICE_SCRIPT} and enter your passkey."
    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"running": False, "state": "off", "updatedAt": None, "startedAt": None, "hint": hint}
    state = str(data.get("state") or "off")
    updated = data.get("updatedAt")
    fresh = False
    try:
        moment = datetime.fromisoformat(str(updated))
        fresh = (datetime.now(timezone.utc) - moment).total_seconds() <= STATUS_FRESH_SECONDS
    except (TypeError, ValueError):
        pass
    running = fresh and state in ("listening", "hearing", "replying")
    return {
        "running": running,
        "state": state if running else "off",
        "updatedAt": updated,
        "startedAt": data.get("startedAt") if running else None,
        "hint": None if running else hint,
        "timing": data.get("timing") if running and isinstance(data.get("timing"),dict) else None,
        # False when PC Voice keeps failing the owner voice check.
        "recognising": (bool(data["recognising"]) if "recognising" in data else _recently_recognising()) if running else None,
    }
