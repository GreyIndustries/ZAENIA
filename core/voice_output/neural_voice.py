"""Kokoro neural voice: a more natural local voice for ZÆNIA, Piper as fallback.

Runs entirely on this PC (kokoro-onnx + onnxruntime). Every caller treats a
None result as "use Piper", so a missing package or model never silences her.
"""
from __future__ import annotations

import io
import threading
import wave
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "core" / "voice_output" / "voice_config.yaml"

_LOCK = threading.Lock()
_ENGINE: Any = None
_FAILED: str | None = None


def settings() -> dict[str, Any]:
    try:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        config = {}
    kokoro = config.get("kokoro") or {}
    provider = str((config.get("voice_output") or {}).get("provider", "piper")).lower()
    return {
        "active": provider == "kokoro" and kokoro.get("enabled", True) is not False,
        "model_path": PROJECT_ROOT / str(kokoro.get("model_path", "data/voices/kokoro/kokoro-v1.0.onnx")),
        "voices_path": PROJECT_ROOT / str(kokoro.get("voices_path", "data/voices/kokoro/voices-v1.0.bin")),
        # One voice ("af_heart") or a blend ("af_heart:0.7,af_bella:0.3").
        "voice": str(kokoro.get("voice", "af_heart")),
        "speed": min(1.5, max(0.6, float(kokoro.get("speed", 1.0) or 1.0))),
        "lang": str(kokoro.get("lang", "en-us")),
    }


def _engine(config: dict[str, Any]) -> Any:
    global _ENGINE, _FAILED
    if _ENGINE is None and _FAILED is None:
        if not config["model_path"].exists() or not config["voices_path"].exists():
            return None  # checked again next time, so a later download just works
        try:
            from kokoro_onnx import Kokoro
            _ENGINE = Kokoro(str(config["model_path"]), str(config["voices_path"]))
        except Exception as error:  # Missing package/model: Piper takes over.
            _FAILED = f"{type(error).__name__}: {error}"
    return _ENGINE


def _style(engine: Any, voice: str) -> Any:
    if ":" not in voice and "," not in voice:
        return voice
    mix, total = None, 0.0
    for part in voice.split(","):
        name, _, weight = part.strip().partition(":")
        share = float(weight or 1.0)
        style = engine.get_voice_style(name.strip()) * share
        mix = style if mix is None else mix + style
        total += share
    return mix / total if total else voice


def status() -> dict[str, Any]:
    config = settings()
    return {"active": config["active"], "voice": config["voice"], "loaded": _ENGINE is not None, "error": _FAILED}


def _paced(speed: float) -> float:
    """Her speaking speed, nudged toward Zack's own pace once it's been learned."""
    try:
        from core.personal_memory.speech_style import speech_style
        return min(1.5, max(0.6, speed * speech_style().voice_speed()))
    except Exception:
        return speed


def synthesize_wav(text: str) -> bytes | None:
    """16-bit mono WAV of text in the Kokoro voice, or None to fall back to Piper."""
    config = settings()
    words = " ".join(str(text).split())
    if not config["active"] or not words:
        return None
    with _LOCK:
        engine = _engine(config)
        if engine is None:
            return None
        try:
            import numpy as np
            samples, rate = engine.create(words, voice=_style(engine, config["voice"]),
                                          speed=_paced(config["speed"]), lang=config["lang"])
            pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2")
        except Exception:
            return None
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(rate))
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()
