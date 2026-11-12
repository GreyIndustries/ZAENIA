"""System file tools for the ZÆNIA UI.

Token clients may read ZÆNIA's own code and config inside an allowlist and
propose edits. A proposal changes nothing until it is approved in the desktop
app, which holds the paired desktop approval key. Edits saved in the desktop
app apply directly with that key. Every applied change is backed up first.

Never reachable here: data/ (vaults, memory, sessions, tokens), virtual
environments, node_modules, build output, backups, binaries and anything that
looks like a secret. Security code is readable but not editable from the UI.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from core.foundation.security.io import atomic_write, file_lock, reject_link

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DATA_DIR = PROJECT_ROOT / "data" / "ui"

ALLOWED_DIRS = ("core", "scripts", "docs", "desktop/src", "desktop/src-tauri/src")
ALLOWED_FILES = (
    "desktop/index.html", "desktop/package.json", "desktop/vite.config.ts", "desktop/tsconfig.json",
    "desktop/src-tauri/tauri.conf.json", "desktop/src-tauri/Cargo.toml",
)
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".css", ".html", ".json", ".yaml", ".yml", ".md",
    ".txt", ".toml", ".ps1", ".bat", ".cmd", ".rs", ".cfg", ".ini", ".csv", ".sql", ".sh",
}
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "dist-web", "target", "data",
             "secure", "ui-backups", ".pytest_cache", ".mypy_cache"}
SKIP_DIR_PREFIXES = ("_backup", "ui-backup", "src backup")
SECRET_WORDS = ("secret", "credential", "passkey", "password", "token", "ics_url", "id_rsa", ".env", "private")
# Readable, but changed only in a code editor at the PC.
PROTECTED = ("core/foundation", "core/voice_security", "core/api/auth.py", "core/api/brief_gate.py",
             "core/api/ui_files.py", "core/api/desktop_key.py", "core/api/phone_app.py",
             # Modules that decide which operation each request needs.
             "core/api/server.py", "core/api/ui_routes.py", "core/api/assistant_routes.py", "core/api/chat_routes.py",
             "core/api/operator_routes.py", "core/api/platform_routes.py", "core/api/mobile_auth.py",
             "core/assistant_platform/capabilities.py")
READ_LIMIT = 1024 * 1024
EDIT_LIMIT = 512 * 1024
MAX_PENDING = 50
SCAN_LIMIT = 20000


class FileToolError(ValueError):
    """A request the file tools refuse; the message is safe to show."""


class FileNotAvailable(LookupError):
    pass


class FileConflict(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _skip_dir(name: str) -> bool:
    lowered = name.lower()
    return lowered in SKIP_DIRS or lowered.startswith(SKIP_DIR_PREFIXES) or lowered.startswith(".")


def _secret_name(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in SECRET_WORDS)


def is_protected(rel: str) -> bool:
    # Windows paths ignore case, so "Core/Foundation/..." is the same file as
    # "core/foundation/...": compare case-insensitively, and by the real path.
    lowered = rel.lower()
    if any(lowered == item or lowered.startswith(item + "/") for item in PROTECTED):
        return True
    try:
        target = PROJECT_ROOT.joinpath(*rel.split("/")).resolve()
        return any(target == (root := PROJECT_ROOT.joinpath(*item.split("/")).resolve()) or root in target.parents
                   for item in PROTECTED)
    except (OSError, ValueError):
        return True


def _in_allowlist(rel: str) -> bool:
    return rel in ALLOWED_FILES or any(rel == d or rel.startswith(d + "/") for d in ALLOWED_DIRS)


def normalize(rel: Any) -> str:
    """A clean project-relative path with forward slashes, or an error."""
    if not isinstance(rel, str) or not rel.strip() or len(rel) > 400 or "\x00" in rel:
        raise FileToolError("Choose a file.")
    text = rel.strip().replace("\\", "/").strip("/")
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts) or ":" in text:
        raise FileToolError("Use a path inside the ZÆNIA project.")
    return pure.as_posix()


def resolve_file(rel: Any) -> tuple[str, Path]:
    clean = normalize(rel)
    parts = clean.split("/")
    if not _in_allowlist(clean) or any(_skip_dir(part) for part in parts[:-1]):
        raise FileToolError("That location isn't open to the file tools.")
    name = parts[-1]
    if _secret_name(name) or Path(name).suffix.lower() not in TEXT_SUFFIXES:
        raise FileToolError("That file isn't open to the file tools.")
    path = PROJECT_ROOT.joinpath(*parts)
    reject_link(path)
    if PROJECT_ROOT.resolve() not in path.resolve().parents:
        raise FileToolError("Use a path inside the ZÆNIA project.")
    return clean, path


def resolve_dir(rel: Any) -> tuple[str, Path]:
    if rel in (None, ""):
        return "", PROJECT_ROOT
    clean = normalize(rel)
    if any(_skip_dir(part) for part in clean.split("/")):
        raise FileToolError("That folder isn't open to the file tools.")
    is_ancestor = any(item.startswith(clean + "/") for item in ALLOWED_DIRS + ALLOWED_FILES)
    if not (is_ancestor or any(clean == d or clean.startswith(d + "/") for d in ALLOWED_DIRS)):
        raise FileToolError("That folder isn't open to the file tools.")
    path = PROJECT_ROOT.joinpath(*clean.split("/"))
    reject_link(path)
    if not path.is_dir():
        raise FileNotAvailable(clean)
    return clean, path


def _entry(rel: str, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": rel, "name": path.name, "kind": "file", "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        "editable": not is_protected(rel) and stat.st_size <= EDIT_LIMIT,
    }


def _visible_file(rel: str, name: str) -> bool:
    return (_in_allowlist(rel) and not _secret_name(name) and Path(name).suffix.lower() in TEXT_SUFFIXES)


def list_dir(rel: Any) -> dict[str, Any]:
    clean, path = resolve_dir(rel)
    entries: list[dict[str, Any]] = []
    with os.scandir(path) as scan:
        for item in scan:
            child = f"{clean}/{item.name}" if clean else item.name
            if item.is_symlink():
                continue
            if item.is_dir():
                if _skip_dir(item.name):
                    continue
                opens = any(child == d or child.startswith(d + "/") or d.startswith(child + "/")
                            for d in ALLOWED_DIRS) or any(f.startswith(child + "/") for f in ALLOWED_FILES)
                if opens:
                    entries.append({"path": child, "name": item.name, "kind": "dir"})
            elif item.is_file() and _visible_file(child, item.name):
                entries.append(_entry(child, Path(item.path)))
    entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
    parent = "/".join(clean.split("/")[:-1]) if clean else None
    return {"dir": clean, "parent": parent, "entries": entries}


def recent_files(limit: int = 40) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    found: list[tuple[float, str, Path]] = []
    scanned = 0
    roots = [d for d in ALLOWED_DIRS if (PROJECT_ROOT / d).is_dir()]
    for single in ALLOWED_FILES:
        path = PROJECT_ROOT / single
        if path.is_file() and not path.is_symlink():
            found.append((path.stat().st_mtime, single, path))
    for root in roots:
        stack = [(root, PROJECT_ROOT / root)]
        while stack and scanned < SCAN_LIMIT:
            rel_dir, directory = stack.pop()
            try:
                with os.scandir(directory) as scan:
                    for item in scan:
                        scanned += 1
                        if item.is_symlink():
                            continue
                        child = f"{rel_dir}/{item.name}"
                        if item.is_dir():
                            if not _skip_dir(item.name):
                                stack.append((child, Path(item.path)))
                        elif item.is_file() and _visible_file(child, item.name):
                            found.append((item.stat().st_mtime, child, Path(item.path)))
            except OSError:
                continue
    found.sort(key=lambda row: row[0], reverse=True)
    return [_entry(rel, path) for _, rel, path in found[:limit]]


def _decode(raw: bytes) -> tuple[str, bool]:
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise FileToolError("This file isn't UTF-8 text, so the UI can't open it.") from error
    return text, bom


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_file(rel: Any) -> dict[str, Any]:
    clean, path = resolve_file(rel)
    if not path.is_file():
        raise FileNotAvailable(clean)
    if path.stat().st_size > READ_LIMIT:
        raise FileToolError("This file is too large to open in the UI (over 1 MB).")
    raw = path.read_bytes()
    text, bom = _decode(raw)
    crlf = b"\r\n" in raw
    return {**_entry(clean, path), "text": text.replace("\r\n", "\n"), "sha256": _sha(raw),
            "lineEnding": "crlf" if crlf else "lf", "bom": bom, "protected": is_protected(clean)}


def _encode_like(original: bytes, text: str) -> bytes:
    """Keep the file's existing line endings and byte-order mark."""
    body = text.replace("\r\n", "\n")
    if b"\r\n" in original:
        body = body.replace("\n", "\r\n")
    data = body.encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if original.startswith(b"\xef\xbb\xbf") else data


