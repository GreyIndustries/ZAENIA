"""Opt-in browser delivery of the canonical inbox, with durable per-device retries.

No credentials or notice contents enter the delivery ledger. Its only records
are hashed device ids, notice ids, retry state, and provider acceptance time.
The source inbox remains authoritative for quiet hours, snooze and cancellation.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Callable

from core.api import web_push
from core.foundation.security.io import file_lock, reject_link, protect_storage

DELIVERY_FILE = web_push.PROJECT_ROOT / "data" / "secure" / "push_delivery.sqlite3"


def category(source: str) -> str:
    if source in web_push.CATEGORIES:
        return source
    return "research" if source in ("research_ready", "watch", "web_agent") else "other"


class PushDelivery:
    def __init__(self, inbox: Callable[[], dict[str, Any]] | None = None, *, path: Path = DELIVERY_FILE,
                 subs_path: Path = web_push.SUBS_FILE, sender: Callable[..., str] = web_push.send_one,
                 clock: Callable[[], float] = time.time):
        self.path, self.subs_path, self.inbox = Path(path), Path(subs_path), inbox
        self.sender, self.clock = sender, clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path == DELIVERY_FILE:
            protect_storage(self.path.parent)
        with self._db() as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS deliveries (
                    notice TEXT NOT NULL, device TEXT NOT NULL, generation TEXT NOT NULL,
                    state TEXT NOT NULL, attempts INTEGER NOT NULL, next_attempt REAL NOT NULL,
                    updated REAL NOT NULL, error TEXT,
                    PRIMARY KEY(notice,device,generation)
                );
            """)

    @contextmanager
    def _db(self):
        with file_lock(self.path.with_suffix(".lock")):
            reject_link(self.path)
            for suffix in ("-journal", "-wal", "-shm"):
                reject_link(Path(str(self.path) + suffix))
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                yield db
            finally:
                db.close()

    def _claim(self, notice: str, device: str, generation: str, *, test: bool = False) -> int:
        now = self.clock()
        with self._db() as db, db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM deliveries WHERE notice=? AND device=? AND generation=?",
                                  (notice, device, generation)).fetchone()
            if previous and ((previous["updated"] + 30 > now if test else previous["state"] in ("accepted", "failed", "gone")) or previous["next_attempt"] > now):
                return 0
            attempts = previous["attempts"] + 1 if previous and not test else 1
            db.execute("INSERT OR REPLACE INTO deliveries VALUES(?,?,?,'sending',?,?,?,NULL)",
                       (notice, device, generation, attempts, now + 120, now))
            return attempts

    def _attempt(self, item: dict[str, Any], notice: dict[str, Any], *, test: bool = False) -> str:
        identity = web_push.device_id(item["endpoint"])
        generation = "manual" if test else notice.get("snoozedUntil") or "initial"
        identifier = "test" if test else notice["id"]
        attempts = self._claim(identifier, identity, generation, test=test)
        if not attempts:
            return "unchanged"
        options = web_push.preferences(item.get("preferences"))
        preview = options["preview"] or test
        title = notice["title"] if preview else "ZAE reminder" if category(notice["source"]) in ("reminder", "calendar", "task", "training") else "ZAE update"
        body = notice["message"] if preview else "Open ZAE to view your notification."
        expires = notice.get("expiresAt")
        ttl = max(1, min(3600, int(datetime.fromisoformat(expires).timestamp() - self.clock()))) if expires else 3600
        try:
            result = self.sender(item, title, body, notice_id=f"{identifier}:{generation}", ttl=ttl)
        except Exception:
            result = "network"
        state = "accepted" if result == "accepted" else "gone" if result in ("http_404", "http_410") else "retry"
        if result in ("invalid_subscription", "http_400", "http_401", "http_403", "http_413") or attempts >= 8 and state == "retry":
            state = "failed"
        now = self.clock()
        with self._db() as db, db:
            db.execute("UPDATE deliveries SET state=?,next_attempt=?,updated=?,error=? WHERE notice=? AND device=? AND generation=?",
                       (state, now + (30 if test else min(900, 30 * 2 ** min(attempts - 1, 5))), now,
                        None if result == "accepted" else result, identifier, identity, generation))
        if state == "gone":
            web_push.unsubscribe(item["endpoint"], self.subs_path)
        return result

    def tick(self) -> int:
        items = web_push.subscriptions(self.subs_path)
        if not items or self.inbox is None:
            return 0
        snapshot = self.inbox()
        eligible = [n for n in snapshot["notifications"] if n["canInterrupt"] and not n.get("readAt")]
        count, attempted = 0, 0
        # Newest first, bounded work; progress is durable so the next tick continues.
        for notice in eligible:
            for item in items:
                if attempted >= 10 or self._stop.is_set():
                    return count
                if category(notice["source"]) in web_push.preferences(item.get("preferences"))["categories"]:
                    result = self._attempt(item, notice)
                    attempted += result != "unchanged"
                    count += result == "accepted"
        with self._db() as db, db:
            db.execute("DELETE FROM deliveries WHERE updated<?", (self.clock() - 90 * 86400,))
        return count

    def test(self, device: str | None = None) -> dict[str, Any]:
        items = web_push.subscriptions(self.subs_path)
        if device:
            items = [item for item in items if web_push.device_id(item["endpoint"]) == device]
        if not items:
            raise ValueError("This browser isn't connected. Turn on notifications here first.")
        results = [{"id": web_push.device_id(item["endpoint"]), "result": self._attempt(item, {
            "id": "test", "source": "other", "title": "ZAE test notification",
            "message": "Your browser received ZAE's test notification.",
        }, test=True)} for item in items]
        return {"sent": sum(r["result"] == "accepted" for r in results), "attempted": len(items), "results": results,
                "meaning": "Accepted by the push service; display on the phone is not confirmed."}

    def status(self) -> dict[str, Any]:
        devices = []
        with self._db() as db:
            for item in web_push.subscriptions(self.subs_path):
                identity = web_push.device_id(item["endpoint"])
                latest = db.execute("SELECT state,error,updated FROM deliveries WHERE device=? ORDER BY updated DESC LIMIT 1", (identity,)).fetchone()
                accepted = db.execute("SELECT MAX(updated) FROM deliveries WHERE device=? AND state='accepted'", (identity,)).fetchone()[0]
                retries = db.execute("SELECT COUNT(*) FROM deliveries WHERE device=? AND state='retry'", (identity,)).fetchone()[0]
                devices.append({"id": identity, "label": item.get("label", "Browser"),
                                "preferences": web_push.preferences(item.get("preferences")), "added": item.get("added"),
                                "lastAcceptedAt": datetime.fromtimestamp(accepted, timezone.utc).isoformat() if accepted else None,
                                "lastResult": latest["error"] or latest["state"] if latest else None,
                                "deliveryState": latest["state"] if latest else None,
                                "retryRecords": retries})
        return {"devices": devices, "transportAvailable": importlib.util.find_spec("pywebpush") is not None,
                "workerRunning": bool(self._thread and self._thread.is_alive() and not self._stop.is_set()),
                "workerError": self.last_error, "categories": list(web_push.CATEGORIES)}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def run():
            while not self._stop.is_set():
                try:
                    self.tick()
                    self.last_error = None
                except Exception as error:
                    self.last_error = type(error).__name__
                self._stop.wait(15)
        self._thread = threading.Thread(target=run, name="zaenia-browser-push", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


_SERVICE: PushDelivery | None = None
_SERVICE_LOCK = threading.Lock()


def push_delivery() -> PushDelivery:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = PushDelivery()
        return _SERVICE
