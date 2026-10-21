from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import torch
import yaml

from huggingface_hub import (
    hf_hub_download,
)
from speechbrain.inference.speaker import (
    EncoderClassifier,
)
from speechbrain.utils.fetching import (
    LocalStrategy,
)

from core.voice_listener.voice_listener import (
    find_approved_input_device,
)


def approved_voice_microphone() -> tuple[int, dict]:
    from core.foundation.auth.voice_passkey import get_allowed_mic_index
    index = get_allowed_mic_index()
    return index, {"index": index, "name": str(sd.query_devices(index)["name"])}


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "foundation"
    / "auth"
    / "speaker_verification_config.yaml"
)


DEFAULT_REQUIRED_MODEL_FILES = (
    "hyperparams.yaml",
    "embedding_model.ckpt",
    "mean_var_norm_emb.ckpt",
    "classifier.ckpt",
    "label_encoder.txt",
)


def load_config(
) -> dict[str, Any]:
    """
    Load ZÆNIA's speaker-verification configuration.
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "Missing speaker verification config: "
            f"{CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        data = (
            yaml.safe_load(
                file
            )
            or {}
        )

    config = (
        data.get(
            "speaker_verification",
            {},
        )
        or {}
    )

    if not isinstance(
        config,
        dict,
    ):
        raise ValueError(
            "speaker_verification configuration "
            "must be a dictionary."
        )

    return config


def resolve_project_path(
    value: str,
) -> Path:
    """
    Resolve a path inside ZÆNIA's project boundary.
    """

    path = Path(
        value
    )

    if path.is_absolute():
        resolved = (
            path.resolve()
        )

    else:
        resolved = (
            PROJECT_ROOT
            / path
        ).resolve()

    project_root = (
        PROJECT_ROOT.resolve()
    )

    try:
        resolved.relative_to(
            project_root
        )

    except ValueError as error:
        raise ValueError(
            "Speaker verification attempted to use "
            "a path outside the ZÆNIA project."
        ) from error

    return resolved


def choose_device(
    configured_device: str,
) -> str:
    """
    Select the local PyTorch inference device.

    auto:
        CUDA when available
        CPU otherwise
    """

    configured_device = (
        configured_device
        .strip()
        .lower()
    )

    if configured_device == "auto":
        if torch.cuda.is_available():
            return "cuda:0"

        return "cpu"

    return configured_device


def model_source_is_ready(
    model_dir: Path,
    required_files: tuple[str, ...],
) -> bool:
    """
    A model directory is considered usable only when every
    SpeechBrain-required model file exists and is non-empty.

    This prevents an interrupted or incomplete first download
    from masquerading as a complete offline model.
    """

    for filename in required_files:
        path = (
            model_dir
            / filename
        )

        if not path.exists():
            return False

        try:
            if path.stat().st_size <= 0:
                return False

        except OSError:
            return False

    return True


class SpeakerVerifier:
    """
    ZÆNIA's local speaker-identity engine.

    Current stage:

        DIAGNOSTIC ONLY

    This class can:

        use the approved microphone
        create ECAPA speaker embeddings
        compare speaker embeddings
        repair an incomplete local model installation

    It cannot yet:

        persist Zack's biometric profile
        authorize commands
        bypass the rule engine
        change security state
    """

    def __init__(
        self,
    ) -> None:
        self.config = (
            load_config()
        )

        audio_config = (
            self.config.get(
                "audio",
                {},
            )
            or {}
        )

        model_config = (
            self.config.get(
                "model",
                {},
            )
            or {}
        )

        diagnostic_config = (
            self.config.get(
                "diagnostic",
                {},
            )
            or {}
        )

        self.sample_rate = int(
            audio_config.get(
                "sample_rate",
                16000,
            )
        )

        self.channels = int(
            audio_config.get(
                "channels",
                1,
            )
        )

        self.recording_seconds = float(
            audio_config.get(
                "recording_seconds",
                4.0,
            )
        )

        self.minimum_rms = float(
            audio_config.get(
                "minimum_rms",
                0.008,
            )
        )

        self.max_recording_attempts = max(
            1,
            int(
                audio_config.get(
                    "max_recording_attempts",
                    3,
                )
            ),
        )

        self.reference_samples = max(
            2,
            int(
                diagnostic_config.get(
                    "reference_samples",
                    3,
                )
            ),
        )

        self.diagnostic_threshold = float(
            diagnostic_config.get(
                "same_speaker_threshold",
                0.25,
            )
        )

        self.remote_source = str(
            model_config.get(
                "remote_source",
                (
                    "speechbrain/"
                    "spkrec-ecapa-voxceleb"
                ),
            )
        )

        self.local_source_dir = (
            resolve_project_path(
                str(
                    model_config.get(
                        "local_source_dir",
                        (
                            "data/models/"
                            "speaker_verification/"
                            "ecapa_voxceleb"
                        ),
                    )
                )
            )
        )

        self.local_runtime_cache_dir = (
            resolve_project_path(
                str(
                    model_config.get(
                        "local_runtime_cache_dir",
                        (
                            "data/models/"
                            "speaker_verification/"
                            "runtime_cache"
                        ),
                    )
                )
            )
        )

        self.device = (
            choose_device(
                str(
                    model_config.get(
                        "device",
                        "auto",
                    )
                )
            )
        )

        configured_required_files = (
            model_config.get(
                "required_files",
                [],
            )
            or []
        )

        if configured_required_files:
            self.required_model_files = tuple(
                str(
                    filename
                ).strip()
                for filename
                in configured_required_files
                if str(
                    filename
                ).strip()
            )

        else:
            self.required_model_files = (
                DEFAULT_REQUIRED_MODEL_FILES
            )

        self.local_source_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.local_runtime_cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.classifier: (
            EncoderClassifier | None
        ) = None

    def missing_model_files(
        self,
    ) -> list[str]:
        """
        Return required model files that are absent or empty.
        """

        missing: list[str] = []

        for filename in (
            self.required_model_files
        ):
            path = (
                self.local_source_dir
                / filename
            )

            if not path.exists():
                missing.append(
                    filename
                )

                continue

            try:
                if path.stat().st_size <= 0:
                    missing.append(
                        filename
                    )

            except OSError:
                missing.append(
                    filename
                )

        return missing

    def fetch_model_file(
        self,
        filename: str,
    ) -> Path:
        """
        Locate one official SpeechBrain model file.

        Order:

            1. Hugging Face's existing local cache
            2. network download only if the cache lacks it

        The returned cached file is then COPIED into ZÆNIA's
        own project directory.

        That gives ZÆNIA a real local copy rather than relying
        on Hugging Face's Windows symlink behavior.
        """

        cached_path: Path | None = (
            None
        )

        try:
            cached_path = Path(
                hf_hub_download(
                    repo_id=(
                        self.remote_source
                    ),
                    filename=(
                        filename
                    ),
                    repo_type="model",
                    local_files_only=True,
                )
            )

        except Exception:
            cached_path = None

        if (
            cached_path is None
            or not cached_path.exists()
        ):
            try:
                cached_path = Path(
                    hf_hub_download(
                        repo_id=(
                            self.remote_source
                        ),
                        filename=(
                            filename
                        ),
                        repo_type="model",
                        local_files_only=False,
                    )
                )

            except Exception as error:
                raise RuntimeError(
                    "Could not obtain required speaker "
                    f"model file: {filename}"
                ) from error

        if not cached_path.exists():
            raise RuntimeError(
                "Hugging Face reported a model file, "
                "but the cached file does not exist: "
                f"{filename}"
            )

        destination = (
            self.local_source_dir
            / filename
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            shutil.copy2(
                cached_path,
                destination,
            )

        except shutil.SameFileError:
            pass

        if not destination.exists():
            raise RuntimeError(
                "Failed to copy speaker model file into "
                f"ZÆNIA's local model directory: {filename}"
            )

        if destination.stat().st_size <= 0:
            raise RuntimeError(
                "Speaker model file was copied but is empty: "
                f"{filename}"
            )

        return destination

    def ensure_local_model_files(
        self,
    ) -> None:
        """
        Heal an incomplete local speaker-model installation.

        This specifically prevents the failure Zack hit where:

            embedding_model.ckpt existed

        but:

            label_encoder.txt

        did not exist in ZÆNIA's project directory.

        Existing good files are left untouched.
        Only missing/empty files are repaired.
        """

        missing = (
            self.missing_model_files()
        )

        if not missing:
            return

        print()

        print(
            "Local speaker model is incomplete."
        )

        print(
            "Repairing missing model files..."
        )

        for filename in missing:
            print(
                f"  Repairing: {filename}"
            )

            self.fetch_model_file(
                filename
            )

        remaining = (
            self.missing_model_files()
        )

        if remaining:
            raise RuntimeError(
                "Speaker model repair did not complete. "
                "Still missing: "
                + ", ".join(
                    remaining
                )
            )

        print(
            "Local speaker model repair complete."
        )

    def load_model(
        self,
    ) -> None:
        """
        Load SpeechBrain entirely from ZÆNIA's local project
        copy.

        If that copy is incomplete, repair it first using the
        Hugging Face cache or, only when necessary, the network.

        Once the project copy is complete, normal future loads
        do not require the Internet.
        """

        if self.classifier is not None:
            return

        self.ensure_local_model_files()

        if not model_source_is_ready(
            self.local_source_dir,
            self.required_model_files,
        ):
            raise RuntimeError(
                "Local ECAPA speaker model is incomplete."
            )

        run_options = {
            "device": (
                self.device
            ),
        }

        local_source = str(
            self.local_source_dir
        )

        local_pretrained_path = (
            self.local_source_dir
            .as_posix()
        )

        try:
            self.classifier = (
                EncoderClassifier.from_hparams(
                    source=(
                        local_source
                    ),
                    savedir=str(
                        self.local_runtime_cache_dir
                    ),
                    overrides={
                        "pretrained_path": (
                            local_pretrained_path
                        ),
                    },
                    run_opts=(
                        run_options
                    ),
                    local_strategy=(
                        LocalStrategy.COPY
                    ),
                )
            )

        except Exception as error:
            raise RuntimeError(
                "The local ECAPA model files are present, "
                "but SpeechBrain could not load them."
            ) from error

    @staticmethod
    def calculate_rms(
        audio: np.ndarray,
    ) -> float:
        """
        Calculate root-mean-square signal level.

        This is only a recording sanity check.
        It is not speaker authentication.
        """

        if audio.size == 0:
            return 0.0

        squared_mean = float(
            np.mean(
                np.square(
                    audio,
                    dtype=np.float64,
                )
            )
        )

        if squared_mean <= 0.0:
            return 0.0

        return math.sqrt(
            squared_mean
        )

    def record_sample(
        self,
        *,
        prompt: str,
    ) -> np.ndarray:
        """
        Record one usable sample from ZÆNIA's approved mic.

        If a recording is too quiet, only that recording is
        repeated.

        Zack no longer has to restart all reference recordings
        because one four-second sample fell slightly below the
        minimum RMS floor.
        """

        # Record from the same approved microphone the voice service
        # verifies with, so the profile matches what it hears live.
        device_index, device = (
            approved_voice_microphone()
        )

        frame_count = int(
            self.sample_rate
            * self.recording_seconds
        )

        for attempt in range(
            1,
            self.max_recording_attempts + 1,
        ):
            print()

            print(
                prompt
            )

            if attempt > 1:
                print(
                    "Retry "
                    f"{attempt}/"
                    f"{self.max_recording_attempts}"
                )

            input(
                "Press Enter when ready..."
            )

            print(
                "Recording for "
                f"{self.recording_seconds:.1f} seconds..."
            )

            audio = sd.rec(
                frames=(
                    frame_count
                ),
                samplerate=(
                    self.sample_rate
                ),
                channels=(
                    self.channels
                ),
                dtype="float32",
                device=(
                    device_index
                ),
                blocking=True,
            )

            audio = np.asarray(
                audio,
                dtype=np.float32,
            )

            if audio.ndim == 2:
                audio = audio.mean(
                    axis=1,
                )

            audio = np.ascontiguousarray(
                audio.reshape(
                    -1
                ),
                dtype=np.float32,
            )

            rms = (
                self.calculate_rms(
                    audio
                )
            )

            print(
                "Mic:",
                device[
                    "name"
                ],
            )

            print(
                "Sample RMS:",
                round(
                    rms,
                    5,
                ),
            )

            if rms >= self.minimum_rms:
                return audio

            print(
                "Sample was too quiet for the "
                "configured diagnostic floor."
            )

            if (
                attempt
                < self.max_recording_attempts
            ):
                print(
                    "Only this sample will be retried."
                )

        raise RuntimeError(
            "Recording remained too quiet after "
            f"{self.max_recording_attempts} attempts."
        )

    def create_embedding(
        self,
        audio: np.ndarray,
    ) -> torch.Tensor:
        """
        Convert one 16 kHz waveform into a normalized ECAPA
        speaker embedding.

        Raw microphone audio is not persisted.
        """

        self.load_model()

        if self.classifier is None:
            raise RuntimeError(
                "Speaker model failed to load."
            )

        waveform = (
            torch.from_numpy(
                audio
            )
            .float()
            .unsqueeze(
                0
            )
        )

        with torch.no_grad():
            embedding = (
                self.classifier.encode_batch(
                    waveform
                )
            )

        embedding = (
            embedding
            .detach()
            .float()
            .cpu()
            .reshape(
                -1
            )
        )

        if embedding.numel() == 0:
            raise RuntimeError(
                "Speaker model returned an empty embedding."
            )

        return (
            torch.nn.functional.normalize(
                embedding,
                p=2,
                dim=0,
            )
        )

    @staticmethod
    def average_embeddings(
        embeddings: list[torch.Tensor],
    ) -> torch.Tensor:
        """
        Create one temporary reference from several recordings.
        """

        if not embeddings:
            raise ValueError(
                "No speaker embeddings were supplied."
            )

        stacked = torch.stack(
            embeddings,
            dim=0,
        )

        averaged = (
            stacked.mean(
                dim=0,
            )
        )

        return (
            torch.nn.functional.normalize(
                averaged,
                p=2,
                dim=0,
            )
        )

    @staticmethod
    def compare_embeddings(
        reference: torch.Tensor,
        candidate: torch.Tensor,
    ) -> float:
        """
        Compare two normalized speaker embeddings with cosine
        similarity.
        """

        if (
            reference.numel()
            != candidate.numel()
        ):
            raise ValueError(
                "Speaker embeddings have different sizes."
            )

        score = (
            torch.nn.functional.cosine_similarity(
                reference.unsqueeze(
                    0
                ),
                candidate.unsqueeze(
                    0
                ),
                dim=1,
            )
            .item()
        )

        return float(
            score
        )

    def run_diagnostic(
        self,
    ) -> bool:
        """
        Non-persistent same-speaker diagnostic.

        Several samples create a temporary in-memory reference.

        One additional recording is compared against it.

        Nothing becomes Zack's permanent biometric profile.
        """

        print()

        print(
            "ZÆNIA Speaker Verification Diagnostic"
        )

        print()

        print(
            "Mode: diagnostic only"
        )

        print(
            "Authentication authority: DISABLED"
        )

        print(
            "Raw audio persistence: DISABLED"
        )

        print(
            "Embedding persistence: DISABLED"
        )

        print()

        print(
            "Model device:",
            self.device,
        )

        print(
            "Sample rate:",
            self.sample_rate,
        )

        print()

        self.load_model()

        reference_embeddings: list[
            torch.Tensor
        ] = []

        reference_prompts = (
            (
                "Reference 1: Say a natural sentence "
                "in your normal speaking voice."
            ),
            (
                "Reference 2: Say a different sentence "
                "in the same normal voice."
            ),
            (
                "Reference 3: Say one more different "
                "sentence naturally."
            ),
        )

        for index in range(
            self.reference_samples
        ):
            prompt = reference_prompts[
                index
                % len(
                    reference_prompts
                )
            ]

            audio = (
                self.record_sample(
                    prompt=(
                        prompt
                    )
                )
            )

            embedding = (
                self.create_embedding(
                    audio
                )
            )

            reference_embeddings.append(
                embedding
            )

            del audio

        reference = (
            self.average_embeddings(
                reference_embeddings
            )
        )

        candidate_audio = (
            self.record_sample(
                prompt=(
                    "Verification sample: "
                    "Say another different sentence "
                    "in your normal speaking voice."
                )
            )
        )

        candidate = (
            self.create_embedding(
                candidate_audio
            )
        )

        del candidate_audio

        similarity = (
            self.compare_embeddings(
                reference,
                candidate,
            )
        )

        passed = (
            similarity
            >= self.diagnostic_threshold
        )

        print()

        print(
            "Speaker similarity:",
            round(
                similarity,
                4,
            ),
        )

        print(
            "Diagnostic comparison floor:",
            self.diagnostic_threshold,
        )

        print()

        print(
            "Same-speaker diagnostic:",
            (
                "PASS"
                if passed
                else "FAIL"
            ),
        )

        print()

        print(
            "No biometric profile was saved."
        )

        return passed


def main(
) -> None:
    """
    ZÆNIA speaker-verification development interface.
    """

    parser = argparse.ArgumentParser(
        description=(
            "ZÆNIA local speaker-verification engine."
        )
    )

    parser.add_argument(
        "command",
        choices=[
            "diagnostic",
        ],
    )

    args = parser.parse_args()

    if args.command == "diagnostic":
        verifier = (
            SpeakerVerifier()
        )

        passed = (
            verifier.run_diagnostic()
        )

        if not passed:
            raise SystemExit(
                1
            )


if __name__ == "__main__":
    main()