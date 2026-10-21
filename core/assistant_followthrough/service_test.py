"""Isolated local follow-through checks; never touch owner files or send alerts."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from core.assistant_followthrough.service import FollowThroughService, NotificationNotFound

UTC = timezone.utc
NOW = datetime(2026, 10, 16, 19, 0, tzinfo=UTC)  # Noon Pacific, outside quiet hours.


def event(**patches):
    return {"id": "event-one", "title": "Inspect the car", "start": (NOW + timedelta(hours=1)).isoformat(), "recurrence": "none", "revision": 1, **patches}


def task(**patches):
    return {"id": "task-one", "title": "Call the shop", "status": "Pending", "archived": False, "priority": "Normal", "deadline": (NOW + timedelta(hours=1)).isoformat(), "updatedAt": NOW.isoformat(), **patches}


class FollowThroughTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="zae-followthrough-test-")
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "inbox.sqlite3"
        self.clock = NOW
        self.events = []
        self.tasks = []
        self.service = self.new_service()
        self.addCleanup(self.service.stop)

    def new_service(self, **options):
        return FollowThroughService(self.path, clock=lambda: self.clock, calendar_loader=lambda: self.events, task_loader=lambda: self.tasks, **options)

    def inbox(self, **options):
        return self.service.list_notifications(**options)

    def test_calendar_stages_dedupe_after_restart_and_concurrent_poll(self):
        self.events = [event()]
        self.assertEqual(self.service.poll(), 1)
        self.assertEqual(self.new_service().poll(), 0)
        first_id = self.inbox()["notifications"][0]["id"]
        self.assertEqual(self.inbox()["notifications"][0]["leadMinutes"], 60)
        self.clock += timedelta(minutes=45)
        services = [self.new_service() for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(lambda service: service.poll(), services)), 1)
        self.clock += timedelta(minutes=15)
        self.assertEqual(self.service.poll(), 1)
        self.assertEqual(self.inbox()["unreadCount"], 3)
        self.assertEqual(len({item["id"] for item in self.inbox()["notifications"]}), 3)
        self.assertIn(first_id, {item["id"] for item in self.inbox()["notifications"]})
        current = [item for item in self.inbox()["notifications"] if item["canInterrupt"]]
        self.assertEqual([item["leadMinutes"] for item in current], [0])

    def test_catchup_suppresses_obsolete_lead_stages_and_old_events(self):
        self.events = [event(start=(NOW - timedelta(hours=2)).isoformat()), event(id="too-old", start=(NOW - timedelta(days=2)).isoformat())]
        self.assertEqual(self.service.poll(), 1)
        notifications = self.inbox()["notifications"]
        self.assertEqual([(item["sourceId"], item["leadMinutes"]) for item in notifications], [("event-one", 0)])
        self.clock += timedelta(days=3)
        self.assertEqual(self.new_service().poll(), 0)
        self.assertFalse(self.inbox()["notifications"][0]["canInterrupt"])

    def test_startup_inside_fifteen_minutes_does_not_replay_hour_reminder(self):
        self.events = [event(start=(NOW + timedelta(minutes=10)).isoformat())]
        self.assertEqual(self.service.poll(), 1)
        self.assertEqual(self.inbox()["notifications"][0]["leadMinutes"], 15)

    def test_calendar_edit_delete_and_revision_cancel_stale_records(self):
        self.events = [event()]
        self.service.poll()
        self.events = [event(start=(NOW + timedelta(days=1)).isoformat(), revision=2)]
        self.assertEqual(self.service.poll(), 0)
        self.assertEqual(self.inbox()["unreadCount"], 0)
        self.clock += timedelta(days=1)
        self.assertEqual(self.service.poll(), 1)
        self.events = []
        self.service.poll()
        self.assertEqual(self.inbox()["notifications"], [])
        self.clock += timedelta(hours=1)
        self.assertEqual(self.service.poll(), 0)

    def test_task_approaching_overdue_ack_snooze_and_completion(self):
        self.tasks = [task()]
        self.assertEqual(self.service.poll(), 1)
        approaching = self.inbox()["notifications"][0]
        self.assertEqual(approaching["kind"], "task.approaching")
        result = self.service.snooze(approaching["id"], 15)
        self.assertTrue(result["snoozedUntil"])
        self.assertFalse(self.inbox()["notifications"][0]["canInterrupt"])
        self.clock += timedelta(minutes=15)
        self.assertTrue(self.new_service().list_notifications()["notifications"][0]["canInterrupt"])
        self.service.acknowledge(approaching["id"])
        self.service.acknowledge(approaching["id"])  # Idempotent acknowledgement.
        self.assertEqual(self.new_service().list_notifications()["unreadCount"], 0)
        self.assertTrue(self.inbox(include_read=True)["notifications"][0]["readAt"])
        self.clock += timedelta(minutes=45)
        self.assertEqual(self.service.poll(), 1)
        self.assertEqual(self.inbox()["notifications"][0]["kind"], "task.overdue")
        self.assertEqual(self.service.poll(), 0)
        self.tasks = [task(status="Completed")]
        self.service.poll()
        self.assertEqual(self.inbox()["unreadCount"], 0)

    def test_task_deadline_change_cleared_archived_deleted(self):
        self.tasks = [task()]
        self.service.poll()
        self.tasks = [task(deadline=(NOW + timedelta(days=1)).isoformat())]
        self.service.poll()
        self.assertEqual(self.inbox()["notifications"], [])
        self.clock += timedelta(days=1)
        self.assertEqual(self.service.poll(), 1)
        self.tasks = [task(deadline=None)]
        self.service.poll()
        self.assertEqual(self.inbox()["notifications"], [])
        self.tasks = [task(id="archived", archived=True), task(id="completed", status="Completed"), task(id="no-deadline", deadline=None)]
        self.assertEqual(self.service.poll(), 0)
        self.tasks = []
        self.assertEqual(self.service.poll(), 0)

    def test_task_catchup_bounded_to_twenty_four_hours(self):
        self.tasks = [task(deadline=(NOW - timedelta(minutes=30)).isoformat()), task(id="old-task", deadline=(NOW - timedelta(days=7)).isoformat())]
        self.assertEqual(self.service.poll(), 1)
        self.assertEqual(self.inbox()["notifications"][0]["kind"], "task.overdue")
        self.assertEqual(self.new_service().poll(), 0)

    def test_quiet_hours_keep_inbox_and_spoken_requires_explicit_opt_in(self):
        self.clock = datetime(2026, 10, 17, 6, 0, tzinfo=UTC)  # 11 PM Pacific.
        self.tasks = [task(deadline=self.clock.isoformat())]
        self.service.poll()
        response = self.inbox()
        self.assertTrue(response["quiet"])
        self.assertEqual(response["unreadCount"], 1)
        self.assertFalse(response["notifications"][0]["canInterrupt"])
        self.assertFalse(response["notifications"][0]["canSpeak"])
        self.clock += timedelta(hours=8)
        self.assertFalse(self.inbox()["quiet"])
        self.assertTrue(self.inbox()["notifications"][0]["canInterrupt"])
        self.assertFalse(self.inbox()["notifications"][0]["canSpeak"])
        self.service.update_settings({"spoken": True})
        self.assertTrue(self.new_service().list_notifications()["notifications"][0]["canSpeak"])

    def test_disabled_setting_stops_new_delivery_and_interruptions(self):
        self.events = [event()]
        self.service.update_settings({"enabled": False})
        self.assertEqual(self.service.poll(), 0)
        self.assertEqual(self.inbox()["notifications"], [])
        self.service.update_settings({"enabled": True})
        self.assertEqual(self.service.poll(), 1)
        self.service.update_settings({"enabled": False})
        self.assertFalse(self.inbox()["notifications"][0]["canInterrupt"])
        self.events = []
        self.service.poll()
        self.assertEqual(self.inbox()["notifications"], [])

    def test_failed_or_invalid_snapshots_never_cancel_existing_notifications(self):
        self.events = [event()]
        self.service.poll()
        def unavailable():
            raise OSError("private owner file unavailable")
        self.service.task_loader = unavailable
        self.events = []
        with self.assertRaises(OSError):
            self.service.poll()
        self.assertEqual(self.inbox()["unreadCount"], 1)
        self.service.task_loader = lambda: []
        with self.assertRaises(ValueError):
            self.service.poll(events=[event(), event()])
        with self.assertRaises(ValueError):
            self.service.poll(events=[event(start="invalid")])
        self.assertEqual(self.inbox()["unreadCount"], 1)

    def test_invalid_settings_snooze_and_missing_ids(self):
        for patch_value in ({"enabled": 1}, {"spoken": "yes"}, {"quietStart": "25:30"}, {"timezone": "not/a/timezone"}, {"unknown": True}, {}):
            with self.subTest(patch_value=patch_value), self.assertRaises(ValueError):
                self.service.update_settings(patch_value)
        for value in (0, 1441, True, "15"):
            with self.assertRaises(ValueError):
                self.service.snooze("missing", value)
        with self.assertRaises(NotificationNotFound):
            self.service.snooze("missing")
        with self.assertRaises(NotificationNotFound):
            self.service.acknowledge("missing")
        self.assertEqual(self.new_service().get_settings()["quietStart"], "22:00")

    def test_recurring_calendar_preserves_pacific_time_across_dst(self):
        self.events = [event(start="2026-10-31T09:00:00-07:00", recurrence="daily")]
        self.clock = datetime(2026, 10, 31, 16, tzinfo=UTC)
        self.service.poll()
        self.clock = datetime(2026, 11, 1, 17, tzinfo=UTC)
        self.service.poll()
        starts = sorted(item["occurrence"] for item in self.inbox()["notifications"] if item["leadMinutes"] == 0)
        self.assertEqual(starts, ["2026-10-31T16:00:00+00:00", "2026-11-01T17:00:00+00:00"])

    def test_recurring_calendar_skips_ambiguous_and_nonexistent_wall_times(self):
        self.events = [event(start="2026-10-31T01:30:00-07:00", recurrence="daily")]
        self.clock = datetime(2026, 11, 1, 10, tzinfo=UTC)
        self.assertEqual(self.service.poll(), 0)
        self.events = [event(start="2026-03-07T02:30:00-08:00", recurrence="daily")]
        self.clock = datetime(2026, 3, 8, 11, tzinfo=UTC)
        self.assertEqual(self.service.poll(), 0)

    def test_worker_start_stop_idempotence_and_cross_service_lease(self):
        first_poll = threading.Event()
        def load_tasks():
            first_poll.set()
            return []
        self.service.task_loader = load_tasks
        other = self.new_service()
        self.addCleanup(other.stop)
        self.assertTrue(self.service.start())
        self.assertTrue(first_poll.wait(timeout=2))
        self.assertTrue(self.service.is_running)
        self.assertTrue(self.inbox()["workerRunning"])
        self.assertFalse(self.service.start())
        self.assertTrue(other.start())  # Live standby; only the lease owner polls.
        self.service.stop()
        self.assertFalse(self.service.is_running)
        self.service.stop()
        self.assertFalse(other.start())  # The standby thread is already alive.
        other.stop()

    def test_replacement_takes_over_an_expired_crash_lease(self):
        crashed = self.new_service()
        self.assertTrue(crashed._lease())
        replacement = self.new_service()
        replacement.poll_interval = 1
        polled = threading.Event()
        replacement.task_loader = lambda: (polled.set() or [])
        self.addCleanup(replacement.stop)
        self.assertTrue(replacement.start())
        self.assertFalse(polled.wait(timeout=.1))
        self.clock += timedelta(seconds=91)
        self.assertTrue(polled.wait(timeout=2))
        replacement.stop()

    def test_default_calendar_loader_reads_only_local_revision_snapshot(self):
        from core.assistant_followthrough.service import local_calendar_snapshot
        from core.scheduling.service import Store, validate_event
        source_path = Path(self.folder.name) / "data" / "scheduling" / "calendar.sqlite3"
        with patch("core.assistant_followthrough.service.PROJECT_ROOT", Path(self.folder.name)):
            self.assertEqual(local_calendar_snapshot(), [])
            store = Store(source_path)
            saved = validate_event({key: value for key, value in event().items() if key != "revision"})
            store.put(saved)
            snapshot = local_calendar_snapshot()
            self.assertEqual(snapshot, [{**saved, "revision": 1}])
            store.put({**saved, "title": "Changed"})
            self.assertEqual(local_calendar_snapshot()[0]["revision"], 2)
            with closing(sqlite3.connect(source_path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 0)

    def test_spoken_claim_dedupes_concurrent_devices_and_survives_restart(self):
        self.tasks = [task()]
        self.service.update_settings({"spoken": True})
        self.service.poll()
        notification_id = self.inbox()["notifications"][0]["id"]
        services = [self.new_service() for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda service: service.claim_delivery(notification_id), services))
        self.assertEqual(sum(claim["claimed"] for claim in claims), 1)
        self.assertFalse(self.new_service().claim_delivery(notification_id)["claimed"])
        self.assertEqual(self.inbox()["unreadCount"], 1)

    def test_spoken_claim_requires_optin_and_respects_quiet_disabled_read_and_expiry(self):
        self.tasks = [task()]
        self.service.poll()
        notification_id = self.inbox()["notifications"][0]["id"]
        self.assertFalse(self.service.claim_delivery(notification_id)["claimed"])
        self.service.update_settings({"spoken": True, "enabled": False})
        self.assertFalse(self.service.claim_delivery(notification_id)["claimed"])
        self.service.update_settings({"enabled": True, "quietStart": "11:00", "quietEnd": "13:00"})
        self.assertFalse(self.service.claim_delivery(notification_id)["claimed"])
        self.service.update_settings({"quietHoursEnabled": False})
        self.clock += timedelta(hours=1)
        self.assertFalse(self.service.claim_delivery(notification_id)["claimed"])
        self.clock = NOW
        self.service.acknowledge(notification_id)
        self.assertFalse(self.service.claim_delivery(notification_id)["claimed"])
        with self.assertRaises(ValueError):
            self.service.claim_delivery(notification_id, "phone")
        with self.assertRaises(NotificationNotFound):
            self.service.claim_delivery("missing")

    def test_snooze_allows_one_new_spoken_generation_when_due(self):
        self.tasks = [task()]
        self.service.update_settings({"spoken": True})
        self.service.poll()
        notification_id = self.inbox()["notifications"][0]["id"]
        self.assertTrue(self.service.claim_delivery(notification_id)["claimed"])
        self.service.snooze(notification_id, 15)
        self.assertFalse(self.service.claim_delivery(notification_id)["claimed"])
        self.clock += timedelta(minutes=15)
        self.assertTrue(self.new_service().claim_delivery(notification_id)["claimed"])
        self.assertFalse(self.service.claim_delivery(notification_id)["claimed"])


if __name__ == "__main__":
    unittest.main()
