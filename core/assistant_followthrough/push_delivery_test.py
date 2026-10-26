"""Isolated browser notification tests. No owner data, credentials or live pushes."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from core.api import web_push
from core.api.server import create_app
from core.api.ui_routes import operation_for
from core.assistant_followthrough.push_delivery import PushDelivery
from core.assistant_followthrough.service import FollowThroughService

NOW = datetime(2026, 10, 25, 19, tzinfo=timezone.utc)


def subscription(tail="a"):
    raw = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
    return {"endpoint": "https://web.push.apple.com/" + tail, "keys": {"p256dh": encode(raw), "auth": encode(b"x" * 16)}}


class PushDeliveryTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="zae-push-test-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.now = NOW
        self.subs = self.root / "subscriptions.json"
        self.path = self.root / "deliveries.sqlite3"
        self.inbox = FollowThroughService(self.root / "inbox.sqlite3", clock=lambda: self.now)
        self.calls = []
        self.result = "accepted"
        self.delivery = self.new_delivery()
        self.phone = subscription()
        web_push.subscribe(self.phone, "Test phone", self.subs, origin="https://zae.example.test")

    def new_delivery(self):
        return PushDelivery(lambda: self.inbox.list_notifications(limit=500), path=self.path, subs_path=self.subs,
                            sender=self.send, clock=lambda: self.now.timestamp())

    def send(self, item, title, body, **kwargs):
        self.calls.append({"endpoint": item["endpoint"], "title": title, "body": body})
        return self.result

    def post(self, source="reminder", identity="one"):
        return self.inbox.post(source, identity, "Private appointment", "Private details")

    def test_calendar_and_task_reach_phone_once_across_restart(self):
        self.inbox.poll(events=[{"id": "event", "title": "Calendar item", "start": (NOW + timedelta(hours=1)).isoformat()}],
                        tasks=[{"id": "task", "title": "Task item", "deadline": (NOW + timedelta(hours=1)).isoformat()}])
        self.assertEqual(self.delivery.tick(), 2)
        self.assertEqual(self.new_delivery().tick(), 0)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(self.delivery.status()["devices"][0]["lastAcceptedAt"])

    def test_quiet_pause_snooze_and_read_are_authoritative(self):
        item = self.post()
        self.inbox.update_settings({"quietStart": "00:00", "quietEnd": "23:59"})
        self.assertEqual(self.delivery.tick(), 0)
        self.inbox.update_settings({"quietHoursEnabled": False, "enabled": False})
        self.assertEqual(self.delivery.tick(), 0)
        self.inbox.update_settings({"enabled": True})
        self.inbox.snooze(item, 15)
        self.assertEqual(self.delivery.tick(), 0)
        self.now += timedelta(minutes=16)
        self.assertEqual(self.delivery.tick(), 1)
        self.inbox.snooze(item, 15)
        self.now += timedelta(minutes=16)
        self.assertEqual(self.delivery.tick(), 1)
        self.inbox.acknowledge(item)
        self.assertEqual(self.delivery.tick(), 0)

    def test_retry_survives_restart_without_resending_to_successful_device(self):
        web_push.subscribe(subscription("b"), "Second", self.subs, origin="https://zae.example.test")
        self.post()
        first = self.phone["endpoint"]
        failed = [True]
        def sender(item, title, body, **kwargs):
            self.calls.append(item["endpoint"])
            return "network" if item["endpoint"] == first and failed[0] else "accepted"
        self.delivery.sender = sender
        self.assertEqual(self.delivery.tick(), 1)
        other = self.new_delivery()
        other.sender = sender
        self.assertEqual(other.tick(), 0)
        self.now += timedelta(seconds=31)
        failed[0] = False
        self.assertEqual(other.tick(), 1)
        self.assertEqual(self.calls.count(first), 2)
        self.assertEqual(self.calls.count("https://web.push.apple.com/b"), 1)

    def test_cancelled_notice_is_not_retried(self):
        item = self.post()
        self.result = "network"
        self.delivery.tick()
        self.inbox.acknowledge(item)
        self.now += timedelta(minutes=1)
        self.assertEqual(self.delivery.tick(), 0)
        self.assertEqual(len(self.calls), 1)

    def test_category_choice_and_private_preview(self):
        self.post("email")
        web_push.subscribe(self.phone, path=self.subs, options={"categories": ["reminder"], "preview": False})
        self.assertEqual(self.delivery.tick(), 0)
        self.post()
        self.assertEqual(self.delivery.tick(), 1)
        self.assertNotIn("Private", json.dumps(self.calls))
        web_push.subscribe(self.phone, path=self.subs, options={"categories": ["email"], "preview": True})
        self.assertEqual(self.delivery.tick(), 1)
        self.assertEqual(self.calls[-1]["body"], "Private details")
        # Status contains neither raw endpoints nor subscription secrets.
        self.assertNotIn(self.phone["endpoint"], json.dumps(self.delivery.status()))
        self.assertNotIn(self.phone["keys"]["auth"], json.dumps(self.delivery.status()))

    def test_gone_subscription_removed_and_no_false_success(self):
        self.result = "http_410"
        self.post()
        self.assertEqual(self.delivery.tick(), 0)
        self.assertEqual(web_push.subscriptions(self.subs), [])
        with self.assertRaises(ValueError):
            self.delivery.test()

    def test_test_uses_chosen_device_and_rate_limit(self):
        web_push.subscribe(subscription("b"), "Second", self.subs, origin="https://zae.example.test")
        chosen = web_push.device_id(self.phone["endpoint"])
        self.result = "network"
        self.assertEqual(self.delivery.test(chosen)["sent"], 0)
        self.assertEqual(self.delivery.test(chosen)["results"][0]["result"], "unchanged")
        self.assertEqual(len(self.calls), 1)
        self.now += timedelta(seconds=31)
        self.result = "accepted"
        self.assertEqual(self.delivery.test(chosen)["sent"], 1)
        self.assertEqual([c["endpoint"] for c in self.calls], [self.phone["endpoint"]] * 2)

    def test_concurrent_delivery_claim_is_unique(self):
        self.post()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(lambda service: service.tick(), [self.delivery, self.new_delivery()]))
        self.assertEqual(sum(result), 1)
        self.assertEqual(len(self.calls), 1)

    def test_endpoint_and_key_validation_rejects_arbitrary_destinations(self):
        for endpoint in ("http://web.push.apple.com/a", "https://127.0.0.1/a", "https://web.push.apple.com.evil.test/a",
                         "https://evil.test/a", "https://user@web.push.apple.com/a", "https://web.push.apple.com:8443/a"):
            with self.assertRaises(ValueError, msg=endpoint):
                web_push.subscribe({**self.phone, "endpoint": endpoint}, path=self.subs)
        with self.assertRaises(ValueError):
            web_push.subscribe({**self.phone, "keys": {"p256dh": "x", "auth": "y"}}, path=self.subs)
        with self.assertRaises(ValueError):
            web_push.preferences({"categories": ["execute"], "preview": True})

    def test_transport_uses_valid_contact_timeout_and_no_redirects(self):
        item = web_push.subscriptions(self.subs)[0]
        key = ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        seen = []
        def fake_push(**kwargs):
            seen.append(kwargs)
            with patch("requests.Session.post", return_value=type("Reply", (), {"status_code": 302})()) as post:
                kwargs["requests_session"].post(item["endpoint"], timeout=8)
                self.assertFalse(post.call_args.kwargs["allow_redirects"])
            return type("Reply", (), {"status_code": 302})()
        with patch.dict("os.environ", {"ZAENIA_PUSH_CONTACT": ""}):
            self.assertEqual(web_push.send_one(item, "T", "B", push=fake_push, pem=key, url="https://evil.test"), "http_302")
        self.assertEqual(seen[0]["timeout"], 8)
        self.assertEqual(seen[0]["vapid_claims"]["sub"], "https://zae.example.test")
        self.assertEqual(json.loads(seen[0]["data"])["url"], "/app/")

    def test_route_auth_scopes_and_private_status(self):
        class Gate:
            allowed = {"notifications.read", "status.read"}
            def authorize(self, operation):
                return operation in self.allowed
        gate = Gate()
        app = create_app(token_verifier=lambda token: token == "test-only", client_gate=gate, include_carplay=False, include_phone_app=False)
        with patch("core.assistant_followthrough.push_delivery.push_delivery", return_value=self.delivery), TestClient(app) as client:
            self.assertEqual(client.get("/api/push/status").status_code, 401)
            client.headers["X-ZAENIA-API-TOKEN"] = "test-only"
            self.assertEqual(client.get("/api/push/status").status_code, 200)
            self.assertEqual(client.post("/api/push/subscribe", json={"subscription": self.phone}).status_code, 403)
            self.assertEqual(client.post("/api/push/test", json={"deviceId": "bad"}).status_code, 422)
            response = client.post("/api/push/test", json={"deviceId": web_push.device_id(self.phone["endpoint"])})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["sent"], 1)
        self.assertEqual(operation_for("POST", "/api/push/device"), "memory.write")
        self.assertEqual(operation_for("GET", "/api/push/status"), "notifications.read")
        self.assertIsNone(operation_for("DELETE", "/api/push/status"))


if __name__ == "__main__":
    unittest.main()
