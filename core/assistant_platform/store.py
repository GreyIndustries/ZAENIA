"""Private, transactional records for the assistant's new capabilities."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

from core.foundation.security.io import file_lock, protect_storage, reject_link

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "data" / "assistant_platform" / "platform.sqlite3"


def now_text():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text(value, label="Name", limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be 1–{limit} printable characters.")
    return " ".join(value.split())


class Conflict(ValueError):
    pass


class PlatformStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else DEFAULT_PATH
        protect_storage(self.path.parent)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,revision INTEGER NOT NULL,updated TEXT NOT NULL,PRIMARY KEY(kind,id))")

    @contextmanager
    def connection(self):
        with file_lock(self.path.with_suffix(".lock")):
            reject_link(self.path)
            db = sqlite3.connect(self.path, timeout=10)
            try:
                with db:
                    db.row_factory = sqlite3.Row
                    db.execute("PRAGMA secure_delete=ON")
                    yield db
            finally:
                db.close()

    @staticmethod
    def decode(row):
        return {**json.loads(row["payload"]), "id": row["id"], "revision": row["revision"], "updatedAt": row["updated"]}

    def list(self, kind, *, limit=None):
        with self.connection() as db:
            if limit is not None and (type(limit) is not int or not 1<=limit<=2000): raise ValueError('Invalid record limit.')
            return [self.decode(row) for row in db.execute("SELECT * FROM records WHERE kind=? ORDER BY updated DESC,id"+(' LIMIT ?' if limit is not None else ''), (kind,limit) if limit is not None else (kind,))]

    def get(self, kind, identifier):
        with self.connection() as db:
            row = db.execute("SELECT * FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
            return self.decode(row) if row else None

    def put(self, kind, payload, identifier=None, *, revision=None):
        identifier = identifier or uuid.uuid4().hex
        safe = {key: value for key, value in payload.items() if key not in {"id", "revision", "updatedAt"}}
        encoded = json.dumps(safe, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 2_000_000:
            raise ValueError("Record is too large.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
            old = row[0] if row else 0
            if revision is not None and old != revision:
                raise Conflict("This item changed. Refresh it before saving.")
            if row is None and db.execute("SELECT COUNT(*) FROM records WHERE kind=?", (kind,)).fetchone()[0] >= 2000:
                raise ValueError("This collection is full; review old items first.")
            db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)", (kind, identifier, encoded, old + 1, now_text()))
        return self.get(kind, identifier)

    def delete(self, kind, identifier, *, revision=None):
        with self.connection() as db:
            if revision is not None:
                row = db.execute("SELECT revision FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
                if row is None or row[0] != revision:
                    raise Conflict("This item changed. Refresh it before removing.")
            return db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, identifier)).rowcount > 0

    def patch(self, kind, identifier, changes, *, preserve_true=()):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
            if row is None: return None
            payload = json.loads(row["payload"])
            changes={key:value for key,value in changes.items() if key not in {"id","revision","updatedAt"}}
            for key in preserve_true:
                if payload.get(key) is True: changes[key]=True
            payload.update(changes)
            db.execute("UPDATE records SET payload=?,revision=revision+1,updated=? WHERE kind=? AND id=?",
                (json.dumps(payload,ensure_ascii=False,allow_nan=False),now_text(),kind,identifier))
        return self.get(kind,identifier)
