"""User-selected approval policies and receipts; undo refuses changed state."""
from copy import deepcopy
import hashlib
import json

from core.assistant_platform.store import Conflict

KINDS = frozenset({"task.create", "calendar.create", "memory.remember", "memory.forget", "app.launch", "workspace.restore"})

def memory_fingerprint(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ActionHistory:
    def __init__(self, store): self.store = store

    def policy(self):
        saved = self.store.get("settings", "approvals")
        if saved: return saved
        from core.voice_listener.cognitive_filter import load_config
        voice = (load_config().get("voice_authorization") or {}).get("auto_confirm", [])
        return {"voiceAutomatic": [kind for kind in voice if kind in KINDS and kind != "memory.forget"], "chatAutomatic": []}

    def save_policy(self, body):
        if not isinstance(body,dict) or set(body)-{"voiceAutomatic","chatAutomatic"}:
            raise ValueError("Use only the supported voice/chat approval choices.")
        result = {}
        for key in ("voiceAutomatic", "chatAutomatic"):
            values = body.get(key, [])
            if not isinstance(values, list) or any(kind not in KINDS-{ "memory.forget"} for kind in values):
                raise ValueError("Choose supported actions; forgetting memory always requires review.")
            result[key] = list(dict.fromkeys(values))
        return self.store.put("settings", result, "approvals")

    def receipt(self, kind, label, *, before=None, after=None, target=None):
        undoable = kind in {"task.create", "task.update", "memory.remember", "calendar.create"} and after is not None
        if kind == "memory.remember":
            undoable = before is None and after is not None
            before = {"existed": True} if before is not None else None
            after = {"id": after["id"], "key": after["key"], "sha256": memory_fingerprint(after)} if after else None
        return self.store.put("receipt", {"kind": kind, "label": label, "before": deepcopy(before), "after": deepcopy(after),
            "target": target, "undoable": undoable, "status": "completed"})

    def public(self):
        return [{key: value for key, value in row.items() if key not in {"before", "after"}} for row in self.store.list("receipt")[:100]]

    def undo(self, identifier, authorize):
        record = self.store.get("receipt", identifier)
        if not record or not record.get("undoable") or record["status"] != "completed":
            raise ValueError("This action has no available undo.")
        kind, target, after, before = (record[key] for key in ("kind", "target", "after", "before"))
        # Domain locks must cover compare + mutation. Receipts never restore over
        # a later edit merely because it has the same title.
        if kind.startswith("task."):
            if authorize("ui.tasks.delete" if kind == "task.create" else "ui.tasks.write") is False: raise PermissionError("Undo permission denied.")
            from core.api import ui_tasks
            from core.foundation.security.io import file_lock
            path, lock = ui_tasks._paths()
            with file_lock(lock):
                tasks = ui_tasks._read(path)
                current = next((item for item in tasks if item["id"] == target), None)
                if current != after: raise Conflict("The task changed after this action; Undo would overwrite newer work.")
                tasks = [item for item in tasks if item["id"] != target] if kind == "task.create" else [before if item["id"] == target else item for item in tasks]
                ui_tasks._write(path, tasks)
        elif kind == "memory.remember":
            if authorize("memory.write") is False: raise PermissionError("Undo permission denied.")
            from core.personal_memory import MemoryStore
            memory = MemoryStore()
            # Store only a fingerprint in receipts, never another copy of a fact.
            with memory._connection() as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    row = db.execute("SELECT * FROM memories WHERE id=?", (target,)).fetchone()
                    if row is None or memory_fingerprint(dict(row)) != after["sha256"]:
                        raise Conflict("The memory changed after this action; Undo would overwrite newer work.")
                    db.execute("DELETE FROM memories WHERE id=?", (target,))
                    db.commit()
                except BaseException:
                    db.rollback(); raise
        elif kind == "calendar.create":
            if authorize("ui.calendar.delete") is False: raise PermissionError("Undo permission denied.")
            from core.google_calendar_sync.google_calendar_api import status
            if status().get("connected"):
                raise ValueError("This calendar is connected to Google. Review/delete the event in Calendar so remote synchronization is handled explicitly.")
            from core.api.ui_calendar import _store
            store = _store()
            with store.db() as db, db:
                row = db.execute("SELECT body FROM events WHERE id=?", (target,)).fetchone()
                if row is None or json.loads(row[0]) != after:
                    raise Conflict("The event changed after this action; Undo would overwrite newer work.")
                db.execute("DELETE FROM events WHERE id=?", (target,))
                db.execute("DELETE FROM outbox WHERE event_id=?", (target,))
        record.update(status="undone", undoable=False)
        return self.store.put("receipt", record, identifier, revision=record["revision"])
