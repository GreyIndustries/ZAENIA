from __future__ import annotations

import argparse
import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

import torch

from core.foundation.auth.passkey import (
    require_passkey,
)
from core.foundation.auth.speaker_verifier import (
    SpeakerVerifier,
    load_config,
)
from core.foundation.security.audit import (
    audit,
)
from core.foundation.security.crypto import (
    decrypt_text_scoped,
    encrypt_text_scoped,
)
from core.foundation.storage.paths import (
    SPEAKER_PROFILE_FILE,
    ensure_storage,
)


PROFILE_ID = (
    "zaenia-zack-speaker-profile"
)


def get_enrollment_config(
) -> dict[str, Any]:
    """
    Read enrollment settings from the existing speaker
    verification configuration.
    """

    config = (
        load_config()
    )

    enrollment = (
        config.get(
            "enrollment",
            {},
        )
        or {}
    )

    if not isinstance(
        enrollment,
        dict,
    ):
        raise ValueError(
            "speaker_verification.enrollment "
            "must be a dictionary."
        )

    return enrollment


def get_encryption_scope(
) -> str:
    """
    Return the biometric profile's cryptographic domain.
    """

    enrollment = (
        get_enrollment_config()
    )

    scope = str(
        enrollment.get(
            "encryption_scope",
            "speaker_profile_v1",
        )
    ).strip()

    if not scope:
        raise ValueError(
            "Speaker profile encryption scope "
            "cannot be empty."
        )

    return scope


def get_enrollment_sample_count(
) -> int:
    """
    Number of independent enrollment samples.

    Six gives us a better reference than the three-sample
    diagnostic while remaining practical to record.
    """

    enrollment = (
        get_enrollment_config()
    )

    return max(
        3,
        int(
            enrollment.get(
                "sample_count",
                6,
            )
        ),
    )


def get_profile_version(
) -> int:
    """
    Speaker-profile storage schema version.
    """

    enrollment = (
        get_enrollment_config()
    )

    return int(
        enrollment.get(
            "profile_version",
            1,
        )
    )


def tensor_to_float_list(
    tensor: torch.Tensor,
) -> list[float]:
    """
    Convert an in-memory normalized speaker embedding into a
    JSON-serializable list.

    This list is never written to disk before encryption.
    """

    return [
        float(
            value
        )
        for value in (
            tensor
            .detach()
            .cpu()
            .reshape(
                -1
            )
            .tolist()
        )
    ]


def calculate_enrollment_similarities(
    verifier: SpeakerVerifier,
    reference: torch.Tensor,
    embeddings: list[torch.Tensor],
) -> list[float]:
    """
    Compare each enrollment sample against the final averaged
    reference.

    These values are useful later during Zack-specific
    threshold calibration.

    They are metadata inside the encrypted profile.
    """

    return [
        verifier.compare_embeddings(
            reference,
            embedding,
        )
        for embedding in embeddings
    ]


def build_profile(
    *,
    verifier: SpeakerVerifier,
    embeddings: list[torch.Tensor],
) -> dict[str, Any]:
    """
    Build Zack's biometric identity template in memory.

    Stored biometric material:

        normalized averaged ECAPA embedding

    Not stored:

        raw microphone recordings
        transcripts
        spoken phrases
    """

    if not embeddings:
        raise ValueError(
            "Cannot create speaker profile "
            "without enrollment embeddings."
        )

    reference = (
        verifier.average_embeddings(
            embeddings
        )
    )

    similarities = (
        calculate_enrollment_similarities(
            verifier,
            reference,
            embeddings,
        )
    )

    if not similarities:
        raise RuntimeError(
            "Enrollment consistency scores "
            "could not be calculated."
        )

    embedding_values = (
        tensor_to_float_list(
            reference
        )
    )

    if not embedding_values:
        raise RuntimeError(
            "Enrollment produced an empty "
            "speaker embedding."
        )

    created_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    return {
        "profile_id": (
            PROFILE_ID
        ),
        "version": (
            get_profile_version()
        ),
        "created_at": (
            created_at
        ),

        "owner": {
            "identifier": "Zack",
            "profile_type": (
                "speaker_identity"
            ),
        },

        "model": {
            "provider": (
                "speechbrain_local"
            ),
            "architecture": (
                "ECAPA-TDNN"
            ),
            "source": (
                verifier.remote_source
            ),
            "sample_rate": (
                verifier.sample_rate
            ),
            "embedding_dimensions": (
                len(
                    embedding_values
                )
            ),
            "normalization": (
                "L2"
            ),
        },

        "enrollment": {
            "sample_count": (
                len(
                    embeddings
                )
            ),
            "minimum_similarity_to_centroid": (
                min(
                    similarities
                )
            ),
            "average_similarity_to_centroid": (
                sum(
                    similarities
                )
                / len(
                    similarities
                )
            ),
            "maximum_similarity_to_centroid": (
                max(
                    similarities
                )
            ),
        },

        "speaker_embedding": (
            embedding_values
        ),

        "security": {
            "raw_audio_persisted": False,
            "plaintext_profile_persisted": False,
            "authentication_enabled": False,
        },
    }


