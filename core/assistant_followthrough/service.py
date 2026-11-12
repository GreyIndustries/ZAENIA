"""An in-app reminder inbox. This module never sends email, push, or audio.

The API process may run ``start()`` while it is alive. Each poll reads local
calendar/task snapshots, reconciles obsolete reminders, and atomically promotes
due reminders into a SQLite inbox. Unique keys and a worker lease make retries,
process restarts, and concurrent API processes safe. Delivery into this inbox is
separate from the scheduling service's console/email/phone outbox.
"""
from __future__ import annotations

from contextlib import closing, contextmanager, nullcontext
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import re
import logging
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable, Iterable
import uuid
from zoneinfo import ZoneInfo

from core.foundation.security.io import reject_link, file_lock, protect_storage
from core.scheduling.service import TZ, wall

UTC = timezone.utc
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = PROJECT_ROOT / "data" / "assistant_followthrough" / "inbox.sqlite3"
DEFAULT_SETTINGS = {
    "enabled": True,
    "spoken": False,
    "quietHoursEnabled": True,
    "quietStart": "22:00",
    "quietEnd": "07:00",
    "timezone": "America/Los_Angeles",
}
LOGGER = logging.getLogger(__name__)
CATCH_UP = timedelta(hours=24)
HORIZON = timedelta(days=2)


class NotificationNotFound(LookupError):
    pass


def _instant(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Use a date and time with a UTC offset.")
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]


def _clock_time(value: Any) -> time:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("Use a quiet-hours time like 22:00.")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Use a quiet-hours time like 22:00.") from error
    if parsed.tzinfo is not None or parsed.second:
        raise ValueError("Use a quiet-hours time like 22:00.")
    return parsed


def _quiet(settings: dict[str, Any], now: datetime) -> bool:
    if not settings["quietHoursEnabled"]:
        return False
    local = now.astimezone(ZoneInfo(settings["timezone"])).time().replace(tzinfo=None)
    start, end = _clock_time(settings["quietStart"]), _clock_time(settings["quietEnd"])
    if start == end:
        return False
    return start <= local < end if start < end else local >= start or local < end


def local_calendar_snapshot() -> list[dict[str, Any]]:
    """Read saved scheduling events and their revisions without network access."""
    path = PROJECT_ROOT / "data" / "scheduling" / "calendar.sqlite3"
    if not path.exists():
        return []
    reject_link(path)
    # URI read-only mode prevents an accidental new scheduling database.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        rows = db.execute("SELECT body,revision FROM events ORDER BY id").fetchall()
    return [{**json.loads(body), "revision": revision} for body, revision in rows]


def local_task_snapshot() -> list[dict[str, Any]]:
    from core.api.ui_tasks import list_tasks
    return list_tasks()


