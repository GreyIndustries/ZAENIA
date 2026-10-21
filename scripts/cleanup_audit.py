"""Inventory ZAENIA and prepare a local cleanup review. This script never deletes.

The filesystem pass reads metadata only, including security-file paths but never
their contents. A separate, bounded source-reference pass reads application code
and the public voice-path settings. No databases, archives, audio, credentials,
owner memories or logs are opened. Static absence of a reference is not proof
that a file is unused. Every candidate remains pending owner review.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
TEXT_SUFFIXES = {".py", ".ps1", ".cmd", ".bat", ".ts", ".tsx", ".js", ".cjs", ".html"}
REFERENCE_QUERIES = {
    "legacy_database": ("core.db", "core/db.py", "connect_to_db"),
    "legacy_path_helpers": ("core.utils", "core/utils.py", "utils.path_utils", "utils/path_utils.py"),
    "legacy_configs": ("core/settings.yaml", "config/settings.yaml", '"config.yaml"', "'config.yaml'"),
    "legacy_reply_engine": ("reply_engine",),
    "runtime_test_dependency": ("fluid_runtime_test",),
    "root_only_drei": ("@react-three/drei",),
    "old_environment": (".venv_broken_20260829",),
    "carplay_sessions": ("carplay_sessions",),
    "web_bundle": ("dist-web",),
    "launchers": ("foundation_main", "main.py", "start.py"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def scan(root: Path) -> dict:
    """Visit every ordinary directory once, without following links/junctions."""
    root = Path(root).absolute()
    if is_reparse(root.lstat()):
        raise ValueError("The audit root must be an ordinary directory, not a link or junction.")
    started = time.monotonic()
    result = {
        "schema_version": SCHEMA_VERSION,
        "root": str(root.resolve()),
        "started_at": utc_now(),
        "files": [],
        "directories": {},
        "skipped_reparse_points": [],
        "errors": [],
    }
    pending = [(root, "")]
    while pending:
        directory, relative_dir = pending.pop()
        try:
            info = directory.lstat()
            if is_reparse(info):
                result["skipped_reparse_points"].append(relative_dir)
                continue
            result["directories"][relative_dir] = {
                "path": relative_dir, "mtime_ns": info.st_mtime_ns,
                "files": 0, "bytes": 0,
            }
            with os.scandir(directory) as entries:
                for entry in entries:
                    relative = (relative_dir + "/" + entry.name).lstrip("/")
                    try:
                        metadata = entry.stat(follow_symlinks=False)
                        if is_reparse(metadata):
                            result["skipped_reparse_points"].append(relative)
                        elif stat.S_ISDIR(metadata.st_mode):
                            pending.append((Path(entry.path), relative))
                        elif stat.S_ISREG(metadata.st_mode):
                            result["files"].append({
                                "path": relative, "bytes": metadata.st_size,
                                "mtime_ns": metadata.st_mtime_ns,
                            })
                    except OSError as error:
                        result["errors"].append({"path": relative, "error": type(error).__name__})
        except OSError as error:
            result["errors"].append({"path": relative_dir, "error": type(error).__name__})
    result["files"].sort(key=lambda row: row["path"].casefold())
    for row in result["files"]:
        parts = row["path"].split("/")[:-1]
        for length in range(len(parts) + 1):
            parent = "/".join(parts[:length])
            if parent in result["directories"]:
                result["directories"][parent]["files"] += 1
                result["directories"][parent]["bytes"] += row["bytes"]
    result["finished_at"] = utc_now()
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["totals"] = {
        "files": len(result["files"]), "directories": len(result["directories"]),
        "bytes": sum(row["bytes"] for row in result["files"]),
        "skipped_reparse_points": len(result["skipped_reparse_points"]),
        "errors": len(result["errors"]),
    }
    return result


def ordinary_path(root: Path, relative: str) -> Path:
    """Restrict reads/writes to ordinary paths within the chosen project."""
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("Report paths must be project-relative and cannot contain '..'.")
    candidate = root / value
    current = root
    for part in value.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if is_reparse(current.lstat()):
                raise ValueError("Linked paths are not opened: " + relative)
    candidate.resolve().relative_to(root.resolve())
    return candidate


def report_destination(root: Path, relative: str, *, kind: str) -> Path:
    """Only generated review names may be written or read as baselines."""
    normalized = relative.replace("\\", "/")
    pattern = (r"data/cleanup_review/inventory(?:[-_][A-Za-z0-9._-]+)?\.json" if kind == "json" else
               r"docs/CLEANUP_REVIEW(?:[-_][A-Za-z0-9._-]+)?\.md")
    if not re.fullmatch(pattern, normalized):
        raise ValueError("Use the dedicated private inventory or generated Markdown review filename.")
    path = ordinary_path(root, normalized)
    if path.exists():
        if not path.is_file():
            raise ValueError("The generated report path is not a regular file.")
        if kind == "json":
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("schema_version") != SCHEMA_VERSION or not isinstance(existing.get("files"), list):
                raise ValueError("Existing output is not a generated cleanup inventory.")
        else:
            with path.open(encoding="utf-8") as stream:
                if stream.readline().rstrip() != "# ZAENIA cleanup review — nothing deleted":
                    raise ValueError("Existing output is not a generated cleanup review.")
    return path


def source_path(relative: str) -> bool:
    """Only inspect application sources, never data/security/backups/models."""
    parts = relative.split("/")
    if any(part == "__pycache__" or "backup" in part.lower() or part.startswith(".venv") for part in parts):
        return False
    if relative in {"core/brain/component_registry.yaml", "package.json", "desktop/package.json"}:
        return True
    if len(parts) == 1:
        return relative in {"main.py", "start.py", "foundation_main.py", "build_scripture_corpus.py"}
    return relative.startswith(("core/", "scripts/", "desktop/src/", "desktop/scripts/")) and relative not in {
        "scripts/cleanup_audit.py", "scripts/cleanup_audit_test.py",
    }


def reference_audit(root: Path, inventory: dict) -> dict:
    """Report reference locations, not source text or configuration values."""
    references = {key: [] for key in REFERENCE_QUERIES}
    imports: dict[str, list[dict]] = {}
    for row in inventory["files"]:
        relative = row["path"]
        selected_config = relative in {"core/brain/component_registry.yaml", "package.json", "desktop/package.json"}
        if not source_path(relative) or (Path(relative).suffix not in TEXT_SUFFIXES and not selected_config) or row["bytes"] > 2_000_000:
            continue
        try:
            text = ordinary_path(root, relative).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError, ValueError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            normalized = line.replace("\\\\", "/").replace("\\", "/")
            for key, needles in REFERENCE_QUERIES.items():
                if any(needle in normalized for needle in needles):
                    references[key].append({"path": relative, "line": number})
        if relative.endswith(".py"):
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    modules = ([node.module] if isinstance(node, ast.ImportFrom) and node.module else
                               [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                    for module in modules:
                        imports.setdefault(module, []).append({"path": relative, "line": node.lineno})
            except SyntaxError:
                continue
    launchers = {}
    for name in ("main.py", "start.py", "foundation_main.py"):
        try:
            content = ordinary_path(root, name).read_bytes()
            launchers[name] = hashlib.sha256(content).hexdigest()
        except (OSError, ValueError):
            pass
    active_voices = []
    try:
        voice_text = ordinary_path(root, "core/voice_output/voice_config.yaml").read_text(encoding="utf-8")
        for match in re.finditer(r'^\s*(?:model_path|config_path):\s*["\']?([^\s"\']+)', voice_text, re.MULTILINE):
            voice_path = match.group(1).replace("\\", "/")
            if voice_path.startswith("data/voices/piper/") and ".." not in Path(voice_path).parts:
                active_voices.append(voice_path)
    except (OSError, UnicodeError, ValueError):
        pass
    requirements_status = {"present": False, "combined_sounddevice_tzdata_entry": None,
                           "split_sounddevice_tzdata_present": False, "duplicate_entries": None}
    try:
        requirements = ordinary_path(root, "requirements.txt").read_text(encoding="utf-8")
        entries = [line.strip().casefold() for line in requirements.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        requirements_status = {"present": True, "combined_sounddevice_tzdata_entry": "sounddevicetzdata" in entries,
                               "split_sounddevice_tzdata_present": "sounddevice" in entries and "tzdata" in entries,
                               "duplicate_entries": len(entries) - len(set(entries))}
    except (OSError, UnicodeError, ValueError):
        pass
    return {
        "searched_scope": "Application code/configuration and root entry points; excludes data, credentials, archives, backups and dependency trees.",
        "limitations": "Static references cannot prove a file is unused; external launchers, manually run tools and dynamic path construction may not appear.",
        "references": references,
        "python_imports": {key: value for key, value in imports.items() if key in {
            "core.db", "core.utils", "core.init", "utils", "utils.path_utils",
            "core.conversation.reply_engine", "core.conversation_runtime.fluid_runtime_test",
        }},
        "launcher_sha256": launchers,
        "launchers_identical": len(launchers) == 3 and len(set(launchers.values())) == 1,
        "active_voice_paths": active_voices,
        "requirements_status": requirements_status,
    }


def rows_for(inventory: dict, paths: list[str]) -> list[dict]:
    return [row for row in inventory["files"] if any(
        row["path"] == path or row["path"].startswith(path + "/") for path in paths
    )]


def candidates(inventory: dict, usage: dict) -> list[dict]:
    files = {row["path"]: row for row in inventory["files"]}
    dirs = inventory["directories"]
    groups = []

    def add(identifier, title, paths, recommendation, reason, risk="review", evidence=None):
        paths = sorted(set(path for path in paths if path in files or path in dirs))
        if not paths:
            return
        rows = rows_for(inventory, paths)
        groups.append({
            "id": identifier, "title": title, "paths": paths,
            "files": len(rows), "bytes": sum(row["bytes"] for row in rows),
            "risk": risk, "recommendation": recommendation, "reason": reason,
            "evidence": evidence or [], "approval": "pending_owner_selection", "deleted": False,
        })

    rust = "desktop/src-tauri/target"
    add("C01", "Rust build intermediates", [rust + "/debug"] + [
        rust + "/release/" + name for name in (".fingerprint", "build", "deps", "examples", "incremental")
    ], "Review first; close the desktop app/build tools before selected cache cleanup.",
        "Rebuilt by Cargo. Keep target/release/desktop.exe, its support artifacts and any installer bundles. The next native build will take longer.", "regenerable",
        ["desktop/src-tauri/target/release/desktop.exe"])
    active = set(usage["active_voice_paths"])
    models = [path for path in files if path.startswith("data/voices/piper/") and path.endswith(".onnx")]
    inactive = []
    if active:  # Without a verified configured model, never suggest discarding voice models.
        for model in models:
            if model not in active:
                inactive.extend([model, model + ".json"])
    add("C02", "Alternative Piper voices", inactive,
        "Review whether you want to keep the alternative voices; preserve the configured model/config pair.",
        "These model paths are not selected by the current Piper configuration. They are optional voice choices, not proof of useless data.", "optional_models",
        ["core/voice_output/voice_config.yaml"])
    add("C03", "Voice audition audio", [path for path in files if path.startswith("data/voices/piper/") and
        (path.endswith("-test.wav") or Path(path).name == "zaenia_test.wav")],
        "Review the test recordings for removal.", "Generated voice auditions, including a test for the active voice; these are separate from the active ONNX model.", "review_audio")
    add("C04", "Archived broken Python environment", [path for path in dirs if "/" not in path and path.startswith(".venv_broken_")],
        "Review after confirming all launchers use .venv.",
        "Startup scripts select .venv/Scripts/python.exe. Keep the active .venv and its installed speech/ML dependencies.", "old_environment",
        ["scripts/start_zaenia_server.ps1", "scripts/start_zaenia_voice.ps1"])
    add("C05", "Root npm installation and its manifests", ["node_modules", "package.json", "package-lock.json"],
        "Likely redundant for the current desktop build; approve a controlled build check before removal.",
        "The root manifest has no run/build scripts. The desktop owns its own manifest and node_modules. The root-only drei package has no current application-source import. Node can resolve parent modules, so static scanning alone is insufficient.", "dependency_review",
        ["package.json", "desktop/package.json"])
    add("C06", "Security restore copy", ["restore_check/secure"],
        "Owner review required; do not keep stale credential material in routine source backups.",
        "This is a restore-copy location, not data/secure. Contents were deliberately not read. Verify recovery needs before selecting the copy for removal.", "sensitive_copy")
    add("C07", "Blender autosaves", [path for path in files if path.startswith("desktop/blender/") and re.search(r"\.blend\d+$", path)],
        "Review autosaves separately from scenes and generator scripts.",
        "Autosaves can recover lost work. Scene revisions and scripts are authored assets and remain protected from automatic cleanup.", "authored_asset_backup")
    add("C08", "Older UI snapshot folders", [path for path in dirs if path.count("/") == 1 and
        (path.startswith("desktop/ui-backup-") or path == "desktop/src backup")],
        "Review after the current UI behavior is accepted.", "Historical UI rollback copies; do not discard the only rollback for unverified changes.", "rollback")
    dated_ui = [path for path in dirs if path.startswith("desktop/ui-backups/") and path.count("/") == 2]
    dated_ui.sort(key=lambda path: (dirs[path]["mtime_ns"], path), reverse=True)
    add("C09", "Older UI history (keep newest three)", dated_ui[3:],
        "Review the older snapshots; preserve the three newest plus any known good milestone.",
        "Newest is based on folder modification metadata, not a guarantee of quality. Retention is a review suggestion only.", "rollback")
    add("C10", "Source rollback/export-preparation copies", ["backups", "module1_backups", "module1_prep"] + [
        path for path in dirs if Path(path).name.startswith("_backup_before_") and path.startswith(("core/", "scripts/"))
    ], "Review rollback needs after accepting and testing the upgrades.",
        "These copies support recovery and are small beside build output. Archives or copied source may include private configuration; no archive contents were opened.", "rollback")
    add("C11", "One-time source exports and review tools", [path for path in files if "/" not in path and
        (re.fullmatch(r"ZAENIA_.*_Source_Review\.zip", path) or path in {"carplay_review.txt", "collect_module2_source.py", "test_carplay_update.py"})],
        "Review whether the export/debug workflow is still useful.",
        "Not current application entry points. A test or export tool can still be useful when run manually; its name is not deletion authorization.", "manual_tools")
    add("C12", "Legacy placeholders and configuration candidates", ["core/db.py", "core/init.py", "core/utils.py", "core/settings.yaml", "config/settings.yaml", "config.yaml", "utils", "voice", "core/foundation/_init_.py", "core/conversation/conversation_main.py"],
        "Review source/configuration together; external scripts and dynamic readers still need consideration.",
        "No direct application imports of the old db/path-helper modules were found. Empty folders/files take negligible space. Configuration contents, including placeholder credentials, were not copied into the report.", "legacy_source")
    add("C13", "CarPlay generated briefing audio", [path for path in files if path.startswith("data/carplay_sessions/") and path.endswith(".wav")],
        "Retain current sessions; design reference-aware retention before selecting old audio.",
        "The running CarPlay service stores audio paths in sessions.sqlite3 and exposes delivery/replay. Age or a .wav extension alone is insufficient. The database was not read or changed.", "runtime_references",
        ["core/carplay_trigger/briefing_session.py", "core/api/status_feed.py"])
    add("C14", "Application Python bytecode caches", [path for path in dirs if Path(path).name == "__pycache__" and
        path.startswith(("core/", "scripts/", "utils/")) and not any("backup" in part.lower() for part in path.split("/"))],
        "Optional cache cleanup after selected processes are closed; little benefit.",
        "Recreated by Python. No source modules or active virtual-environment packages are selected.", "regenerable")
    return groups


def compare_inventory(current: dict, baseline: dict) -> dict:
    if baseline.get("schema_version") != SCHEMA_VERSION or not isinstance(baseline.get("files"), list):
        raise ValueError("Baseline is not a compatible cleanup inventory.")
    if os.path.normcase(os.path.abspath(baseline.get("root", ""))) != os.path.normcase(os.path.abspath(current["root"])):
        raise ValueError("Baseline belongs to a different project root.")
    old = {row["path"]: row for row in baseline["files"]}
    new = {row["path"]: row for row in current["files"]}
    return {
        "baseline_finished_at": baseline.get("finished_at"),
        "added": sorted(new.keys() - old.keys()),
        "missing": sorted(old.keys() - new.keys()),
        "changed": sorted(path for path in old.keys() & new.keys() if
                          (old[path]["bytes"], old[path]["mtime_ns"]) != (new[path]["bytes"], new[path]["mtime_ns"])),
        "limitations": "Size/mtime comparison only; identical-size content changes with preserved timestamps are not detected. Missing paths were not deleted by this tool.",
    }


def size_label(value: int) -> str:
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.2f} GiB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.2f} MiB"
    if value >= 1024:
        return f"{value / 1024:.2f} KiB"
    return f"{value} B"


def render_review(inventory: dict) -> str:
    totals, usage = inventory["totals"], inventory["usage"]
    dirs = inventory["directories"]
    files = {row["path"]: row for row in inventory["files"]}
    groups = inventory["candidates"]
    all_candidate_paths = [path for group in groups for path in group["paths"]]
    candidate_rows = rows_for(inventory, all_candidate_paths)
    lines = [
        "# ZAENIA cleanup review — nothing deleted", "",
        f"Scanned `{inventory['root']}` at {inventory['finished_at']} in {inventory['elapsed_seconds']:.1f} seconds.", "",
        f"**{totals['files']:,} files, {totals['directories']:,} directories, {size_label(totals['bytes'])} ({totals['bytes']:,} logical bytes).** "
        f"Skipped links/junctions: {totals['skipped_reparse_points']}; scan errors: {totals['errors']}.", "",
        "Sizes are logical file lengths, not allocated disk space. Copies/hard links, compression, running writes and rebuilds can change the space actually recovered. This is a point-in-time inventory, not a frozen filesystem.", "",
        "The complete tree was visited for metadata, including dependencies and build output. Security files, memories, databases, audio, archives and logs were not opened. The separate reference check reads application code and the public Piper model paths only; it records reference locations, never configuration or source contents.", "",
        "## Review candidates", "",
        f"The groups below cover {size_label(sum(row['bytes'] for row in candidate_rows))} without double-counting. **This is review volume, not approved or guaranteed recoverable space.** Every group is pending your selection. No cleanup operation, shell deletion command or automatic-delete schedule has been added.", "",
        "| ID | Item | Verified size / files | Assessment |", "| --- | --- | ---: | --- |",
    ]
    for group in groups:
        lines.append(f"| {group['id']} | {group['title']} | {size_label(group['bytes'])} / {group['files']:,} | {group['recommendation']} |")
    lines += ["", "## Keep protected", "", "| Item | Verified size | Why |", "| --- | ---: | --- |"]
    protected = [
        (".venv", "Active Python environment selected by both startup scripts; includes ML/speech dependencies."),
        ("desktop/node_modules", "Desktop build dependencies; preserve while upgrading and testing."),
        ("desktop/src-tauri/target/release/desktop.exe", "Current runnable desktop build. Removing all of target removes this executable."),
        ("desktop/dist", "Built desktop frontend; rebuildable but currently used by packaging/build workflows."),
        ("desktop/dist-web", "Live phone/web frontend served by core/api/phone_app.py."),
        ("data/secure", "Owner authentication, policy and recovery material; metadata only, never classified as expendable."),
        ("data/models", "Speech/ML model data."),
        ("data/personal_memory", "Lasting personal memory, not cache."),
        ("data/assistant_followthrough", "Reminder inbox, delivery claims and preferences, not cache."),
    ]
    for path in usage["active_voice_paths"]:
        protected.append((path, "Configured active Piper voice; keep both model and JSON configuration."))
    for path, why in protected:
        row = files.get(path) or dirs.get(path)
        lines.append(f"| `{path}` | {size_label(row['bytes']) if row else 'Not present at scan'} | {why} |")
    target = dirs.get("desktop/src-tauri/target")
    if target:
        lines += ["", f"The **whole** Rust target tree is {size_label(target['bytes'])}, which differs from the older pasted estimate. C01 selects the large compiler/intermediate folders for review and excludes the top-level release executable/support artifacts."]
    lines += ["", "## Corrections to the earlier list", ""]
    lines += [
        "- `core/conversation_runtime/fluid_runtime_test.py` is a **live runtime dependency**, imported by `core/voice_security/runtime.py`. Do not delete `*_test.py` files based on the suffix. Keep the microphone/voice diagnostics unless separately reviewed.",
        "- `core/conversation/reply_engine.py` is listed in `core/brain/component_registry.yaml`. No direct Python import was found in the checked application sources, but removing it also requires correcting that component evidence. It remains outside cleanup candidates.",
        f"- `main.py`, `start.py` and `foundation_main.py` {'are byte-identical' if usage['launchers_identical'] else 'are not all verified identical'}. They are documented compatibility entry points; keeping all three costs less than 1 KiB. External shortcuts were outside this audit.",
        "- Root npm dependencies look redundant for the current app, but parent-module resolution exists. Preserve the root manifests until a controlled desktop build check confirms removal is harmless. The desktop has its own separate dependency installation.",
        "- CarPlay WAV files belong to an active session/replay system. Preserve `data/carplay_sessions/sessions.sqlite3`. An age-only deletion job could break replay; reference-aware retention needs its own reviewed change.",
        "- Blender scenes, scripts and UI/source backups are authored work or recovery points. A newer timestamp does not prove an older scene is unnecessary.",
        "- The requirements files are installation instructions, not disposable space savings. Keep both Python manifests until a complete dependency inventory is validated; no Python manifest is selected for deletion.",
    ]
    requirements_status = usage["requirements_status"]
    if requirements_status["present"]:
        if requirements_status["combined_sounddevice_tzdata_entry"]:
            lines += ["- The malformed `sounddevicetzdata` requirement is still present and should be split into `sounddevice` and `tzdata` before a fresh installation."]
        else:
            lines += [("- Corrected the malformed `sounddevicetzdata` entry into separate `sounddevice` and `tzdata` requirements. "
                       if requirements_status["split_sounddevice_tzdata_present"] else
                       "- The malformed `sounddevicetzdata` entry is absent from the current requirements file. ")
                      + ("No exact duplicate package lines remain." if requirements_status["duplicate_entries"] == 0 else
                         "Exact duplicate package lines still require review.")]
        lines += ["- Retained `requirements-module1.txt`, the pinned security dependency manifest. This audit installed no packages and changed no dependency manifest."]
    lines += ["", "## Candidate details", ""]
    for group in groups:
        lines += [f"### {group['id']} — {group['title']}", "", group["reason"], "", f"Risk category: `{group['risk']}`. Approval: **pending owner selection**. Files: {group['files']:,}; bytes: {group['bytes']:,}.", "", "Exact paths:", ""]
        visible_paths = (["data/carplay_sessions/*.wav (exact session filenames kept in the private inventory)"]
                         if group["id"] == "C13" else group["paths"])
        lines += ["- `" + path + "`" for path in visible_paths]
        if group["evidence"]:
            lines += ["", "Evidence locations: " + ", ".join("`" + path + "`" for path in group["evidence"]) + "."]
        lines.append("")
    lines += ["## Largest top-level items", "", "| Path | Logical size |", "| --- | ---: |"]
    top = [row for path, row in dirs.items() if path and "/" not in path]
    for row in sorted(top, key=lambda value: value["bytes"], reverse=True):
        lines.append(f"| `{row['path']}` | {size_label(row['bytes'])} |")
    lines += ["", "## Source-reference evidence", "", usage["limitations"], ""]
    for key, locations in usage["references"].items():
        lines.append(f"- `{key}`: " + (", ".join(f"`{item['path']}:{item['line']}`" for item in locations[:20]) or "no match in the checked scope") + (f"; {len(locations)} matches total" if len(locations) > 20 else "") + ".")
    lines += ["", "## Repeatable review process", "",
        "1. Run the read-only audit again to refresh metadata and reference evidence.",
        "2. Review the group IDs and exact paths. Select explicitly which items to remove; all current entries remain unapproved.",
        "3. Compare a fresh scan with this snapshot. Investigate changed paths and active references before approving any selected deletion. A comparison is a metadata hint, not a cryptographic content or authorization check.",
        "4. Before a separately authorized cleanup, preserve the runnable desktop build and useful rollback points, close affected processes and verify each resolved path stays inside this project. Never expand a selection to credentials, personal state, models, other projects or games.",
        "5. A future deletion command must show the exact selected paths and current sizes for owner approval. This scanner has no deletion mode, and ZAE is not authorized to delete any candidate automatically.", "",
        "Run from the project directory:", "", "```powershell",
        ".venv\\Scripts\\python.exe scripts\\cleanup_audit.py",
        "# Load the existing inventory first, then report metadata changes while refreshing it:",
        ".venv\\Scripts\\python.exe scripts\\cleanup_audit.py --baseline data/cleanup_review/inventory.json",
        "```", "",
        "Outputs: `docs/CLEANUP_REVIEW.md` and `data/cleanup_review/inventory.json`. Only these generated review artifacts are written. The detailed inventory is under private owner/SYSTEM permissions and excluded from the token file browser by the existing data-directory boundary. It records local file paths, sizes, timestamps, reference locations and candidate explanations; it contains no file contents. Protected-state filenames and detailed diff paths are kept out of this Markdown report.", "",
    ]
    if inventory.get("comparison"):
        comparison = inventory["comparison"]
        lines += ["## Changes since the previous snapshot", "",
            f"Baseline: {comparison.get('baseline_finished_at')}. Added: {len(comparison['added']):,}; missing: {len(comparison['missing']):,}; changed size/timestamp: {len(comparison['changed']):,}.", "", comparison["limitations"], ""]
        lines += ["Exact added/missing/changed paths are available only in the private JSON inventory.", ""]
    if inventory["errors"] or inventory["skipped_reparse_points"]:
        lines += ["## Scan limitations", "", "Paths that could not be safely inspected are not clean-up approvals. See JSON for all errors and skipped reparse points.", ""]
    return "\n".join(lines)


def write_generated(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".cleanup-review-", suffix=".tmp", delete=False) as output:
        output.write(text)
        temporary = Path(output.name)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only ZAENIA metadata and cleanup-review audit; never deletes project files.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Project root to inventory")
    parser.add_argument("--baseline", help="Project-relative inventory JSON to compare; loaded before outputs are refreshed")
    parser.add_argument("--json", default="data/cleanup_review/inventory.json", help="Private generated metadata output")
    parser.add_argument("--report", default="docs/CLEANUP_REVIEW.md", help="Project-relative generated review output")
    args = parser.parse_args()
    root = args.root.absolute()
    try:
        json_path = report_destination(root, args.json, kind="json")
        report_path = report_destination(root, args.report, kind="report")
        if json_path == report_path:
            raise ValueError("JSON and review outputs must be different paths.")
        baseline = None
        if args.baseline:
            baseline = json.loads(report_destination(root, args.baseline, kind="json").read_text(encoding="utf-8"))
        inventory = scan(root)
        inventory["usage"] = reference_audit(root, inventory)
        inventory["candidates"] = candidates(inventory, inventory["usage"])
        if baseline is not None:
            inventory["comparison"] = compare_inventory(inventory, baseline)
        review = render_review(inventory)
        if str(DEFAULT_ROOT) not in sys.path:
            sys.path.insert(0, str(DEFAULT_ROOT))
        from core.foundation.security.io import protect_storage
        protect_storage(json_path.parent)
        write_generated(json_path, json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
        write_generated(report_path, review)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Audit stopped: {type(error).__name__}: {error}\n")
    print(json.dumps({
        "nothing_deleted": True, "totals": inventory["totals"],
        "report": str(report_path), "inventory": str(json_path),
        "candidate_groups": len(inventory["candidates"]),
        "pending_owner_selection": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