def validate_profile(
    profile: dict[str, Any],
) -> None:
    """
    Validate a decrypted profile before it is trusted.

    This prevents malformed or incomplete data from quietly
    becoming authentication state later.
    """

    if not isinstance(
        profile,
        dict,
    ):
        raise ValueError(
            "Speaker profile must be a dictionary."
        )

    if (
        profile.get(
            "profile_id"
        )
        != PROFILE_ID
    ):
        raise ValueError(
            "Speaker profile identifier is invalid."
        )

    embedding = (
        profile.get(
            "speaker_embedding",
            []
        )
        or []
    )

    if not isinstance(
        embedding,
        list,
    ):
        raise ValueError(
            "Speaker embedding must be a list."
        )

    if len(
        embedding
    ) < 64:
        raise ValueError(
            "Speaker embedding is unexpectedly small."
        )

    try:
        [
            float(
                value
            )
            for value in embedding
        ]

    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "Speaker embedding contains "
            "non-numeric data."
        ) from error

    security = (
        profile.get(
            "security",
            {},
        )
        or {}
    )

    if (
        security.get(
            "raw_audio_persisted"
        )
        is not False
    ):
        raise ValueError(
            "Speaker profile security metadata "
            "does not confirm raw-audio privacy."
        )

    if (
        security.get(
            "authentication_enabled"
        )
        is not False
    ):
        raise ValueError(
            "Enrollment profile must not enable "
            "authentication authority."
        )


def serialize_profile(
    profile: dict[str, Any],
) -> str:
    """
    Serialize only in memory.

    The plaintext JSON is never written to a file.
    """

    validate_profile(
        profile
    )

    return json.dumps(
        profile,
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
    )


def save_encrypted_profile(profile: dict[str, Any], passphrase: str) -> None:
    """Create a profile after fresh exact-payload authentication at commit time.

    The legacy passphrase argument is retained for caller compatibility; a cached
    string is never accepted as authorization and is not used for encryption.
    """
    import hashlib
    from core.foundation.auth.passkey import consume_fresh_auth
    from core.foundation.rules.policy import assert_owner_scope
    from core.foundation.security.io import atomic_write, reject_link
    ensure_storage()
    reject_link(SPEAKER_PROFILE_FILE)
    if SPEAKER_PROFILE_FILE.exists():
        raise RuntimeError("Speaker profile already exists; refusing to overwrite it.")
    serialized = serialize_profile(profile)
    scope = get_encryption_scope()
    binding = {"profile_digest":hashlib.sha256(serialized.encode("utf-8")).hexdigest(),"scope":scope}
    proof = require_passkey(operation="auth.speaker.enroll",payload=binding)
    assert_owner_scope(proof,"auth.speaker.enroll")
    consume_fresh_auth(proof,operation="auth.speaker.enroll",payload=binding)
    encrypted = encrypt_text_scoped(serialized,proof,scope=scope)
    validate_profile(json.loads(decrypt_text_scoped(encrypted,proof,scope=scope)))
    atomic_write(SPEAKER_PROFILE_FILE,encrypted,overwrite=False)
    audit("speaker_profile.created",operation="auth.speaker.enroll",reason_code="fresh_owner_enrollment")


