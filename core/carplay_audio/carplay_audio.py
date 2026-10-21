from __future__ import annotations

import os
import subprocess
import sys
import wave
from array import array
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from core.briefing.drive_briefing import (
    build_drive_briefing,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

VOICE_CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "voice_output"
    / "voice_config.yaml"
)

DEFAULT_AUDIO_NAME = (
    "CarStartupAudio.wav"
)

DEFAULT_TEXT_NAME = (
    "CarStartupAudio.txt"
)

# [comment omitted from source review]
CARPLAY_TARGET_PEAK = 0.92
CARPLAY_HEADROOM_FLOOR = 0.05

CARPLAY_LEAD_SILENCE_MS = 250
CARPLAY_TRAIL_SILENCE_MS = 700


def load_voice_config(
) -> dict[str, Any]:
    """
    Load ZÆNIA's voice configuration.
    """

    if not VOICE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Voice config not found: "
            f"{VOICE_CONFIG_PATH}"
        )

    with VOICE_CONFIG_PATH.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        return (
            yaml.safe_load(
                file
            )
            or {}
        )


def resolve_project_path(
    value: str,
) -> Path:
    """
    Resolve Piper paths relative to the ZÆNIA project.
    """

    path = Path(
        value
    )

    if path.is_absolute():
        return path

    return (
        PROJECT_ROOT
        / path
    )


def get_onedrive_folder(
) -> Path:
    """
    Locate Zack's OneDrive directory.
    """

    for variable in (
        "OneDrive",
        "OneDriveConsumer",
    ):
        value = (
            os.environ.get(
                variable
            )
        )

        if value:
            return Path(
                value
            )

    return (
        Path.home()
        / "OneDrive"
    )


def get_default_audio_path(
) -> Path:
    return (
        get_onedrive_folder()
        / DEFAULT_AUDIO_NAME
    )


def get_default_text_path(
) -> Path:
    return (
        get_onedrive_folder()
        / DEFAULT_TEXT_NAME
    )


def get_piper_settings(
) -> dict[str, Any]:
    """
    Read the same Piper model used by ZÆNIA's normal voice.
    """

    config = (
        load_voice_config()
    )

    voice_output = (
        config.get(
            "voice_output",
            {},
        )
        or {}
    )

    piper = (
        config.get(
            "piper",
            {},
        )
        or {}
    )

    if not bool(
        voice_output.get(
            "enabled",
            False,
        )
    ):
        raise RuntimeError(
            "ZÆNIA voice output is disabled."
        )

    if not bool(
        piper.get(
            "enabled",
            False,
        )
    ):
        raise RuntimeError(
            "Local Piper voice is disabled."
        )

    model_path = (
        resolve_project_path(
            str(
                piper.get(
                    "model_path",
                    "",
                )
            )
        )
    )

    config_path = (
        resolve_project_path(
            str(
                piper.get(
                    "config_path",
                    "",
                )
            )
        )
    )

    if not model_path.exists():
        raise FileNotFoundError(
            "Piper model not found: "
            f"{model_path}"
        )

    if not config_path.exists():
        raise FileNotFoundError(
            "Piper voice config not found: "
            f"{config_path}"
        )

    return {
        "model_path": (
            model_path
        ),
        "config_path": (
            config_path
        ),
        "length_scale": float(
            piper.get(
                "length_scale",
                1.10,
            )
        ),
        "noise_scale": float(
            piper.get(
                "noise_scale",
                0.667,
            )
        ),
        "noise_w": float(
            piper.get(
                "noise_w",
                0.8,
            )
        ),
    }


