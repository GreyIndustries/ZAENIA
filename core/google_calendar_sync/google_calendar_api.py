"""Two-way Google Calendar: events Zack adds in ZÆNIA are also created in Google.

Reading stays on the private ICS feed (google_calendar_ics.py). Writing uses the
Google Calendar API with Zack's own OAuth client and a one-time sign-in:

    1. Put the OAuth client file (Desktop app) at data/google_calendar/credentials.json
    2. python -m core.google_calendar_sync.google_calendar_api connect

The sign-in token is kept on this PC only (data/google_calendar/token.json). Only
the calendar-events scope is requested. Every Google write is best effort: the
ZÆNIA event is saved first and never depends on Google being reachable.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FOLDER = PROJECT_ROOT / "data" / "google_calendar"
CREDENTIALS = FOLDER / "credentials.json"
TOKEN = FOLDER / "token.json"
PUSHED = FOLDER / "pushed_events.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TIMEZONE = "America/Los_Angeles"
MARKER = "zaenia-id:"
_LOCK = threading.Lock()


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


def _service():
    from googleapiclient.discovery import build
    creds = _credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False) if creds else None


def connect() -> None:
    """One-time sign-in: opens the browser; Zack clicks Allow."""
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
    print("Google Calendar connected. New ZAENIA events will also appear in Google.")


def _pushed() -> dict[str, str]:
    try:
        data = json.loads(PUSHED.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def event_body(params: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime, timedelta
    start = datetime.fromisoformat(str(params["start"]))
    end = start + timedelta(hours=1)
    body: dict[str, Any] = {
        "summary": str(params.get("title") or "ZAENIA event"),
        "description": f"Added by ZAENIA. {MARKER}{params['id']}",
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
    }
    rule = {"daily": "RRULE:FREQ=DAILY", "weekly": "RRULE:FREQ=WEEKLY"}.get(str(params.get("recurrence") or "none"))
    if rule:
        body["recurrence"] = [rule]
    return body


def push_event(params: dict[str, Any]) -> str | None:
    """Create the event in Google; returns Google's event id, or None if not connected/failed."""
    try:
        service = _service()
        if service is None:
            return None
        created = service.events().insert(calendarId="primary", body=event_body(params)).execute()
        with _LOCK:
            pushed = _pushed()
            pushed[str(params["id"])] = created["id"]
            PUSHED.write_text(json.dumps(pushed, indent=1), encoding="utf-8")
        return created["id"]
    except Exception:
        return None


def remove_event(local_id: str) -> bool:
    """Delete the Google copy of a ZÆNIA event, if one was made."""
    with _LOCK:
        pushed = _pushed()
        google_id = pushed.pop(local_id, None)
    if not google_id:
        return False
    try:
        service = _service()
        if service is not None:
            service.events().delete(calendarId="primary", eventId=google_id).execute()
        with _LOCK:
            PUSHED.write_text(json.dumps(pushed, indent=1), encoding="utf-8")
        return True
    except Exception:
        return False


def push_in_background(params: dict[str, Any]) -> None:
    if TOKEN.is_file():
        threading.Thread(target=push_event, args=(dict(params),), name="zaenia-google-push", daemon=True).start()


def is_mirror(description: Any, local_ids: set[str]) -> bool:
    """A Google event that is just the copy of a ZÆNIA event still saved locally."""
    text = str(description or "")
    if MARKER not in text:
        return False
    return text.split(MARKER, 1)[1].split()[0].strip(" .") in local_ids


if __name__ == "__main__":
    if sys.argv[1:] == ["connect"]:
        connect()
    else:
        print(json.dumps(status()))
