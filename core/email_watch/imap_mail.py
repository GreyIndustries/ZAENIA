"""Gmail over IMAP with a Google app password: no Google Cloud project, no API quota.

ZAE copies every message in Gmail's "All Mail" (inbox, sent, archived and
labelled mail; not Spam or Trash) into the local store (mail_store.py), so
reading and searching work offline. After the first copy, each check only
fetches new mail and refreshes labels.

One-time setup (Grey):
    1. Turn on 2-Step Verification for the Google account.
    2. Create an app password at https://myaccount.google.com/apppasswords
    3. Run scripts\\connect_gmail.ps1 (or press Fix it on "Email" in System
       Status) and type the address and app password at the PC.

The app password is sealed to Grey's Windows account with DPAPI in
data/secure/gmail_app_password.dpapi. It is typed only at the PC: no API route
or chat turn accepts it. Reading here is read-only (folders are opened
read-only and bodies are fetched with BODY.PEEK, so mail isn't marked read).
Sending lives in replies.py and needs Grey's approval for each message.
"""
from __future__ import annotations

import base64
import email
import email.header
import email.policy
import email.utils
import getpass
import html
import imaplib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from core.email_watch.mail_store import CATEGORIES, MailStore, mail_store

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FOLDER = PROJECT_ROOT / "data" / "email"
CONFIG = FOLDER / "imap.json"
SECRET = PROJECT_ROOT / "data" / "secure" / "gmail_app_password.dpapi"
IMAP_HOST, IMAP_PORT = "imap.gmail.com", 993
NEW_BATCH = 200          # messages per FETCH command
FIRST_COPY = 500         # newest messages copied on the very first check
BACKFILL = 1000          # older messages copied per check until the whole mailbox is local
FETCH_BYTES = 300_000    # enough for the text of nearly any message; large attachments aren't downloaded
CATEGORY_REFRESH = 3600  # seconds between full re-reads of Gmail's categories (new mail is sorted every check)
WATCH_QUERY = "in:inbox -category:promotions -category:social -category:forums newer_than:3d"
TIMEOUT = 60

Opener = Callable[[], imaplib.IMAP4]


# ------------------------------------------------------------- the sealed app password

def _seal(data: bytes) -> bytes:
    from core.voice_security.windows_protection import protect
    return protect(data)


def _unseal(data: bytes) -> bytes:
    from core.voice_security.windows_protection import protect
    return protect(data, decrypt=True)


def _config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def address() -> str:
    return str(_config().get("address") or "")


def status() -> dict[str, Any]:
    return {"method": "imap", "connected": bool(address()) and SECRET.is_file(), "address": address()}


def _password() -> str:
    return _unseal(SECRET.read_bytes()).decode("utf-8")


def _open(user: str | None = None, password: str | None = None) -> imaplib.IMAP4:
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=TIMEOUT)
    try:
        imap.login(user or address(), password if password is not None else _password())
    except Exception:
        try:
            imap.logout()
        except Exception:
            pass
        raise
    return imap


def connect_account(user: str, password: str, *, opener: Callable[[str, str], imaplib.IMAP4] | None = None) -> dict[str, Any]:
    """Check the app password against Gmail, then keep it sealed on this PC."""
    from core.foundation.security.io import atomic_write
    user = user.strip().lower()
    password = re.sub(r"\s+", "", password)  # Google shows app passwords as four groups of four
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", user):
        raise ValueError("That doesn't look like an email address.")
    if not password:
        raise ValueError("The app password is empty.")
    imap = (opener or _open)(user, password)
    try:
        imap.logout()
    except Exception:
        pass
    FOLDER.mkdir(parents=True, exist_ok=True)
    SECRET.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(SECRET, _seal(password.encode("utf-8")))
    atomic_write(CONFIG, json.dumps({"address": user}, indent=1).encode("utf-8"))
    try:
        from core.foundation.security.io import protect_storage
        protect_storage(FOLDER)
        protect_storage(SECRET.parent)
    except Exception:
        pass
    return status()


