from datetime import datetime, timezone
import shutil
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

from core.email_watch import imap_mail, replies
from core.email_watch.mail_store import MailStore
from core.email_watch.service import EmailWatch


def raw_mail(subject, sender="Sgt Rivera <rivera@army.mil>", body="Range moved to Thursday 0700.", msgid=None,
             html=False, attachment=False, to="grey@gmail.com", reply_to=None):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Date"] = sender, to, subject, "Sun, 08 Nov 2026 10:00:00 +0000"
    m["Message-ID"] = msgid or f"<{abs(hash(subject))}@army.mil>"
    if reply_to:
        m["Reply-To"] = reply_to
    if html:
        m.set_content("<p>Hello <b>Grey</b></p><script>bad()</script>", subtype="html")
    else:
        m.set_content(body)
    if attachment:
        m.add_attachment(b"%PDF", maintype="application", subtype="pdf", filename="orders.pdf")
    return m.as_bytes()


class FakeImap:
    """Just enough of imaplib.IMAP4 for a Gmail All Mail folder."""

    def __init__(self, box, validity="7", watch=()):
        self.box, self.validity, self.watch, self.selected = box, validity, set(watch), None
        self.searches = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\All \\HasNoChildren) "/" "[Gmail]/All Mail"',
                      b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

    def select(self, name, readonly=False):
        assert readonly, "reads must open folders read-only"
        self.selected = name
        return "OK", [str(len(self.box)).encode()]

    def response(self, code):
        return code, [self.validity.encode()]

    def uid(self, command, *args):
        if command == "SEARCH":
            criteria = args[1:]
            self.searches.append(criteria)
            scope = set(self.box)
            if criteria[0] == "UID":
                low, high = (int(x) for x in criteria[1].split(":"))
                scope = {u for u in scope if low <= u <= high}
                criteria = criteria[2:]
            if criteria[0] == "X-GM-MSGID":
                return "OK", [" ".join(str(u) for u in self.box if 5000 + u == int(criteria[1])).encode()]
            if criteria[0] == "X-GM-RAW" and criteria[1].startswith('"category:'):
                wanted = criteria[1].strip('"').split(":", 1)[1]
                return "OK", [" ".join(str(u) for u in sorted(scope) if self.box[u].get("category") == wanted).encode()]
            if criteria[0] == "ALL":
                return "OK", [" ".join(str(u) for u in sorted(self.box)).encode()]
            if criteria[0] == "X-GM-RAW" and "rfc822msgid" in criteria[1]:
                hit = [u for u, m in self.box.items() if criteria[1].strip('"').split(":", 1)[1] in m["raw"].decode()]
                return "OK", [" ".join(map(str, hit)).encode()]
            return "OK", [" ".join(str(u) for u in sorted(self.watch & set(self.box))).encode()]
        assert command == "FETCH"
        uids, parts = [int(u) for u in args[0].split(",")], args[1]
        data = []
        for seq, uid in enumerate(uids, 1):
            m = self.box[uid]
            labels = " ".join(m.get("labels", ['"\\\\Inbox"']))
            flags = " ".join(m.get("flags", []))
            head = (f'{seq} (X-GM-THRID {m.get("thread", 1000 + uid)} X-GM-MSGID {5000 + uid} X-GM-LABELS ({labels}) '
                    f'UID {uid} FLAGS ({flags})')
            if "BODY.PEEK" in parts:
                head += f' INTERNALDATE "08-Nov-2026 10:{uid % 60:02d}:00 +0000" RFC822.SIZE {len(m["raw"])} BODY[]<0> {{{len(m["raw"])}}}'
                data += [(head.encode(), m["raw"]), b")"]
            else:
                data.append((head + ")").encode())
        return "OK", data


class MailCopyTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.store = MailStore(self.dir / "mail.db")
        self.box = {1: {"raw": raw_mail("Old leave form")},
                    2: {"raw": raw_mail("Weekly deals", sender="Shop <no-reply@shop.com>")},
                    3: {"raw": raw_mail("Range moved", msgid="<range@army.mil>"), "labels": ['"\\\\Inbox"', '"\\\\Important"']}}
        self.imap = FakeImap(self.box, watch={3})

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def sync(self, **kw):
        return imap_mail.sync(self.store, opener=lambda: self.imap, **kw)

    def test_copies_all_mail_and_parses(self):
        result = self.sync()
        self.assertEqual((result["fetched"], result["stored"], result["complete"]), (3, 3, True))
        self.assertEqual(self.imap.selected, '"[Gmail]/All Mail"')
        m = self.store.message(format(5003, "x"))
        self.assertEqual((m["fromName"], m["fromAddress"], m["subject"]), ("Sgt Rivera", "rivera@army.mil", "Range moved"))
        self.assertIn("Thursday 0700", m["body"])
        self.assertEqual(m["messageId"], "<range@army.mil>")
        self.assertEqual(set(m["labels"]), {"INBOX", "IMPORTANT", "UNREAD"})
        self.assertEqual(result["watchIds"], [format(5003, "x")])

    def test_second_check_fetches_only_new_mail_and_drops_deleted(self):
        self.sync()
        self.box[4] = {"raw": raw_mail("Formation at 0600")}
        del self.box[1]
        result = self.sync()
        self.assertEqual((result["fetched"], result["removed"], result["stored"]), (1, 1, 3))
        self.assertIsNone(self.store.message(format(5001, "x")))

    def test_first_copy_is_newest_first_then_backfills(self):
        for uid in range(4, 30):
            self.box[uid] = {"raw": raw_mail(f"Note {uid}")}
        with mock.patch.object(imap_mail, "FIRST_COPY", 5), mock.patch.object(imap_mail, "BACKFILL", 10):
            first = self.sync()
            self.assertEqual((first["stored"], first["complete"]), (15, False))
            self.assertIsNotNone(self.store.message(format(5029, "x")))
            second = self.sync()
            self.assertEqual(second["stored"], 25)
            third = self.sync()
        self.assertEqual((third["stored"], third["complete"]), (29, True))

    def test_label_changes_are_picked_up(self):
        self.sync()
        self.box[3]["flags"] = ["\\Seen"]
        self.box[3]["labels"] = ['"\\\\Inbox"', '"\\\\Starred"', "Army"]
        self.sync()
        self.assertEqual(set(self.store.message(format(5003, "x"))["labels"]), {"INBOX", "STARRED", "Army"})

    def test_html_attachments_and_search(self):
        self.box[4] = {"raw": raw_mail("Hello", html=True)}
        self.box[5] = {"raw": raw_mail("Your orders", attachment=True)}
        self.sync()
        hello = self.store.message(format(5004, "x"))
        self.assertEqual(hello["body"], "Hello Grey")
        self.assertEqual(self.store.message(format(5005, "x"))["attachments"],
                         [{"index": 0, "name": "orders.pdf", "type": "application/pdf", "size": 4}])
        self.assertEqual([m["subject"] for m in self.store.search("rivera leave form")], ["Old leave form"])
        self.assertEqual(self.store.search("deals")[0]["fromAddress"], "no-reply@shop.com")
        self.assertEqual(self.store.search("", sender="shop.com")[0]["subject"], "Weekly deals")

    def test_fetch_items_handles_label_literals(self):
        data = [(b'1 (X-GM-LABELS ({4}', b"Army"), (b' "\\\\Inbox") UID 9 X-GM-MSGID 77 FLAGS () BODY[]<0> {5}', b"hello"), b")"]
        [(meta, raw)] = imap_mail.fetch_items(data)
        self.assertEqual(raw, b"hello")
        self.assertEqual(imap_mail._meta_list(meta, "X-GM-LABELS"), ["Army", "\\Inbox"])

    def test_non_ascii_labels_decode(self):
        self.assertEqual(imap_mail._imap_utf7("&AOk-cole"), "école")
        self.assertEqual(imap_mail._imap_utf7("A&-B"), "A&B")

    def test_watch_uses_the_local_copy(self):
        notified = []
        watch = EmailWatch(fetch=lambda after: imap_mail.recent_messages(after, store=self.store, opener=lambda: self.imap),
                           judge=lambda m: {"important": True, "summary": "Range moved to Thursday."},
                           notify=notified.append, connected=lambda: True, state_file=self.dir / "important.json", clock=lambda: datetime(2026,11,8,12,tzinfo=timezone.utc))
        result = watch.check()
        self.assertEqual([i["subject"] for i in result["new"]], ["Range moved"])
        self.assertTrue(result["new"][0]["link"].startswith("https://mail.google.com/"))


class CategoryAndAttachmentTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.store = MailStore(self.dir / "mail.db")
        self.box = {1: {"raw": raw_mail("Sale!", sender="Shop <deals@shop.com>"), "category": "promotions"},
                    2: {"raw": raw_mail("Range moved"), "category": "primary"},
                    3: {"raw": raw_mail("Your orders", attachment=True), "category": "updates"}}
        self.imap = FakeImap(self.box)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def sync(self):
        return imap_mail.sync(self.store, opener=lambda: self.imap)

    def test_gmail_categories_are_kept_and_filtered(self):
        self.sync()
        self.assertEqual([m["subject"] for m in self.store.recent(10, label="INBOX", category="promotions")], ["Sale!"])
        self.assertEqual(self.store.message(format(5002, "x"))["category"], "primary")
        self.assertEqual(self.store.counts()["promotions"], 1)
        self.assertEqual(self.store.counts()["inbox"], 3)
        # New mail is sorted on the next check without a full re-read.
        self.box[4] = {"raw": raw_mail("Friend tagged you"), "category": "social"}
        self.sync()
        self.assertEqual(self.store.message(format(5004, "x"))["category"], "social")
        self.assertIn(("UID", "4:4", "X-GM-RAW", '"category:social"'), self.imap.searches)

    def test_attachments_list_preview_save_and_read(self):
        from core.email_watch import attachments
        self.sync()
        mid = format(5003, "x")
        fetch = lambda m: imap_mail.fetch_full(m, opener=lambda: self.imap)
        listed = attachments.list_attachments(mid, store=self.store, fetch=fetch)
        self.assertEqual(listed, [{"index": 0, "name": "orders.pdf", "type": "application/pdf", "size": 4}])
        self.assertEqual(attachments.preview(mid, 0, fetch=fetch)["data"], "JVBERg==")
        first = attachments.save(mid, 0, folder=self.dir / "dl", fetch=fetch)
        second = attachments.save(mid, 0, folder=self.dir / "dl", fetch=fetch)
        self.assertEqual(Path(first["path"]).read_bytes(), b"%PDF")
        self.assertEqual(Path(second["path"]).name, "orders (1).pdf")
        with mock.patch("core.api.chat_files.extract_text", return_value=("PDF", "Report to building 4 at 0600.")):
            read = attachments.read(mid, 0, fetch=fetch, summarise=lambda n, k, t: "Orders: building 4, 0600.")
        self.assertEqual((read["kind"], read["summary"]), ("PDF", "Orders: building 4, 0600."))
        with self.assertRaises(attachments.AttachmentError):
            attachments.get(mid, 5, fetch=fetch)
        with self.assertRaises(attachments.AttachmentError):
            attachments.get("ffff", 0, fetch=fetch)

    def test_safe_file_names(self):
        from core.email_watch.attachments import safe_name
        self.assertEqual(safe_name("..\\..\\evil?.exe"), "_.._evil_.exe")
        self.assertEqual(safe_name("CON.txt"), "_CON.txt")
        self.assertEqual(safe_name(""), "attachment")

    def test_old_mail_db_gains_new_columns(self):
        import sqlite3
        old = self.dir / "old.db"
        db = sqlite3.connect(old)
        db.execute("CREATE TABLE messages(id TEXT PRIMARY KEY, uid INTEGER NOT NULL DEFAULT 0, thread_id TEXT, message_id TEXT, "
                   "in_reply_to TEXT, refs TEXT, reply_to TEXT, from_name TEXT, from_address TEXT, to_addrs TEXT, cc_addrs TEXT, "
                   "subject TEXT, date TEXT, internal_ms INTEGER NOT NULL DEFAULT 0, labels TEXT NOT NULL DEFAULT '[]', "
                   "list_unsubscribe INTEGER NOT NULL DEFAULT 0, attachments TEXT NOT NULL DEFAULT '[]', snippet TEXT, body TEXT)")
        db.execute("INSERT INTO messages(id, subject, attachments) VALUES('a1', 'Old', '[\"x.pdf\"]')")
        db.commit(); db.close()
        store = MailStore(old)
        message = store.message("a1")
        self.assertEqual((message["category"], message["attachments"]), (None, [{"name": "x.pdf"}]))


class ConnectTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(imap_mail, "FOLDER", self.dir / "email"),
                        mock.patch.object(imap_mail, "CONFIG", self.dir / "email" / "imap.json"),
                        mock.patch.object(imap_mail, "SECRET", self.dir / "secure" / "pw.dpapi"),
                        mock.patch.object(imap_mail, "_seal", lambda b: b"sealed:" + b),
                        mock.patch.object(imap_mail, "_unseal", lambda b: b[len(b"sealed:"):])]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_password_checked_then_sealed_never_plain(self):
        logins = []

        class Ok:
            def logout(self):
                pass
        result = imap_mail.connect_account(" Grey@Gmail.com ", "abcd efgh ijkl mnop",
                                           opener=lambda u, p: logins.append((u, p)) or Ok())
        self.assertEqual(logins, [("grey@gmail.com", "abcdefghijklmnop")])
        self.assertEqual(result, {"method": "imap", "connected": True, "address": "grey@gmail.com"})
        self.assertEqual((self.dir / "secure" / "pw.dpapi").read_bytes(), b"sealed:abcdefghijklmnop")
        self.assertNotIn("abcd", (self.dir / "email" / "imap.json").read_text())
        self.assertEqual(imap_mail._password(), "abcdefghijklmnop")
        self.assertFalse(imap_mail.disconnect()["connected"])

    def test_rejected_password_saves_nothing(self):
        def refuse(u, p):
            raise imap_mail.imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        with self.assertRaises(imap_mail.imaplib.IMAP4.error):
            imap_mail.connect_account("grey@gmail.com", "wrong", opener=refuse)
        self.assertFalse((self.dir / "secure" / "pw.dpapi").exists())
        self.assertFalse(imap_mail.status()["connected"])


class ReplyTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.store = MailStore(self.dir / "mail.db")
        self.store.upsert([{"id": "abc", "uid": 3, "threadId": "t1", "messageId": "<range@army.mil>",
                            "references": "<first@army.mil>", "fromName": "Sgt Rivera", "fromAddress": "rivera@army.mil",
                            "to": ["grey@gmail.com", "ssg.lee@army.mil"], "cc": ["ops@army.mil"], "subject": "Range moved",
                            "internalDate": 1, "labels": ["INBOX"], "body": "Range moved to Thursday."},
                           {"id": "def", "uid": 4, "fromAddress": "news@shop.com", "replyTo": "help@shop.com",
                            "subject": "Re: Order", "internalDate": 2, "labels": ["INBOX"]}])
        self.sent = []

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def draft(self, mid="abc", **kw):
        return replies.create_draft(mid, "Roger, I'll be there.", store=self.store, own_address="grey@gmail.com", **kw)

    def send(self, draft_id, confirm=lambda mid: True, transport=None):
        return replies.send_draft(draft_id, store=self.store, sender="grey@gmail.com",
                                  transport=transport or self.sent.append, confirm=confirm)

    def test_draft_threads_with_the_original(self):
        d = self.draft()
        self.assertEqual((d["to"], d["cc"], d["subject"], d["status"]), (["rivera@army.mil"], [], "Re: Range moved", "draft"))
        self.assertEqual((d["inReplyTo"], d["references"]), ("<range@army.mil>", "<first@army.mil> <range@army.mil>"))
        self.assertEqual(self.sent, [], "a draft never sends")

    def test_reply_all_skips_own_address_and_reply_to_wins(self):
        self.assertEqual(self.draft(reply_all=True)["cc"], ["ssg.lee@army.mil", "ops@army.mil"])
        d = self.draft("def")
        self.assertEqual((d["to"], d["subject"]), (["help@shop.com"], "Re: Order"))

    def test_send_once_with_threading_headers_and_confirmation(self):
        d = self.draft()
        result = self.send(d["id"])
        self.assertEqual((result["status"], result["verified"]), ("sent", True))
        [message] = self.sent
        self.assertEqual((message["To"], message["In-Reply-To"], message["Subject"]),
                         ("rivera@army.mil", "<range@army.mil>", "Re: Range moved"))
        self.assertEqual(result["sentMessageId"], message["Message-ID"])
        with self.assertRaises(replies.ReplyError):
            self.send(d["id"])
        self.assertEqual(len(self.sent), 1)

    def test_unconfirmed_send_is_reported_unconfirmed(self):
        self.assertFalse(self.send(self.draft()["id"], confirm=lambda mid: False)["verified"])

    def test_failed_send_stays_a_draft(self):
        def boom(message):
            raise OSError("network")
        d = self.draft()
        with self.assertRaises(replies.ReplyError):
            self.send(d["id"], transport=boom)
        again = self.store.draft(d["id"])
        self.assertEqual(again["status"], "draft")
        self.assertIn("OSError", again["error"])

    def test_edit_and_discard_only_unsent_drafts(self):
        d = self.draft()
        self.assertEqual(replies.update_draft(d["id"], "Will do.", store=self.store)["body"], "Will do.")
        replies.discard_draft(d["id"], store=self.store)
        with self.assertRaises(replies.ReplyError):
            self.send(d["id"])
        with self.assertRaises(replies.ReplyError):
            replies.update_draft(d["id"], "x", store=self.store)

    def test_unknown_message_and_empty_body_refused(self):
        with self.assertRaises(replies.ReplyError):
            replies.create_draft("nope", "hi", store=self.store, own_address="g@gmail.com")
        with self.assertRaises(replies.ReplyError):
            replies.create_draft("abc", "   ", store=self.store, own_address="g@gmail.com")


if __name__ == "__main__":
    unittest.main()
