"""Heartbeat for the PC voice service, so the desktop and phone UI can show
whether ZÆNIA is listening on the PC microphone.

State only ("listening", "hearing", "replying", "off") and timestamps: no
transcripts and no audio. Writing it never interrupts the voice runtime.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_FILE = PROJECT_ROOT / "data" / "ui" / "voice_service.json"
REFRESH_SECONDS = 2.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Heartbeat:
    def __init__(self) -> None:
        self.started_at = _now()
        self.state: str | None = None
        self.last = 0.0

    def report(self, state: str, *, force: bool = False, recognising: bool = True) -> None:
        now = time.monotonic()
        if not force and state == self.state and recognising == getattr(self, "recognising", True) and now - self.last < REFRESH_SECONDS:
            return
        self.state, self.last, self.recognising = state, now, recognising
        # recognising: False after several turns in a row failed the owner
        # voice check, so the app can listen with its own mic meanwhile.
        record = {"state": state, "startedAt": self.started_at, "updatedAt": _now(), "pid": os.getpid(),
                  "recognising": recognising}
        from core.assistant_platform.performance import COORDINATOR
        record["timing"] = COORDINATOR.snapshot()
        try:
            from core.foundation.security.io import atomic_write
            atomic_write(STATUS_FILE, json.dumps(record).encode("utf-8"))
        except Exception:
            pass  # the UI just shows the service as off
