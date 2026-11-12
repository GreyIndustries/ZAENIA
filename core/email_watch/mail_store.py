"""Local, searchable copy of Grey's Gmail, kept on this PC (data/email/mail.db).

Filled by core/email_watch/imap_mail.py over IMAP, so search, summaries and
"emails from Rivera last week" work offline once mail is copied. Message ids
are Gmail's own ids (the hex X-GM-MSGID), the same ids the Gmail API and the
Gmail website use, so links and the important-email "seen" list stay valid.

Each message also keeps Gmail's inbox category (primary, promotions, social,
updates, forums), read with Gmail's own search over IMAP, and the size it has
in Gmail, so big messages fetch their attachments on demand.

Reply drafts live here too. A draft is only text until Grey approves it in the
app; nothing in this module sends mail.

Email content is untrusted: callers present it as reference, never as
instructions, and it never grants any action.
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "data" / "email" / "mail.db"
BODY_KEEP = 20000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages(
  id TEXT PRIMARY KEY, uid INTEGER NOT NULL DEFAULT 0, thread_id TEXT, message_id TEXT, in_reply_to TEXT,
  refs TEXT, reply_to TEXT, from_name TEXT, from_address TEXT, to_addrs TEXT, cc_addrs TEXT, subject TEXT,
  date TEXT, internal_ms INTEGER NOT NULL DEFAULT 0, labels TEXT NOT NULL DEFAULT '[]', list_unsubscribe INTEGER NOT NULL DEFAULT 0,
  attachments TEXT NOT NULL DEFAULT '[]', snippet TEXT, body TEXT, category TEXT, size INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS messages_time ON messages(internal_ms DESC);
CREATE INDEX IF NOT EXISTS messages_uid ON messages(uid);
CREATE INDEX IF NOT EXISTS messages_thread ON messages(thread_id);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
  subject, from_name, from_address, body, content='messages', content_rowid='rowid', tokenize='unicode61');
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, subject, from_name, from_address, body)
  VALUES (new.rowid, new.subject, new.from_name, new.from_address, new.body); END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, subject, from_name, from_address, body)
  VALUES ('delete', old.rowid, old.subject, old.from_name, old.from_address, old.body); END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE OF subject, from_name, from_address, body ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, subject, from_name, from_address, body)
  VALUES ('delete', old.rowid, old.subject, old.from_name, old.from_address, old.body);
  INSERT INTO messages_fts(rowid, subject, from_name, from_address, body)
  VALUES (new.rowid, new.subject, new.from_name, new.from_address, new.body); END;
CREATE TABLE IF NOT EXISTS sync(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS drafts(
  id TEXT PRIMARY KEY, reply_to_id TEXT NOT NULL, to_addrs TEXT NOT NULL, cc_addrs TEXT NOT NULL DEFAULT '[]',
  subject TEXT NOT NULL, body TEXT NOT NULL, in_reply_to TEXT, refs TEXT, status TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, sent_at TEXT, sent_message_id TEXT,
  verified INTEGER NOT NULL DEFAULT 0, error TEXT);
"""

_COLUMNS = ("id", "uid", "thread_id", "message_id", "in_reply_to", "refs", "reply_to", "from_name", "from_address",
            "to_addrs", "cc_addrs", "subject", "date", "internal_ms", "labels", "list_unsubscribe", "attachments",
            "snippet", "body", "size")
_LIST_COLUMNS = ", ".join(c for c in _COLUMNS if c != "body") + ", category"
_ADDED = {"category": "TEXT", "size": "INTEGER NOT NULL DEFAULT 0"}  # columns newer than the first mail.db
CATEGORIES = ("primary", "promotions", "social", "updates", "forums")


