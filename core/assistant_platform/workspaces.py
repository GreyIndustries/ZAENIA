"""Named layouts and session context; restoring never silently launches apps."""
import math
from core.assistant_platform.store import text

WINDOWS = frozenset({"status", "security", "tasks", "calendar", "notes", "news", "files", "assistant", "system", "workbench", "music", "fitness"})


def validate_workspace(body):
    windows = body.get("windows", [])
    if not isinstance(windows, list) or len(windows)>len(WINDOWS):
        raise ValueError("Choose a bounded set of workspace windows.")
    result, seen = [], set()
    for item in windows:
        if not isinstance(item, dict) or item.get("id") not in WINDOWS or item["id"] in seen:
            raise ValueError("Use unique known workspace windows.")
        seen.add(item["id"])
        rect = {}
        for key in ("x", "y", "w", "h"):
            value = item.get(key)
            if type(value) not in (int, float) or not math.isfinite(value): raise ValueError("Window positions must be finite numbers.")
            rect[key] = float(value)
        rect["w"] = min(.98, max(.26, rect["w"])); rect["h"] = min(.96, max(.3, rect["h"]))
        rect["x"] = min(1-rect["w"], max(0, rect["x"])); rect["y"] = min(1-rect["h"], max(0, rect["y"]))
        result.append({"id": item["id"], **rect, "z": len(result)+11, "minimized": item.get("minimized") is True})
    apps = body.get("apps", [])
    if not isinstance(apps, list) or len(apps)>12 or any(not isinstance(item, str) or len(item)>64 for item in apps):
        raise ValueError("Choose up to twelve registered app IDs.")
    return {"name": text(body.get("name"), "Workspace name", 80), "windows": result,
        "apps": list(dict.fromkeys(apps)), "projectId": body.get("projectId") or None,
        "note": str(body.get("note") or "")[:2000]}
