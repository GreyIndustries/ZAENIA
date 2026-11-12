"""Settings > Updates and About: version numbers, staged updates and the install history.

Reads only. Updates are staged by scripts/stage_update.ps1 into updates/pending/<id>/ (desktop exe, phone
site and manifest.json) and installed by the owner from the desktop app (Tauri install_update, which runs
scripts/install_update.ps1). Nothing here can install, restart or change anything.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends

ROOT = Path(__file__).resolve().parents[2]
VERSIONS_FILE = ROOT / "desktop" / "src" / "config" / "versions.json"
PENDING_DIR = ROOT / "updates" / "pending"
INSTALL_LOG = ROOT / "data" / "updates" / "installed.json"
LAST_RESULT = ROOT / "data" / "updates" / "last-install.json"
UPDATE_ID = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.\-]{0,63}$")
_MAX_BYTES = 512_000


def _read_json(path: Path) -> Any:
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _brain_models() -> dict[str, str]:
    try:
        from core.brain import conductor
    except Exception:  # the brains are optional for this read
        return {}
    return {name: str(getattr(conductor, f"{name.upper()}_MODEL", "")) for name in ("talk", "seek", "keep", "study")}


def running_versions() -> dict[str, Any]:
    """The version file as this server sees it, with each brain's current model from the conductor."""
    versions = _read_json(VERSIONS_FILE)
    if not isinstance(versions, dict):
        return {}
    models = _brain_models()
    nodes = versions.get("nodes")
    if isinstance(nodes, dict):
        for key, node in nodes.items():
            if isinstance(node, dict) and models.get(key):
                node["model"] = models[key]
    return versions


def pending_updates() -> list[dict[str, Any]]:
    if not PENDING_DIR.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for folder in sorted(PENDING_DIR.iterdir(), reverse=True):
        if not folder.is_dir() or not UPDATE_ID.match(folder.name):
            continue
        manifest = _read_json(folder / "manifest.json")
        if not isinstance(manifest, dict):
            continue
        manifest["id"] = folder.name
        manifest["ready"] = (folder / "ZAENIA.exe").is_file() and (folder / "dist-web" / "index.html").is_file()
        found.append(manifest)
    return found[:10]


def install_history() -> list[dict[str, Any]]:
    log = _read_json(INSTALL_LOG)
    return [item for item in log if isinstance(item, dict)][-50:][::-1] if isinstance(log, list) else []


def create_update_router(require_api_authentication: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/api/updates", dependencies=[Depends(require_api_authentication)], tags=["updates"])

    @router.get("")
    def updates() -> dict[str, Any]:
        last = _read_json(LAST_RESULT)
        return {"running": running_versions(), "pending": pending_updates(), "installed": install_history(),
                "lastInstall": last if isinstance(last, dict) else None}

    return router
