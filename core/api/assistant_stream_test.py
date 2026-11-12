"""Chat action integration checks with temporary storage and no model/network.

Run: .venv/Scripts/python.exe -m unittest core.api.assistant_stream_test
"""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from core.api import ui_calendar, ui_chat_stream, ui_tasks
from core.api.server import create_app


class FakeBrain:
    def __init__(self):
        self.memories = []
        self.questions = []
        self.receipts = []

    def remember_exchange(self, **record):
        self.memories.append(record)

    def remember_action_result(self, *, answer):
        self.receipts.append(answer)

    def stream_ask(self, message, *, remember):
        self.questions.append(message)
        yield {"type": "route", "route": "normal"}
        yield {"type": "text", "text": "A normal answer."}
        yield {"type": "final", "answer": "A normal answer."}


class Gate:
    def __init__(self, *allowed):
        self.allowed = allowed
        self.seen = []

    def authorize(self, operation):
        self.seen.append(operation)
        return operation in self.allowed


class ChatActionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.brain = FakeBrain()
        self.stack.enter_context(patch.object(ui_chat_stream, "_brain", return_value=self.brain))
        self.stack.enter_context(patch.object(ui_chat_stream, "_conversation_hooks"))
        self.stack.enter_context(patch.object(ui_tasks, "UI_DATA_DIR", self.root / "tasks"))
        self.stack.enter_context(patch.object(ui_calendar, "scheduling_db", return_value=self.root / "calendar.sqlite3"))
        self.stack.enter_context(patch("core.api.ui_routes.audit"))

    def client(self, gate):
        app = create_app(token_verifier=lambda token: token == "isolated-test-token",
                         client_gate=gate, include_carplay=False, include_phone_app=False)
        client = self.stack.enter_context(TestClient(app))
        client.headers["X-ZAENIA-API-TOKEN"] = "isolated-test-token"
        return client

    def events(self, message, request_id="isolated-request"):
        return [json.loads(line) for line in ui_chat_stream.stream(message, request_id)]

    def test_proposal_does_not_call_model_or_create_task(self):
        events = self.events("Add a task to inspect the car")
        proposal = next(event["proposal"] for event in events if event["type"] == "proposal")
        self.assertEqual(proposal["kind"], "task.create")
        self.assertEqual(proposal["parameters"]["title"], "inspect the car")
        self.assertFalse(self.brain.questions)
        self.assertFalse((self.root / "tasks").exists())
        self.assertEqual(events[-1]["type"], "done")
        self.assertFalse(events[-1]["interrupted"])
        self.assertEqual(self.brain.memories[-1]["answer"], events[-1]["reply"])
        self.assertNotIn("isolated-request", ui_chat_stream._ACTIVE)

    def test_normal_conversation_keeps_existing_brain_path(self):
        events = self.events("Explain how a bicycle works")
        self.assertEqual(self.brain.questions, ["Explain how a bicycle works"])
        self.assertFalse(any(event["type"] == "proposal" for event in events))
        self.assertEqual(events[-1]["reply"], "A normal answer.")

    def test_cancellation_prevents_proposal(self):
        stream = ui_chat_stream.stream("Add a task to inspect the car", "cancel-proposal")
        self.assertEqual(json.loads(next(stream))["type"], "start")
        self.assertTrue(ui_chat_stream.cancel("cancel-proposal"))
        events = [json.loads(line) for line in stream]
        self.assertFalse(any(event["type"] == "proposal" for event in events))
        self.assertTrue(events[-1]["interrupted"])
        self.assertFalse(self.brain.memories)
        self.assertNotIn("cancel-proposal", ui_chat_stream._ACTIVE)

    def test_cancel_between_text_and_card_suppresses_card(self):
        stream = ui_chat_stream.stream("Add a task to inspect the car", "cancel-after-text")
        while json.loads(next(stream))["type"] != "delta":
            pass
        ui_chat_stream.cancel("cancel-after-text")
        events = [json.loads(line) for line in stream]
        self.assertFalse(any(event["type"] == "proposal" for event in events))
        self.assertTrue(events[-1]["interrupted"])

    def test_memory_failure_does_not_break_proposal(self):
        with patch.object(self.brain, "remember_exchange", side_effect=OSError("fixture")):
            events = self.events("Add a task to inspect the car")
        self.assertTrue(any(event["type"] == "proposal" for event in events))
        self.assertEqual(events[-1]["type"], "done")

    def test_task_execution_requires_separate_permission(self):
        gate = Gate("chat.reply")
        client = self.client(gate)
        reply = client.post("/api/chat/stream", json={"message": "Add a task to inspect the car", "requestId": "scoped-chat-turn"})
        self.assertEqual(reply.status_code, 200)
        proposal = next(json.loads(line)["proposal"] for line in reply.text.splitlines()
                        if json.loads(line)["type"] == "proposal")
        denied = client.post("/api/tasks", json=proposal["parameters"])
        self.assertEqual(denied.status_code, 403)
        self.assertFalse((self.root / "tasks").exists())
        gate.allowed = ("chat.reply", "ui.tasks.write", "tasks.read")
        saved = client.post("/api/tasks", json=proposal["parameters"])
        self.assertEqual(saved.status_code, 200)
        task = saved.json()["task"]
        self.assertEqual(task["title"], "inspect the car")
        self.assertEqual(client.get("/api/tasks").json()["tasks"][0]["id"], task["id"])
        self.assertIn("ui.tasks.write", gate.seen)

    def test_calendar_execution_requires_separate_permission(self):
        gate = Gate("chat.reply")
        client = self.client(gate)
        reply = client.post("/api/chat/stream", json={"message": "Schedule car inspection on 2099-10-20 at 09:30", "requestId": "calendar-chat-turn"})
        self.assertEqual(reply.status_code, 200)
        proposal = next(json.loads(line)["proposal"] for line in reply.text.splitlines()
                        if json.loads(line)["type"] == "proposal")
        denied = client.post("/api/calendar/events", json=proposal["parameters"])
        self.assertEqual(denied.status_code, 403)
        self.assertFalse((self.root / "calendar.sqlite3").exists())
        gate.allowed = ("chat.reply", "ui.calendar.write")
        saved = client.post("/api/calendar/events", json=proposal["parameters"])
        self.assertEqual(saved.status_code, 200)
        event = saved.json()["event"]
        self.assertEqual(event["title"], "car inspection")
        self.assertEqual(event["start"], "2099-10-20T09:30:00-07:00")
        self.assertEqual(event["channels"], ["console"])
        self.assertEqual(ui_calendar._store().events()[0]["id"], event["id"])

    def test_natural_reminder_is_saved_and_opens_tasks(self):
        gate = Gate("ui.tasks.write")
        reminder_store = Mock()
        with patch("core.assistant_platform.reminders.reminders", return_value=reminder_store):
            result = ui_chat_stream._protocol_or_reminder("Put a reminder on the 8th for GitHub 2FA", gate.authorize)
        self.assertEqual(result[1:], ("reminder", ["tasks"]))
        reminder_store.add.assert_called_once()
        _, due = reminder_store.add.call_args.args
        self.assertEqual(due.day, 8)
        self.assertIn("GitHub 2FA", result[0])
        self.assertIn("ui.tasks.write", gate.seen)

    def test_token_mode_says_so_instead_of_the_brain_claiming_the_reminder_was_set(self):
        from fastapi import HTTPException
        def locked(operation):
            raise HTTPException(503, "ZÆNIA is running in token mode. Unlock it with the passkey at the PC to use this.")
        reminder_store = Mock()
        with patch("core.assistant_platform.reminders.reminders", return_value=reminder_store):
            events = [json.loads(chunk) for chunk in ui_chat_stream.stream("Put a reminder on November 8 at 9am for GitHub 2FA", "req0123456789abcd", authorize=locked)]
        done = events[-1]
        self.assertEqual((done["type"], done["route"]), ("done", "locked"))
        self.assertIn("token mode", done["reply"])
        self.assertFalse(reminder_store.add.called)
        self.assertFalse(self.brain.questions)

    def test_incomplete_reminder_asks_for_details_instead_of_claiming_success(self):
        gate = Gate("ui.tasks.write")
        reminder_store = Mock()
        with patch("core.assistant_platform.reminders.reminders", return_value=reminder_store):
            result = ui_chat_stream._protocol_or_reminder("Put a reminder on the 8th", gate.authorize)
        self.assertEqual(result[1:], ("reminder", ["tasks"]))
        self.assertIn("What should I remind you about", result[0])
        self.assertFalse(reminder_store.add.called)
        self.assertFalse(self.brain.questions)

    def test_stream_requires_token_and_chat_permission(self):
        gate = Gate("chat.reply")
        client = self.client(gate)
        body = {"message": "Add a task to inspect the car", "requestId": "unauthorized-turn"}
        client.headers.pop("X-ZAENIA-API-TOKEN")
        self.assertEqual(client.post("/api/chat/stream", json=body).status_code, 401)
        client.headers["X-ZAENIA-API-TOKEN"] = "isolated-test-token"
        gate.allowed = ()
        self.assertEqual(client.post("/api/chat/stream", json=body).status_code, 403)
        self.assertFalse(self.brain.memories)

    def test_only_successful_chat_actions_write_verified_receipt(self):
        gate = Gate("ui.tasks.write", "ui.calendar.write")
        client = self.client(gate)
        bad = client.post("/api/tasks", json={"title": " ", "fromConversation": True})
        self.assertEqual(bad.status_code, 422)
        self.assertFalse(self.brain.receipts)
        task = client.post("/api/tasks", json={"title": "Inspect the car", "fromConversation": True}).json()["task"]
        self.assertIn(task["id"], self.brain.receipts[-1])
        self.assertIn(task["title"], self.brain.receipts[-1])
        self.assertIn("No notification was scheduled", self.brain.receipts[-1])
        event = client.post("/api/calendar/events", json={"title": "Inspection", "date": "2099-10-20", "time": "09:30", "fromConversation": True}).json()["event"]
        self.assertIn(event["id"], self.brain.receipts[-1])
        self.assertIn(event["start"], self.brain.receipts[-1])
        self.assertIn("does not confirm phone or spoken alert", self.brain.receipts[-1])
        self.assertEqual(len(self.brain.receipts), 2)

    def test_receipt_failure_keeps_saved_action_successful(self):
        client = self.client(Gate("ui.tasks.write", "tasks.read"))
        with patch.object(self.brain, "remember_action_result", side_effect=OSError("fixture")):
            saved = client.post("/api/tasks", json={"title": "Inspect the car", "fromConversation": True})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(len(client.get("/api/tasks").json()["tasks"]), 1)

    def test_verified_receipt_persists_as_assistant_context_only(self):
        from core.brain import brain_service
        path = self.root / "conversation.jsonl"
        with patch.object(brain_service, "MEMORY_PATH", path):
            brain = brain_service.BrainService()
            brain.remember_action_result(answer="Created task 'Inspect the car' (ID: fixture).")
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["role"], "assistant")
            self.assertEqual(records[0]["source"], "confirmed_action")
            self.assertEqual(brain.load_recent_messages()[0]["content"], records[0]["content"])


if __name__ == "__main__":
    unittest.main()