def _check_edit(rel: Any, base_sha: Any, text: Any) -> tuple[str, Path, bytes]:
    clean, path = resolve_file(rel)
    if is_protected(clean):
        raise FileToolError("Security code is read-only in the UI. Edit it at the PC in your code editor.")
    if not isinstance(text, str) or len(text.encode("utf-8")) > EDIT_LIMIT:
        raise FileToolError("The new text is too large (over 512 KB).")
    if not path.is_file():
        raise FileNotAvailable(clean)
    original = path.read_bytes()
    if not isinstance(base_sha, str) or base_sha != _sha(original):
        raise FileConflict("This file changed since it was opened. Reopen it and make the edit again.")
    _decode(original)
    return clean, path, original


def _backup(clean: str, original: bytes, label: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = f"{stamp}-{label}-{uuid.uuid4().hex[:6]}"
    target = UI_DATA_DIR / "file_backups" / folder / Path(*clean.split("/"))
    atomic_write(target, original, overwrite=False)
    return target.relative_to(PROJECT_ROOT).as_posix()


def _apply(clean: str, path: Path, original: bytes, text: str, label: str) -> dict[str, Any]:
    backup = _backup(clean, original, label)
    data = _encode_like(original, text)
    atomic_write(path, data)
    return {"path": clean, "sha256": _sha(data), "backup": backup}


def save_from_desktop(rel: Any, base_sha: Any, text: Any) -> dict[str, Any]:
    """Direct save from the desktop app (caller has checked the desktop key)."""
    with file_lock(UI_DATA_DIR / "file_tools.lock"):
        clean, path, original = _check_edit(rel, base_sha, text)
        if _encode_like(original, text) == original:
            return {"path": clean, "sha256": _sha(original), "backup": None, "unchanged": True}
        return _apply(clean, path, original, text, "desktop")


# ------------------------------------------------------------- proposals

def _proposal_dir() -> Path:
    return UI_DATA_DIR / "file_proposals"


def _proposal_path(proposal_id: str) -> Path:
    if not isinstance(proposal_id, str) or len(proposal_id) != 32 or not all(c in "0123456789abcdef" for c in proposal_id):
        raise FileNotAvailable(str(proposal_id)[:40])
    return _proposal_dir() / f"{proposal_id}.json"


def _load(proposal_id: str) -> dict[str, Any]:
    path = _proposal_path(proposal_id)
    if not path.is_file():
        raise FileNotAvailable(proposal_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _save(record: dict[str, Any]) -> None:
    atomic_write(_proposal_path(record["id"]), json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))


def _stats(before: str, after: str) -> dict[str, int]:
    added = removed = 0
    for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {"added": added, "removed": removed}


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in ("id", "path", "note", "status", "createdAt", "decidedAt", "stats", "backup", "from")}


