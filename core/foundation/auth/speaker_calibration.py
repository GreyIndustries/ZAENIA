from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml

from core.foundation.auth.passkey import (
    require_passkey,
)
from core.foundation.auth.speaker_profile import (
    load_encrypted_profile,
)
from core.foundation.auth.speaker_verifier import (
    SpeakerVerifier,
    load_config,
    resolve_project_path,
)
from core.foundation.security.audit import (
    audit,
)


def get_calibration_config(
) -> dict[str, Any]:
    config = load_config()

    calibration = (
        config.get(
            "calibration",
            {},
        )
        or {}
    )

    if not isinstance(
        calibration,
        dict,
    ):
        raise ValueError(
            "speaker_verification.calibration "
            "must be a dictionary."
        )

    return calibration


def get_calibration_path(
) -> Path:
    calibration = (
        get_calibration_config()
    )

    configured = str(
        calibration.get(
            "calibration_file",
            (
                "data/secure/"
                "speaker_auth_calibration.yaml"
            ),
        )
    ).strip()

    if not configured:
        raise ValueError(
            "Calibration file path cannot be empty."
        )

    return resolve_project_path(
        configured
    )


def profile_reference_tensor(
    profile: dict[str, Any],
) -> torch.Tensor:
    values = (
        profile.get(
            "speaker_embedding",
            [],
        )
        or []
    )

    if not values:
        raise RuntimeError(
            "Encrypted speaker profile contains "
            "no speaker embedding."
        )

    tensor = torch.tensor(
        [
            float(value)
            for value in values
        ],
        dtype=torch.float32,
    )

    if tensor.numel() < 64:
        raise RuntimeError(
            "Speaker profile embedding is "
            "unexpectedly small."
        )

    return torch.nn.functional.normalize(
        tensor,
        p=2,
        dim=0,
    )


def collect_scores(
    *,
    verifier: SpeakerVerifier,
    reference: torch.Tensor,
    sample_count: int,
    speaker_label: str,
) -> list[float]:
    scores: list[float] = []

    for index in range(
        sample_count
    ):
        audio = (
            verifier.record_sample(
                prompt=(
                    f"{speaker_label} sample "
                    f"{index + 1}/{sample_count}: "
                    "Speak one natural sentence."
                )
            )
        )

        embedding = (
            verifier.create_embedding(
                audio
            )
        )

        del audio

        score = (
            verifier.compare_embeddings(
                reference,
                embedding,
            )
        )

        scores.append(
            score
        )

        print(
            f"{speaker_label} similarity "
            f"{index + 1}: "
            f"{score:.4f}"
        )

    return scores


def calculate_threshold(
    *,
    genuine_scores: list[float],
    impostor_scores: list[float],
    minimum_gap: float,
) -> dict[str, float]:
    if not genuine_scores:
        raise ValueError(
            "No genuine scores were collected."
        )

    if not impostor_scores:
        raise ValueError(
            "No impostor scores were collected."
        )

    genuine_min = min(
        genuine_scores
    )

    genuine_average = (
        sum(
            genuine_scores
        )
        / len(
            genuine_scores
        )
    )

    impostor_max = max(
        impostor_scores
    )

    impostor_average = (
        sum(
            impostor_scores
        )
        / len(
            impostor_scores
        )
    )

    separation = (
        genuine_min
        - impostor_max
    )

    if separation < minimum_gap:
        raise RuntimeError(
            "Speaker calibration FAILED.\n"
            f"Genuine minimum: {genuine_min:.4f}\n"
            f"Impostor maximum: {impostor_max:.4f}\n"
            f"Observed gap: {separation:.4f}\n"
            f"Required gap: {minimum_gap:.4f}\n\n"
            "ZÆNIA will NOT enable voice "
            "authentication with overlapping "
            "speaker scores."
        )

    threshold = (
        genuine_min
        + impostor_max
    ) / 2.0

    return {
        "threshold": float(
            threshold
        ),
        "genuine_min": float(
            genuine_min
        ),
        "genuine_average": float(
            genuine_average
        ),
        "impostor_max": float(
            impostor_max
        ),
        "impostor_average": float(
            impostor_average
        ),
        "score_gap": float(
            separation
        ),
    }


def save_calibration(results: dict[str, Any]) -> Path:
    from core.foundation.local_entry import owner_execute
    from core.foundation.security.io import atomic_write, reject_link
    from core.foundation.storage.paths import SECURE_DIR
    path = get_calibration_path().absolute()
    expected = (SECURE_DIR / "speaker_auth_calibration.yaml").absolute()
    def validate(p):
        if set(p) != {"results"} or not isinstance(p["results"],dict):
            raise ValueError("Invalid calibration results.")
        binding = p["results"].get("profile_cipher_digest")
        if binding is not None:
            import hashlib
            from core.foundation.storage.paths import SPEAKER_PROFILE_FILE
            reject_link(SPEAKER_PROFILE_FILE)
            if binding != hashlib.sha256(SPEAKER_PROFILE_FILE.read_bytes()).hexdigest():
                raise PermissionError("Calibration profile changed; record fresh calibration.")
        threshold = p["results"].get("threshold")
        if type(threshold) not in (int,float) or not -1 <= threshold <= 1:
            raise ValueError("Invalid speaker similarity threshold.")
        reject_link(path)
        if path != expected:
            raise PermissionError("Calibration can write only data/secure/speaker_auth_calibration.yaml.")
        return p
    def commit(p):
        validate(p)
        atomic_write(path,yaml.safe_dump(p["results"],sort_keys=False,allow_unicode=True).encode("utf-8"))
        return path
    return owner_execute("auth.speaker.calibrate",{"results":results},commit,validate)


