"""Chat history and spoken replies for the ZÆNIA UI.

History is read from ZÆNIA's own conversation memory (read-only). Speech uses
the same local Piper voice as the CarPlay brief and returns WAV audio; nothing
is played on the PC's speakers.
"""
from __future__ import annotations

import base64
import io
import json
import re
import subprocess
import sys
import threading
import uuid
import wave
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_PATH = PROJECT_ROOT / "data" / "conversation_memory.jsonl"
VOICE_DIR = PROJECT_ROOT / "data" / "ui" / "voice"
HISTORY_TAIL_BYTES = 512 * 1024
SPEECH_LIMIT = 1200
PIPER_TIMEOUT_SECONDS = 120

# The API chat route sends the moral-compass guidance ahead of the owner's
# words; history shows only what was actually typed.
_GUIDED_PREFIX = "[ZÆNIA owner moral compass]"
_OWNER_MARKER = "\n\n[Owner message]\n"

_SPEECH_LOCK = threading.Lock()


class SpeechError(RuntimeError):
    """Speech could not be made; the message is safe to show."""


def _owner_words(text: str) -> str:
    if text.startswith(_GUIDED_PREFIX) and _OWNER_MARKER in text:
        return text.split(_OWNER_MARKER, 1)[1]
    return text


def read_history(limit: int = 40) -> list[dict[str, str]]:
    limit = max(1, min(int(limit), 200))
    if not MEMORY_PATH.exists():
        return []
    with MEMORY_PATH.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - HISTORY_TAIL_BYTES))
        raw = handle.read()
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if size > HISTORY_TAIL_BYTES and lines:
        lines = lines[1:]  # first line may be cut in half
    messages: list[dict[str, str]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        role, content = item.get("role"), item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
            continue
        text = _owner_words(content) if role == "user" else content
        messages.append({"role": role, "text": text.strip()[:8000], "at": str(item.get("timestamp") or "")})
    return messages[-limit:]


def speech_text(text: str) -> str:
    """Plain words for the voice: no markdown symbols, links or code fences."""
    text = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
    text = re.sub(r"https?://\S+", "a link", text)
    text = re.sub(r"[*_#`>|~]+", " ", text)
    text = "".join(ch if ch.isprintable() or ch in "\n" else " " for ch in text)
    text = " ".join(text.split())
    if len(text) > SPEECH_LIMIT:
        cut = text[:SPEECH_LIMIT]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = cut[: end + 1] if end > SPEECH_LIMIT // 2 else cut
    return text.strip()


_VOICE: Any = None
_VOICE_FAILED = False


def _voice(settings: dict[str, Any]) -> Any:
    """Piper loaded once inside the server (fast); None if that isn't possible."""
    global _VOICE, _VOICE_FAILED
    if _VOICE_FAILED:
        return None
    if _VOICE is None:
        try:
            from piper import PiperVoice
            try:
                _VOICE = PiperVoice.load(str(settings["model_path"]), config_path=str(settings["config_path"]))
            except TypeError:
                _VOICE = PiperVoice.load(str(settings["model_path"]))
        except Exception:
            _VOICE_FAILED = True
            return None
    return _VOICE


def _synthesize_loaded(voice: Any, words: str, settings: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        if hasattr(voice, "synthesize_wav"):  # piper-tts 1.3+
            from piper import SynthesisConfig
            config = SynthesisConfig(length_scale=float(settings["length_scale"]),
                                     noise_scale=float(settings["noise_scale"]),
                                     noise_w_scale=float(settings["noise_w"]))
            voice.synthesize_wav(words, wav, syn_config=config)
        else:  # piper-tts 1.2
            voice.synthesize(words, wav, length_scale=float(settings["length_scale"]),
                             noise_scale=float(settings["noise_scale"]), noise_w=float(settings["noise_w"]))
    return buffer.getvalue()


def _synthesize_process(words: str, settings: dict[str, Any]) -> bytes:
    """The CarPlay way: one Piper process per clip (slower, always available)."""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    path = VOICE_DIR / f"{uuid.uuid4().hex}.wav"
    command = [
        sys.executable, "-m", "piper",
        "--model", str(settings["model_path"]), "--config", str(settings["config_path"]),
        "--output_file", str(path),
        "--length-scale", str(settings["length_scale"]),
        "--noise-scale", str(settings["noise_scale"]),
        "--noise-w", str(settings["noise_w"]),
    ]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        result = subprocess.run(command, input=words, text=True, capture_output=True,
                                creationflags=flags, timeout=PIPER_TIMEOUT_SECONDS)
        if result.returncode != 0 or not path.exists():
            raise SpeechError("Piper couldn't make the audio.")
        return path.read_bytes()
    except subprocess.TimeoutExpired as error:
        raise SpeechError("Piper took too long.") from error
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


from core.assistant_platform.performance import measure

@measure("speech_synthesis")
def synthesize(text: str) -> dict[str, Any]:
    """WAV audio of text in ZÆNIA's Piper voice, as base64 for the UI.

    The app sends one sentence at a time while a reply streams in, so the
    voice stays loaded in the server between sentences.
    """
    global _VOICE_FAILED
    words = speech_text(text)
    if not words:
        raise SpeechError("There's nothing to say.")
    from core.carplay_audio.carplay_audio import get_piper_settings
    try:
        settings = get_piper_settings()
    except Exception as error:
        raise SpeechError(f"ZÆNIA's voice isn't available: {error}") from error
    with _SPEECH_LOCK:
        # The Kokoro neural voice when it's set up; Piper otherwise.
        from core.voice_output.neural_voice import synthesize_wav
        audio = synthesize_wav(words) or b""
        voice = _voice(settings) if not audio else None
        if voice is not None:
            try:
                audio = _synthesize_loaded(voice, words, settings)
            except Exception:
                _VOICE_FAILED = True  # use the Piper process from now on
                audio = b""
        if not audio:
            audio = _synthesize_process(words, settings)
    with wave.open(io.BytesIO(audio), "rb") as clip:
        seconds = clip.getnframes() / float(clip.getframerate() or 1)
    return {"mime": "audio/wav", "seconds": round(seconds, 1), "audio": base64.b64encode(audio).decode("ascii")}