def disconnect() -> dict[str, Any]:
    """Forget the app password and address. The local mail copy is kept."""
    for path in (SECRET, CONFIG):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return status()


# ------------------------------------------------------------- parsing

def _imap_utf7(text: str) -> str:
    """Decode IMAP's modified UTF-7 (used for non-ASCII label names)."""
    def repl(match: re.Match[str]) -> str:
        chunk = match.group(1)
        if not chunk:
            return "&"
        data = chunk.replace(",", "/")
        data += "=" * (-len(data) % 4)
        try:
            return base64.b64decode(data).decode("utf-16-be")
        except Exception:
            return match.group(0)
    return re.sub(r"&([A-Za-z0-9+,]*)-", repl, text)


def _tokens(text: str) -> list[str]:
    out = []
    for quoted, atom in re.findall(r'"((?:[^"\\]|\\.)*)"|([^\s()"]+)', text):
        out.append(re.sub(r"\\(.)", r"\1", quoted) if quoted or not atom else atom)
    return out


_SYSTEM_LABELS = {"\\inbox": "INBOX", "\\important": "IMPORTANT", "\\starred": "STARRED", "\\sent": "SENT",
                  "\\draft": "DRAFT", "\\spam": "SPAM", "\\trash": "TRASH"}


def gmail_labels(raw_labels: list[str], flags: list[str]) -> list[str]:
    """Gmail-API-style label names, so the importance rules work on either connection."""
    labels = []
    for label in raw_labels:
        name = _SYSTEM_LABELS.get(label.lower()) or _imap_utf7(label)
        if name not in labels:
            labels.append(name)
    lowered = {f.lower() for f in flags}
    if "\\seen" not in lowered:
        labels.append("UNREAD")
    if "\\flagged" in lowered and "STARRED" not in labels:
        labels.append("STARRED")
    return labels


def _meta_value(meta: str, name: str) -> str | None:
    found = re.search(rf"\b{name} (\d+)", meta)
    return found.group(1) if found else None


def _meta_list(meta: str, name: str) -> list[str]:
    found = re.search(rf"\b{name} \(((?:[^()\"]|\"(?:[^\"\\]|\\.)*\")*)\)", meta)
    return _tokens(found.group(1)) if found else []


def fetch_items(data: list[Any]) -> list[tuple[str, bytes | None]]:
    """Split an imaplib FETCH reply into (metadata text, literal bytes) per message."""
    items: list[tuple[str, bytes | None]] = []
    for part in data or []:
        if isinstance(part, tuple):
            meta, literal = part[0].decode("utf-8", "replace"), part[1]
            is_body = bool(re.search(r"BODY\[[^\]]*\](?:<\d+>)? \{\d+\}$", meta))
            if not is_body:  # a label name sent as a literal: put it back inline as a quoted string
                quoted = literal.decode("utf-8", "replace").replace("\\", "\\\\").replace('"', '\\"')
                meta, literal = re.sub(r"\{\d+\}$", "", meta) + '"' + quoted + '"', None
            if re.match(r"^\d+ \(", meta) or not items:
                items.append((meta, literal))
            else:  # a second literal in the same message (e.g. a label sent as a literal, then the body)
                last_meta, raw = items[-1]
                items[-1] = (last_meta + " " + meta, literal if is_body else raw)
        elif isinstance(part, bytes) and part.strip() not in (b"", b")"):
            text = part.decode("utf-8", "replace")
            if re.match(r"^\d+ \(", text):
                items.append((text, None))
            elif items:  # items the server sent after the literal, e.g. ' FLAGS (\\Seen))'
                meta, raw = items[-1]
                items[-1] = (meta + " " + text, raw)
    return items


def _decoded_name(value: Any) -> str:
    try:
        return str(email.header.make_header(email.header.decode_header(str(value))))
    except Exception:
        return str(value)