def run_calibration(
    *, persist=None,
) -> bool:
    print()
    print(
        "ZÆNIA Speaker Authentication Calibration"
    )
    print()
    print(
        "This step calibrates Zack-only "
        "speaker verification."
    )
    print()
    print(
        "Raw audio persistence: DISABLED"
    )
    print(
        "New embedding persistence: DISABLED"
    )
    print(
        "Authentication authority during test: "
        "DISABLED"
    )
    print()

    calibration = (
        get_calibration_config()
    )

    genuine_count = max(
        3,
        int(
            calibration.get(
                "genuine_samples",
                5,
            )
        ),
    )

    impostor_count = max(
        2,
        int(
            calibration.get(
                "impostor_samples",
                3,
            )
        ),
    )

    minimum_gap = float(
        calibration.get(
            "minimum_score_gap",
            0.05,
        )
    )

    print(
        "Passkey authentication required "
        "to unlock Zack's encrypted profile."
    )

    passphrase = (
        require_passkey()
    )

    profile = (
        load_encrypted_profile(
            passphrase
        )
    )

    reference = (
        profile_reference_tensor(
            profile
        )
    )

    verifier = (
        SpeakerVerifier()
    )

    verifier.load_model()

    print()
    print(
        "STEP 1 — Zack samples"
    )
    print(
        f"Record {genuine_count} natural "
        "samples from Zack."
    )

    genuine_scores = (
        collect_scores(
            verifier=verifier,
            reference=reference,
            sample_count=(
                genuine_count
            ),
            speaker_label="Zack",
        )
    )

    print()
    print(
        "STEP 2 — Non-Zack samples"
    )
    print(
        "Have another person use the SAME "
        "approved microphone."
    )
    print(
        f"Record {impostor_count} natural "
        "samples from that person."
    )

    impostor_scores = (
        collect_scores(
            verifier=verifier,
            reference=reference,
            sample_count=(
                impostor_count
            ),
            speaker_label="Non-Zack",
        )
    )

    results = (
        calculate_threshold(
            genuine_scores=(
                genuine_scores
            ),
            impostor_scores=(
                impostor_scores
            ),
            minimum_gap=(
                minimum_gap
            ),
        )
    )

    calibration_record = {
        "version": 1,
        "created_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "profile_id": (
            profile.get(
                "profile_id"
            )
        ),
        "model": (
            "ECAPA-TDNN"
        ),
        "threshold": (
            results[
                "threshold"
            ]
        ),
        "minimum_required_gap": (
            minimum_gap
        ),
        "observed": {
            "genuine_sample_count": (
                len(
                    genuine_scores
                )
            ),
            "genuine_min": (
                results[
                    "genuine_min"
                ]
            ),
            "genuine_average": (
                results[
                    "genuine_average"
                ]
            ),
            "impostor_sample_count": (
                len(
                    impostor_scores
                )
            ),
            "impostor_max": (
                results[
                    "impostor_max"
                ]
            ),
            "impostor_average": (
                results[
                    "impostor_average"
                ]
            ),
            "score_gap": (
                results[
                    "score_gap"
                ]
            ),
        },
        "privacy": {
            "raw_audio_persisted": False,
            "new_embeddings_persisted": False,
        },
        "authentication_ready": True,
    }

    path = (
        (persist or save_calibration)(calibration_record)
    )

    audit(
        "speaker_calibration",
        (
            "Zack speaker authentication "
            "threshold calibrated successfully."
        ),
    )

    print()
    print(
        "Speaker calibration: PASS"
    )

    print(
        "Genuine minimum:",
        round(
            results[
                "genuine_min"
            ],
            4,
        ),
    )

    print(
        "Impostor maximum:",
        round(
            results[
                "impostor_max"
            ],
            4,
        ),
    )

    print(
        "Score gap:",
        round(
            results[
                "score_gap"
            ],
            4,
        ),
    )

    print(
        "Authentication threshold:",
        round(
            results[
                "threshold"
            ],
            4,
        ),
    )

    print(
        "Calibration saved:",
        path,
    )

    print()
    print(
        "Live command authentication is "
        "still DISABLED until the next step "
        "wires this calibrated threshold into "
        "the runtime."
    )

    return True


def main(
) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ZÆNIA Zack-only speaker "
            "authentication calibration."
        )
    )

    parser.add_argument(
        "command",
        choices=[
            "calibrate",
        ],
    )

    args = (
        parser.parse_args()
    )

    if args.command == "calibrate":
        passed = (
            run_calibration()
        )

        if not passed:
            raise SystemExit(
                1
            )


if __name__ == "__main__":
    main()