import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.api import security_activity


def line(event, reason, op="status.read", at="2026-10-21T01:00:00+00:00"):
    return json.dumps({"timestamp": at, "event": event, "operation": op, "reason_code": reason, "message_digest": None})


class SecurityActivityTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.log = self.dir / "audit.log"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_routine_allows_are_counted_and_notable_events_listed_newest_first(self):
        rows = [line("api.capability_checked", "scoped_client_allowed")] * 50 + [
            line("api.capability_checked", "scoped_client_denied", "files.desktop.apply", "2026-10-21T02:00:00+00:00"),
            line("voice.turn_rejected", "speaker_rejected", "chat.reply", "2026-10-21T03:00:00+00:00")]
        self.log.write_text("\n".join(rows) + "\n", encoding="utf-8")
        result = security_activity.recent_activity(self.log)
        self.assertEqual(result["routineAllowed"], 50)
        self.assertEqual([e["label"] for e in result["events"]], ["Voice not recognised as you", "Request denied by your security rules"])
        self.assertEqual(result["events"][1]["severity"], "warn")

    def test_only_the_end_of_a_large_log_is_read(self):
        old = security_activity.TAIL_BYTES
        security_activity.TAIL_BYTES = 2000
        try:
            rows = [line("auth.failed", "bad", at="2020-01-01T00:00:00+00:00")] + [line("api.capability_checked", "scoped_client_allowed")] * 200 \
                + [line("auth.verified", "owner_passkey_verified")]
            self.log.write_text("\n".join(rows) + "\n", encoding="utf-8")
            result = security_activity.recent_activity(self.log)
        finally:
            security_activity.TAIL_BYTES = old
        self.assertEqual([e["label"] for e in result["events"]], ["Passkey accepted"])

    def test_missing_log_is_empty(self):
        self.assertEqual(security_activity.recent_activity(self.dir / "none.log")["events"], [])


if __name__ == "__main__":
    unittest.main()
