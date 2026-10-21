"""Collect calendar/reminder/notification source and its ZÆNIA integration points.

Requires Python 3.11+. Never reads live data/secure, .env, non-source
configuration, recordings or credential stores. Original source files are
never modified. Known hard-coded credential literals are redacted in copies;
review those copies before upload and never install them over live source.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import stat
import tempfile
import tokenize
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SOURCE_DIRECTORIES = (
    "core/reminders", "core/calendar_context", "core/google_calendar_sync",
    "core/notifications", "core/notification_service", "core/scheduler",
    "core/foundation", "core/api", "core/brain", "core/conversation",
    "core/voice_listener", "core/conversation_runtime", "core/voice_output",
    "core/briefing", "core/carplay_trigger", "core/carplay_audio", "core/console",
)
PRIMARY_DIRECTORIES = ("core/reminders", "core/calendar_context", "core/google_calendar_sync")
ROOT_FILES = (
    "main.py", "start.py", "foundation_main.py", "requirements.txt",
    "requirements-module1.txt", "core/db.py", "core/utils.py", "core/init.py",
    "test_carplay_update.py",
)
IGNORED_DIRECTORIES = {
    "data", "secure", "credentials", "secrets", "logs", "models", "recordings",
    "node_modules", "venv", "env", "__pycache__", "site-packages",
}
SECRET_FILE = re.compile(
    r"^(?:secrets?|credentials?|tokens?|passwords?|private_keys?)(?:[._-]|$)",
    re.IGNORECASE,
)
SENSITIVE_NAME = re.compile(
    r"passkey|passphrase|password|secret|credential|api_?key|access_?token|"
    r"refresh_?token|auth_?token|private_?key|client_?key|voice_?phrase|"
    r"auth_?phrase|authorization|bearer|ics_?url|ical_?url|calendar_?url|feed_?url|webhook_?url|(?:^|_)token$",
    re.IGNORECASE,
)
NONSECRET_SUFFIXES = (
    "_header", "_header_name", "_path", "_file", "_filename", "_directory",
    "_dir", "_env", "_env_name", "_env_var", "_length", "_size", "_name",
)
KNOWN_CREDENTIAL = re.compile(
    r"sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{15,}|"
    r"github_pat_[A-Za-z0-9_]{15,}|xox[baprs]-[A-Za-z0-9-]{12,}|"
    r"AKIA[A-Z0-9]{16}|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|"
    r"https?://[^/\s:]+:[^/@\s]+@|"
    r"https?://[^\s\"']*/calendar/ical/[^\s\"']+|"
    r"https?://[^\s\"']*/private-[^\s\"']+\.ics|"
    r"[?&](?:api_?key|access_?token|auth_?token|token|secret|password)=[^\s&\"']+",
    re.IGNORECASE,
)
REDACTED = "[REDACTED FOR SOURCE REVIEW]"
MAX_SOURCE_BYTES = 2 * 1024 * 1024


def is_link(path: Path) -> bool:
    """Exclude Windows junctions/reparse points as well as symbolic links."""
    if path.is_symlink():
        return True
    return bool(getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def sensitive_name(name: str) -> bool:
    return bool(SENSITIVE_NAME.search(name)) and not name.lower().endswith(
        NONSECRET_SUFFIXES
    )


def sanitize_python(source: str) -> tuple[str, int]:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line))

    def ast_position(row: int, byte_column: int) -> int:
        # AST columns are UTF-8 byte offsets, unlike tokenize columns.
        prefix = lines[row - 1].encode("utf-8")[:byte_column].decode("utf-8")
        return line_starts[row - 1] + len(prefix)

    replacements: dict[tuple[int, int], str] = {}

    def redact_literal(node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            value = REDACTED.encode("ascii") if isinstance(node.value, bytes) else REDACTED
            start = ast_position(node.lineno, node.col_offset)
            end = ast_position(node.end_lineno, node.end_col_offset)
            # Keep approximate line layout for review of multiline literals.
            rendered = repr(value)
            rendered += "\n" * max(0, node.end_lineno - node.lineno)
            if node.end_lineno > node.lineno:
                rendered = "(" + rendered + ")"
            replacements[(start, end)] = rendered

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [
                part.id if isinstance(part, ast.Name) else part.attr
                for target in targets
                for part in ast.walk(target)
                if isinstance(part, (ast.Name, ast.Attribute))
            ]
            if any(sensitive_name(name) for name in names):
                redact_literal(node.value)
        elif isinstance(node, ast.keyword):
            if node.arg and sensitive_name(node.arg):
                redact_literal(node.value)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if sensitive_name(key.value):
                        redact_literal(value)
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            text = node.value.decode("utf-8", errors="replace") if isinstance(node.value, bytes) else node.value
            if KNOWN_CREDENTIAL.search(text):
                redact_literal(node)

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            start = line_starts[token.start[0] - 1] + token.start[1]
            end = line_starts[token.end[0] - 1] + token.end[1]
            replacements[(start, end)] = "# [comment omitted from source review]"

    # Skip comment replacements already inside a redacted multiline literal.
    edits = []
    for span, value in replacements.items():
        if any(other[0] <= span[0] and span[1] <= other[1] and span != other
               for other in replacements):
            continue
        edits.append((span, value))
    output = source
    for (start, end), value in sorted(edits, reverse=True):
        output = output[:start] + value + output[end:]
    ast.parse(output)
    return output, len(edits)


def iter_python_files(directory: Path):
    if not directory.is_dir() or is_link(directory):
        return
    for current, subdirectories, files in os.walk(directory, followlinks=False):
        subdirectories[:] = [
            name for name in subdirectories
            if not name.startswith(".")
            and name.lower() not in IGNORED_DIRECTORIES
            and not is_link(Path(current) / name)
        ]
        for name in sorted(files):
            path = Path(current) / name
            if path.suffix.lower() == ".py" and not is_link(path):
                if not SECRET_FILE.search(name):
                    yield path


def export_source(project_root: Path, output: Path) -> dict:
    for part in (project_root.absolute(), *project_root.absolute().parents):
        if is_link(part):
            raise ValueError("Select the project directory without links or junctions.")
    root = project_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("The project root must be a directory.")
    if not (root / "core").is_dir() or not any((root / name).is_dir() for name in PRIMARY_DIRECTORIES):
        raise ValueError("Select the ZÆNIA project containing its existing calendar or reminder module.")
    paths = []
    missing = []
    for relative in SOURCE_DIRECTORIES:
        directory = root / relative
        if directory.is_dir() and not is_link(directory):
            paths.extend(iter_python_files(directory))
        else:
            missing.append(relative)
    for relative in ROOT_FILES:
        path = root / relative
        if path.is_file() and not is_link(path):
            if any(is_link(part) for part in path.parents if part != root and part.is_relative_to(root)):
                continue
            paths.append(path)
    paths = sorted(set(paths))
    if not paths:
        raise ValueError(
            "No selected source files found. Check --project-root."
        )
    selected = []
    for path in paths:
        if not path.resolve().is_relative_to(root):
            raise ValueError("A selected source path leaves the project root.")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("A selected source file exceeds the 2 MiB limit.")
        if path.suffix.lower() == ".py":
            with tokenize.open(path) as handle:
                text = handle.read()
            text, count = sanitize_python(text)
        else:
            text = path.read_text(encoding="utf-8-sig")
            text = KNOWN_CREDENTIAL.sub(REDACTED, text)
            count = 0
        selected.append((path.relative_to(root).as_posix(), text, count))

    inventory = sorted(
        path.relative_to(root).as_posix()
        for path in iter_python_files(root / "core")
    )
    inventory.extend(
        sorted(path.name for path in root.glob("*.py") if not is_link(path)
               and not SECRET_FILE.search(path.name))
    )
    manifest = {
        "artifact": "ZAENIA Module 2 sanitized source review",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "not_for_installation": True,
        "selected_directories": list(SOURCE_DIRECTORIES),
        "missing_directories": missing,
        "review_focus": [
            "Existing reminder storage, recurrence, delivery and restart behavior",
            "Calendar synchronization, offline cache, timezones and event filtering",
            "Notification delivery through the current local voice and CarPlay services",
            "Rules/authentication gate, attention requirements and trusted action handlers",
        ],
        "files": [
            {"path": name, "redactions_or_omitted_comments": count}
            for name, _, count in selected
        ],
        "limits": [
            "Only source files are selected; live credential stores are excluded.",
            "Hard-coded credential redaction is best effort, not a guarantee.",
            "Review copies have been sanitized and must not replace live source.",
        ],
    }
    output = output.absolute()
    for part in (output, *output.parents):
        if part.exists() or part.is_symlink():
            if is_link(part):
                raise ValueError("The output must not use links or junctions.")
    output = output.resolve()
    if output in {path.resolve() for path in paths}:
        raise ValueError("The output must not replace a selected source file.")
    if output.suffix.lower() != ".zip":
        raise ValueError("The output filename must end in .zip.")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=output.parent, prefix=".zaenia-module2-", suffix=".zip"
    )
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, text, _ in selected:
                archive.writestr(name, text.encode("utf-8"))
            archive.writestr(
                "SOURCE_REVIEW_MANIFEST.json",
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
            archive.writestr(
                "PYTHON_SOURCE_PATHS.txt",
                "\n".join(sorted(set(inventory))) + "\n",
            )
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root", type=Path, default=Path(r"C:\Projects\ZAENIA")
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.project_root / "ZAENIA_Module2_Source_Review.zip"
    try:
        manifest = export_source(args.project_root, output)
    except (OSError, ValueError, SyntaxError, UnicodeError, tokenize.TokenError) as error:
        print("Source export failed:", error)
        return 1
    print("Created:", output.resolve())
    print("Source files:", len(manifest["files"]))
    if manifest["missing_directories"]:
        print("Optional module folders not present:", ", ".join(manifest["missing_directories"]))
    print("Original files unchanged. Review and upload the generated ZIP.")
    print("Do not install the sanitized review copies over your project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

