from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.brain.index_freshness import (
    ensure_index_fresh,
)
from core.brain.local_embeddings import (
    embed_texts,
    get_embedding_settings,
    load_semantic_config,
)
from core.brain.system_index import (
    load_index,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_project_path(
    value: str,
) -> Path:
    """
    Resolve a path relative to the ZÆNIA project root.

    Example:

        data/system_awareness/semantic_index.json

    becomes:

        C:/Projects/ZAENIA/
        data/system_awareness/semantic_index.json
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


def get_semantic_settings() -> dict[str, Any]:
    """
    Load settings that control semantic indexing.

    Keeping these settings outside the Python implementation
    means Zack can later change the embedding model or chunk
    strategy without redesigning this module.
    """

    config = (
        load_semantic_config()
    )

    chunking = (
        config.get(
            "chunking",
            {},
        )
        or {}
    )

    storage = (
        config.get(
            "storage",
            {},
        )
        or {}
    )

    embedding = (
        config.get(
            "embedding",
            {},
        )
        or {}
    )

    return {
        "max_chars": int(
            chunking.get(
                "max_chars",
                1200,
            )
        ),
        "overlap_chars": int(
            chunking.get(
                "overlap_chars",
                200,
            )
        ),
        "semantic_index_file": str(
            storage.get(
                "semantic_index_file",
                (
                    "data/system_awareness/"
                    "semantic_index.json"
                ),
            )
        ),
        "batch_size": int(
            embedding.get(
                "batch_size",
                16,
            )
        ),
    }


def get_semantic_index_path() -> Path:
    """
    Return the local semantic-index storage path.
    """

    settings = (
        get_semantic_settings()
    )

    return resolve_project_path(
        settings[
            "semantic_index_file"
        ]
    )


def normalize_chunk_text(
    text: str,
) -> str:
    """
    Remove excessive blank lines without rewriting source
    content.

    This reduces meaningless whitespace inside embeddings.
    """

    lines: list[str] = []

    previous_blank = False

    for raw_line in text.splitlines():
        line = (
            raw_line.rstrip()
        )

        if not line.strip():
            if previous_blank:
                continue

            previous_blank = True

            lines.append(
                ""
            )

            continue

        previous_blank = False

        lines.append(
            line
        )

    return "\n".join(
        lines
    ).strip()


def find_safe_end(
    text: str,
    start: int,
    target_end: int,
) -> int:
    """
    Try to end a semantic chunk at a natural text boundary.

    Preferred order:

        paragraph
        newline
        space
        hard character boundary
    """

    if target_end >= len(
        text
    ):
        return len(
            text
        )

    search_start = max(
        start,
        target_end - 250,
    )

    window = text[
        search_start:
        target_end
    ]

    paragraph_position = (
        window.rfind(
            "\n\n"
        )
    )

    if paragraph_position >= 0:
        return (
            search_start
            + paragraph_position
            + 2
        )

    newline_position = (
        window.rfind(
            "\n"
        )
    )

    if newline_position >= 0:
        return (
            search_start
            + newline_position
            + 1
        )

    space_position = (
        window.rfind(
            " "
        )
    )

    if space_position >= 0:
        return (
            search_start
            + space_position
            + 1
        )

    return target_end


def create_text_chunks(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int,
) -> list[str]:
    """
    Divide an approved source file into overlapping semantic
    chunks.

    Embedding smaller sections prevents unrelated functions
    from being blended into one large vector.
    """

    text = (
        normalize_chunk_text(
            text
        )
    )

    if not text:
        return []

    if max_chars <= 0:
        raise ValueError(
            "max_chars must be greater "
            "than zero."
        )

    if overlap_chars < 0:
        raise ValueError(
            "overlap_chars cannot "
            "be negative."
        )

    if overlap_chars >= max_chars:
        raise ValueError(
            "overlap_chars must be "
            "smaller than max_chars."
        )

    if len(text) <= max_chars:
        return [
            text,
        ]

    chunks: list[str] = []

    start = 0

    while start < len(
        text
    ):
        target_end = min(
            len(text),
            start + max_chars,
        )

        end = find_safe_end(
            text,
            start,
            target_end,
        )

        if end <= start:
            end = target_end

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        if end >= len(
            text
        ):
            break

        next_start = max(
            0,
            end - overlap_chars,
        )

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def calculate_text_hash(
    text: str,
) -> str:
    """
    Calculate a SHA-256 fingerprint for a semantic chunk.
    """

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def build_embedding_input(
    *,
    path: str,
    extension: str,
    chunk_text: str,
) -> str:
    """
    Add useful local project context to the text before
    generating its embedding.

    The stored source itself is not modified.
    """

    return (
        f"ZÆNIA project file: {path}\n"
        f"File type: "
        f"{extension or 'unknown'}\n"
        "\n"
        f"{chunk_text}"
    )


def calculate_semantic_source_signature(
    system_index: dict[str, Any],
) -> str:
    """
    Create a STABLE fingerprint representing everything that
    determines the meaning index.

    The signature includes:

        approved searchable files
        file fingerprints
        embedding model
        chunk size
        chunk overlap

    Why not simply compare timestamps?

    Because timestamps describe WHEN something happened.

    This signature describes WHAT semantic knowledge should
    currently exist.

    If the signature changes, the semantic index is stale.
    """

    semantic_settings = (
        get_semantic_settings()
    )

    embedding_settings = (
        get_embedding_settings()
    )

    source_files: list[
        dict[str, Any]
    ] = []

    for record in system_index.get(
        "files",
        [],
    ):
        if not record.get(
            "content_indexed",
            False,
        ):
            continue

        fingerprint = str(
            record.get(
                "sha256",
                "",
            )
        )

        # [comment omitted from source review]
        # [comment omitted from source review]
        if not fingerprint:
            fingerprint = (
                str(
                    record.get(
                        "size_bytes",
                        "",
                    )
                )
                + ":"
                + str(
                    record.get(
                        "modified",
                        "",
                    )
                )
            )

        source_files.append(
            {
                "root": str(
                    record.get(
                        "root",
                        "",
                    )
                ),
                "path": str(
                    record.get(
                        "path",
                        "",
                    )
                ),
                "fingerprint": (
                    fingerprint
                ),
            }
        )

    source_files.sort(
        key=lambda item: (
            item[
                "root"
            ].lower(),
            item[
                "path"
            ].lower(),
        )
    )

    signature_payload = {
        "embedding_model": (
            embedding_settings[
                "model"
            ]
        ),
        "max_chars": (
            semantic_settings[
                "max_chars"
            ]
        ),
        "overlap_chars": (
            semantic_settings[
                "overlap_chars"
            ]
        ),
        "source_files": (
            source_files
        ),
    }

    serialized = json.dumps(
        signature_payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
    )

    return hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()


def collect_semantic_chunks(
    system_index: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert APPROVED searchable files into semantic chunks.

    Security boundary:

        system awareness policy
            ↓
        approved content index
            ↓
        semantic index

    Semantic indexing cannot independently read ignored files
    or secure directories.
    """

    settings = (
        get_semantic_settings()
    )

    max_chars = (
        settings[
            "max_chars"
        ]
    )

    overlap_chars = (
        settings[
            "overlap_chars"
        ]
    )

    chunks: list[
        dict[str, Any]
    ] = []

    for record in system_index.get(
        "files",
        [],
    ):
        if not record.get(
            "content_indexed",
            False,
        ):
            continue

        content = str(
            record.get(
                "content",
                "",
            )
        )

        if not content.strip():
            continue

        path = str(
            record.get(
                "path",
                "",
            )
        )

        root = str(
            record.get(
                "root",
                "",
            )
        )

        extension = str(
            record.get(
                "extension",
                "",
            )
        )

        file_chunks = (
            create_text_chunks(
                content,
                max_chars=max_chars,
                overlap_chars=(
                    overlap_chars
                ),
            )
        )

        for (
            chunk_number,
            chunk_text,
        ) in enumerate(
            file_chunks,
            start=1,
        ):
            embedding_text = (
                build_embedding_input(
                    path=path,
                    extension=extension,
                    chunk_text=(
                        chunk_text
                    ),
                )
            )

            chunks.append(
                {
                    "root": root,
                    "path": path,
                    "display_path": (
                        f"{root}:{path}"
                    ),
                    "extension": (
                        extension
                    ),
                    "chunk_number": (
                        chunk_number
                    ),
                    "text": (
                        chunk_text
                    ),
                    "embedding_text": (
                        embedding_text
                    ),
                    "text_sha256": (
                        calculate_text_hash(
                            chunk_text
                        )
                    ),
                }
            )

    return chunks


def embed_chunks(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate local semantic vectors in batches.

    No external vector service or cloud API is used.
    """

    settings = (
        get_semantic_settings()
    )

    batch_size = (
        settings[
            "batch_size"
        ]
    )

    if batch_size <= 0:
        raise ValueError(
            "Embedding batch_size must "
            "be greater than zero."
        )

    completed: list[
        dict[str, Any]
    ] = []

    total = len(
        chunks
    )

    for start in range(
        0,
        total,
        batch_size,
    ):
        batch = chunks[
            start:
            start + batch_size
        ]

        texts = [
            item[
                "embedding_text"
            ]
            for item in batch
        ]

        vectors = embed_texts(
            texts
        )

        if len(
            vectors
        ) != len(
            batch
        ):
            raise RuntimeError(
                "Embedding vector count "
                "did not match semantic "
                "chunk count."
            )

        for (
            item,
            vector,
        ) in zip(
            batch,
            vectors,
        ):
            stored = dict(
                item
            )

            stored.pop(
                "embedding_text",
                None,
            )

            stored[
                "embedding"
            ] = vector

            completed.append(
                stored
            )

        finished_count = min(
            start + len(
                batch
            ),
            total,
        )

        print(
            f"Embedded "
            f"{finished_count}/"
            f"{total} chunks"
        )

    return completed


def build_semantic_index() -> dict[str, Any]:
    """
    Fully rebuild ZÆNIA's local semantic index.

    Pipeline:

        refresh literal filesystem knowledge
            ↓
        calculate source signature
            ↓
        collect approved contents
            ↓
        chunk contents
            ↓
        embed locally
            ↓
        save semantic vectors locally
    """

    freshness = (
        ensure_index_fresh()
    )

    system_index = (
        load_index()
    )

    source_signature = (
        calculate_semantic_source_signature(
            system_index
        )
    )

    chunks = (
        collect_semantic_chunks(
            system_index
        )
    )

    if not chunks:
        raise RuntimeError(
            "No approved searchable "
            "file content was available "
            "for semantic indexing."
        )

    print(
        "ZÆNIA Semantic Index"
    )

    print()

    print(
        "Approved source files:",
        system_index.get(
            "content_file_count",
            0,
        ),
    )

    print(
        "Semantic chunks:",
        len(
            chunks
        ),
    )

    print()

    semantic_chunks = (
        embed_chunks(
            chunks
        )
    )

    if not semantic_chunks:
        raise RuntimeError(
            "Semantic indexing produced "
            "no chunks."
        )

    vector_dimensions = len(
        semantic_chunks[
            0
        ].get(
            "embedding",
            [],
        )
    )

    embedding_settings = (
        get_embedding_settings()
    )

    output_path = (
        get_semantic_index_path()
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    semantic_index = {
        "version": 2,
        "generated_at": (
            datetime.now().isoformat(
                timespec="seconds"
            )
        ),
        "source_system_index_generated_at": (
            system_index.get(
                "generated_at",
                "",
            )
        ),
        "source_signature": (
            source_signature
        ),
        "source_file_count": (
            system_index.get(
                "file_count",
                0,
            )
        ),
        "source_content_file_count": (
            system_index.get(
                "content_file_count",
                0,
            )
        ),
        "embedding_provider": (
            "ollama_local"
        ),
        "embedding_model": (
            embedding_settings[
                "model"
            ]
        ),
        "embedding_dimensions": (
            vector_dimensions
        ),
        "chunk_count": len(
            semantic_chunks
        ),
        "source_index_was_refreshed": (
            bool(
                freshness.get(
                    "refreshed",
                    False,
                )
            )
        ),
        "chunks": (
            semantic_chunks
        ),
    }

    output_path.write_text(
        json.dumps(
            semantic_index,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return semantic_index


def read_semantic_index_file() -> dict[str, Any]:
    """
    Read the saved semantic index WITHOUT performing any
    freshness checks.

    Internal helpers use this when they need to inspect
    current state without triggering a rebuild.
    """

    path = (
        get_semantic_index_path()
    )

    if not path.exists():
        raise FileNotFoundError(
            "Semantic index does not "
            "exist yet."
        )

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def check_semantic_index_freshness() -> dict[str, Any]:
    """
    Check whether the current semantic vectors still represent
    ZÆNIA's approved local source files.

    This function DOES NOT rebuild the semantic index.
    """

    system_freshness = (
        ensure_index_fresh()
    )

    system_index = (
        load_index()
    )

    current_signature = (
        calculate_semantic_source_signature(
            system_index
        )
    )

    try:
        semantic_index = (
            read_semantic_index_file()
        )

    except FileNotFoundError:
        return {
            "stale": True,
            "reason": (
                "semantic index does not exist"
            ),
            "current_signature": (
                current_signature
            ),
            "stored_signature": "",
            "system_index_refreshed": (
                bool(
                    system_freshness.get(
                        "refreshed",
                        False,
                    )
                )
            ),
        }

    stored_signature = str(
        semantic_index.get(
            "source_signature",
            "",
        )
    )

    if not stored_signature:
        return {
            "stale": True,
            "reason": (
                "semantic index was created "
                "before source signatures "
                "were supported"
            ),
            "current_signature": (
                current_signature
            ),
            "stored_signature": "",
            "system_index_refreshed": (
                bool(
                    system_freshness.get(
                        "refreshed",
                        False,
                    )
                )
            ),
        }

    if (
        stored_signature
        != current_signature
    ):
        return {
            "stale": True,
            "reason": (
                "approved semantic source "
                "knowledge changed"
            ),
            "current_signature": (
                current_signature
            ),
            "stored_signature": (
                stored_signature
            ),
            "system_index_refreshed": (
                bool(
                    system_freshness.get(
                        "refreshed",
                        False,
                    )
                )
            ),
        }

    return {
        "stale": False,
        "reason": (
            "semantic index matches "
            "current approved local knowledge"
        ),
        "current_signature": (
            current_signature
        ),
        "stored_signature": (
            stored_signature
        ),
        "system_index_refreshed": (
            bool(
                system_freshness.get(
                    "refreshed",
                    False,
                )
            )
        ),
    }


def ensure_semantic_index_fresh() -> dict[str, Any]:
    """
    Automatically rebuild semantic knowledge only when needed.

    This is the function used by normal semantic retrieval.

    Result:

        filesystem changes
            ↓
        filesystem index refreshes
            ↓
        semantic signature changes
            ↓
        semantic vectors automatically rebuild
    """

    freshness = (
        check_semantic_index_freshness()
    )

    if not freshness.get(
        "stale",
        True,
    ):
        semantic_index = (
            read_semantic_index_file()
        )

        return {
            **freshness,
            "refreshed": False,
            "index": (
                semantic_index
            ),
        }

    reason = str(
        freshness.get(
            "reason",
            "semantic index was stale",
        )
    )

    semantic_index = (
        build_semantic_index()
    )

    return {
        "stale": False,
        "refreshed": True,
        "reason": (
            reason
        ),
        "current_signature": (
            semantic_index.get(
                "source_signature",
                "",
            )
        ),
        "stored_signature": (
            semantic_index.get(
                "source_signature",
                "",
            )
        ),
        "system_index_refreshed": (
            bool(
                freshness.get(
                    "system_index_refreshed",
                    False,
                )
            )
        ),
        "index": (
            semantic_index
        ),
    }


def load_semantic_index(
    *,
    auto_refresh: bool = True,
) -> dict[str, Any]:
    """
    Load ZÆNIA's semantic index.

    By default, callers receive FRESH semantic knowledge.

    This is important because hybrid_retriever.py already calls:

        load_semantic_index()

    Therefore hybrid retrieval gains automatic freshness
    without needing a second implementation of the same rule.
    """

    if auto_refresh:
        result = (
            ensure_semantic_index_fresh()
        )

        return (
            result[
                "index"
            ]
        )

    return (
        read_semantic_index_file()
    )


def print_freshness_status(
    result: dict[str, Any],
) -> None:
    """
    Human-readable semantic freshness output.
    """

    print()

    if result.get(
        "refreshed",
        False,
    ):
        print(
            "ZÆNIA semantic index: "
            "refreshed"
        )

    elif result.get(
        "stale",
        False,
    ):
        print(
            "ZÆNIA semantic index: "
            "stale"
        )

    else:
        print(
            "ZÆNIA semantic index: "
            "current"
        )

    print(
        "Reason:",
        result.get(
            "reason",
            "",
        ),
    )

    index = (
        result.get(
            "index",
            {},
        )
        or {}
    )

    if index:
        print(
            "Semantic chunks:",
            index.get(
                "chunk_count",
                0,
            ),
        )

        print(
            "Embedding model:",
            index.get(
                "embedding_model",
                "",
            ),
        )


def show_status() -> None:
    """
    Inspect semantic-index status without intentionally
    rebuilding semantic vectors.

    The normal 'ensure' command performs automatic repair.
    """

    try:
        index = (
            load_semantic_index(
                auto_refresh=False,
            )
        )

    except FileNotFoundError:
        print(
            "ZÆNIA semantic index: "
            "not built"
        )

        return

    print(
        "ZÆNIA Semantic Index"
    )

    print()

    print(
        "Generated:",
        index.get(
            "generated_at",
            "",
        ),
    )

    print(
        "Embedding model:",
        index.get(
            "embedding_model",
            "",
        ),
    )

    print(
        "Vector dimensions:",
        index.get(
            "embedding_dimensions",
            0,
        ),
    )

    print(
        "Semantic chunks:",
        index.get(
            "chunk_count",
            0,
        ),
    )

    print(
        "Approved source files:",
        index.get(
            "source_content_file_count",
            0,
        ),
    )

    print(
        "Has source signature:",
        bool(
            index.get(
                "source_signature",
                "",
            )
        ),
    )


@owner_command('files.read')
def main() -> None:
    """
    Local semantic-index command interface.

    Commands:

        build
            Force a full semantic rebuild.

        status
            Inspect the saved index.

        ensure
            Automatically rebuild only if stale.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Build, inspect, or refresh "
            "ZÆNIA's local semantic "
            "filesystem index."
        )
    )

    parser.add_argument(
        "command",
        choices=[
            "build",
            "status",
            "ensure",
        ],
    )

    args = parser.parse_args()

    if args.command == "build":
        index = (
            build_semantic_index()
        )

        print()

        print(
            "ZÆNIA semantic index built."
        )

        print(
            "Chunks:",
            index[
                "chunk_count"
            ],
        )

        print(
            "Vector dimensions:",
            index[
                "embedding_dimensions"
            ],
        )

        print(
            "Embedding model:",
            index[
                "embedding_model"
            ],
        )

    elif args.command == "status":
        show_status()

    elif args.command == "ensure":
        result = (
            ensure_semantic_index_fresh()
        )

        print_freshness_status(
            result
        )


if __name__ == "__main__":
    main()