def attachment_parts(message: email.message.Message) -> list[tuple[dict[str, Any], email.message.Message]]:
    """Attachments in order, with their details; `index` is how the app asks for one later."""
    found = []
    for part in message.walk() if message.is_multipart() else [message]:
        if part.is_multipart():
            continue
        filename = part.get_filename()
        disposition = (part.get("Content-Disposition") or "").lower()
        if not (filename or disposition.startswith("attachment")):
            continue
        try:
            size = len(part.get_payload(decode=True) or b"")
        except Exception:
            size = 0
        name = _decoded_name(filename) if filename else f"attachment-{len(found) + 1}"
        found.append(({"index": len(found), "name": name[:200], "type": part.get_content_type(), "size": size}, part))
    return found


def _plain(message: email.message.Message) -> tuple[str, list[dict[str, Any]]]:
    plain, rich = [], []
    attachments = [info for info, _ in attachment_parts(message)]
    for part in message.walk() if message.is_multipart() else [message]:
        if part.is_multipart():
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        if part.get_filename() or disposition.startswith("attachment"):
            continue
        kind = part.get_content_type()
        if kind not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        (plain if kind == "text/plain" else rich).append(text)
    if plain:
        text = "\n".join(plain)
    else:
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", "\n".join(rich), flags=re.S | re.I)
        text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.I)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text, attachments[:30]


def _addresses(value: str | None) -> list[str]:
    return [a.lower() for _, a in email.utils.getaddresses([value or ""]) if "@" in a][:50]


def to_message(meta: str, raw: bytes | None) -> dict[str, Any] | None:
    msgid = _meta_value(meta, "X-GM-MSGID")
    uid = _meta_value(meta, "UID")
    if not msgid or not uid:
        return None
    thread = _meta_value(meta, "X-GM-THRID")
    labels = gmail_labels(_meta_list(meta, "X-GM-LABELS"), _meta_list(meta, "FLAGS"))
    internal = imaplib.Internaldate2tuple(meta.encode("utf-8", "replace"))
    size = _meta_value(meta, "RFC822.SIZE")
    item: dict[str, Any] = {"id": format(int(msgid), "x"), "uid": int(uid), "size": int(size or 0),
                            "threadId": format(int(thread), "x") if thread else None,
                            "labels": labels, "internalDate": int(time.mktime(internal) * 1000) if internal else 0}
    if raw is None:
        return item
    parsed = email.message_from_bytes(raw, policy=email.policy.compat32)

    def header(name: str) -> str:
        value = parsed.get(name)
        if value is None:
            return ""
        try:
            return str(email.header.make_header(email.header.decode_header(str(value))))
        except Exception:
            return str(value)

    sender = header("From")
    name, addr = email.utils.parseaddr(sender)
    body, attachments = _plain(parsed)
    reply_to = _addresses(header("Reply-To"))
    item.update({
        "fromName": (name or addr or sender)[:120], "fromAddress": addr.lower()[:200],
        "to": _addresses(header("To")), "cc": _addresses(header("Cc")), "replyTo": reply_to[0] if reply_to else None,
        "subject": header("Subject")[:300], "date": header("Date")[:80],
        "messageId": header("Message-ID").strip()[:300] or None, "inReplyTo": header("In-Reply-To").strip()[:300] or None,
        "references": " ".join(header("References").split())[:4000] or None,
        "listUnsubscribe": bool(header("List-Unsubscribe")), "attachments": attachments,
        "snippet": " ".join(body.split())[:400], "body": body,
    })
    return item


# ------------------------------------------------------------- folders

def special_folder(imap: imaplib.IMAP4, flag: str) -> str:
    """Name of the folder with a special-use flag (\\All, \\Sent), whatever its language."""
    typ, data = imap.list()
    for line in data or []:
        text = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line)
        found = re.match(r'^\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$', text)
        if found and flag.lower() in found.group("flags").lower().split():
            return found.group("name").strip()
    if flag == "\\All":
        return '"[Gmail]/All Mail"'
    raise LookupError(f"No {flag} folder")


def _uids(imap: imaplib.IMAP4, *criteria: str) -> list[int]:
    typ, data = imap.uid("SEARCH", None, *criteria)
    if typ != "OK":
        raise RuntimeError("IMAP search failed")
    return sorted(int(u) for u in (data[0] or b"").split())


