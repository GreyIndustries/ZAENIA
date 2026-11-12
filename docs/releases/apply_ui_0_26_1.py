r"""Apply ZAENIA UI 0.26.1: visual correction, the core docks beside the page's top row (C1) instead of the mic (C5) (Claude, 2026-11-11).

Usage (Python 3.11+, standard library only):
    python apply_ui_0_26_1.py C:\Projects\ZAENIA --dry-run   # check only, writes nothing
    python apply_ui_0_26_1.py C:\Projects\ZAENIA             # apply
    python apply_ui_0_26_1.py C:\Projects\ZAENIA --revert <backup folder printed by apply>

What it does, in order:
 1. Checks every file it would change or remove. Each must still be exactly the UI 0.26.0 version (line endings
    ignored), or already be the new version. Otherwise it lists the conflicts and writes nothing.
 2. Copies the current versions of all those files to <checkout>\.tmp\core-c1-before-<time>\.
 3. Writes the new frontend source, test and release docs from payload\files\, keeping each file's line endings, and
    removes the C5-only files (MicCore.tsx/.css).
 4. Updates desktop\src\config\versions.json in place: UI 0.26.0 -> 0.26.1 and adds the 0.26.1 history entry.
 5. Appends section 48.1 to the master build plan and a section to HANDOFF_2026-10-30.md, only if not already there.
It does not build, stage, install, restart, commit, merge or push anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAYLOAD = HERE / "payload"
VERSIONS = "desktop/src/config/versions.json"
PLAN = "docs/architecture/ZAENIA_Master_Build_Plan.md"
HANDOFF = "docs/architecture/HANDOFF_2026-10-30.md"
PLAN_MARKER = "### 48.1 Visual correction: C1"
HANDOFF_MARKER = "## Visual correction: C1 \"Docked companion\" — UI 0.26.1"
UI_FROM, UI_TO = "0.26.0", "0.26.1"


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def digest(data: bytes) -> str:
    return hashlib.sha256(lf(data)).hexdigest()


def current(path: Path) -> str | None:
    return digest(path.read_bytes()) if path.is_file() else None


def load_manifest() -> dict:
    return json.loads((PAYLOAD / "manifest.json").read_text(encoding="utf-8"))


def check(root: Path, manifest: dict) -> tuple[list[str], list[dict]]:
    conflicts: list[str] = []
    todo: list[dict] = []
    for item in manifest["files"]:
        now = current(root / item["path"])
        if now == item["after"]:
            continue  # already applied
        befores = item["before"] if isinstance(item["before"], list) else [item["before"]]
        if now not in befores:
            state = "missing" if now is None else "changed by someone else"
            want = "a new file" if befores == [None] else "the UI 0.26.0 version"
            conflicts.append(f"{item['path']}: {state} (expected {want})")
        else:
            todo.append(item)
    versions = root / VERSIONS
    if versions.is_file():
        ui = json.loads(versions.read_text(encoding="utf-8-sig")).get("ui", {}).get("version")
        if ui not in (UI_FROM, UI_TO):
            conflicts.append(f"{VERSIONS}: UI version is {ui}, expected {UI_FROM} (another update changed it; merge by hand)")
    else:
        conflicts.append(f"{VERSIONS}: missing")
    return conflicts, todo


def write_like(target: Path, data: bytes) -> None:
    """Write with the line endings the existing file used (CRLF for new files, as in this Windows checkout)."""
    crlf = True
    if target.is_file():
        crlf = b"\r\n" in target.read_bytes()
    body = lf(data)
    target.write_bytes(body.replace(b"\n", b"\r\n") if crlf else body)


def bump_versions(root: Path, manifest: dict) -> bool:
    path = root / VERSIONS
    raw = path.read_bytes().decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in raw else "\n"
    data = json.loads(raw)
    history = data.setdefault("history", [])
    entry = manifest["history_entry"]
    mine = [i for i, h in enumerate(history) if h.get("part") == "ui" and h.get("version") == UI_TO]
    if data["ui"]["version"] == UI_TO and mine and history[mine[0]] == entry:
        return False
    data["ui"]["version"] = UI_TO
    if mine:
        history[mine[0]] = entry  # refresh notes from an earlier 0.26.0 build
    else:
        history.insert(0, entry)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if raw.endswith(("\n", "\r\n")):
        text += "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return True


def append_once(path: Path, marker: str, addition: str, version_bump: tuple[str, str] | None = None) -> bool:
    if not path.is_file():
        print(f"  skipped {path} (not present in this checkout)")
        return False
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    if marker in raw:
        # An earlier 0.26.0 build appended an older version of this text: replace it in place.
        start = raw.index(marker)
        nxt = raw.find("\n## ", start + 1)
        end = nxt if nxt != -1 else len(raw)
        old = raw[start:end].rstrip()
        new = addition.strip().replace("\n", newline)
        if old == new:
            return False
        path.write_bytes((raw[:start] + new + raw[start + len(old):]).encode("utf-8"))
        return True
    if version_bump and version_bump[0] in raw:
        raw = raw.replace(version_bump[0], version_bump[1], 1)
    text = raw.rstrip() + newline + newline + addition.strip().replace("\n", newline) + newline
    path.write_bytes(text.encode("utf-8"))
    return True


def backup(root: Path, manifest: dict) -> Path:
    folder = root / ".tmp" / f"core-c1-before-{time.strftime('%Y%m%d-%H%M%S')}"
    record = {"created": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": []}
    for rel in [item["path"] for item in manifest["files"]] + [VERSIONS, PLAN, HANDOFF]:
        source = root / rel
        existed = source.is_file()
        if existed:
            target = folder / "files" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        record["files"].append({"path": rel, "existed": existed})
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "backup.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return folder


def revert(root: Path, folder: Path) -> int:
    record = json.loads((folder / "backup.json").read_text(encoding="utf-8"))
    for item in record["files"]:
        target = root / item["path"]
        if item["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(folder / "files" / item["path"], target)
            print("restored", item["path"])
        elif target.is_file():
            target.unlink()
            print("removed", item["path"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--revert", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "desktop" / "src").is_dir():
        print(f"{root} does not look like a ZAENIA checkout (no desktop/src).")
        return 2
    if args.revert:
        return revert(root, args.revert.resolve())
    manifest = load_manifest()
    conflicts, todo = check(root, manifest)
    if conflicts:
        print("Not applied. These files differ from what this update was built on:")
        for line in conflicts:
            print("  -", line)
        return 3
    print(f"{len(todo)} file(s) to write, {len(manifest['files']) - len(todo)} already up to date.")
    if args.dry_run:
        for item in todo:
            print("  would remove" if item["after"] is None else "  would write", item["path"])
        print("Dry run: nothing written.")
        return 0
    folder = backup(root, manifest)
    print("backup:", folder)
    for item in todo:
        target = root / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if item["after"] is None:
            target.unlink()
            print("removed", item["path"])
            continue
        write_like(target, (PAYLOAD / "files" / item["path"]).read_bytes())
        if current(target) != item["after"]:
            print("verification failed for", item["path"], "- run with --revert", folder)
            return 4
        print("wrote", item["path"])
    if bump_versions(root, manifest):
        print("updated", VERSIONS, f"(UI {UI_TO} + history entry)")
    if append_once(root / PLAN, PLAN_MARKER, manifest["plan_section"], ("Version: 3.78  |  Date: 2026-11-11", "Version: 3.79  |  Date: 2026-11-11")):
        print("updated", PLAN)
    if append_once(root / HANDOFF, HANDOFF_MARKER, manifest["handoff_pointer"]):
        print("updated", HANDOFF)
    print("Done. Build and stage with scripts\\stage_update.ps1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
