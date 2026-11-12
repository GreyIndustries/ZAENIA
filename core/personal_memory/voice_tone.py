"""Ædaptive: how Grey sounds right now, from his voice (2026-10-31).

Grey's definition of the Æ in ZÆNIA: "emotional adaptability ... able to detect through my voice any emotional or
contextual info and knows how to respond to assist me."

For each spoken turn that already passed his voice check, a few plain measures are taken from the audio:
speaking pace, loudness, pitch and how much the pitch moves. Each is compared with his own running average
(learned from his turns, not from other people), and clear differences become a short, tentative note for the
brain: what his voice suggests and how to answer (briefer and calmer, gentler, matching his energy...).

* Only numbers are kept (data/personal_memory/voice_tone.json, on this PC): never audio, never words.
* Nothing is judged until 8 turns have built his baseline. A reading is used for 45 seconds, for the reply to that
  turn, and is shared with the PC voice service through data/ui/voice_tone_now.json.
* The note describes his voice, not a diagnosis, and ZAE never claims feelings of her own.
"""
from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASELINE_FILE = ROOT / "data" / "personal_memory" / "voice_tone.json"
NOW_FILE = ROOT / "data" / "ui" / "voice_tone_now.json"
RATE = 16000
MIN_SAMPLES = 8
WEIGHT = 0.12          # running average: about the last 8–10 turns count most
FRESH_SECONDS = 45.0
FEATURES = ("db", "pitch", "spread", "wps")
_LOCK = threading.Lock()


def measure(pcm: bytes, words: int) -> dict[str, float] | None:
    """Loudness (dB), median pitch (Hz), pitch spread (semitones) and pace (words per voiced second)."""
    samples = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype=np.int16).astype(np.float32)
    frame = RATE // 25  # 40 ms
    if samples.size < frame * 10 or words < 3:
        return None
    frames = samples[: samples.size - samples.size % frame].reshape(-1, frame)
    rms = np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-6
    voiced = frames[rms > max(500.0, float(np.percentile(rms, 60)) * 0.5)]
    if voiced.shape[0] < 8:
        return None
    pitches = []
    lo, hi = RATE // 400, RATE // 70  # 70–400 Hz
    for chunk in voiced:
        chunk = chunk - chunk.mean()
        corr = np.correlate(chunk, chunk, mode="full")[frame - 1:]
        if corr[0] <= 0:
            continue
        lag = lo + int(np.argmax(corr[lo:hi]))
        if corr[lag] / corr[0] > 0.45:
            pitches.append(RATE / lag)
    if len(pitches) < 6:
        return None
    semis = 12 * np.log2(np.array(pitches) / np.median(pitches))
    seconds = voiced.shape[0] * frame / RATE
    return {"db": float(20 * np.log10(np.mean(np.sqrt(np.mean(voiced ** 2, axis=1))))), "pitch": float(np.median(pitches)),
            "spread": float(np.percentile(semis, 90) - np.percentile(semis, 10)), "wps": float(words / seconds)}


def _load() -> dict[str, Any]:
    try:
        data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def read(now_values: dict[str, float], base: dict[str, Any]) -> dict[str, Any] | None:
    """Compare one turn with his usual voice: the cues that stand out and how to answer, or None."""
    if int(base.get("samples", 0)) < MIN_SAMPLES:
        return None
    try:
        louder = now_values["db"] - float(base["db"])
        higher = 12 * math.log2(now_values["pitch"] / float(base["pitch"]))
        livelier = now_values["spread"] / max(0.5, float(base["spread"]))
        faster = now_values["wps"] / max(0.5, float(base["wps"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    cues = []
    if faster >= 1.2: cues.append("faster")
    if faster <= 0.8: cues.append("slower")
    if louder >= 4: cues.append("louder")
    if louder <= -4: cues.append("quieter")
    if higher >= 1.5: cues.append("higher-pitched")
    if livelier <= 0.7: cues.append("flatter")
    if livelier >= 1.4: cues.append("more animated")
    if not cues:
        return None
    tense = sum(c in cues for c in ("faster", "louder", "higher-pitched"))
    low = sum(c in cues for c in ("slower", "quieter", "flatter"))
    if "more animated" in cues and tense >= 1 and "faster" not in cues and low == 0:
        sense, how = "energized or excited", "match his energy and keep the momentum"
    elif tense >= 2:
        sense, how = "rushed or under pressure", "be brief, calm and direct; lead with the answer or the next step"
    elif low >= 2:
        sense, how = "tired or low", "be gentle and short, and offer to take something off his plate if it fits"
    elif "more animated" in cues:
        sense, how = "engaged and upbeat", "keep pace with him"
    elif "faster" in cues:
        sense, how = "in a hurry", "keep it short"
    else:
        sense, how = "", "keep your usual tone"
    return {"cues": cues, "sense": sense, "how": how}


def observe(pcm: bytes, words: int, *, now: float | None = None) -> dict[str, Any] | None:
    """One verified spoken turn: update his baseline and note how this turn sounded."""
    values = measure(pcm, words)
    if values is None:
        return None
    now = now if now is not None else time.time()
    with _LOCK:
        base = _load()
        reading = read(values, base)
        samples = int(base.get("samples", 0))
        for key in FEATURES:
            old = base.get(key)
            # Learn more slowly from a turn that stands out, so one shout doesn't move his "usual".
            weight = WEIGHT * (0.4 if reading else 1.0)
            base[key] = values[key] if old is None or samples == 0 else float(old) + weight * (values[key] - float(old))
        base["samples"] = samples + 1
        _save(BASELINE_FILE, base)
        _save(NOW_FILE, {"at": now, "reading": reading})
    return reading


def hint(*, now: float | None = None) -> str | None:
    """A note for the brain about the turn he just spoke, or None."""
    try:
        data = json.loads(NOW_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    now = now if now is not None else time.time()
    reading = data.get("reading") if isinstance(data, dict) else None
    try:
        fresh = now - float(data.get("at", 0)) <= FRESH_SECONDS
    except (TypeError, ValueError, AttributeError):
        return None
    if not fresh or not reading:
        return None
    sounds = f"; it may mean he is {reading['sense']}" if reading.get("sense") else ""
    return ("HOW ZACK SOUNDS RIGHT NOW (from his voice, compared with his usual; tentative): "
            f"{', '.join(reading['cues'])} than usual{sounds}. Adapt: {reading['how']}. Don't name or diagnose his mood "
            "unless he asks, never claim feelings yourself, and let his words win if they say otherwise.")
