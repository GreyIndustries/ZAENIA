from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
import fnmatch
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "core"
    / "brain"
    / "system_awareness_config.yaml"
)


def load_config() -> dict[str, Any]:
    """
    Load ZÆNIA's local system-awareness policy.

    This configuration controls:
        - which directories ZÆNIA may inspect
        - which files are ignored
        - which files may have their contents indexed
        - which areas are protected
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing system awareness config: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file) or {}

    return (
        config.get(
            "system_awareness",
            {},
        )
        or {}
    )


def resolve_project_path(
    value: str,
) -> Path:
    """
    Resolve a configured path.

    Relative paths are based from:
        C:\\Projects\\ZAENIA
    """

    path = Path(value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def normalize_relative_path(
    path: Path | str,
) -> str:
    """
    Normalize paths into forward-slash form.

    Windows normally uses:
        core\\brain\\file.py

    ZÆNIA stores paths as:
        core/brain/file.py

    This makes matching predictable across platforms.
    """

    return (
        str(path)
        .replace("\\", "/")
        .strip("/")
    )


def matches_any_glob(
    relative_path: str,
    patterns: list[str],
) -> bool:
    """
    Check a path against wildcard patterns.

    Example:

        .venv*

    matches:

        .venv
        .venv_backup
        .venv_broken_20260829
    """

    normalized = (
        normalize_relative_path(
            relative_path
        )
        .lower()
    )

    for pattern in patterns:
        normalized_pattern = (
            normalize_relative_path(
                pattern
            )
            .lower()
        )

        if fnmatch.fnmatch(
            normalized,
            normalized_pattern,
        ):
            return True

    return False


def directory_is_ignored(
    relative_path: str,
    ignored_directories: list[str],
) -> bool:
    """
    Determine whether a directory is forbidden from indexing.

    This supports both:

        exact paths:
            data/models

        wildcard names:
            .venv*

    Wildcard rules are also checked against each individual
    directory component.

    Example:

        tools/.venv_backup/Lib

    is ignored because:

        .venv_backup

    matches:

        .venv*
    """

    normalized = (
        normalize_relative_path(
            relative_path
        )
        .lower()
    )

    if not normalized:
        return False

    path_parts = normalized.split("/")

    for ignored in ignored_directories:
        pattern = (
            normalize_relative_path(
                ignored
            )
            .lower()
        )

        if not pattern:
            continue

        # [comment omitted from source review]
        if fnmatch.fnmatch(
            normalized,
            pattern,
        ):
            return True

        contains_wildcard = any(
            character in pattern
            for character in (
                "*",
                "?",
                "[",
            )
        )

        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        if not contains_wildcard:
            if normalized.startswith(
                pattern + "/"
            ):
                return True

        # [comment omitted from source review]
        # [comment omitted from source review]
        for part in path_parts:
            if fnmatch.fnmatch(
                part,
                pattern,
            ):
                return True

    return False


def calculate_sha256(
    path: Path,
) -> str:
    """
    Generate a SHA-256 fingerprint.

    A fingerprint lets ZÆNIA determine whether the actual
    contents of a file changed.

    Reading occurs in 1 MB chunks so large files do not need
    to be loaded completely into RAM.
    """

    digest = hashlib.sha256()

    with path.open(
        "rb",
    ) as file:
        while True:
            block = file.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def read_text_content(
    path: Path,
    max_file_bytes: int,
) -> str:
    """
    Read an approved text file into the searchable index.

    Files larger than max_file_bytes remain known to ZÆNIA,
    but their full contents are not copied into this index.
    """

    try:
        size = path.stat().st_size

    except OSError:
        return ""

    if size > max_file_bytes:
        return ""

    try:
        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except OSError:
        return ""


def should_skip_file(
    *,
    path: Path,
    relative_text: str,
    config: dict[str, Any],
) -> bool:
    """
    Determine whether one file must be completely excluded.

    This is different from metadata-only files.

    Excluded files do not appear in ZÆNIA's index at all.
    """

    ignored_files = {
        str(item).lower()
        for item in config.get(
            "ignore_files",
            [],
        )
    }

    if path.name.lower() in ignored_files:
        return True

    ignore_globs = [
        str(item)
        for item in config.get(
            "ignore_globs",
            [],
        )
    ]

    if matches_any_glob(
        relative_text,
        ignore_globs,
    ):
        return True

    return False


def build_file_record(
    *,
    path: Path,
    root_path: Path,
    root_label: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Convert one local file into a system-awareness record.

    A record contains things such as:

        path
        type
        size
        modified time
        SHA-256 fingerprint

    Approved text files may additionally contain searchable
    content.
    """

    try:
        relative = path.relative_to(
            root_path
        )

    except ValueError:
        return None

    relative_text = (
        normalize_relative_path(
            relative
        )
    )

    if should_skip_file(
        path=path,
        relative_text=relative_text,
        config=config,
    ):
        return None

    indexing = (
        config.get(
            "indexing",
            {},
        )
        or {}
    )

    text_extensions = {
        str(extension).lower()
        for extension in indexing.get(
            "text_extensions",
            [],
        )
    }

    include_content = bool(
        indexing.get(
            "include_file_content",
            True,
        )
    )

    max_file_bytes = int(
        indexing.get(
            "max_file_bytes",
            262144,
        )
    )

    metadata_only_patterns = [
        str(item)
        for item in config.get(
            "metadata_only_globs",
            [],
        )
    ]

    metadata_only = matches_any_glob(
        relative_text,
        metadata_only_patterns,
    )

    try:
        stat = path.stat()

    except OSError:
        return None

    modified = datetime.fromtimestamp(
        stat.st_mtime
    ).isoformat(
        timespec="seconds"
    )

    try:
        sha256 = calculate_sha256(
            path
        )

    except (
        OSError,
        PermissionError,
    ):
        sha256 = ""

    record: dict[str, Any] = {
        "root": root_label,
        "path": relative_text,
        "display_path": (
            f"{root_label}:{relative_text}"
        ),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": modified,
        "sha256": sha256,
        "content_indexed": False,
    }

    if (
        include_content
        and not metadata_only
        and path.suffix.lower()
        in text_extensions
    ):
        content = read_text_content(
            path,
            max_file_bytes,
        )

        if content:
            record["content"] = content

            record["content_indexed"] = True

    return record


