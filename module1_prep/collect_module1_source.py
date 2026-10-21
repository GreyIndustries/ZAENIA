"""Create a sanitized, source-only archive for ZÆNIA Module 1 review.

Requires Python 3.11+. Never reads data/secure, .env, configuration files,
recordings or credential stores. Original source files are never modified.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import tempfile
import tokenize
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SOURCE_DIRECTORIES = ("core/foundation", "core/api")
ROOT_FILES = ("main.py", "start.py", "foundation_main.py", "requirements.txt")
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
    r"auth_?phrase|(?:^|_)token$",
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
    r"https?://[^/\s:]+:[^/@\s]+@",
)
REDACTED = "[REDACTED FOR SOURCE REVIEW]"
MAX_SOURCE_BYTES = 2 * 1024 * 1024


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
    if not directory.is_dir() or directory.is_symlink():
        return
    for current, subdirectories, files in os.walk(directory, followlinks=False):
        subdirectories[:] = [
            name for name in subdirectories
            if not name.startswith(".")
            and name.lower() not in IGNORED_DIRECTORIES
            and not (Path(current) / name).is_symlink()
        ]
        for name in sorted(files):
            path = Path(current) / name
            if path.suffix.lower() == ".py" and not path.is_symlink():
                if not SECRET_FILE.search(name):
                    yield path


def export_source(project_root: Path, output: Path) -> dict:
    root = project_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("The project root must be a directory.")
    paths = []
    missing = []
    for relative in SOURCE_DIRECTORIES:
        directory = root / relative
        if directory.is_dir() and not directory.is_symlink():
            paths.extend(iter_python_files(directory))
        else:
            missing.append(relative)
    for relative in ROOT_FILES:
        path = root / relative
        if path.is_file() and not path.is_symlink():
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
        sorted(path.name for path in root.glob("*.py") if not path.is_symlink()
               and not SECRET_FILE.search(path.name))
    )
    manifest = {
        "artifact": "ZAENIA Module 1 sanitized source review",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "not_for_installation": True,
        "selected_directories": list(SOURCE_DIRECTORIES),
        "missing_directories": missing,
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
    output = output.resolve()
    if output in {path.resolve() for path in paths}:
        raise ValueError("The output must not replace a selected source file.")
    if output.suffix.lower() != ".zip":
        raise ValueError("The output filename must end in .zip.")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=output.parent, prefix=".zaenia-module1-", suffix=".zip"
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
    output = args.output or args.project_root / "ZAENIA_Module1_Source_Review.zip"
    try:
        manifest = export_source(args.project_root, output)
    except (OSError, ValueError, SyntaxError, UnicodeError, tokenize.TokenError) as error:
        print("Source export failed:", error)
        return 1
    print("Created:", output.resolve())
    print("Source files:", len(manifest["files"]))
    if manifest["missing_directories"]:
        print("Not found:", ", ".join(manifest["missing_directories"]))
    print("Original files unchanged. Review and upload the generated ZIP.")
    print("Do not install the sanitized review copies over your project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

