from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core.brain.system_index import (
    build_index,
    load_config,
    load_index,
    normalize_relative_path,
    prune_directories,
    resolve_project_path,
    should_skip_file,
)


def collect_current_inventory() -> dict[str, dict[str, Any]]:
    """
    Scan ZÆNIA's approved filesystem roots and collect
    lightweight metadata about every allowed file.

    This does NOT read file contents.

    It only records enough information to determine whether
    the existing search index is stale.

    Inventory key format:

        root_label:relative/path/to/file.py
    """

    config = load_config()

    ignored_directories = [
        str(item)
        for item in config.get(
            "ignore_directories",
            [],
        )
    ]

    inventory: dict[
        str,
        dict[str, Any],
    ] = {}

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
                    "",
                )
            )
        )

        if not root_path.exists():
            continue

        if not root_path.is_dir():
            continue

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

            allowed_directories = (
                prune_directories(
                    current_path=current_path,
                    root_path=root_path,
                    directory_names=directory_names,
                    ignored_directories=ignored_directories,
                )
            )

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

                try:
                    if path.is_symlink():
                        continue

                except OSError:
                    continue

                try:
                    relative_path = (
                        path.relative_to(
                            root_path
                        )
                    )

                except ValueError:
                    continue

                relative_text = (
                    normalize_relative_path(
                        relative_path
                    )
                )

                if should_skip_file(
                    path=path,
                    relative_text=relative_text,
                    config=config,
                ):
                    continue

                try:
                    stat = path.stat()

                except (
                    OSError,
                    PermissionError,
                ):
                    continue

                modified = (
                    datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(
                        timespec="seconds"
                    )
                )

                key = (
                    f"{label}:"
                    f"{relative_text}"
                )

                inventory[key] = {
                    "root": label,
                    "path": relative_text,
                    "size_bytes": stat.st_size,
                    "modified": modified,
                }

    return inventory


