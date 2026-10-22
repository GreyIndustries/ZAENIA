"""Gmail, read-only, with Grey's own Google OAuth client.

One-time setup (Grey):
    1. In Google Cloud Console (same project as Calendar), enable the Gmail API
       and add the scope .../auth/gmail.readonly to the OAuth consent screen.
    2. python -m core.email_watch.gmail connect   (or scripts\\connect_gmail.ps1)

Only `gmail.readonly` is requested: ZAE can read and summarise mail but can
never send, delete, label or change anything. The sign-in token stays on this
PC (data/email/token.json), separate from the Calendar token.
"""
from __future__ import annotations

import base64
import html
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FOLDER = PROJECT_ROOT / "data" / "email"
TOKEN = FOLDER / "token.json"
CREDENTIALS = PROJECT_ROOT / "data" / "google_calendar" / "credentials.json"  # same OAuth client as Calendar
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BODY_LIMIT = 6000


def status() -> dict[str, Any]:
    return {"clientFile": CREDENTIALS.is_file(), "connected": TOKEN.is_file()}


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    if not TOKEN.is_file():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds if creds and creds.valid else None


def service():
    from googleapiclient.discovery import build
    creds = _credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False) if creds else None


def connect() -> None:
    """One-time sign-in: opens the browser; Grey clicks Allow."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not CREDENTIALS.is_file():
        raise SystemExit(f"Put your Google OAuth client file (Desktop app) at {CREDENTIALS} first.")
    FOLDER.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    try:
        from core.foundation.security.io import protect_storage
        protect_storage(FOLDER)
    except Exception:
        pass
    print("Gmail connected (read-only). ZAE will summarise important new mail.")


def _header(headers: list[dict[str, str]], name: str) -> str:
    return next((h.get("value", "") for h in headers if h.get("name", "").lower() == name.lower()), "")


def _text_from_payload(payload: dict[str, Any]) -> str:
    """Plain text of a message: text/plain if present, else stripped text/html."""
    plain, rich = [], []

    def walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if data and mime in ("text/plain", "text/html"):
            text = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "ignore")
            (plain if mime == "text/plain" else rich).append(text)
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    if plain:
        text = "\n".join(plain)
    else:
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", "\n".join(rich), flags=re.S | re.I)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return " ".join(text.split())[:BODY_LIMIT]


def to_message(raw: dict[str, Any]) -> dict[str, Any]:
    payload = raw.get("payload") or {}
    headers = payload.get("headers") or []
    sender = _header(headers, "From")
    name = re.sub(r"\s*<[^>]+>\s*", "", sender).strip().strip('"') or sender
    address = (re.search(r"<([^>]+)>", sender) or re.search(r"(\S+@\S+)", sender))
    return {
        "id": raw.get("id"), "threadId": raw.get("threadId"),
        "fromName": name[:120], "fromAddress": (address.group(1) if address else "")[:200].lower(),
        "subject": _header(headers, "Subject")[:300], "date": _header(headers, "Date"),
        "internalDate": int(raw.get("internalDate") or 0),
        "labels": list(raw.get("labelIds") or []), "snippet": html.unescape(raw.get("snippet") or "")[:400],
        "listUnsubscribe": bool(_header(headers, "List-Unsubscribe")),
        "body": _text_from_payload(payload),
    }


def recent_messages(after_ms: int = 0, limit: int = 25) -> list[dict[str, Any]]:
    """New inbox mail (no promotions/social/forums), newest first."""
    gmail = service()
    if gmail is None:
        return []
    query = "in:inbox -category:promotions -category:social -category:forums newer_than:3d"
    listed = gmail.users().messages().list(userId="me", q=query, maxResults=max(1, min(limit, 50))).execute()
    found = []
    for item in listed.get("messages", []):
        raw = gmail.users().messages().get(userId="me", id=item["id"], format="full").execute()
        message = to_message(raw)
        if message["internalDate"] > after_ms:
            found.append(message)
    return found


if __name__ == "__main__":
    if sys.argv[1:] == ["connect"]:
        connect()
    else:
        print(status())