def _fetch(imap: imaplib.IMAP4, uids: list[int], parts: str) -> list[dict[str, Any]]:
    found = []
    for start in range(0, len(uids), NEW_BATCH):
        chunk = uids[start:start + NEW_BATCH]
        typ, data = imap.uid("FETCH", ",".join(str(u) for u in chunk), parts)
        if typ != "OK":
            raise RuntimeError("IMAP fetch failed")
        for meta, raw in fetch_items(data):
            message = to_message(meta, raw)
            if message:
                found.append(message)
    return found


FULL = f"(UID X-GM-MSGID X-GM-THRID X-GM-LABELS FLAGS INTERNALDATE RFC822.SIZE BODY.PEEK[]<0.{FETCH_BYTES}>)"
LABELS = "(UID X-GM-MSGID X-GM-LABELS FLAGS)"


# ------------------------------------------------------------- sync

def sync(store: MailStore | None = None, *, opener: Opener | None = None, label_window: int = 500) -> dict[str, Any]:
    """One check: copy new mail, copy a batch of older mail, refresh recent labels, drop deleted mail.

    Returns progress plus `watchIds`: recent inbox mail (no promotions/social/forums) for the
    important-email watch.
    """
    store = store or mail_store()
    started = time.monotonic()
    with (opener or _open)() as imap:
        imap.select(special_folder(imap, "\\All"), readonly=True)
        validity = (imap.response("UIDVALIDITY")[1] or [b""])[0]
        validity = validity.decode() if isinstance(validity, bytes) else str(validity or "")
        if store.get("uidvalidity") != validity:  # Gmail renumbered: copy again (ids stay the same, so no duplicates)
            store.put(uidvalidity=validity, max_uid=0, min_uid=None, complete=0)
        uids = _uids(imap, "ALL")
        max_uid = int(store.get("max_uid") or 0)
        min_uid = int(store.get("min_uid") or 0)
        if max_uid == 0:
            fresh = uids[-FIRST_COPY:]
        else:
            fresh = [u for u in uids if u > max_uid]
        fetched = store.upsert(_fetch(imap, fresh, FULL)) if fresh else 0
        if fresh:
            max_uid = max(max_uid, fresh[-1])
            min_uid = min(min_uid or fresh[0], fresh[0])
        older = [u for u in uids if min_uid and u < min_uid][-BACKFILL:]
        if older:
            fetched += store.upsert(_fetch(imap, older, FULL))
            min_uid = older[0]
        complete = not any(u < min_uid for u in uids) if min_uid else not uids
        store.put(max_uid=max_uid, min_uid=min_uid or None, complete=int(complete), lastSync=int(time.time()))

        known = store.known_uids()
        live = set(uids)
        gone = [mid for uid, mid in known.items() if uid not in live and uid <= max_uid]
        if gone:
            store.delete(gone)
        window = [u for u in uids if u in known and u not in fresh][-label_window:]
        if window:
            store.update_labels((m["id"], m["labels"], m["uid"]) for m in _fetch(imap, window, LABELS))
        copied = fresh + older
        last_full = int(store.get("lastCategories") or 0)
        try:
            if time.time() - last_full > CATEGORY_REFRESH:
                _sort_categories(imap, store, None)
                store.put(lastCategories=int(time.time()))
            elif copied:
                _sort_categories(imap, store, f"{min(copied)}:{max(copied)}")
        except Exception:
            pass  # categories are a convenience; mail still copies without them
        try:
            watch = _uids(imap, "X-GM-RAW", f'"{WATCH_QUERY}"')
        except Exception:
            watch = []
    watch_set = set(watch)
    watch_ids = [mid for uid, mid in store.known_uids().items() if uid in watch_set]
    return {"fetched": fetched, "removed": len(gone), "total": len(uids), "stored": store.count(),
            "complete": complete, "seconds": round(time.monotonic() - started, 1), "watchIds": watch_ids}


