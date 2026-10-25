"""Self-Sustain: ZAE looking after herself.

* Nightly backup of her data/ folder (memory, profile, notes, settings, research,
  game styles, reminders, protocols and her sealed secrets) to a zip in
  %USERPROFILE%\\ZAENIA Backups, keeping the newest 14. Big downloadable things
  (models, voices, caches) are left out; they can be downloaded again.
* Auto-restart: an optional Windows scheduled task checks her server every 5
  minutes and restarts it (token mode) if it stops answering twice in a row.
* Health: memory, disk, CPU, her brain and voice, with plain-language warnings.

Restoring a backup is deliberately a console step with the passkey
(python -m core.assistant_platform.selfcare restore <zip>), never an app button.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA = PROJECT_ROOT / "data"
LAST_FILE = DATA / "backups" / "last.json"
DEFAULT_DEST = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "ZAENIA Backups"
KEEP = 14
SKIP_DIRS = {"models", "voices", "web_cache", "audit_archive", "backups", "chat_files", "__pycache__", "speaker_cache",
             "pretrained_models", "huggingface"}
SKIP_SUFFIXES = (".onnx", ".bin", ".pt", ".ckpt", ".safetensors", ".gguf", ".tmp", ".lock", ".wav", ".mp3")
MAX_FILE = 200 * 2**20
TASK = "ZAENIA Watchdog"
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
_LOCK = threading.Lock()


def _settings() -> dict[str, Any]:
    try:
        return json.loads((DATA / "backups" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def destination() -> Path:
    return Path(_settings().get("destination") or DEFAULT_DEST)


def last_backup() -> dict[str, Any]:
    try:
        return json.loads(LAST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _files(root: Path = DATA):
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            path = Path(folder) / name
            if name.endswith(SKIP_SUFFIXES) or path.is_symlink():
                continue
            try:
                if path.stat().st_size <= MAX_FILE:
                    yield path
            except OSError:
                continue


def backup_now(dest: Path | None = None, data: Path = DATA) -> dict[str, Any]:
    """Zip data/ into the backup folder and keep the newest 14."""
    with _LOCK:
        dest = Path(dest or destination())
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = dest / f"ZAENIA-data-{stamp}.zip"
        count = 0
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in _files(data):
                try:
                    archive.write(path, path.relative_to(data.parent))
                    count += 1
                except (OSError, PermissionError):
                    continue
        for old in sorted(dest.glob("ZAENIA-data-*.zip"))[:-KEEP]:
            try:
                old.unlink()
            except OSError:
                pass
        record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "path": str(target), "files": count,
                  "bytes": target.stat().st_size}
        from core.foundation.security.io import atomic_write
        atomic_write(LAST_FILE, json.dumps(record).encode("utf-8"))
        return record


def watchdog_installed() -> bool:
    try:
        return subprocess.run(["schtasks", "/Query", "/TN", TASK], capture_output=True, timeout=10, **NO_WINDOW).returncode == 0
    except Exception:
        return False


def install_watchdog() -> bool:
    script = PROJECT_ROOT / "scripts" / "zae_watchdog.ps1"
    command = f'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{script}"'
    result = subprocess.run(["schtasks", "/Create", "/F", "/TN", TASK, "/SC", "MINUTE", "/MO", "5", "/TR", command],
                            capture_output=True, text=True, timeout=20, **NO_WINDOW)
    return result.returncode == 0


def remove_watchdog() -> bool:
    return subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK], capture_output=True, timeout=20, **NO_WINDOW).returncode == 0


def health() -> dict[str, Any]:
    import psutil
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(str(PROJECT_ROOT.anchor or "C:\\"))
    issues = []
    if memory.percent >= 90:
        issues.append(f"Memory is {memory.percent:.0f}% full. Close something big, or turn on game mode's brain unloading.")
    if disk.free < 20 * 2**30:
        issues.append(f"Only {disk.free // 2**30} GB free on the drive. Clear space so backups and updates keep working.")
    backup = last_backup()
    if not backup:
        issues.append("No backup yet. Press Back up now.")
    elif time.time() - datetime.fromisoformat(backup["at"]).timestamp() > 2 * 86400:
        issues.append("The last backup is more than two days old.")
    try:
        from core.assistant_platform.health import inspect_health
        probe = inspect_health()
    except Exception:
        probe = None
    return {"memoryPercent": memory.percent, "diskFreeGb": disk.free // 2**30, "cpuPercent": psutil.cpu_percent(interval=None),
            "backup": backup, "destination": str(destination()), "watchdog": watchdog_installed(), "issues": issues, "probe": probe}


class Nightly:
    """Backs up once a day (about 3 a.m., or soon after start-up when the last one is over a day old)."""

    def __init__(self):
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread is not None:
            return

        def run():
            while not self.stop_event.wait(600):
                try:
                    last = last_backup().get("at")
                    age = time.time() - datetime.fromisoformat(last).timestamp() if last else 1e9
                    if age > 26 * 3600 or (age > 20 * 3600 and datetime.now().hour == 3):
                        backup_now()
                except Exception:
                    pass
        self.thread = threading.Thread(target=run, name="zaenia-nightly-backup", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()


NIGHTLY = Nightly()


def restore(zip_path: str) -> None:
    """Console only, with the passkey: put a backup's files back (the current data/ is copied aside first)."""
    from core.foundation.auth.passkey import consume_fresh_auth, require_passkey
    source = Path(zip_path)
    if not source.is_file() or not zipfile.is_zipfile(source):
        raise ValueError("That isn't a ZAE backup zip.")
    proof = require_passkey(operation="backup.restore", payload={"zip": source.name})
    consume_fresh_auth(proof, operation="backup.restore", payload={"zip": source.name})
    aside = DATA.parent / f"data-before-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copytree(DATA, aside, ignore=shutil.ignore_patterns(*SKIP_DIRS))
    with zipfile.ZipFile(source) as archive:
        for member in archive.namelist():
            target = (DATA.parent / member).resolve()
            if not str(target).startswith(str(DATA.resolve())):
                raise ValueError("The backup has a file outside data/; nothing more was restored.")
        archive.extractall(DATA.parent)
    print(f"Restored. Your previous data is kept in {aside}. Restart ZAE: .\\scripts\\zae.ps1 restart")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "restore":
        restore(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "backup":
        print(backup_now())
    else:
        print("python -m core.assistant_platform.selfcare backup | restore <zip>")
