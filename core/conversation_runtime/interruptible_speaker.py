from __future__ import annotations

import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pygame
import yaml


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


def load_voice_config(
) -> dict[str, Any]:
    """
    Load ZÆNIA's local voice configuration.
    """

    if not VOICE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing voice config: "
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
    Resolve a voice-model path relative to the project root.
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


def normalize_spoken_text(
    text: str,
) -> str:
    """
    Normalize written punctuation for more natural Piper
    speech.

    Em/en dashes are converted to spoken pauses represented
    by commas.
    """

    text = (
        text.strip()
    )

    replacements = {
        "\u2014": ", ",
        "\u2013": ", ",
        " -- ": ", ",
    }

    for old, new in (
        replacements.items()
    ):
        text = text.replace(
            old,
            new,
        )

    while ", ," in text:
        text = text.replace(
            ", ,",
            ",",
        )

    while "  " in text:
        text = text.replace(
            "  ",
            " ",
        )

    return (
        text.strip()
    )


class InterruptibleSpeaker:
    """
    Local Piper speech output supporting:

        interruption
        unique temporary WAV files
        punctuation normalization
        configurable voice pacing
    """

    def __init__(
        self,
    ) -> None:
        config = (
            load_voice_config()
        )

        piper = (
            config.get(
                "piper",
                {},
            )
            or {}
        )

        self.model_path = (
            resolve_project_path(
                piper.get(
                    "model_path",
                    (
                        "data/voices/piper/"
                        "en_US-hfc_female-medium.onnx"
                    ),
                )
            )
        )

        self.config_path = (
            resolve_project_path(
                piper.get(
                    "config_path",
                    (
                        "data/voices/piper/"
                        "en_US-hfc_female-medium.onnx.json"
                    ),
                )
            )
        )

        # Piper:
        #
        # > 1.0 = slower
        # < 1.0 = faster
        self.length_scale = float(
            piper.get(
                "length_scale",
                1.10,
            )
        )

        self.noise_scale = float(
            piper.get(
                "noise_scale",
                0.667,
            )
        )

        self.noise_w = float(
            piper.get(
                "noise_w",
                0.8,
            )
        )

        self.output_dir = (
            PROJECT_ROOT
            / "data"
            / "audio"
            / "runtime"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                "Piper model not found: "
                f"{self.model_path}"
            )

        if not self.config_path.exists():
            raise FileNotFoundError(
                "Piper config not found: "
                f"{self.config_path}"
            )

        self._stop_event = (
            threading.Event()
        )

        self._speaking_event = (
            threading.Event()
        )

        self._lock = (
            threading.Lock()
        )

        if not pygame.mixer.get_init():
            pygame.mixer.init()

    def is_speaking(
        self,
    ) -> bool:
        """
        True while generated speech is actively playing.
        """

        return (
            self._speaking_event.is_set()
        )

    def interrupt(
        self,
    ) -> None:
        """
        Stop currently playing speech.
        """

        self._stop_event.set()

        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()

            except pygame.error:
                pass

    def _new_output_file(
        self,
    ) -> Path:
        """
        Allocate a unique temporary WAV file.

        Unique files avoid Windows file-lock conflicts between
        rapidly generated sentences.
        """

        filename = (
            "zaenia_"
            + uuid.uuid4().hex
            + ".wav"
        )

        return (
            self.output_dir
            / filename
        )

    def _generate_audio(
        self,
        text: str,
        output_file: Path,
    ) -> None:
        """
        Generate one local WAV: Kokoro when set up, Piper otherwise.
        """
        from core.voice_output.neural_voice import synthesize_wav
        neural = synthesize_wav(text)
        if neural:
            output_file.write_bytes(neural)
            return

        creation_flags = 0

        if sys.platform == "win32":
            creation_flags = (
                subprocess.CREATE_NO_WINDOW
            )

        command = [
            sys.executable,
            "-m",
            "piper",
            "--model",
            str(
                self.model_path
            ),
            "--config",
            str(
                self.config_path
            ),
            "--output_file",
            str(
                output_file
            ),
            "--length-scale",
            str(
                self.length_scale
            ),
            "--noise-scale",
            str(
                self.noise_scale
            ),
            "--noise-w",
            str(
                self.noise_w
            ),
        ]

        result = subprocess.run(
            command,
            input=text,
            text=True,
            capture_output=True,
            creationflags=(
                creation_flags
            ),
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Piper failed to generate speech.\n"
                f"{result.stderr}"
            )

        if not output_file.exists():
            raise RuntimeError(
                "Piper reported success but did "
                "not create the WAV file."
            )

    def _release_audio_file(
        self,
    ) -> None:
        """
        Release pygame's handle to the current WAV.
        """

        try:
            pygame.mixer.music.stop()

        except pygame.error:
            pass

        try:
            pygame.mixer.music.unload()

        except pygame.error:
            pass

    def _delete_temp_file(
        self,
        output_file: Path,
    ) -> None:
        """
        Remove temporary WAV files after playback.

        Windows can briefly retain file handles, so deletion is
        retried for a short period.
        """

        for _ in range(
            10
        ):
            try:
                if output_file.exists():
                    output_file.unlink()

                return

            except PermissionError:
                time.sleep(
                    0.05
                )

            except OSError:
                return

    def speak(
        self,
        text: str,
    ) -> bool:
        """
        Generate and play one sentence.

        Returns:

            True
                sentence completed

            False
                sentence was interrupted
        """

        text = (
            normalize_spoken_text(
                text
            )
        )

        if not text:
            return True

        with self._lock:
            self._stop_event.clear()

            output_file = (
                self._new_output_file()
            )

            try:
                self._generate_audio(
                    text,
                    output_file,
                )

                # If interruption happened while Piper was
                # generating the WAV, do not begin playback.
                if self._stop_event.is_set():
                    return False

                pygame.mixer.music.load(
                    str(
                        output_file
                    )
                )

                self._speaking_event.set()

                pygame.mixer.music.play()

                while (
                    pygame.mixer.music.get_busy()
                ):
                    if self._stop_event.is_set():
                        pygame.mixer.music.stop()

                        return False

                    time.sleep(
                        0.02
                    )

                return (
                    not self._stop_event.is_set()
                )

            finally:
                self._speaking_event.clear()

                self._release_audio_file()

                self._delete_temp_file(
                    output_file
                )

                self._stop_event.clear()


def self_test(
) -> None:
    """
    Direct Piper pacing test.
    """

    speaker = (
        InterruptibleSpeaker()
    )

    text = (
        "Good, Zack—this should sound calmer, "
        "with a more natural pace, and without "
        "those awkward spoken dashes."
    )

    print(
        "Testing natural ZÆNIA pacing..."
    )

    speaker.speak(
        text
    )

    print(
        "Pacing test complete."
    )


if __name__ == "__main__":
    self_test()