def _sort_categories(imap: imaplib.IMAP4, store: MailStore, uid_range: str | None) -> None:
    """Gmail's inbox tabs (Primary, Promotions, Social, Updates, Forums) via Gmail search, saved per message."""
    known = store.known_uids()
    if uid_range:
        low, high = (int(x) for x in uid_range.split(":"))
        scope = {uid for uid in known if low <= uid <= high}
    else:
        scope = set(known)
    found: dict[int, str] = {}
    for category in CATEGORIES:
        criteria = (("UID", uid_range) if uid_range else ()) + ("X-GM-RAW", f'"category:{category}"')
        for uid in _uids(imap, *criteria):
            found.setdefault(uid, category)
    store.set_categories({known[uid]: found.get(uid) for uid in scope})


def sync_state(store: MailStore | None = None) -> dict[str, Any]:
    store = store or mail_store()
    last = store.get("lastSync")
    return {"stored": store.count(), "complete": store.get("complete") == "1",
            "lastSync": int(last) if last else None, "unread": store.counts()}


def fetch_full(message_id: str, *, opener: Opener | None = None) -> bytes:
    """The whole message from Gmail (read-only, not marked read), for attachments."""
    if not re.fullmatch(r"[0-9a-f]{1,32}", message_id or ""):
        raise LookupError("Unknown email")
    with (opener or _open)() as imap:
        imap.select(special_folder(imap, "\\All"), readonly=True)
        uids = _uids(imap, "X-GM-MSGID", str(int(message_id, 16)))
        if not uids:
            raise LookupError("That email is no longer in Gmail.")
        typ, data = imap.uid("FETCH", str(uids[-1]), "(UID BODY.PEEK[])")
        if typ != "OK":
            raise RuntimeError("IMAP fetch failed")
        for meta, raw in fetch_items(data):
            if raw:
                return raw
    raise LookupError("That email is no longer in Gmail.")


def recent_messages(after_ms: int = 0, limit: int = 25, *, store: MailStore | None = None,
                    opener: Opener | None = None) -> list[dict[str, Any]]:
    """For the important-email watch: syncs once, then returns new inbox mail newest first."""
    store = store or mail_store()
    result = sync(store, opener=opener)
    found = [m for m in store.by_ids(result["watchIds"]) if m["internalDate"] > after_ms]
    return found[:max(1, min(limit, 100))]


def find_sent(message_id: str, *, opener: Opener | None = None, attempts: int = 4, wait: float = 3.0) -> bool:
    """True once a sent message (by Message-ID) shows up in Gmail: proof the send really landed."""
    needle = message_id.strip().strip("<>")
    for attempt in range(attempts):
        try:
            with (opener or _open)() as imap:
                imap.select(special_folder(imap, "\\All"), readonly=True)
                if _uids(imap, "X-GM-RAW", f'"rfc822msgid:{needle}"'):
                    return True
        except Exception:
            pass
        if attempt + 1 < attempts:
            time.sleep(wait)
    return False


def connect_interactive() -> None:
    print("Connect Gmail to ZAENIA with an app password (no Google Cloud needed).")
    print("Create one at https://myaccount.google.com/apppasswords (needs 2-Step Verification).\n")
    user = input("Gmail address: ").strip()
    password = getpass.getpass("App password (hidden as you type): ")
    try:
        result = connect_account(user, password)
    except imaplib.IMAP4.error:
        raise SystemExit("Gmail refused that address or app password. Check both and try again.")
    except OSError as error:
        raise SystemExit(f"Couldn't reach Gmail ({type(error).__name__}). Check the internet connection.")
    print(f"\nConnected {result['address']}. ZAE will copy your mail to this PC in the background.")
    print("Replies are drafts until you press Approve in the app.")


if __name__ == "__main__":
    command = sys.argv[1:2]
    if command == ["connect"]:
        connect_interactive()
    elif command == ["disconnect"]:
        print(disconnect())
    elif command == ["sync"]:
        print({k: v for k, v in sync().items() if k != "watchIds"})
    else:
        print({**status(), **sync_state()})