def prune_directories(
    *,
    current_path: Path,
    root_path: Path,
    directory_names: list[str],
    ignored_directories: list[str],
) -> list[str]:
    """
    Decide which child directories os.walk is allowed to enter.

    This is the key optimization.

    os.walk allows us to modify its 'dirs' list before it
    descends into those folders.

    So if ZÆNIA sees:

        .venv_broken_20260829

    and the policy contains:

        .venv*

    the directory is removed before Python ever walks inside it.
    """

    allowed: list[str] = []

    for directory_name in directory_names:
        child_path = (
            current_path
            / directory_name
        )

        try:
            relative_child = (
                child_path.relative_to(
                    root_path
                )
            )

        except ValueError:
            continue

        relative_text = (
            normalize_relative_path(
                relative_child
            )
        )

        if directory_is_ignored(
            relative_text,
            ignored_directories,
        ):
            continue

        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        try:
            if child_path.is_symlink():
                continue

        except OSError:
            continue

        allowed.append(
            directory_name
        )

    return allowed


def build_index() -> dict[str, Any]:
    """
    Build a clean local index of all approved roots.

    The traversal is deliberately performed with os.walk rather
    than Path.rglob.

    Why?

    os.walk lets ZÆNIA remove forbidden directories BEFORE
    entering them.
    """

    config = load_config()

    index_path = resolve_project_path(
        str(
            config.get(
                "index_file",
                "data/system_awareness/system_index.json",
            )
        )
    )

    index_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    ignored_directories = [
        str(item)
        for item in config.get(
            "ignore_directories",
            [],
        )
    ]

    records: list[
        dict[str, Any]
    ] = []

    indexed_roots: list[
        dict[str, str]
    ] = []

    skipped_directory_count = 0

    for root_config in config.get(
        "roots",
        [],
    ):
        label = str(
            root_config.get(
                "label",
                "root",
            )
        )

        root_path = resolve_project_path(
            str(
                root_config.get(
                    "path",
                    PROJECT_ROOT,
                )
            )
        )

        if not root_path.exists():
            print(
                "Warning: root does not exist: "
                f"{root_path}"
            )
            continue

        if not root_path.is_dir():
            print(
                "Warning: root is not a directory: "
                f"{root_path}"
            )
            continue

        indexed_roots.append(
            {
                "label": label,
                "path": str(
                    root_path
                ),
            }
        )

        for (
            current_root,
            directory_names,
            file_names,
        ) in os.walk(
            root_path,
            topdown=True,
            followlinks=False,
        ):
            current_path = Path(
                current_root
            )

            original_directory_count = len(
                directory_names
            )

            allowed_directories = prune_directories(
                current_path=current_path,
                root_path=root_path,
                directory_names=directory_names,
                ignored_directories=ignored_directories,
            )

            skipped_directory_count += (
                original_directory_count
                - len(
                    allowed_directories
                )
            )

            # [comment omitted from source review]
            # [comment omitted from source review]
            # [comment omitted from source review]
            # [comment omitted from source review]
            directory_names[:] = (
                allowed_directories
            )

            for file_name in file_names:
                path = (
                    current_path
                    / file_name
                )

                # [comment omitted from source review]
                # [comment omitted from source review]
                try:
                    if path.is_symlink():
                        continue

                except OSError:
                    continue

                try:
                    record = build_file_record(
                        path=path,
                        root_path=root_path,
                        root_label=label,
                        config=config,
                    )

                except KeyboardInterrupt:
                    print()
                    print(
                        "Index build cancelled."
                    )

                    raise

                except (
                    OSError,
                    PermissionError,
                ):
                    continue

                if record is not None:
                    records.append(
                        record
                    )

    records.sort(
        key=lambda item: (
            item["root"],
            item["path"].lower(),
        )
    )

    index = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "project_root": str(
            PROJECT_ROOT
        ),
        "roots": indexed_roots,
        "file_count": len(
            records
        ),
        "content_file_count": sum(
            1
            for record in records
            if record.get(
                "content_indexed"
            )
        ),
        "skipped_directory_count": (
            skipped_directory_count
        ),
        "files": records,
    }

    # [comment omitted from source review]
    # [comment omitted from source review]
    # [comment omitted from source review]
    # [comment omitted from source review]
    # [comment omitted from source review]
    index_path.write_text(
        json.dumps(
            index,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return index


def load_index() -> dict[str, Any]:
    """
    Load the last successfully generated local index.
    """

    config = load_config()

    index_path = resolve_project_path(
        str(
            config.get(
                "index_file",
                "data/system_awareness/system_index.json",
            )
        )
    )

    if not index_path.exists():
        raise FileNotFoundError(
            "System index has not been built yet."
        )

    return json.loads(
        index_path.read_text(
            encoding="utf-8",
        )
    )


def show_status() -> None:
    """
    Display current filesystem-awareness status.
    """

    try:
        index = load_index()

    except FileNotFoundError:
        print(
            "ZÆNIA system index: not built"
        )

        return

    print(
        "ZÆNIA Local System Index"
    )

    print(
        "Generated: "
        f"{index.get('generated_at')}"
    )

    print(
        "Files known: "
        f"{index.get('file_count', 0)}"
    )

    print(
        "Files with searchable content: "
        f"{index.get('content_file_count', 0)}"
    )

    print(
        "Ignored directory branches: "
        f"{index.get('skipped_directory_count', 0)}"
    )

    print(
        "Roots:"
    )

    for root in index.get(
        "roots",
        [],
    ):
        print(
            f"  - "
            f"{root.get('label')}: "
            f"{root.get('path')}"
        )


@owner_command('files.read')
def main() -> None:
    """
    Command-line interface.

    Supported commands:

        build
        status
    """

    parser = argparse.ArgumentParser(
        description=(
            "ZÆNIA local filesystem awareness index."
        )
    )

    parser.add_argument(
        "command",
        choices=[
            "build",
            "status",
        ],
    )

    args = parser.parse_args()

    if args.command == "build":
        index = build_index()

        print(
            "ZÆNIA local system index built."
        )

        print(
            "Files known: "
            f"{index['file_count']}"
        )

        print(
            "Files with searchable content: "
            f"{index['content_file_count']}"
        )

        print(
            "Ignored directory branches: "
            f"{index['skipped_directory_count']}"
        )

    elif args.command == "status":
        show_status()


if __name__ == "__main__":
    main()