def add_silence_and_normalize_wav(
    source_path: Path,
    output_path: Path,
) -> Path:
    """
    Prepare Piper audio specifically for CarPlay.

    Changes:

        - raises weak output to a strong but safe peak
        - adds a short lead-in so CarPlay does not clip the
          first syllable
        - adds a longer tail so CarPlay does not cut off the
          final word

    Only 16-bit mono/stereo PCM WAV is supported here.
    Piper produces compatible WAV output.
    """

    with wave.open(
        str(
            source_path
        ),
        "rb",
    ) as reader:
        channels = (
            reader.getnchannels()
        )

        sample_width = (
            reader.getsampwidth()
        )

        frame_rate = (
            reader.getframerate()
        )

        frame_count = (
            reader.getnframes()
        )

        frames = (
            reader.readframes(
                frame_count
            )
        )

    if sample_width != 2:
        raise RuntimeError(
            "CarPlay WAV normalization currently "
            "requires 16-bit PCM audio."
        )

    samples = array(
        "h"
    )

    samples.frombytes(
        frames
    )

    if not samples:
        raise RuntimeError(
            "Generated Piper WAV contains no audio samples."
        )

    current_peak = max(
        abs(
            sample
        )
        for sample in samples
    )

    max_sample = 32767

    target_peak = int(
        max_sample
        * CARPLAY_TARGET_PEAK
    )

    if current_peak <= 0:
        raise RuntimeError(
            "Generated Piper WAV contains silent audio."
        )

    gain = (
        target_peak
        / current_peak
    )

    if (
        current_peak
        / max_sample
        < CARPLAY_HEADROOM_FLOOR
    ):
        gain = min(
            gain,
            4.0,
        )

    normalized = array(
        "h"
    )

    for sample in samples:
        boosted = int(
            round(
                sample
                * gain
            )
        )

        boosted = max(
            -32768,
            min(
                32767,
                boosted,
            ),
        )

        normalized.append(
            boosted
        )

    lead_frames = int(
        frame_rate
        * (
            CARPLAY_LEAD_SILENCE_MS
            / 1000.0
        )
    )

    trail_frames = int(
        frame_rate
        * (
            CARPLAY_TRAIL_SILENCE_MS
            / 1000.0
        )
    )

    silence_sample_count_lead = (
        lead_frames
        * channels
    )

    silence_sample_count_trail = (
        trail_frames
        * channels
    )

    final_samples = array(
        "h"
    )

    final_samples.extend(
        [0]
        * silence_sample_count_lead
    )

    final_samples.extend(
        normalized
    )

    final_samples.extend(
        [0]
        * silence_sample_count_trail
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with wave.open(
        str(
            output_path
        ),
        "wb",
    ) as writer:
        writer.setnchannels(
            channels
        )

        writer.setsampwidth(
            sample_width
        )

        writer.setframerate(
            frame_rate
        )

        writer.writeframes(
            final_samples.tobytes()
        )

    return output_path


def validate_audio_destination(output_path: Path) -> Path:
    from core.foundation.security.io import reject_link
    candidate=Path(output_path).absolute()
    reject_link(candidate)
    allowed={get_onedrive_folder().absolute(),(PROJECT_ROOT / "data" / "carplay_sessions").absolute()}
    if candidate.suffix.lower() != ".wav" or candidate.parent not in allowed:
        raise PermissionError("CarPlay audio can write only WAV files in OneDrive or data/carplay_sessions.")
    for suffix in (".raw.wav",".tmp.wav"):
        reject_link(candidate.with_name(candidate.stem+suffix))
    return candidate


def generate_piper_audio(
    text: str,
    output_path: Path,
) -> Path:
    """
    Generate the briefing in ZÆNIA's configured local voice, with Piper
    as fallback, then prepare the WAV for browser or CarPlay playback.

    The historical function name is retained for existing callers.
    """

    output_path = validate_audio_destination(output_path)

    text = (
        text.strip()
    )

    if not text:
        raise ValueError(
            "Cannot generate CarPlay audio "
            "from empty text."
        )

    if (
        output_path.suffix.lower()
        != ".wav"
    ):
        raise ValueError(
            "Local Piper CarPlay output must "
            "use a .wav file."
        )

    if not (load_voice_config().get("voice_output") or {}).get("enabled", False):
        raise RuntimeError("ZÆNIA voice output is disabled.")

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_path = (
        output_path.with_name(
            output_path.stem
            + ".raw.wav"
        )
    )

    final_temp_path = (
        output_path.with_name(
            output_path.stem
            + ".tmp.wav"
        )
    )

    for path in (
        raw_path,
        final_temp_path,
    ):
        if path.exists():
            path.unlink()

    try:
        from core.voice_output.neural_voice import synthesize_wav
        audio = synthesize_wav(text)
        if audio:
            raw_path.write_bytes(audio)
        else:
            # Resolve Piper settings only when it is actually needed. The
            # configured neural voice also works when Piper is disabled.
            settings = get_piper_settings()
            command = [
                sys.executable, "-m", "piper",
                "--model", str(settings["model_path"]),
                "--config", str(settings["config_path"]),
                "--output_file", str(raw_path),
                "--length-scale", str(settings["length_scale"]),
                "--noise-scale", str(settings["noise_scale"]),
                "--noise-w", str(settings["noise_w"]),
            ]
            result = subprocess.run(
                command, input=text, text=True, capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                raise RuntimeError("Piper failed to generate briefing audio.\n" + result.stderr)

        if not raw_path.exists():
            raise RuntimeError(
                "The voice engine did not create briefing audio."
            )

        add_silence_and_normalize_wav(
            raw_path,
            final_temp_path,
        )

        if not final_temp_path.exists():
            raise RuntimeError(
                "CarPlay audio processing failed."
            )

        final_temp_path.replace(
            output_path
        )

    finally:
        for path in (
            raw_path,
            final_temp_path,
        ):
            if path.exists():
                try:
                    path.unlink()

                except OSError:
                    pass

    return output_path


def save_briefing_text(
    text: str,
    output_path: Path,
) -> Path:
    """
    Atomically save the latest text briefing.
    """

    from core.foundation.security.io import reject_link
    output_path=Path(output_path).absolute()
    reject_link(output_path)
    if output_path != get_default_text_path().absolute():
        raise PermissionError("Briefing text can write only its intended OneDrive CarStartupAudio.txt.")
    output_path.parent.mkdir(parents=True,exist_ok=True)

    temporary_path = (
        output_path.with_name(
            output_path.name
            + ".tmp"
        )
    )

    reject_link(temporary_path)
    try:
        temporary_path.write_text(
            text,
            encoding="utf-8",
        )

        temporary_path.replace(
            output_path
        )

    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()

            except OSError:
                pass

    return output_path


def build_and_save_carplay_audio(
    force_traffic: bool = False,
    output_path: Path | None = None,
    calendar_date: date | None = None,
) -> dict[str, Any]:
    """
    Build the current briefing and create the CarPlay-tuned
    local Piper WAV.
    """

    briefing = (
        build_drive_briefing(
            include_traffic_force=(
                force_traffic
            ),
            calendar_date=(
                calendar_date
            ),
        )
    )

    text = str(
        briefing[
            "spoken_briefing"
        ]
    ).strip()

    if not text:
        raise RuntimeError(
            "Drive briefing generated empty text."
        )

    audio_path = (
        output_path
        or get_default_audio_path()
    )

    text_path = (
        get_default_text_path()
    )

    generated_audio_path = (
        generate_piper_audio(
            text,
            audio_path,
        )
    )

    generated_text_path = (
        save_briefing_text(
            text,
            text_path,
        )
    )

    return {
        "text": text,
        "audio_path": str(
            generated_audio_path
        ),
        "text_path": str(
            generated_text_path
        ),
        "traffic_included": (
            briefing[
                "traffic_included"
            ]
        ),
        "traffic_window": (
            briefing[
                "traffic_window"
            ]
        ),
        "weather_location": (
            briefing[
                "weather_location"
            ]
        ),
        "calendar_context": (
            briefing[
                "calendar_context"
            ]
        ),
    }