def _occurrences(event: dict[str, Any], lower: datetime, upper: datetime) -> Iterable[datetime]:
    """Use the scheduler's Pacific wall-time/DST policy for daily/weekly events."""
    start = _instant(event["start"]).astimezone(TZ)
    recurrence = event.get("recurrence", "none")
    if recurrence not in ("none", "daily", "weekly"):
        raise ValueError("Unsupported calendar recurrence.")
    step = {"none": 0, "daily": 1, "weekly": 7}[recurrence]
    day = start.date()
    if step:
        elapsed = max(0, (lower.astimezone(TZ).date() - day).days)
        day += timedelta(days=max(0, elapsed // step - 1) * step)
    while day <= upper.astimezone(TZ).date():
        try:
            occurrence = start if day == start.date() else wall(day, start.timetz())
        except ValueError:
            # Match the scheduler: do not guess during missing/repeated hours.
            occurrence = None
        if occurrence is not None and lower <= occurrence.astimezone(UTC) <= upper:
            yield occurrence.astimezone(UTC)
        if not step:
            break
        day += timedelta(days=step)


class FollowThroughService:
    """Persistent reminders for the local API process and its connected clients.

    ``poll`` accepts explicit snapshots and an aware ``now`` for isolated tests.
    A failure reading either source aborts the entire poll before reconciliation,
    so a temporarily unavailable file never looks like a deleted task/event.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        calendar_loader: Callable[[], list[dict[str, Any]]] | None = None,
        task_loader: Callable[[], list[dict[str, Any]]] | None = None,
        poll_interval: float = 30,
    ):
        if not 1 <= poll_interval <= 60:
            raise ValueError("Poll interval must be between 1 and 60 seconds.")
        self.path = Path(path) if path is not None else DEFAULT_PATH
        self.clock = clock or (lambda: datetime.now(UTC))
        self.calendar_loader = calendar_loader or local_calendar_snapshot
        self.task_loader = task_loader or local_task_snapshot
        self.poll_interval = float(poll_interval)
        self._worker_id = uuid.uuid4().hex
        self._worker_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None
        reject_link(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(self.path.with_suffix(".lock")):
            if path is None:
                protect_storage(self.path.parent)
            if not self.path.exists():
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(descriptor)
        with self._db() as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, source_id TEXT NOT NULL,
                    revision TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                    message TEXT NOT NULL, occurrence TEXT NOT NULL, lead_minutes INTEGER NOT NULL,
                    due REAL NOT NULL, valid_until REAL NOT NULL, created REAL,
                    state TEXT NOT NULL DEFAULT 'pending', read_at TEXT, snoozed_until REAL
                );
                CREATE INDEX IF NOT EXISTS notifications_state_due ON notifications(state,due);
                CREATE TABLE IF NOT EXISTS delivery_claims (
                    notification_id TEXT NOT NULL, channel TEXT NOT NULL, generation TEXT NOT NULL,
                    PRIMARY KEY(notification_id,channel,generation)
                );
                CREATE TABLE IF NOT EXISTS worker_lease (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, expires REAL NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO settings VALUES(1,?)", (json.dumps(DEFAULT_SETTINGS),))

    @contextmanager
    def _db(self):
        with file_lock(self.path.with_suffix(".lock")):
            reject_link(self.path)
            for suffix in ("-journal", "-wal", "-shm"):
                reject_link(Path(str(self.path) + suffix))
            db = sqlite3.connect(self.path, timeout=15)
            db.row_factory = sqlite3.Row
            try:
                yield db
            finally:
                db.close()

    def _now(self, now: datetime | None = None) -> datetime:
        return _instant(now if now is not None else self.clock())

    def get_settings(self) -> dict[str, Any]:
        with self._db() as db:
            return {**DEFAULT_SETTINGS, **json.loads(db.execute("SELECT body FROM settings WHERE id=1").fetchone()[0])}

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(patch, dict) or not patch or set(patch) - DEFAULT_SETTINGS.keys():
            raise ValueError("Choose valid follow-through settings.")
        for key in ("enabled", "spoken", "quietHoursEnabled"):
            if key in patch and type(patch[key]) is not bool:
                raise ValueError(f"{key} must be true or false.")
        for key in ("quietStart", "quietEnd"):
            if key in patch:
                _clock_time(patch[key])
        if "timezone" in patch:
            if not isinstance(patch["timezone"], str) or len(patch["timezone"]) > 100:
                raise ValueError("Choose a valid timezone.")
            try:
                ZoneInfo(patch["timezone"])
            except (ValueError, KeyError) as error:
                raise ValueError("Choose a valid timezone.") from error
        with self._db() as db, db:
            db.execute("BEGIN IMMEDIATE")
            settings = {**DEFAULT_SETTINGS, **json.loads(db.execute("SELECT body FROM settings WHERE id=1").fetchone()[0]), **patch}
            db.execute("UPDATE settings SET body=? WHERE id=1", (json.dumps(settings),))
        return settings

    @staticmethod
    def _snapshot(records: Any, source: str) -> list[dict[str, Any]]:
        if not isinstance(records, list) or len(records) > 10000:
            raise ValueError(f"The saved {source} snapshot is invalid.")
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"] or record["id"] in seen:
                raise ValueError(f"The saved {source} snapshot is invalid.")
            seen.add(record["id"])
        return records

    def _plan(self, events: list[dict[str, Any]], tasks: list[dict[str, Any]], now: datetime):
        sources: dict[tuple[str, str], str] = {}
        planned: list[tuple[Any, ...]] = []

        def add(source, source_id, revision, kind, title, message, occurrence, lead, due, valid_until):
            identity = [source, source_id, revision, _iso(occurrence), lead]
            planned.append(("ft-" + _digest(identity), source, source_id, revision, kind, title, message,
                            _iso(occurrence), lead, due.timestamp(), valid_until.timestamp()))

        for event in events:
            title = str(event.get("title") or "Untitled event")[:500]
            revision = _digest({key: event.get(key) for key in ("revision", "title", "start", "recurrence")})
            sources[("calendar", event["id"])] = revision
            for occurrence in _occurrences(event, now - CATCH_UP, now + HORIZON):
                for lead in (60, 15, 0):
                    due = occurrence - timedelta(minutes=lead)
                    valid_until = occurrence - timedelta(minutes=15) if lead == 60 else occurrence if lead == 15 else occurrence + CATCH_UP
                    if valid_until <= now:
                        continue
                    message = f"{title} starts within {'an hour' if lead == 60 else '15 minutes'}." if lead else f"{title} has reached its scheduled start."
                    add("calendar", event["id"], revision, "calendar.upcoming" if lead else "calendar.start", title, message, occurrence, lead, due, valid_until)

        for task in tasks:
            if task.get("archived") or task.get("status") == "Completed" or not task.get("deadline"):
                continue
            deadline = _instant(task["deadline"])
            title = str(task.get("title") or "Untitled task")[:500]
            revision = _digest({key: task.get(key) for key in ("title", "deadline", "updatedAt", "status", "priority")})
            sources[("task", task["id"])] = revision
            for lead in (60, 0):
                valid_until = deadline if lead else deadline + CATCH_UP
                due = deadline - timedelta(minutes=lead)
                if valid_until <= now or due > now + HORIZON:
                    continue
                kind = "task.approaching" if lead else "task.overdue"
                message = f"{title} is due within an hour." if lead else f"{title} has reached its deadline and is still open."
                add("task", task["id"], revision, kind, title, message, deadline, lead, due, valid_until)
        return sources, planned

    def poll(self, now: datetime | None = None, *, events=None, tasks=None) -> int:
        now = self._now(now)
        events = self._snapshot(self.calendar_loader() if events is None else events, "calendar")
        tasks = self._snapshot(self.task_loader() if tasks is None else tasks, "task")
        # Complete/validate both plans before mutating the inbox.
        sources, planned = self._plan(events, tasks, now)
        stamp = now.timestamp()
        with self._db() as db, db:
            db.execute("BEGIN IMMEDIATE")
            settings = {**DEFAULT_SETTINGS, **json.loads(db.execute("SELECT body FROM settings WHERE id=1").fetchone()[0])}
            # Only calendar/task notices are planned here; posted notices (e.g. email) are left alone.
            for row in db.execute("SELECT id,source,source_id,revision FROM notifications WHERE state IN ('pending','ready') AND source IN ('calendar','task')").fetchall():
                if sources.get((row["source"], row["source_id"])) != row["revision"]:
                    db.execute("UPDATE notifications SET state='cancelled' WHERE id=?", (row["id"],))
            db.execute("UPDATE notifications SET state='expired' WHERE state='pending' AND valid_until<=?", (stamp,))
            if not settings["enabled"]:
                return 0
            db.executemany("""INSERT OR IGNORE INTO notifications
                (id,source,source_id,revision,kind,title,message,occurrence,lead_minutes,due,valid_until)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", planned)
            delivered = db.execute("UPDATE notifications SET state='ready',created=? WHERE state='pending' AND due<=? AND valid_until>?", (stamp, stamp, stamp)).rowcount
            # Only terminal records outside every catch-up window are pruned.
            db.execute("DELETE FROM notifications WHERE state IN ('read','cancelled','expired') AND valid_until<?", ((now - timedelta(days=90)).timestamp(),))
            db.execute("DELETE FROM delivery_claims WHERE notification_id NOT IN (SELECT id FROM notifications)")
            return delivered

    def post(self, source: str, source_id: str, title: str, message: str, *, hours: float = 12,
             now: datetime | None = None) -> str | None:
        """Add a ready-now notice from another ZAE module (for example an important email).

        Posting the same source item twice is a no-op. Returns the notice id,
        or None while follow-through is switched off.
        """
        if source in ("calendar", "task") or not re.fullmatch(r"[a-z][a-z_]{1,30}", source):
            raise ValueError("Use a module name other than calendar or task.")
        now = self._now(now)
        stamp = now.timestamp()
        notice_id = "ft-" + _digest([source, str(source_id)])
        with self._db() as db, db:
            settings = {**DEFAULT_SETTINGS, **json.loads(db.execute("SELECT body FROM settings WHERE id=1").fetchone()[0])}
            if not settings["enabled"]:
                return None
            db.execute("""INSERT OR IGNORE INTO notifications
                (id,source,source_id,revision,kind,title,message,occurrence,lead_minutes,due,valid_until,created,state)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'ready')""",
                (notice_id, source, str(source_id)[:200], "posted", f"{source}.important", str(title)[:500], str(message)[:2000],
                 _iso(now), 0, stamp, stamp + hours * 3600, stamp)).rowcount
        # Browser delivery reads this canonical inbox in its own worker. This
        # keeps posting offline-safe and applies the same quiet/snooze rules to
        # posted notices and scheduled calendar/task notices.
        return notice_id

    def list_notifications(self, include_read: bool = False, limit: int = 100, now: datetime | None = None) -> dict[str, Any]:
        if type(include_read) is not bool or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("Choose a notification limit from 1 to 500.")
        now = self._now(now)
        settings = self.get_settings()
        quiet = _quiet(settings, now)
        with self._db() as db:
            where = "state IN ('ready','read')" if include_read else "state='ready'"
            rows = db.execute(f"SELECT * FROM notifications WHERE {where} ORDER BY due DESC,id LIMIT ?", (limit,)).fetchall()
            unread = db.execute("SELECT COUNT(*) FROM notifications WHERE state='ready'").fetchone()[0]
        notifications = []
        for row in rows:
            snoozed = row["snoozed_until"] is not None and row["snoozed_until"] > now.timestamp()
            snooze_catchup = row["snoozed_until"] is not None and row["snoozed_until"] <= now.timestamp() < row["snoozed_until"] + CATCH_UP.total_seconds()
            can_interrupt = bool(settings["enabled"] and not quiet and not snoozed and row["state"] == "ready" and (row["valid_until"] > now.timestamp() or snooze_catchup))
            notifications.append({
                "id": row["id"], "source": row["source"], "sourceId": row["source_id"],
                "kind": row["kind"], "title": row["title"], "message": row["message"],
                "occurrence": row["occurrence"], "leadMinutes": row["lead_minutes"],
                "dueAt": _iso(datetime.fromtimestamp(row["due"], UTC)),
                "expiresAt": _iso(datetime.fromtimestamp(max(row["valid_until"], row["snoozed_until"] + CATCH_UP.total_seconds() if row["snoozed_until"] else row["valid_until"]), UTC)),
                "createdAt": _iso(datetime.fromtimestamp(row["created"], UTC)) if row["created"] is not None else None,
                "readAt": row["read_at"],
                "snoozedUntil": _iso(datetime.fromtimestamp(row["snoozed_until"], UTC)) if row["snoozed_until"] is not None else None,
                "canInterrupt": can_interrupt, "canSpeak": bool(can_interrupt and settings["spoken"]),
            })
        return {"notifications": notifications, "unreadCount": unread, "settings": settings, "quiet": quiet, "workerRunning": self.is_running}

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def acknowledge(self, notification_id: str) -> dict[str, Any]:
        with self._db() as db, db:
            changed = db.execute("UPDATE notifications SET state='read',read_at=COALESCE(read_at,?),snoozed_until=NULL WHERE id=? AND state IN ('ready','read')", (_iso(self._now()), notification_id)).rowcount
            if not changed:
                raise NotificationNotFound(notification_id)
        return {"id": notification_id, "acknowledged": True}

    def snooze(self, notification_id: str, minutes: int = 15) -> dict[str, Any]:
        if type(minutes) is not int or not 1 <= minutes <= 1440:
            raise ValueError("Snooze for 1 to 1440 minutes.")
        until = self._now() + timedelta(minutes=minutes)
        with self._db() as db, db:
            changed = db.execute("UPDATE notifications SET snoozed_until=? WHERE id=? AND state='ready'", (until.timestamp(), notification_id)).rowcount
            if not changed:
                raise NotificationNotFound(notification_id)
        return {"id": notification_id, "snoozedUntil": _iso(until)}

    def claim_delivery(self, notification_id: str, channel: str = "speech") -> dict[str, Any]:
        """Claim optional speech once across all apps/voice processes.

        This does not speak or acknowledge the inbox item. Quiet hours, explicit
        spoken opt-in, current reminder validity, and snoozing are rechecked in
        the same transaction as the durable claim. A completed snooze creates
        one new delivery generation. A failed/crashed speaker keeps its claim
        to favor silence over duplicate unsolicited speech after a restart.
        """
        if channel != "speech":
            raise ValueError("Choose the supported delivery channel: speech.")
        now = self._now()
        stamp = now.timestamp()
        with self._db() as db, db:
            db.execute("BEGIN IMMEDIATE")
            settings = {**DEFAULT_SETTINGS, **json.loads(db.execute("SELECT body FROM settings WHERE id=1").fetchone()[0])}
            row = db.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone()
            if row is None:
                raise NotificationNotFound(notification_id)
            snoozed_until = row["snoozed_until"]
            snoozed = snoozed_until is not None and snoozed_until > stamp
            snooze_catchup = snoozed_until is not None and snoozed_until <= stamp < snoozed_until + CATCH_UP.total_seconds()
            eligible = settings["enabled"] and settings["spoken"] and not _quiet(settings, now) and not snoozed and row["state"] == "ready" and (row["valid_until"] > stamp or snooze_catchup)
            if not eligible:
                return {"id": notification_id, "claimed": False}
            generation = str(snoozed_until) if snoozed_until is not None else "initial"
            claimed = db.execute("INSERT OR IGNORE INTO delivery_claims VALUES(?,?,?)", (notification_id, channel, generation)).rowcount == 1
        return {"id": notification_id, "claimed": claimed}

    def _lease(self) -> bool:
        now = self._now().timestamp()
        with self._db() as db, db:
            db.execute("BEGIN IMMEDIATE")
            lease = db.execute("SELECT owner,expires FROM worker_lease WHERE id=1").fetchone()
            if lease and lease["owner"] != self._worker_id and lease["expires"] > now:
                return False
            db.execute("INSERT OR REPLACE INTO worker_lease VALUES(1,?,?)", (self._worker_id, now + max(90, self.poll_interval * 3)))
        return True

    def _release(self):
        with self._db() as db, db:
            db.execute("DELETE FROM worker_lease WHERE id=1 AND owner=?", (self._worker_id,))

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    if self._lease():
                        self.poll()
                        self.last_error = None
                except Exception as error:
                    # Do not persist/log exception text that may include personal data.
                    self.last_error = type(error).__name__
                    LOGGER.warning("Local follow-through poll failed (%s).", self.last_error)
                if self._stop.wait(self.poll_interval):
                    return
        finally:
            self._release()

    def start(self) -> bool:
        """Start one local thread; the DB lease allows only one active poller.

        A replacement waits and retries while another process owns the lease,
        so a crash cannot leave the replacement permanently inactive.
        """
        with self._worker_lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="zae-local-followthrough", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._worker_lock:
            self._stop.set()
            if self._thread is not None:
                self._thread.join(timeout=5)
