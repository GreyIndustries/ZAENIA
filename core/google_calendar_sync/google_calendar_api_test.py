"""Google write tests: no network, no sign-in."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core.google_calendar_sync import google_calendar_api as api


class GoogleWriteTest(unittest.TestCase):
    def test_event_body_marks_the_zaenia_id_and_repeats(self):
        body = api.event_body({"id": "app-abc", "title": "Inspection", "start": "2026-10-20T15:30:00-07:00", "recurrence": "weekly"})
        self.assertEqual(body["summary"], "Inspection")
        self.assertIn("zaenia-id:app-abc", body["description"])
        self.assertEqual(body["end"]["dateTime"], "2026-10-20T16:30:00-07:00")
        self.assertEqual(body["recurrence"], ["RRULE:FREQ=WEEKLY"])
        self.assertNotIn("recurrence", api.event_body({"id": "x", "title": "t", "start": "2026-10-20T09:00:00-07:00", "recurrence": "none"}))

    def test_google_copy_of_a_local_event_shows_once(self):
        self.assertTrue(api.is_mirror("Added by ZAENIA. zaenia-id:app-abc", {"app-abc"}))
        self.assertFalse(api.is_mirror("Added by ZAENIA. zaenia-id:app-gone", {"app-abc"}))
        self.assertFalse(api.is_mirror("Team meeting", {"app-abc"}))
        self.assertFalse(api.is_mirror(None, {"app-abc"}))

    def test_not_connected_never_blocks_saving(self):
        with patch.object(api, "_service", return_value=None):
            self.assertIsNone(api.push_event({"id": "app-x", "title": "t", "start": "2026-10-20T09:00:00-07:00"}))
        with patch.object(api, "_service", side_effect=RuntimeError("offline")):
            self.assertIsNone(api.push_event({"id": "app-x", "title": "t", "start": "2026-10-20T09:00:00-07:00"}))


if __name__ == "__main__":
    unittest.main()
