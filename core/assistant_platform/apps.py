"""Owner-selected app and file targets, never model-generated shell commands."""
import hashlib
import os
from pathlib import Path
import subprocess

from core.assistant_platform.store import text
from core.foundation.security.io import reject_link

BLOCKED = {"cmd.exe", "powershell.exe", "pwsh.exe", "wscript.exe", "cscript.exe", "mshta.exe",
           "rundll32.exe", "regsvr32.exe", "python.exe", "pythonw.exe", "node.exe", "bash.exe", "sh"}
OPEN_FILES = {".pdf", ".txt", ".md", ".docx", ".xlsx", ".pptx", ".blend", ".png", ".jpg", ".jpeg", ".wav", ".mp3"}


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""): result.update(chunk)
    return result.hexdigest()


def validate_target(body):
    name = text(body.get("name"), "App or target name", 100)
    raw = body.get("path")
    if not isinstance(raw, str) or len(raw)>1000 or not Path(raw).is_absolute():
        raise ValueError("Choose an absolute local application, document, or folder path.")
    path = Path(raw)
    reject_link(path)
    if raw.startswith(("\\\\", "//")) or not path.exists():
        raise ValueError("Choose an existing local target, not a network location.")
    if path.is_dir(): kind, fingerprint = "folder", None
    elif path.name.casefold() in BLOCKED:
        raise ValueError("Command interpreters cannot be registered as assistant actions.")
    elif path.suffix.casefold() == ".exe" and os.name == "nt": kind, fingerprint = "app", digest(path)
    elif path.suffix.casefold() in OPEN_FILES: kind, fingerprint = "file", digest(path)
    else: raise ValueError("Choose an application executable, supported document, or folder.")
    return {"name": name, "path": str(path.resolve()), "kind": kind, "sha256": fingerprint}


class AppLauncher:
    def __init__(self, store, *, launch=None):
        self.store, self.launcher = store, launch or self._launch

    @staticmethod
    def _launch(target):
        if target["kind"] == "app":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen([target["path"]], shell=False, cwd=str(Path(target["path"]).parent), creationflags=flags)
            return {"pid": process.pid, "status": "launched"}
        if os.name != "nt": raise ValueError("Opening registered files/folders is configured for Windows on this installation.")
        os.startfile(target["path"])
        return {"status": "opened"}

    def open(self, identifier):
        record = self.store.get("app", identifier)
        if record is None: raise ValueError("That target is not registered. Select it in Assistant first.")
        current = validate_target(record)
        if current["kind"] != record["kind"] or current["sha256"] != record.get("sha256"):
            raise ValueError("The registered target changed. Review and register it again before opening.")
        return {"id": identifier, "name": record["name"], **self.launcher(current)}
