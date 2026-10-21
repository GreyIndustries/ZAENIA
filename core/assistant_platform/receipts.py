"""Post-commit action receipts. Fixture stores never write owner history."""
from pathlib import Path
from core.assistant_platform.store import ROOT, DEFAULT_PATH


def record(kind,label,*,source_path,target,after=None,before=None):
    locations={"task":ROOT/"data/ui/tasks.json","calendar":ROOT/"data/scheduling/calendar.sqlite3","memory":ROOT/"data/personal_memory/memory.sqlite3"}
    expected=locations.get(kind.split(".")[0])
    if expected is None or Path(source_path)!=expected or not DEFAULT_PATH.exists(): return
    try:
        from core.assistant_platform.service import platform
        platform().history.receipt(kind,label,before=before,after=after,target=target)
    except Exception:
        # A committed write remains committed even if its optional history fails.
        pass