def load_encrypted_profile(
    passphrase: str,
) -> dict[str, Any]:
    """
    Decrypt Zack's local speaker profile after valid passkey
    authentication.

    This will be used by the later live verifier.
    """

    if not SPEAKER_PROFILE_FILE.exists():
        raise RuntimeError(
            "Encrypted speaker profile does not exist."
        )

    encrypted = (
        SPEAKER_PROFILE_FILE.read_bytes()
    )

    decrypted = (
        decrypt_text_scoped(
            encrypted,
            passphrase,
            scope=(
                get_encryption_scope()
            ),
        )
    )

    profile = (
        json.loads(
            decrypted
        )
    )

    validate_profile(
        profile
    )

    return profile


def enrollment_prompts(
) -> tuple[str, ...]:
    """
    Different natural delivery conditions help the profile
    represent Zack rather than one exact sentence.

    We still avoid extreme imitation/whisper testing here;
    threshold calibration comes next.
    """

    return (
        (
            "Enrollment 1: Speak one natural sentence "
            "in your normal voice."
        ),
        (
            "Enrollment 2: Speak a different sentence "
            "at your normal conversational pace."
        ),
        (
            "Enrollment 3: Speak another sentence "
            "naturally and clearly."
        ),
        (
            "Enrollment 4: Speak a new sentence "
            "slightly more casually."
        ),
        (
            "Enrollment 5: Speak another sentence "
            "with your normal everyday tone."
        ),
        (
            "Enrollment 6: Speak one final different "
            "sentence naturally."
        ),
    )


