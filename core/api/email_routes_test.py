import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core.email_watch.mail_store import MailStore


class EmailRoutesTest(unittest.TestCase):
    """Reading uses the local copy; a reply sends only with the desktop key (or the phone's near-PC pass)."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from core.api.server import create_app
        from core.email_watch import imap_mail, mail_store, replies
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = MailStore(self.dir / "mail.db")
        self.store.upsert([{"id": "abc1", "uid": 1, "threadId": "t1", "messageId": "<range@army.mil>", "fromName": "Sgt Rivera",
                            "fromAddress": "rivera@army.mil", "to": ["grey@gmail.com"], "subject": "Range moved",
                            "internalDate": 1, "labels": ["INBOX", "UNREAD"], "body": "Range moved to Thursday 0700."}])
        self.sent = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(mail_store, "_STORE", self.store))
        self.stack.enter_context(patch.object(imap_mail, "status", lambda: {"method": "imap", "connected": True, "address": "grey@gmail.com"}))
        self.stack.enter_context(patch.object(imap_mail, "address", lambda: "grey@gmail.com"))
        self.stack.enter_context(patch.object(replies, "_smtp_send", self.sent.append))
        original = replies.send_draft
        self.stack.enter_context(patch.object(replies, "send_draft", lambda draft_id: original(
            draft_id, transport=self.sent.append, confirm=lambda mid: True)))
        self.stack.enter_context(patch("core.api.desktop_key.verify", side_effect=lambda key: key == "pc-key"))
        self.stack.enter_context(patch("core.api.desktop_key.is_paired", return_value=True))
        self.stack.enter_context(patch("core.foundation.security.audit.audit"))
        self.stack.enter_context(patch("core.api.ui_routes.audit"))

        class Gate:
            def authorize(self, operation): return operation is not None
        self.client = self.stack.enter_context(TestClient(create_app(
            token_verifier=lambda token: token == "t", client_gate=Gate(), include_carplay=False, include_phone_app=False)))
        self.client.headers.update({"X-ZAENIA-API-TOKEN": "t", "X-ZAENIA-APP": "1"})

    def test_read_search_and_thread(self):
        listed = self.client.get("/api/email/messages").json()["messages"]
        self.assertEqual([m["subject"] for m in listed], ["Range moved"])
        self.assertNotIn("body", listed[0])
        self.assertEqual(self.client.get("/api/email/messages", params={"q": "thursday"}).json()["messages"][0]["id"], "abc1")
        one = self.client.get("/api/email/messages/abc1").json()
        self.assertIn("0700", one["message"]["body"])
        self.assertEqual(self.client.get("/api/email/messages/ffff").status_code, 404)

    def test_reply_needs_desktop_approval_and_sends_once(self):
        draft = self.client.post("/api/email/drafts", json={"messageId": "abc1", "body": "Roger."}).json()
        self.assertEqual((draft["status"], draft["to"]), ("draft", ["rivera@army.mil"]))
        url = f"/api/email/drafts/{draft['id']}/send"
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self.client.post(url, headers={"X-ZAENIA-DESKTOP-KEY": "wrong"}).status_code, 403)
        self.assertEqual(self.sent, [])
        ok = self.client.post(url, headers={"X-ZAENIA-DESKTOP-KEY": "pc-key"})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual((ok.json()["status"], ok.json()["verified"]), ("sent", True))
        self.assertEqual(self.client.post(url, headers={"X-ZAENIA-DESKTOP-KEY": "pc-key"}).status_code, 409)
        self.assertEqual(len(self.sent), 1)

    def test_category_filter_and_attachment_routes(self):
        from core.email_watch import attachments
        self.store.set_categories({"abc1": "primary"})
        self.assertEqual(len(self.client.get("/api/email/messages", params={"category": "primary"}).json()["messages"]), 1)
        self.assertEqual(self.client.get("/api/email/messages", params={"category": "social"}).json()["messages"], [])
        self.assertEqual(self.client.get("/api/email/messages", params={"category": "bogus"}).status_code, 422)
        info = {"index": 0, "name": "orders.pdf", "type": "application/pdf", "size": 4}
        with patch.object(attachments, "get", lambda mid, i, **kw: (info, b"%PDF")), \
             patch.object(attachments, "list_attachments", lambda mid, **kw: [info]), \
             patch.object(attachments, "SAVE_DIR", Path(self.dir) / "dl"):
            self.assertEqual(self.client.get("/api/email/messages/abc1/attachments").json()["attachments"], [info])
            self.assertEqual(self.client.get("/api/email/messages/abc1/attachments/0").json()["data"], "JVBERg==")
            saved = self.client.post("/api/email/messages/abc1/attachments/0/save").json()
            self.assertTrue(Path(saved["path"]).is_file())
        self.assertIn("unread", self.client.get("/api/email/sync").json())

    def test_routes_have_capabilities(self):
        from core.api.ui_routes import operation_for
        self.assertEqual(operation_for("GET", "/api/email/messages/abc1"), "notifications.read")
        self.assertEqual(operation_for("POST", "/api/email/drafts"), "notifications.write")
        self.assertEqual(operation_for("POST", "/api/email/drafts/" + "a" * 32 + "/send"), "notifications.write")
        self.assertIsNone(operation_for("POST", "/api/email/send"))
        self.assertEqual(operation_for("POST", "/api/email/messages/abc1/attachments/0/save"), "notifications.write")
        self.assertEqual(operation_for("GET", "/api/email/messages/abc1/attachments/2"), "notifications.read")


if __name__ == "__main__":
    unittest.main()