def list_proposals(limit: int = 50) -> list[dict[str, Any]]:
    directory = _proposal_dir()
    if not directory.is_dir():
        return []
    records = []
    for path in directory.glob("*.json"):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    records.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    return [_summary(r) for r in records[: max(1, min(int(limit), 100))]]


def pending_count() -> int:
    return sum(1 for item in list_proposals(100) if item.get("status") == "pending")


def get_proposal(proposal_id: str) -> dict[str, Any]:
    record = _load(proposal_id)
    current_text = ""
    current_matches = False
    try:
        clean, path = resolve_file(record["path"])
        if path.is_file():
            raw = path.read_bytes()
            current_text, _ = _decode(raw)
            current_text = current_text.replace("\r\n", "\n")
            current_matches = _sha(raw) == record["baseSha256"]
    except (FileToolError, OSError):
        pass
    diff = list(difflib.unified_diff(current_text.splitlines(), record["text"].splitlines(),
                                     fromfile=f"{record['path']} (now)", tofile=f"{record['path']} (proposed)", lineterm=""))
    truncated = len(diff) > 4000
    return {**_summary(record), "diff": "\n".join(diff[:4000]), "diffTruncated": truncated,
            "baseMatches": current_matches}


def create_proposal(rel: Any, base_sha: Any, text: Any, note: Any = "", origin: str = "phone") -> dict[str, Any]:
    clean_note = " ".join(str(note or "").split())[:300]
    with file_lock(UI_DATA_DIR / "file_tools.lock"):
        clean, path, original = _check_edit(rel, base_sha, text)
        before, _ = _decode(original)
        if _encode_like(original, text) == original:
            raise FileToolError("Nothing changed in this file.")
        if pending_count() >= MAX_PENDING:
            raise FileToolError("Too many changes are waiting. Approve or reject some on the PC first.")
        record = {
            "id": uuid.uuid4().hex, "path": clean, "baseSha256": base_sha, "text": text.replace("\r\n", "\n"),
            "note": clean_note, "status": "pending", "createdAt": _now(), "decidedAt": None, "backup": None,
            "from": origin if origin in ("phone", "desktop") else "phone",
            "stats": _stats(before.replace("\r\n", "\n"), text.replace("\r\n", "\n")),
        }
        _save(record)
        return _summary(record)


def approve_proposal(proposal_id: str) -> dict[str, Any]:
    """Apply a pending change (caller has checked the desktop key)."""
    with file_lock(UI_DATA_DIR / "file_tools.lock"):
        record = _load(proposal_id)
        if record.get("status") != "pending":
            raise FileToolError(f"This change is already {record.get('status')}.")
        try:
            clean, path, original = _check_edit(record["path"], record["baseSha256"], record["text"])
        except FileConflict:
            record.update(status="stale", decidedAt=_now())
            _save(record)
            raise FileConflict("The file changed after this edit was proposed, so it wasn't applied. Make the edit again.")
        result = _apply(clean, path, original, record["text"], proposal_id[:8])
        record.update(status="applied", decidedAt=_now(), backup=result["backup"])
        _save(record)
        return {**_summary(record), "sha256": result["sha256"]}


def reject_proposal(proposal_id: str) -> dict[str, Any]:
    with file_lock(UI_DATA_DIR / "file_tools.lock"):
        record = _load(proposal_id)
        if record.get("status") != "pending":
            raise FileToolError(f"This change is already {record.get('status')}.")
        record.update(status="rejected", decidedAt=_now())
        _save(record)
        return _summary(record)