def replace_speaker_profile() -> bool:
    """Owner-only voice retraining (protected identity change).

    Requires the passkey and a typed REPLACE. The current encrypted profile is
    moved aside (kept, never deleted) so a mistaken retrain can be undone by
    moving it back; then normal enrollment runs and asks for the passkey again.
    """
    import os
    from core.foundation.security.io import reject_link
    print()
    print("ZÆNIA voice retraining: replaces your enrolled voice profile.")
    print("You'll need your passkey, then you'll record new samples on the approved microphone.")
    print()
    if not SPEAKER_PROFILE_FILE.exists():
        print("No profile exists yet; running normal enrollment.")
        return enroll_speaker_profile()
    require_passkey(operation="auth.speaker.enroll", payload={"purpose": "replace_speaker_profile"})
    if input("Type REPLACE to retrain your voice profile: ").strip() != "REPLACE":
        print("Cancelled. Your current profile is unchanged.")
        return False
    backup_dir = SPEAKER_PROFILE_FILE.parent / "profile_backups"
    backup_dir.mkdir(exist_ok=True)
    reject_link(SPEAKER_PROFILE_FILE)
    reject_link(backup_dir)
    target = backup_dir / ("speaker_profile-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".vault")
    os.replace(SPEAKER_PROFILE_FILE, target)
    audit("auth.speaker_profile_retrain", operation="auth.speaker.enroll", reason_code="previous_profile_backed_up")
    print(f"Previous profile kept at {target}.")
    try:
        passed = enroll_speaker_profile()
    except BaseException:
        if not SPEAKER_PROFILE_FILE.exists():
            os.replace(target, SPEAKER_PROFILE_FILE)  # nothing new was written: put the old one back
            print("Enrollment stopped; your previous profile was restored.")
        raise
    if not passed and not SPEAKER_PROFILE_FILE.exists():
        os.replace(target, SPEAKER_PROFILE_FILE)
        print("Enrollment didn't finish; your previous profile was restored.")
    return passed


def enroll_speaker_profile(
) -> bool:
    """
    Create Zack's encrypted speaker identity profile.

    Sensitive identity creation requires the existing ZÆNIA
    passkey first.
    """

    print()

    print(
        "ZÆNIA Encrypted Speaker Enrollment"
    )

    print()

    print(
        "Sensitive identity change: "
        "re-authentication required"
    )

    print(
        "Raw audio persistence: DISABLED"
    )

    print(
        "Plaintext biometric persistence: DISABLED"
    )

    print(
        "Command authentication authority: DISABLED"
    )

    print()

    if SPEAKER_PROFILE_FILE.exists():
        raise RuntimeError(
            "A Zack speaker profile already exists. "
            "Enrollment will not overwrite it."
        )

    passphrase = (
        require_passkey()
    )

    verifier = (
        SpeakerVerifier()
    )

    sample_count = (
        get_enrollment_sample_count()
    )

    print()

    print(
        "Passkey authentication: PASS"
    )

    print(
        "Model device:",
        verifier.device,
    )

    print(
        "Enrollment samples:",
        sample_count,
    )

    print()

    verifier.load_model()

    embeddings: list[
        torch.Tensor
    ] = []

    prompts = (
        enrollment_prompts()
    )

    for index in range(
        sample_count
    ):
        prompt = prompts[
            index
            % len(
                prompts
            )
        ]

        audio = (
            verifier.record_sample(
                prompt=(
                    prompt
                )
            )
        )

        embedding = (
            verifier.create_embedding(
                audio
            )
        )

        embeddings.append(
            embedding
        )

        # [comment omitted from source review]
        # [comment omitted from source review]
        del audio

        print(
            f"Enrollment sample "
            f"{index + 1}/{sample_count}: "
            "accepted"
        )

    profile = (
        build_profile(
            verifier=(
                verifier
            ),
            embeddings=(
                embeddings
            ),
        )
    )

    save_encrypted_profile(
        profile,
        passphrase,
    )

    # [comment omitted from source review]
    # [comment omitted from source review]
    loaded = (
        load_encrypted_profile(
            passphrase
        )
    )

    storage_passed = (
        loaded.get(
            "profile_id"
        )
        == PROFILE_ID
        and len(
            loaded.get(
                "speaker_embedding",
                [],
            )
        )
        == len(
            profile.get(
                "speaker_embedding",
                [],
            )
        )
    )

    print()

    print(
        "Encrypted speaker profile:",
        (
            "CREATED"
            if storage_passed
            else "FAILED"
        ),
    )

    print(
        "Storage:",
        (
            "data/secure/"
            "speaker_profile.vault"
        ),
    )

    print(
        "Embedding dimensions:",
        profile[
            "model"
        ][
            "embedding_dimensions"
        ],
    )

    print(
        "Enrollment samples:",
        profile[
            "enrollment"
        ][
            "sample_count"
        ],
    )

    print(
        "Profile storage verification:",
        (
            "PASS"
            if storage_passed
            else "FAIL"
        ),
    )

    print(
        "Raw audio persisted:",
        False,
    )

    print(
        "Plaintext biometric profile persisted:",
        False,
    )

    print(
        "Authentication authority:",
        "DISABLED",
    )

    if not storage_passed:
        raise RuntimeError(
            "Encrypted speaker-profile "
            "verification failed."
        )

    return True


def main(
) -> None:
    """
    Speaker-profile management interface.

    Commands:

        enroll    create the profile (refuses to overwrite one)
        replace   owner-only retraining: passkey, then typing REPLACE; the
                  old encrypted profile is moved to secure/profile_backups
                  (never deleted), then a fresh enrollment runs on the
                  approved microphone. Calibration must be redone after.
    """

    parser = (
        argparse.ArgumentParser(
            description=(
                "ZÆNIA encrypted local "
                "speaker-profile enrollment."
            )
        )
    )

    parser.add_argument(
        "command",
        choices=[
            "enroll",
            "replace",
        ],
    )

    args = (
        parser.parse_args()
    )

    if args.command == "replace":
        if not replace_speaker_profile():
            raise SystemExit(1)
        return

    if args.command == "enroll":
        passed = (
            enroll_speaker_profile()
        )

        if not passed:
            raise SystemExit(
                1
            )


if __name__ == "__main__":
    main()