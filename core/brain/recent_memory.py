"""Bounded reads for a growing conversation journal; never changes the file."""
from pathlib import Path


def recent_lines(path: Path, *, max_bytes: int = 256 * 1024, limit: int = 200) -> list[str]:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive byte limit.")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive record limit.")
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            start = max(0, size - max_bytes)
            partial = False
            if start:
                handle.seek(start - 1)
                partial = handle.read(1) != b"\n"
            handle.seek(start)
            raw = handle.read(max_bytes)
    except OSError:
        return []
    # Starting mid-record must never turn its suffix into a memory record.
    if partial:
        _, _, raw = raw.partition(b"\n")
    return raw.decode("utf-8-sig", errors="replace").splitlines()[-limit:]
