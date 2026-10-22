"""Structured audit metadata. Legacy messages are hashed, never stored raw."""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from core.foundation.storage.paths import AUDIT_FILE, ensure_storage
from core.foundation.security.io import file_lock, reject_link

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
# Size-based rotation: the full log moves to audit_archive/ (nothing is ever
# deleted), so the live file stays quick to read and append to.
ROTATE_BYTES = 32 * 1024 * 1024


def _rotate_if_large() -> None:
    """Call with the audit lock held."""
    try:
        if AUDIT_FILE.stat().st_size < ROTATE_BYTES:
            return
    except FileNotFoundError:
        return
    archive = AUDIT_FILE.parent / "audit_archive"
    archive.mkdir(exist_ok=True)
    reject_link(archive)
    target = archive / ("audit-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".log")
    os.replace(AUDIT_FILE, target)

def audit(event_type: str, message: str = "", *, operation: str = "", reason_code: str = "") -> None:
    ensure_storage()
    fields = {"event": event_type, "operation": operation, "reason_code": reason_code}
    for value in fields.values():
        if value and not _IDENTIFIER.fullmatch(value):
            raise ValueError("Audit fields must be identifiers, not arbitrary user text.")
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
        "message_digest": hashlib.sha256(message.encode("utf-8")).hexdigest() if message else None,
    }
    line = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    with file_lock(AUDIT_FILE.with_suffix(".lock")):
        reject_link(AUDIT_FILE)
        _rotate_if_large()
        descriptor = os.open(AUDIT_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            offset = 0
            while offset < len(line):
                offset += os.write(descriptor, line[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
