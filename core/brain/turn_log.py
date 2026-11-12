"""A record of how each conversation turn went through the SE (Grey, 2026-11-08), so changes can be measured.

One line per turn: when, route, which model answered, level, time to first text, total time, whether Talk needed the
filler or Seek took over, how many sources were used and how the citation check went. Never the words of the turn.
Only the real server writes data/ui/se_turns.jsonl (the last 2,000 turns); tests and tools keep theirs in memory.
"""
from __future__ import annotations

import json
import sys
import threading
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = PROJECT_ROOT / "data" / "ui" / "se_turns.jsonl"
KEEP = 2000
_lock = threading.Lock()
_recent: deque[dict[str, Any]] = deque(maxlen=KEEP)
_loaded = False


def is_real_server() -> bool:
    """True only inside ZAE's server process, so test runs never touch her real records."""
    return getattr(getattr(sys.modules.get("__main__"), "__spec__", None), "name", "") == "core.api.server"


def _load(path: Path) -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-KEEP:]:
            try:
                _recent.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass


def record(row: dict[str, Any], *, path: Path | None = None) -> None:
    row = {"at": datetime.now().isoformat(timespec="seconds"), **row}
    target = path if path is not None else (LOG_FILE if is_real_server() else None)
    with _lock:
        if target is not None:
            _load(target)
        _recent.append(row)
        if target is None:
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
            if target.stat().st_size > 1_000_000:  # keep the file small: rewrite it with the recent turns
                temp = target.with_suffix(".tmp")
                temp.write_text("".join(json.dumps(item) + "\n" for item in _recent), encoding="utf-8")
                temp.replace(target)
        except OSError:
            pass


def _percentile(values: list[int], share: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * share))]


def summary(limit: int = 200) -> dict[str, Any]:
    """The recent turns in numbers, for Arena > SE & tools."""
    with _lock:
        if is_real_server():
            _load(LOG_FILE)
        rows = list(_recent)[-limit:]
    first = [int(row["firstTextMs"]) for row in rows if row.get("firstTextMs") is not None]
    checked = sum(int(row.get("claimsChecked") or 0) for row in rows)
    return {"turns": len(rows), "firstTextP50Ms": _percentile(first, .5), "firstTextP95Ms": _percentile(first, .95),
            "fillerTurns": sum(1 for row in rows if row.get("filler")), "fallbackTurns": sum(1 for row in rows if row.get("fallback")),
            "failedTurns": sum(1 for row in rows if row.get("outcome") == "failed"),
            "byRoute": dict(Counter(str(row.get("route")) for row in rows).most_common(8)),
            "byModel": dict(Counter(str(row.get("model")) for row in rows).most_common(6)),
            "claimsChecked": checked, "claimsUnsupported": sum(int(row.get("claimsUnsupported") or 0) for row in rows)}