def gmail_link(message_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{message_id}"


class MailStore:
    def __init__(self, path: Path = DB_FILE):
        self.path = Path(path)
        self._ready = False

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        if not self._ready:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        try:
            if not self._ready:
                db.execute("PRAGMA journal_mode=WAL")
                db.executescript(_SCHEMA)
                have = {r[1] for r in db.execute("PRAGMA table_info(messages)")}
                for column, kind in _ADDED.items():
                    if column not in have:
                        db.execute(f"ALTER TABLE messages ADD COLUMN {column} {kind}")
                db.execute("CREATE INDEX IF NOT EXISTS messages_category ON messages(category, internal_ms DESC)")
                self._ready = True
            yield db
            db.commit()
        finally:
            db.close()

    # ---- sync bookkeeping
    def get(self, key: str, default: str | None = None) -> str | None:
        with self._db() as db:
            row = db.execute("SELECT value FROM sync WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def put(self, **values: Any) -> None:
        with self._db() as db:
            db.executemany("INSERT INTO sync(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           [(k, None if v is None else str(v)) for k, v in values.items()])

    # ---- messages
    def upsert(self, messages: Iterable[dict[str, Any]]) -> int:
        rows = []
        for m in messages:
            rows.append((m["id"], int(m.get("uid") or 0), m.get("threadId"), m.get("messageId"), m.get("inReplyTo"),
                         m.get("references"), m.get("replyTo"), m.get("fromName"), m.get("fromAddress"),
                         json.dumps(m.get("to") or []), json.dumps(m.get("cc") or []), m.get("subject"), m.get("date"),
                         int(m.get("internalDate") or 0), json.dumps(m.get("labels") or []), int(bool(m.get("listUnsubscribe"))),
                         json.dumps(m.get("attachments") or []), m.get("snippet"), (m.get("body") or "")[:BODY_KEEP],
                         int(m.get("size") or 0)))
        if not rows:
            return 0
        updates = ", ".join(f"{c}=excluded.{c}" for c in _COLUMNS if c != "id")
        with self._db() as db:
            db.executemany(f"INSERT INTO messages({', '.join(_COLUMNS)}) VALUES({', '.join('?' * len(_COLUMNS))}) "
                           f"ON CONFLICT(id) DO UPDATE SET {updates}", rows)
        return len(rows)

    def update_labels(self, changes: Iterable[tuple[str, list[str], int]]) -> None:
        """(id, labels, uid) for messages already stored."""
        with self._db() as db:
            db.executemany("UPDATE messages SET labels=?, uid=? WHERE id=?",
                           [(json.dumps(labels), int(uid), mid) for mid, labels, uid in changes])

    def set_categories(self, categories: dict[str, str | None]) -> None:
        """id -> Gmail category (or None) for messages already stored."""
        with self._db() as db:
            db.executemany("UPDATE messages SET category=? WHERE id=?", [(c, mid) for mid, c in categories.items()])

    def set_attachments(self, message_id: str, attachments: list[dict[str, Any]]) -> None:
        with self._db() as db:
            db.execute("UPDATE messages SET attachments=? WHERE id=?", (json.dumps(attachments), message_id))

    def counts(self) -> dict[str, int]:
        """Unread inbox mail per Gmail category, plus all unread inbox mail."""
        with self._db() as db:
            rows = db.execute("SELECT category, COUNT(*) FROM messages WHERE labels LIKE '%\"INBOX\"%' "
                              "AND labels LIKE '%\"UNREAD\"%' GROUP BY category").fetchall()
        counts = {c: 0 for c in CATEGORIES}
        for category, number in rows:
            if category in counts:
                counts[category] = int(number)
        counts["inbox"] = sum(int(n) for _, n in rows)
        return counts

    def known_uids(self) -> dict[int, str]:
        with self._db() as db:
            return {int(r["uid"]): r["id"] for r in db.execute("SELECT id, uid FROM messages WHERE uid > 0")}

    def delete(self, ids: Iterable[str]) -> int:
        ids = list(ids)
        with self._db() as db:
            db.executemany("DELETE FROM messages WHERE id=?", [(i,) for i in ids])
        return len(ids)

    def count(self) -> int:
        with self._db() as db:
            return int(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0])

    def message(self, message_id: str) -> dict[str, Any] | None:
        with self._db() as db:
            row = db.execute(f"SELECT {', '.join(_COLUMNS)}, category FROM messages WHERE id=?", (message_id,)).fetchone()
        return _public(row, body=True) if row else None

    def by_ids(self, ids: Iterable[str], *, body: bool = True) -> list[dict[str, Any]]:
        ids = list(ids)
        if not ids:
            return []
        columns = ", ".join(_COLUMNS) + ", category" if body else _LIST_COLUMNS
        with self._db() as db:
            rows = db.execute(f"SELECT {columns} FROM messages WHERE id IN ({', '.join('?' * len(ids))}) "
                              "ORDER BY internal_ms DESC", ids).fetchall()
        return [_public(r, body=body) for r in rows]

    def thread(self, thread_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(f"SELECT {', '.join(_COLUMNS)}, category FROM messages WHERE thread_id=? ORDER BY internal_ms LIMIT ?",
                              (thread_id, max(1, min(limit, 200)))).fetchall()
        return [_public(r, body=True) for r in rows]

    def recent(self, limit: int = 30, *, label: str | None = None, before_ms: int | None = None,
               category: str | None = None) -> list[dict[str, Any]]:
        where, args = [], []
        if label:
            where.append("labels LIKE ?"); args.append(f'%"{label}"%')
        if category:
            where.append("category = ?"); args.append(category)
        if before_ms:
            where.append("internal_ms < ?"); args.append(int(before_ms))
        sql = (f"SELECT {_LIST_COLUMNS} FROM messages {'WHERE ' + ' AND '.join(where) if where else ''} "
               "ORDER BY internal_ms DESC LIMIT ?")
        with self._db() as db:
            rows = db.execute(sql, (*args, max(1, min(limit, 200)))).fetchall()
        return [_public(r, body=False) for r in rows]

    def search(self, text: str, limit: int = 20, *, sender: str | None = None) -> list[dict[str, Any]]:
        """Word search over subject, sender and body (all words must match), newest first."""
        words = [w for w in re.findall(r"[\w@.'-]+", text or "", flags=re.UNICODE) if len(w) > 1][:12]
        where, args = [], []
        if words:
            where.append("messages_fts MATCH ?")
            args.append(" ".join('"' + w.replace('"', "") + '"' for w in words))
        if sender:
            where.append("(m.from_address LIKE ? OR m.from_name LIKE ?)"); args += [f"%{sender}%", f"%{sender}%"]
        if not where:
            return []
        columns = ", ".join(f"m.{c}" for c in _COLUMNS if c != "body") + ", m.category"
        join = "JOIN messages_fts ON messages_fts.rowid = m.rowid" if words else ""
        with self._db() as db:
            rows = db.execute(f"SELECT {columns} FROM messages m {join} WHERE {' AND '.join(where)} "
                              "ORDER BY m.internal_ms DESC LIMIT ?", (*args, max(1, min(limit, 100)))).fetchall()
        return [_public(r, body=False) for r in rows]

    # ---- reply drafts (text only; sending is replies.send_draft behind the owner's approval)
    def save_draft(self, draft: dict[str, Any]) -> None:
        cols = ("id", "reply_to_id", "to_addrs", "cc_addrs", "subject", "body", "in_reply_to", "refs", "status",
                "created_at", "updated_at", "sent_at", "sent_message_id", "verified", "error")
        values = (draft["id"], draft["replyToId"], json.dumps(draft["to"]), json.dumps(draft.get("cc") or []), draft["subject"],
                  draft["body"], draft.get("inReplyTo"), draft.get("references"), draft["status"], draft["createdAt"],
                  draft["updatedAt"], draft.get("sentAt"), draft.get("sentMessageId"), int(bool(draft.get("verified"))),
                  draft.get("error"))
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
        with self._db() as db:
            db.execute(f"INSERT INTO drafts({', '.join(cols)}) VALUES({', '.join('?' * len(cols))}) "
                       f"ON CONFLICT(id) DO UPDATE SET {updates}", values)

    def claim_draft(self, draft_id: str, *, from_status: str, to_status: str) -> bool:
        """Atomic status change, so one approval can never send twice."""
        with self._db() as db:
            return db.execute("UPDATE drafts SET status=? WHERE id=? AND status=?", (to_status, draft_id, from_status)).rowcount == 1

    def draft(self, draft_id: str) -> dict[str, Any] | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return _draft(row) if row else None

    def drafts(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._db() as db:
            if status:
                rows = db.execute("SELECT * FROM drafts WHERE status=? ORDER BY updated_at DESC LIMIT ?", (status, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM drafts ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [_draft(r) for r in rows]


def _public(row: sqlite3.Row, *, body: bool) -> dict[str, Any]:
    keys = row.keys()
    item = {"id": row["id"], "uid": row["uid"], "threadId": row["thread_id"], "messageId": row["message_id"],
            "inReplyTo": row["in_reply_to"], "references": row["refs"], "replyTo": row["reply_to"],
            "fromName": row["from_name"] or "", "fromAddress": row["from_address"] or "",
            "to": json.loads(row["to_addrs"] or "[]"), "cc": json.loads(row["cc_addrs"] or "[]"),
            "subject": row["subject"] or "", "date": row["date"] or "", "internalDate": int(row["internal_ms"] or 0),
            "labels": json.loads(row["labels"] or "[]"), "listUnsubscribe": bool(row["list_unsubscribe"]),
            "attachments": [a if isinstance(a, dict) else {"name": a} for a in json.loads(row["attachments"] or "[]")],
            "snippet": row["snippet"] or "", "link": gmail_link(row["id"]),
            "category": row["category"] if "category" in keys else None, "size": int(row["size"] or 0) if "size" in keys else 0}
    if body and "body" in keys:
        item["body"] = row["body"] or ""
    return item


def _draft(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "replyToId": row["reply_to_id"], "to": json.loads(row["to_addrs"]),
            "cc": json.loads(row["cc_addrs"] or "[]"), "subject": row["subject"], "body": row["body"],
            "inReplyTo": row["in_reply_to"], "references": row["refs"], "status": row["status"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"], "sentAt": row["sent_at"],
            "sentMessageId": row["sent_message_id"], "verified": bool(row["verified"]), "error": row["error"]}


_STORE: MailStore | None = None


def mail_store() -> MailStore:
    global _STORE
    if _STORE is None:
        _STORE = MailStore()
    return _STORE
