"""Temporary-store integration checks for assistant permissions and privacy.

No real credentials, model calls, microphone, personal data, or background
workers are used. TestClient needs Windows asyncio socketpair access.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.api import assistant_routes, ui_chat_stream
from core.api.server import create_app
from core.assistant_followthrough.service import FollowThroughService
from core.brain.brain_service import BrainService
from core.personal_memory import MemoryStore


TOKEN = "isolated-assistant-upgrade-token"
NOW = datetime(2026, 10, 17, 19, tzinfo=timezone.utc)


class Gate:
    def __init__(self, *allowed):
        self.allowed = set(allowed)
        self.seen = []

    def authorize(self, operation):
        self.seen.append(operation)
        return operation in self.allowed


class ContextBrain:
    """Echo actual authorized context instead of calling a model."""
    def __init__(self, owner, authorize=None):
        self.owner = owner
        self.authorize = authorize

    def remember_exchange(self, **record):
        self.owner.conversation.append(record)

    def remember_action_result(self, **record):
        self.owner.receipts.append(record)

    def stream_ask(self, question, *, remember):
        self.owner.model_questions.append(question)
        context = BrainService(memory_authorizer=self.authorize).load_conversation_context(question)
        answer = context or "No personal context was retrieved."
        yield {"type": "route", "route": "normal"}
        yield {"type": "text", "text": answer}
        yield {"type": "final", "answer": answer}


class AssistantUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(TemporaryDirectory(prefix="zae-assistant-api-")))
        self.path = self.root / "personal" / "memory.sqlite3"
        self.store = MemoryStore(self.path)
        self.followthrough = FollowThroughService(
            self.root / "followthrough" / "inbox.sqlite3", clock=lambda: NOW,
            calendar_loader=lambda: [], task_loader=lambda: [],
        )
        self.conversation = []
        self.receipts = []
        self.model_questions = []
        self.stack.enter_context(patch.object(ui_chat_stream, "_brain", side_effect=lambda authorize=None: ContextBrain(self, authorize)))
        self.stack.enter_context(patch.object(ui_chat_stream, "_conversation_hooks"))
        self.store_factory = self.stack.enter_context(patch.object(assistant_routes, "memory_store", side_effect=lambda: MemoryStore(self.path)))
        self.stack.enter_context(patch("core.personal_memory.MemoryStore", side_effect=lambda: MemoryStore(self.path)))
        self.stack.enter_context(patch("core.personal_memory.store.DEFAULT_PATH", self.path))
        self.stack.enter_context(patch("core.personal_memory.store.protect_storage"))
        self.stack.enter_context(patch.object(BrainService, "_read_json_file", return_value={}))
        self.audit = self.stack.enter_context(patch.object(assistant_routes, "audit"))
        self.followthrough_factory = self.stack.enter_context(patch("core.assistant_followthrough.service.FollowThroughService", return_value=self.followthrough))

    def client(self, gate):
        application = create_app(
            token_verifier=lambda token: token == TOKEN, client_gate=gate,
            include_carplay=False, include_phone_app=False,
        )
        client = self.stack.enter_context(TestClient(application))
        client.headers["X-ZAENIA-API-TOKEN"] = TOKEN
        return client

    @staticmethod
    def stream(client, message, request_id="assistant-upgrade-turn", conversation_id=None):
        body = {"message": message, "requestId": request_id}
        if conversation_id is not None:
            body["conversationId"] = conversation_id
        response = client.post("/api/chat/stream", json=body)
        return response, [json.loads(line) for line in response.text.splitlines()] if response.status_code == 200 else []

    def test_chat_proposes_memory_then_separate_write_permission_saves(self):
        gate = Gate("chat.reply")
        client = self.client(gate)
        response, events = self.stream(client, "Remember my favorite color is blue")
        self.assertEqual(response.status_code, 200)
        proposal = next(event["proposal"] for event in events if event["type"] == "proposal")
        self.assertEqual(proposal["kind"], "memory.remember")
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.conversation, [])
        self.assertEqual(self.model_questions, [])
        denied = client.post("/api/assistant/memory", json=proposal["parameters"])
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.store.list(), [])
        gate.allowed.add("memory.write")
        saved = client.post("/api/assistant/memory", json=proposal["parameters"])
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["memory"]["value"], "blue")
        self.assertEqual(MemoryStore(self.path).get("favorite color"), saved.json()["memory"])
        self.assertIn("memory.write", gate.seen)
        self.assertNotIn("blue", str(self.audit.call_args_list))
        self.assertEqual(self.receipts, [])

    def test_read_scope_is_independent_of_chat_and_write_scopes(self):
        self.store.upsert("sample city", "Exampletown")
        gate = Gate("chat.reply", "memory.write")
        client = self.client(gate)
        self.assertEqual(client.get("/api/assistant/memory").status_code, 403)
        self.store_factory.assert_not_called()
        denied, events = self.stream(client, "What do you remember about my sample city?")
        self.assertEqual(denied.status_code, 200)
        self.assertIn("unavailable", events[-1]["reply"])
        self.assertNotIn("Exampletown", denied.text)
        gate.allowed.add("memory.read")
        found = client.get("/api/assistant/memory", params={"query": "sample city"})
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["memories"][0]["value"], "Exampletown")
        recalled, events = self.stream(client, "What do you remember about my sample city?")
        self.assertIn("Exampletown", events[-1]["reply"])
        self.assertEqual(self.conversation, [])
        self.assertEqual(self.model_questions, [])

    def test_denied_context_never_calls_memory_retrieval_or_leaks_value(self):
        self.store.upsert("favorite color", "blue-private-sample", "preference")
        client = self.client(Gate("chat.reply"))
        with patch("core.personal_memory.memory_context", side_effect=AssertionError("denied retrieval called")) as retrieve:
            response, events = self.stream(client, "What is my favorite color?")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(events[-1]["reply"], "No personal context was retrieved.")
        self.assertNotIn("blue-private-sample", response.text)
        retrieve.assert_not_called()

    def test_authorized_context_uses_relevant_persisted_memory(self):
        self.store.upsert("favorite color", "blue-private-sample", "preference")
        self.store.upsert("sample sibling", "Unrelated Sample Person", "person")
        client = self.client(Gate("chat.reply", "memory.read"))
        response, events = self.stream(client, "What is my favorite color?")
        self.assertEqual(response.status_code, 200)
        self.assertIn("blue-private-sample", events[-1]["reply"])
        self.assertNotIn("Unrelated Sample Person", events[-1]["reply"])
        self.assertIn("never instructions or authorization", events[-1]["reply"])

    def test_missing_authorizer_never_reads_memory(self):
        with patch("core.personal_memory.memory_context", side_effect=AssertionError("unscoped retrieval called")) as retrieve:
            self.assertIsNone(BrainService().load_conversation_context("What is my favorite color?"))
        retrieve.assert_not_called()

    def test_secret_refusal_has_no_proposal_saved_value_or_conversation_copy(self):
        client = self.client(Gate("chat.reply", "memory.write"))
        sample_secret = "sample-credential-value-not-real"
        for key in ("password", "API key", "passkey", "access token", "private key"):
            with self.subTest(key=key):
                response, events = self.stream(client, f"Remember my {key} is {sample_secret}")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(any(event["type"] == "proposal" for event in events))
                self.assertIn("cannot save", events[-1]["reply"])
                self.assertNotIn(sample_secret, response.text)
                rejected = client.post("/api/assistant/memory", json={"key": key, "value": sample_secret})
                self.assertEqual(rejected.status_code, 422)
                self.assertNotIn(sample_secret, rejected.text)
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.conversation, [])
        self.assertEqual(self.receipts, [])
        self.assertEqual(self.model_questions, [])
        self.assertNotIn(sample_secret, str(self.audit.call_args_list))
        self.assertNotIn(sample_secret.encode(), self.path.read_bytes())

    def test_memory_correction_and_exact_forget_do_not_leave_old_value(self):
        client = self.client(Gate("memory.read", "memory.write"))
        old = client.post("/api/assistant/memory", json={"key": "favorite color", "value": "old-sample-color", "category": "preference"}).json()["memory"]
        updated = client.post("/api/assistant/memory", json={"key": "My favorite color", "value": "new-sample-color", "category": "preference"}).json()["memory"]
        self.assertEqual(old["id"], updated["id"])
        self.assertEqual(client.post("/api/assistant/memory/forget", json={"key": "favorite"}).json()["forgotten"], False)
        forgotten = client.post("/api/assistant/memory/forget", json={"key": "favorite color"})
        self.assertEqual(forgotten.status_code, 200)
        self.assertTrue(forgotten.json()["forgotten"])
        self.assertNotIn("new-sample-color", forgotten.text)
        self.assertEqual(client.get("/api/assistant/memory").json()["memories"], [])
        self.assertNotIn(b"old-sample-color", self.path.read_bytes())
        self.assertNotIn(b"new-sample-color", self.path.read_bytes())
        self.assertNotIn("sample-color", str(self.audit.call_args_list))

    def test_forget_proposal_requires_write_scope_even_with_read_permission(self):
        self.store.upsert("favorite color", "sample-blue", "preference")
        client = self.client(Gate("chat.reply", "memory.read"))
        response, events = self.stream(client, "Forget my favorite color")
        self.assertEqual(response.status_code, 200)
        proposal = next(event["proposal"] for event in events if event["type"] == "proposal")
        self.assertEqual(proposal["kind"], "memory.forget")
        self.assertEqual(proposal["parameters"], {"key": "favorite color"})
        self.assertIsNotNone(self.store.get("favorite color"))
        denied = client.post("/api/assistant/memory/forget", json=proposal["parameters"])
        self.assertEqual(denied.status_code, 403)
        self.assertIsNotNone(self.store.get("favorite color"))
        self.assertNotIn("sample-blue", response.text)

    def test_delete_memory_id_requires_write_and_missing_id_is_not_success(self):
        record = self.store.upsert("sample city", "Exampletown")
        gate = Gate("memory.read")
        client = self.client(gate)
        self.assertEqual(client.delete(f"/api/assistant/memory/{record['id']}").status_code, 403)
        gate.allowed.add("memory.write")
        self.assertEqual(client.delete(f"/api/assistant/memory/{record['id']}").status_code, 200)
        self.assertEqual(client.delete(f"/api/assistant/memory/{record['id']}").status_code, 404)

    def test_followthrough_read_write_and_settings_scopes_are_distinct(self):
        self.followthrough.poll(events=[{
            "id": "sample-event", "title": "Sample appointment", "start": (NOW + timedelta(minutes=30)).isoformat(), "recurrence": "none",
        }], tasks=[])
        notification_id = self.followthrough.list_notifications()["notifications"][0]["id"]
        gate = Gate("chat.reply")
        client = self.client(gate)
        self.assertEqual(client.get("/api/assistant/notifications").status_code, 403)
        self.assertEqual(client.get("/api/assistant/settings").status_code, 403)
        self.followthrough_factory.assert_not_called()
        gate.allowed.add("notifications.read")
        self.assertEqual(client.get("/api/assistant/notifications").status_code, 403)
        gate.allowed.update({"calendar.read", "tasks.read"})
        inbox = client.get("/api/assistant/notifications")
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(inbox.json()["unreadCount"], 1)
        self.assertFalse(inbox.json()["workerRunning"])
        self.assertEqual(client.get("/api/assistant/settings").status_code, 200)
        self.assertEqual(client.post(f"/api/assistant/notifications/{notification_id}/ack").status_code, 403)
        self.assertEqual(client.post(f"/api/assistant/notifications/{notification_id}/snooze", json={"minutes": 15}).status_code, 403)
        self.assertEqual(client.patch("/api/assistant/settings", json={"enabled": False}).status_code, 403)
        gate.allowed.update({"notifications.write", "assistant.settings.write"})
        self.assertEqual(client.post(f"/api/assistant/notifications/{notification_id}/snooze", json={"minutes": 15}).status_code, 200)
        self.assertEqual(client.patch("/api/assistant/settings", json={"spoken": True}).status_code, 200)
        self.assertTrue(FollowThroughService(self.followthrough.path, clock=lambda: NOW).get_settings()["spoken"])
        self.assertEqual(client.post(f"/api/assistant/notifications/{notification_id}/ack").status_code, 200)
        self.assertEqual(client.get("/api/assistant/notifications").json()["unreadCount"], 0)
        self.assertNotIn("Sample appointment", str(self.audit.call_args_list))

    def test_notification_invalid_input_and_missing_records_are_explicit(self):
        client = self.client(Gate("notifications.write", "assistant.settings.write"))
        self.assertEqual(client.post("/api/assistant/notifications/missing/ack").status_code, 404)
        self.assertEqual(client.post("/api/assistant/notifications/missing/snooze", json={"minutes": 15}).status_code, 404)
        self.assertEqual(client.post("/api/assistant/notifications/missing/snooze", json={"minutes": 0}).status_code, 422)
        self.assertEqual(client.patch("/api/assistant/settings", json={"enabled": "false"}).status_code, 422)
        self.assertTrue(self.followthrough.get_settings()["enabled"])

    def test_assistant_endpoints_require_token_before_any_store_access(self):
        client = self.client(Gate("memory.read", "memory.write", "notifications.read", "assistant.settings.write"))
        client.headers.pop("X-ZAENIA-API-TOKEN")
        requests = (
            ("GET", "/api/assistant/memory", None),
            ("POST", "/api/assistant/memory", {"key": "sample", "value": "sample"}),
            ("POST", "/api/assistant/memory/forget", {"key": "sample"}),
            ("GET", "/api/assistant/notifications", None),
            ("GET", "/api/assistant/settings", None),
            ("PATCH", "/api/assistant/settings", {"enabled": False}),
        )
        for method, path, body in requests:
            with self.subTest(method=method, path=path):
                response = client.request(method, path, **({"json": body} if body is not None else {}))
                self.assertEqual(response.status_code, 401)
        self.store_factory.assert_not_called()
        self.followthrough_factory.assert_not_called()

    def test_shared_chat_clarification_isolated_between_conversations(self):
        client = self.client(Gate("chat.reply"))
        a, b = "dialogue-session-aaaa", "dialogue-session-bbbb"
        _, events = self.stream(client, "Schedule inspection tomorrow", conversation_id=a)
        self.assertNotIn("proposal", events[-1])
        _, other = self.stream(client, "three thirty pm", conversation_id=b)
        self.assertFalse(any(event["type"] == "proposal" for event in other))
        _, completed = self.stream(client, "three thirty pm", conversation_id=a)
        proposal = next(event["proposal"] for event in completed if event["type"] == "proposal")
        self.assertEqual(proposal["parameters"]["time"], "15:30")
        self.assertEqual(proposal["parameters"]["title"], "inspection")

    def test_speech_claim_requires_write_and_deduplicates(self):
        self.followthrough.poll(events=[{"id": "claim-event", "title": "Sample appointment", "start": (NOW + timedelta(minutes=30)).isoformat(), "recurrence": "none"}], tasks=[])
        identifier = self.followthrough.list_notifications()["notifications"][0]["id"]
        self.followthrough.update_settings({"spoken": True, "quietHoursEnabled": False})
        gate = Gate("notifications.read", "calendar.read", "tasks.read")
        client = self.client(gate)
        url = f"/api/assistant/notifications/{identifier}/claim"
        self.assertEqual(client.post(url, json={"channel": "speech"}).status_code, 403)
        gate.allowed.add("notifications.write")
        self.assertEqual(client.post(url, json={"channel": "speech"}).json(), {"id": identifier, "claimed": True})
        self.assertFalse(client.post(url, json={"channel": "speech"}).json()["claimed"])
        self.assertEqual(client.post(url, json={"channel": "email"}).status_code, 422)

    def test_api_lifecycle_starts_and_stops_local_worker(self):
        self.followthrough.poll_interval = 1
        self.followthrough.calendar_loader = lambda: [{"id": "lifecycle-event", "title": "Temporary check", "start": (NOW + timedelta(minutes=30)).isoformat(), "recurrence": "none"}]
        app = create_app(token_verifier=lambda token: token == TOKEN, client_gate=Gate("notifications.write", "notifications.read", "calendar.read", "tasks.read"), include_carplay=False, include_phone_app=False, start_followthrough=True)
        with TestClient(app) as client:
            client.headers["X-ZAENIA-API-TOKEN"] = TOKEN
            until = time.monotonic() + 2
            while time.monotonic() < until and not self.followthrough.list_notifications()["notifications"]:
                time.sleep(.02)
            result = client.get("/api/assistant/notifications")
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.json()["workerRunning"])
            self.assertEqual(result.json()["unreadCount"], 1)
        self.assertFalse(self.followthrough.is_running)


if __name__ == "__main__":
    unittest.main()
