# Email: all of Gmail, local copy, approved replies

Status (2026-11-09, branch `claude/gmail-imap`): IMPLEMENTED and UNIT TESTED (fake IMAP/SMTP; 24 email tests + 3 route tests pass on Python 3.11). **Not yet live-verified against Grey's Gmail, not installed.** Waiting for Grey's app password.

## How ZAE connects

ZAE talks to Gmail's own mail servers over IMAP (reading) and SMTP (sending) with a **Google app password**. No Google Cloud project, Gmail API, OAuth consent screen or API quota is involved, and the connection doesn't expire every 7 days like an unpublished Cloud app's sign-in.

The older read-only Gmail API connection (`gmail.py`) still works as a fallback while the app password isn't set up. Once IMAP is connected, ZAE uses IMAP only.

## What it does

- **All mail, on this PC.** ZAE copies Gmail's "All Mail" folder (inbox, sent, archived and labelled mail; not Spam or Trash) into `data/email/mail.db` (SQLite with full-text search; not in git). The first check copies the newest 500 messages, then 1,000 older ones a minute until the whole mailbox is local. After that, each 5-minute check fetches only new mail, refreshes labels and read/unread for recent mail, and drops mail deleted in Gmail. Large attachments aren't downloaded (only their names); message text is kept up to 20,000 characters.
- **Read-only reading.** Folders are opened read-only and bodies fetched with `BODY.PEEK`, so ZAE never marks mail as read or changes it.
- **Search and chat.** Assistant › Mail lists the inbox, searches all copied mail, and shows whole threads. When Grey asks ZAE about email in chat, she gets matching mail from the local copy (sender, subject, date, a short snippet) as untrusted reference.
- **Important-email alerts** work as before (rules, then the local model, then a notice she can speak), now fed from the local copy.

## Replies (owner approval)

1. In Assistant › Mail, open an email and write a reply, or press **Let ZAE draft** (the local model writes one from Grey's note; the email is treated as untrusted content).
2. **Save draft.** It appears under "Waiting for your approval" with the exact recipients and text.
3. **Approve and send** sends it through Gmail's SMTP server. This route needs the paired desktop app's key, or the phone's near-PC confirmation, exactly like applying a file change. A token alone, chat, memory, model output or email text can't send.

Safety rules in `replies.py`:
- Replies only to a message already in the local copy. Recipients come from that message (Reply-To or From; reply-all adds its To/Cc minus Grey's own address). ZAE can't start new threads or choose arbitrary recipients.
- Each draft sends once (atomic status claim). A failed send stays a draft with the error shown.
- After sending, ZAE searches Gmail for the sent Message-ID. The result says "verified" only when Gmail shows it; otherwise the app says it isn't confirmed yet.
- Replies thread correctly (In-Reply-To/References, "Re:" subject) and Gmail files them in Sent.

## One-time setup (Grey)

1. Turn on 2-Step Verification for the Google account.
2. Create an app password at https://myaccount.google.com/apppasswords (name it "ZAENIA").
3. In ZAE, press **Fix it** on "Email: all mail and replies" in System Status, or say "connect my Gmail", or run `scripts\connect_gmail.ps1`. Type the address and app password in the window at the PC.

The app password is checked against Gmail first, then sealed to Grey's Windows account with DPAPI in `data/secure/gmail_app_password.dpapi`. It's typed only at the PC; no API route or chat turn accepts it. To revoke: delete the app password on the Google page above, or run `python -m core.email_watch.imap_mail disconnect` (the local mail copy is kept).

Optional, later: once IMAP works, the Gmail API can be disabled in Google Cloud Console and `data/email/token.json` deleted.

## Files

- `core/email_watch/imap_mail.py`: app-password connect, IMAP sync into the local copy, Gmail label mapping, sent-message confirmation. CLI: `python -m core.email_watch.imap_mail [connect|sync|disconnect]`.
- `core/email_watch/mail_store.py`: SQLite store (messages + FTS5 search, sync state, reply drafts).
- `core/email_watch/replies.py`: drafts, local-model suggestions, approved SMTP send.
- `core/email_watch/service.py`: important-email watch; picks IMAP or the Gmail API; `email_context()` for the brain.
- `core/email_watch/gmail.py`: older read-only Gmail API fallback.
- API (`core/api/ui_routes.py`): `GET /api/email/messages[?q=|label=]`, `GET /api/email/messages/{id}` (with thread), `GET|POST /api/email/sync`, `GET|POST /api/email/drafts`, `POST /api/email/suggest`, `PUT /api/email/drafts/{id}`, `POST /api/email/drafts/{id}/discard`, `POST /api/email/drafts/{id}/send` (desktop key or near-PC pass). Existing: `GET /api/email/important`, `POST /api/email/check`.
- UI: `desktop/src/components/assistant/MailPanel.tsx` (Assistant › Mail tab). Fix-it action `connect_gmail` runs the new connect script.
- Tests: `core/email_watch/imap_mail_test.py`, `core/email_watch/service_test.py`, `core/api/email_routes_test.py`.

## Gmail tabs and attachments (2026-11-09)

- **Tabs:** the Mail panel has Gmail's own Primary, Promotions, Social and Updates tabs (unread counts shown), plus All mail, Inbox, Unread, Starred and Sent. Categories come from Gmail search over IMAP (`category:primary` etc.): new mail is sorted on every check, and the whole mailbox is re-sorted hourly. Stored in `mail.db` (`category` column, added automatically to an existing database).
- **Attachments:** opening an email lists its attachments (name, type, size; fetched from Gmail when the email is bigger than the 300 KB local copy). **View** previews images, PDFs and text; **Read with ZAE** extracts the text with the chat file readers (PDF, Word, Excel, PowerPoint, images through the local vision model) and the local model summarises it; **Download** saves a copy to `Downloads\ZAENIA Mail` (never overwrites, never opens or runs the file). Attachments are fetched read-only on demand and are untrusted content.
- Code: `core/email_watch/attachments.py`; routes `GET /api/email/messages/{id}/attachments`, `GET .../attachments/{n}` (preview), `POST .../attachments/{n}/read` (notifications.read), `POST .../attachments/{n}/save` (notifications.write); `GET /api/email/messages?category=`.
