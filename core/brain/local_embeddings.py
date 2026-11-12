from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "brain"
    / "semantic_config.yaml"
)


# Reuse one local HTTP session instead of opening a completely
# separate client connection for every embedding batch.
#
# This reduces loopback socket churn while ZÆNIA is rebuilding
# hundreds of semantic chunks.
_HTTP_SESSION = requests.Session()


def load_semantic_config() -> dict[str, Any]:
    """
    Load ZÆNIA's local semantic-search configuration.
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing semantic config: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        config = yaml.safe_load(
            file
        ) or {}

    semantic_config = (
        config.get(
            "semantic_search",
            {},
        )
        or {}
    )

    if not isinstance(
        semantic_config,
        dict,
    ):
        raise ValueError(
            "semantic_search configuration "
            "must be a dictionary."
        )

    return semantic_config


def get_embedding_settings() -> dict[str, Any]:
    """
    Extract settings needed by the local embedding engine.

    All important transport behavior comes from YAML rather
    than being buried in Python constants.
    """

    config = (
        load_semantic_config()
    )

    embedding = (
        config.get(
            "embedding",
            {},
        )
        or {}
    )

    return {
        "model": str(
            embedding.get(
                "model",
                "nomic-embed-text",
            )
        ),
        "endpoint": str(
            embedding.get(
                "endpoint",
                "http://127.0.0.1:11434/api/embed",
            )
        ),
        "timeout": int(
            embedding.get(
                "timeout_seconds",
                120,
            )
        ),
        "batch_size": max(
            1,
            int(
                embedding.get(
                    "batch_size",
                    32,
                )
            ),
        ),
        "retry_attempts": max(
            1,
            int(
                embedding.get(
                    "retry_attempts",
                    5,
                )
            ),
        ),
        "retry_base_delay": max(
            0.1,
            float(
                embedding.get(
                    "retry_base_delay_seconds",
                    2.0,
                )
            ),
        ),
        "retry_max_delay": max(
            0.1,
            float(
                embedding.get(
                    "retry_max_delay_seconds",
                    12.0,
                )
            ),
        ),
    }


def check_ollama_available() -> bool:
    """
    Confirm that Ollama is reachable on this computer.

    127.0.0.1 means the request never needs to leave Zack's
    local machine.

    This function remains useful for diagnostics, but normal
    embedding calls no longer invoke it before every batch.
    The embedding POST itself is sufficient to determine
    whether Ollama is available.
    """

    try:
        response = (
            _HTTP_SESSION.get(
                "http://127.0.0.1:11434/api/tags",
                timeout=3,
            )
        )

        return (
            response.status_code
            == 200
        )

    except requests.RequestException:
        return False


def is_transient_ollama_error(
    status_code: int,
    response_text: str,
) -> bool:
    """
    Decide whether an Ollama failure is probably temporary.

    The Windows error Zack encountered looked like:

        insufficient buffer space
        or
        queue was full

    Ollama returned that as HTTP 400 even though the request
    itself was valid.

    Therefore we cannot treat every HTTP 400 as a permanent
    configuration error.

    We retry only when the response contains recognizable
    temporary resource/transport symptoms.
    """

    if status_code == 429:
        return True

    if 500 <= status_code <= 599:
        return True

    lowered = (
        response_text.lower()
    )

    transient_phrases = (
        "buffer space",
        "queue was full",
        "queue full",
        "temporarily unavailable",
        "temporary failure",
        "server busy",
        "connection reset",
        "connection refused",
        "resource temporarily unavailable",
        "tokenize",
        "socket",
    )

    return any(
        phrase in lowered
        for phrase in transient_phrases
    )


def calculate_retry_delay(
    attempt_number: int,
    *,
    base_delay: float,
    max_delay: float,
) -> float:
    """
    Calculate exponential backoff.

    Example with a 2-second base:

        retry 1 -> 2 seconds
        retry 2 -> 4 seconds
        retry 3 -> 8 seconds
        retry 4 -> 12 seconds maximum

    This gives Ollama and Windows time to release temporary
    socket/tokenizer resources.
    """

    exponent = max(
        0,
        attempt_number - 1,
    )

    delay = (
        base_delay
        * (
            2 ** exponent
        )
    )

    return min(
        delay,
        max_delay,
    )


def validate_embeddings(
    embeddings: Any,
    *,
    expected_count: int,
) -> list[list[float]]:
    """
    Validate Ollama's returned vector structure before another
    ZÆNIA subsystem is allowed to use it.
    """

    if not isinstance(
        embeddings,
        list,
    ):
        raise RuntimeError(
            "Local embedding response did not "
            "contain an embedding list."
        )

    if not embeddings:
        raise RuntimeError(
            "The local embedding model returned "
            "no vectors."
        )

    if (
        len(embeddings)
        != expected_count
    ):
        raise RuntimeError(
            "Embedding count does not match "
            "the number of input texts."
        )

    validated: list[
        list[float]
    ] = []

    expected_dimensions: int | None = (
        None
    )

    for vector in embeddings:
        if not isinstance(
            vector,
            list,
        ):
            raise RuntimeError(
                "Embedding vector was not a list."
            )

        if not vector:
            raise RuntimeError(
                "Embedding vector was empty."
            )

        try:
            numeric_vector = [
                float(value)
                for value in vector
            ]

        except (
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "Embedding vector contained "
                "non-numeric values."
            ) from error

        if expected_dimensions is None:
            expected_dimensions = len(
                numeric_vector
            )

        elif (
            len(
                numeric_vector
            )
            != expected_dimensions
        ):
            raise RuntimeError(
                "Embedding vectors returned "
                "different dimensions."
            )

        validated.append(
            numeric_vector
        )

    return validated


def embed_texts(
    texts: list[str],
) -> list[list[float]]:
    """
    Convert one or more local text strings into semantic
    vectors using Ollama.

    Important transport behavior:

        - one persistent HTTP session is reused
        - no extra /api/tags request occurs before every batch
        - temporary tokenizer/socket pressure is retried
        - retries use exponential backoff
        - permanent configuration errors still fail clearly

    Internet access is not required.
    """

    cleaned_texts = [
        text.strip()
        for text in texts
        if text.strip()
    ]

    if not cleaned_texts:
        return []

    settings = (
        get_embedding_settings()
    )

    payload = {
        "model": (
            settings[
                "model"
            ]
        ),
        "input": (
            cleaned_texts
        ),
    }

    last_error: str | None = None

    retry_attempts = int(
        settings[
            "retry_attempts"
        ]
    )

    for attempt in range(
        1,
        retry_attempts + 1,
    ):
        try:
            response = (
                _HTTP_SESSION.post(
                    settings[
                        "endpoint"
                    ],
                    json=payload,
                    timeout=settings[
                        "timeout"
                    ],
                )
            )

        except requests.RequestException as error:
            last_error = (
                "Local embedding connection failed: "
                f"{error}"
            )

            if attempt >= retry_attempts:
                break

            delay = (
                calculate_retry_delay(
                    attempt,
                    base_delay=settings[
                        "retry_base_delay"
                    ],
                    max_delay=settings[
                        "retry_max_delay"
                    ],
                )
            )

            print(
                "Local embedding transport "
                "temporarily unavailable. "
                f"Retrying in {delay:.1f}s "
                f"({attempt}/{retry_attempts})..."
            )

            time.sleep(
                delay
            )

            continue

        if response.status_code < 400:
            try:
                data = (
                    response.json()
                )

            except ValueError as error:
                raise RuntimeError(
                    "Local embedding service returned "
                    "invalid JSON."
                ) from error

            embeddings = data.get(
                "embeddings",
                [],
            )

            return validate_embeddings(
                embeddings,
                expected_count=len(
                    cleaned_texts
                ),
            )

        response_text = (
            response.text
        )

        last_error = (
            "Local embedding request failed: "
            f"{response.status_code} "
            f"{response_text}"
        )

        transient = (
            is_transient_ollama_error(
                response.status_code,
                response_text,
            )
        )

        if (
            not transient
            or attempt >= retry_attempts
        ):
            break

        delay = (
            calculate_retry_delay(
                attempt,
                base_delay=settings[
                    "retry_base_delay"
                ],
                max_delay=settings[
                    "retry_max_delay"
                ],
            )
        )

        print(
            "Ollama embedding service reported "
            "temporary local resource pressure. "
            f"Retrying in {delay:.1f}s "
            f"({attempt}/{retry_attempts})..."
        )

        time.sleep(
            delay
        )

    raise RuntimeError(
        last_error
        or (
            "Local embedding request failed "
            "for an unknown reason."
        )
    )


def embed_text(
    text: str,
) -> list[float]:
    """
    Convenience wrapper for embedding one string.
    """

    vectors = embed_texts(
        [
            text,
        ]
    )

    if not vectors:
        return []

    return vectors[
        0
    ]


def cosine_similarity(
    first: list[float],
    second: list[float],
) -> float:
    """
    Measure semantic similarity between two embedding vectors.

    Values closer to 1 generally indicate more similar
    semantic meaning.
    """

    if not first or not second:
        return 0.0

    if len(
        first
    ) != len(
        second
    ):
        raise ValueError(
            "Embedding vectors must have "
            "the same dimensions."
        )

    dot_product = 0.0

    first_magnitude = 0.0
    second_magnitude = 0.0

    for (
        first_value,
        second_value,
    ) in zip(
        first,
        second,
    ):
        dot_product += (
            first_value
            * second_value
        )

        first_magnitude += (
            first_value
            * first_value
        )

        second_magnitude += (
            second_value
            * second_value
        )

    if (
        first_magnitude == 0.0
        or second_magnitude == 0.0
    ):
        return 0.0

    denominator = (
        first_magnitude ** 0.5
    ) * (
        second_magnitude ** 0.5
    )

    return (
        dot_product
        / denominator
    )


def semantic_test() -> None:
    """
    Development test for local semantic understanding.

    The first two statements concern voice generation.

    The third concerns calendar scheduling.

    The related pair should therefore receive the stronger
    semantic similarity.
    """

    first_text = (
        "What actually makes your voice?"
    )

    second_text = (
        "Piper is the local text to speech "
        "provider for ZÆNIA."
    )

    unrelated_text = (
        "Recurring calendar events are stored "
        "in the scheduling system."
    )

    vectors = embed_texts(
        [
            first_text,
            second_text,
            unrelated_text,
        ]
    )

    voice_similarity = (
        cosine_similarity(
            vectors[
                0
            ],
            vectors[
                1
            ],
        )
    )

    unrelated_similarity = (
        cosine_similarity(
            vectors[
                0
            ],
            vectors[
                2
            ],
        )
    )

    print(
        "ZÆNIA Local Semantic Engine"
    )

    print()

    print(
        "Embedding dimensions:",
        len(
            vectors[
                0
            ]
        ),
    )

    print()

    print(
        "Voice-related similarity:",
        round(
            voice_similarity,
            4,
        ),
    )

    print(
        "Unrelated similarity:",
        round(
            unrelated_similarity,
            4,
        ),
    )

    print()

    if (
        voice_similarity
        > unrelated_similarity
    ):
        print(
            "Semantic relationship "
            "detected correctly."
        )

    else:
        print(
            "Semantic relationship "
            "test failed."
        )


if __name__ == "__main__":
    semantic_test()