def collect_index_inventory(
    index: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Convert the last saved search index into the same
    lightweight structure used by the live filesystem scan.
    """

    inventory: dict[
        str,
        dict[str, Any],
    ] = {}

    for record in index.get(
        "files",
        [],
    ):
        root = str(
            record.get(
                "root",
                "",
            )
        )

        path = str(
            record.get(
                "path",
                "",
            )
        )

        if not root or not path:
            continue

        key = (
            f"{root}:"
            f"{path}"
        )

        inventory[key] = {
            "root": root,
            "path": path,
            "size_bytes": int(
                record.get(
                    "size_bytes",
                    0,
                )
            ),
            "modified": str(
                record.get(
                    "modified",
                    "",
                )
            ),
        }

    return inventory


def compare_inventory(
    current: dict[str, dict[str, Any]],
    indexed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare live filesystem metadata with the saved index.

    Detects:

        new files
        deleted files
        changed file sizes
        changed modification times
    """

    current_paths = set(
        current.keys()
    )

    indexed_paths = set(
        indexed.keys()
    )

    new_files = sorted(
        current_paths
        - indexed_paths
    )

    deleted_files = sorted(
        indexed_paths
        - current_paths
    )

    changed_files: list[str] = []

    shared_paths = (
        current_paths
        & indexed_paths
    )

    for key in shared_paths:
        current_record = current[
            key
        ]

        indexed_record = indexed[
            key
        ]

        if (
            current_record[
                "size_bytes"
            ]
            != indexed_record[
                "size_bytes"
            ]
        ):
            changed_files.append(
                key
            )

            continue

        if (
            current_record[
                "modified"
            ]
            != indexed_record[
                "modified"
            ]
        ):
            changed_files.append(
                key
            )

    changed_files.sort()

    stale = bool(
        new_files
        or deleted_files
        or changed_files
    )

    return {
        "stale": stale,
        "new_files": new_files,
        "deleted_files": deleted_files,
        "changed_files": changed_files,
    }


def check_index_freshness() -> dict[str, Any]:
    """
    Determine whether ZÆNIA's saved filesystem index still
    represents her actual local project.

    This function does not rebuild anything.
    """

    try:
        index = load_index()

    except FileNotFoundError:
        return {
            "stale": True,
            "reason": (
                "system index does not exist"
            ),
            "new_files": [],
            "deleted_files": [],
            "changed_files": [],
        }

    current_inventory = (
        collect_current_inventory()
    )

    indexed_inventory = (
        collect_index_inventory(
            index
        )
    )

    comparison = compare_inventory(
        current_inventory,
        indexed_inventory,
    )

    if comparison["new_files"]:
        reason = (
            "new approved project files detected"
        )

    elif comparison["deleted_files"]:
        reason = (
            "indexed project files were removed"
        )

    elif comparison["changed_files"]:
        reason = (
            "indexed project files changed"
        )

    else:
        reason = (
            "index matches current local files"
        )

    return {
        **comparison,
        "reason": reason,
        "current_file_count": len(
            current_inventory
        ),
        "indexed_file_count": len(
            indexed_inventory
        ),
    }


def ensure_index_fresh() -> dict[str, Any]:
    """
    Make sure the local system index is current.

    If nothing changed:
        keep the existing index.

    If something changed:
        rebuild the index locally.

    No Internet connection is involved.
    """

    freshness = (
        check_index_freshness()
    )

    if not freshness.get(
        "stale",
        True,
    ):
        return {
            **freshness,
            "refreshed": False,
        }

    original_reason = str(
        freshness.get(
            "reason",
            "index was stale",
        )
    )

    new_files = list(
        freshness.get(
            "new_files",
            [],
        )
    )

    deleted_files = list(
        freshness.get(
            "deleted_files",
            [],
        )
    )

    changed_files = list(
        freshness.get(
            "changed_files",
            [],
        )
    )

    rebuilt_index = build_index()

    return {
        "stale": False,
        "refreshed": True,
        "reason": original_reason,
        "new_files": new_files,
        "deleted_files": deleted_files,
        "changed_files": changed_files,
        "current_file_count": (
            rebuilt_index.get(
                "file_count",
                0,
            )
        ),
        "indexed_file_count": (
            rebuilt_index.get(
                "file_count",
                0,
            )
        ),
    }


def print_status(
    result: dict[str, Any],
) -> None:
    """
    Development-friendly freshness status.
    """

    if result.get(
        "refreshed",
        False,
    ):
        print(
            "ZÆNIA system index: refreshed"
        )

    elif result.get(
        "stale",
        False,
    ):
        print(
            "ZÆNIA system index: stale"
        )

    else:
        print(
            "ZÆNIA system index: current"
        )

    print(
        "Reason:",
        result.get(
            "reason",
            "",
        ),
    )

    print(
        "Current files:",
        result.get(
            "current_file_count",
            0,
        ),
    )

    new_files = (
        result.get(
            "new_files",
            [],
        )
        or []
    )

    deleted_files = (
        result.get(
            "deleted_files",
            [],
        )
        or []
    )

    changed_files = (
        result.get(
            "changed_files",
            [],
        )
        or []
    )

    if new_files:
        print(
            "New files:",
            len(
                new_files
            ),
        )

    if deleted_files:
        print(
            "Deleted files:",
            len(
                deleted_files
            ),
        )

    if changed_files:
        print(
            "Changed files:",
            len(
                changed_files
            ),
        )


@owner_command('files.read')
def main() -> None:
    """
    Local development interface.

    Commands:

        status
            Check freshness without changing anything.

        ensure
            Rebuild automatically only when needed.
    """

    parser = argparse.ArgumentParser(
        description=(
            "ZÆNIA local system-index freshness manager."
        )
    )

    parser.add_argument(
        "command",
        choices=[
            "status",
            "ensure",
        ],
    )

    args = parser.parse_args()

    if args.command == "status":
        result = (
            check_index_freshness()
        )

        result["refreshed"] = False

        print_status(
            result
        )

    elif args.command == "ensure":
        result = (
            ensure_index_fresh()
        )

        print_status(
            result
        )


if __name__ == "__main__":
    main()