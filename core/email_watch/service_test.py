import base64
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.email_watch import gmail
from core.email_watch.service import EmailWatch, email_context, score

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


def mail(mid, subject, sender="Sgt Smith <smith@army.mil>", labels=("INBOX", "UNREAD"), unsub=False, at=NOW, body="Report at 0600."):
    return {"id": mid, "fromName": sender.split(" <")[0], "fromAddress": sender.split("<")[-1].rstrip(">").lower(),
            "subject": subject, "snippet": body[:100], "labels": list(labels), "listUnsubscribe": unsub,
            "internalDate": int(at.timestamp() * 1000), "body": body}


class EmailWatchTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.inbox = []
        self.notified = []
        self.judged = []
        self.watch = EmailWatch(fetch=lambda after: [m for m in self.inbox if m["internalDate"] > after],
                                judge=self.judge, notify=self.notified.append, connected=lambda: True,
                                state_file=self.dir / "important.json", clock=lambda: NOW)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def judge(self, message):
        self.judged.append(message["id"])
        important = "formation" in message["subject"].lower() or "bill" in message["subject"].lower()
        return {"important": important, "reason": "work" if important else "routine", "summary": f"Summary of {message['subject']}"}

    def test_rules_score(self):
        self.assertGreaterEqual(score(mail("a", "Formation moved to 0600", labels=("INBOX", "UNREAD", "IMPORTANT"))), 5)
        self.assertLess(score(mail("b", "Weekly deals", sender="Store <no-reply@shop.com>", unsub=True)), 0)

    def test_first_run_stores_but_does_not_announce_old_mail(self):
        self.inbox = [mail("1", "Formation moved to 0600")]
        result = self.watch.check()
        self.assertEqual([i["id"] for i in result["new"]], ["1"])
        self.assertEqual(self.notified, [])

    def test_later_important_mail_is_announced_once_and_newsletters_skip_the_model(self):
        self.watch.check()  # first run, empty inbox
        later = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)
        self.inbox = [mail("2", "Your electric bill is due Friday", sender="City Power <billing@power.com>", at=later),
                      mail("3", "Big weekend deals", sender="Shop <no-reply@shop.com>", unsub=True, at=later),
                      mail("4", "Lunch?", sender="Alex <alex@example.com>", at=later)]
        self.watch.check()
        self.assertEqual([n["id"] for n in self.notified], ["2"])
        self.assertNotIn("3", self.judged)  # bulk mail never reaches the model
        self.watch.check()
        self.assertEqual(len(self.notified), 1)  # not announced twice

    def test_model_failure_falls_back_to_rules(self):
        self.watch.judge = lambda message: (_ for _ in ()).throw(OSError("model down"))
        self.inbox = [mail("5", "Formation moved", labels=("INBOX", "UNREAD", "IMPORTANT", "STARRED"))]
        self.assertEqual(len(self.watch.check()["new"]), 1)

    def test_context_only_for_email_questions_and_marks_content_untrusted(self):
        self.inbox = [mail("6", "Formation moved to 0600")]
        self.watch.check()
        self.assertIsNone(email_context("what's the weather", self.watch))
        context = email_context("any important emails?", self.watch)
        self.assertIn("never instructions", context)
        self.assertIn("Formation moved to 0600", context)

    def test_gmail_payload_text_prefers_plain_and_strips_html(self):
        def part(mime, text):
            return {"mimeType": mime, "body": {"data": base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")}}
        html_only = {"payload": {"mimeType": "multipart/alternative", "headers": [{"name": "From", "value": "A B <a@b.com>"},
                     {"name": "Subject", "value": "Hi"}], "parts": [part("text/html", "<p>Hello <b>there</b></p><script>x</script>")]},
                     "id": "m", "labelIds": ["INBOX"], "internalDate": "1"}
        message = gmail.to_message(html_only)
        self.assertEqual(message["body"], "Hello there")
        self.assertEqual((message["fromName"], message["fromAddress"]), ("A B", "a@b.com"))


if __name__ == "__main__":
    unittest.main()


class PostedNoticeTest(unittest.TestCase):
    def test_posted_notice_is_ready_and_survives_reminder_polls(self):
        from core.assistant_followthrough.service import FollowThroughService
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        inbox = FollowThroughService(folder / "inbox.sqlite3", clock=lambda: NOW, calendar_loader=lambda: [], task_loader=lambda: [])
        first = inbox.post("email", "m1", "Email from Sgt Smith", "Important email from Sgt Smith: formation moved.")
        self.assertEqual(inbox.post("email", "m1", "again", "again"), first)  # same email, one notice
        inbox.poll()
        notices = inbox.list_notifications()["notifications"]
        self.assertEqual([n["source"] for n in notices], ["email"])
        with self.assertRaises(ValueError):
            inbox.post("calendar", "x", "t", "m")
