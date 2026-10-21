"""Read-only view of recent security activity (Execution and Security engine).

The audit log records every permission check. Almost all of those are routine
"allowed" reads by the app (hundreds of thousands), which bury the events that
matter. This view reads only the end of the log and returns the notable ones:
denials, sign-ins, voice rejections, memory changes, actions, rule changes,
device pairing and screen watching. Routine allowed checks are counted, not
listed. Nothing is written; audit entries never contain message text.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

TAIL_BYTES = 16 * 1024 * 1024  # roughly the last several hours of activity
ROUTINE = {("api.capability_checked", "scoped_client_allowed"), ("api.capability_checked", "unattended_brief_allowed")}

LABELS = {
    "scoped_client_denied": "Request denied by your security rules",
    "unattended_brief_denied": "Request denied (token mode)",
    "speaker_rejected": "Voice not recognised as you",
    "insufficient_audio": "Voice too quiet to check",
    "verification_failed": "Voice check failed",
    "turn_too_long": "Voice turn too long to check",
    "owner_passkey_verified": "Passkey accepted",
    "missing_or_ambiguous_approved_device": "Approved microphone missing",
    "profile_forgotten": "You made ZAE forget a memory",
    "profile_confirmed": "You confirmed a memory",
    "insight_forgotten": "You removed a learned point",
    "insight_reviewed": "You reviewed a learned point",
    "encrypted_rules_committed": "Security rules saved",
    "registered_handler": "Approved action ran",
}
EVENT_LABELS = {
    "auth.failed": "Sign-in failed",
    "auth.verified": "Signed in",
    "api.desktop_paired": "Desktop app paired",
    "assistant.screen_watch": "Screen watching changed",
    "rules.saved": "Security rules saved",
    "voice.turn_rejected": "Voice turn rejected",
    "voice.mic_unavailable": "Approved microphone missing",
    "action.started": "Action started",
    "action.completed": "Action completed",
    "rule.matched": "Security rule applied",
    "gate.checked": "Security gate checked",
    "ui.calendar_changed": "Calendar changed from the app",
    "assistant.memory_changed": "Memory changed",
    "speaker_calibration": "Voice calibration",
}
SEVERITY = {"scoped_client_denied": "warn", "unattended_brief_denied": "warn", "speaker_rejected": "warn",
            "verification_failed": "warn", "missing_or_ambiguous_approved_device": "warn"}


def _tail_lines(path: Path, limit: int | None = None) -> list[str]:
    limit = limit or TAIL_BYTES
    with path.open("rb") as handle:
        size = path.stat().st_size
        handle.seek(max(0, size - limit))
        data = handle.read().decode("utf-8", "ignore")
    lines = data.splitlines()
    return lines[1:] if size > limit else lines  # the first line may be cut


def recent_activity(path: Path | None = None, *, limit: int = 60) -> dict[str, Any]:
    if path is None:
        from core.foundation.storage.paths import AUDIT_FILE
        path = AUDIT_FILE
    if not Path(path).exists():
        return {"events": [], "routineAllowed": 0, "since": None, "logBytes": 0}
    routine = 0
    since = None
    notable: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for line in _tail_lines(Path(path)):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        since = since or row.get("timestamp")
        event, reason = str(row.get("event") or ""), str(row.get("reason_code") or "")
        if (event, reason) in ROUTINE:
            routine += 1
            continue
        label = LABELS.get(reason) or EVENT_LABELS.get(event) or event.replace(".", " ").replace("_", " ")
        counts[label] += 1
        notable.append({"at": row.get("timestamp"), "event": event, "reason": reason, "operation": row.get("operation") or "",
                        "label": label, "severity": SEVERITY.get(reason, "info")})
    return {"events": list(reversed(notable[-max(1, min(limit, 300)):])), "routineAllowed": routine, "since": since,
            "summary": [{"label": label, "count": count} for label, count in counts.most_common(8)],
            "logBytes": Path(path).stat().st_size}
