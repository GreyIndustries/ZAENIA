# Handoff: Gmail over IMAP/SMTP — Claude, 2026-11-09

**Branch:** `claude/gmail-imap` (worktree `C:\Projects\ZAENIA\.tmp\claude-gmail-imap`), based on `cede912` (HEAD of `codex/stream-studio-plan` at the time). Codex's uncommitted work in the shared checkout was not touched. Not pushed, not merged.

**Owner request (Grey):** see all emails and reply to them, without Google Cloud limits, with less cloud work. Grey approved the plan: IMAP/SMTP + app password, local copy, replies need approval.

## What changed
- New: `core/email_watch/imap_mail.py`, `mail_store.py`, `replies.py`, `imap_mail_test.py`; `core/api/email_routes_test.py`; `desktop/src/components/assistant/MailPanel.tsx/.css`.
- Changed: `core/email_watch/service.py` (IMAP-or-API provider, 60 s checks while the first copy runs, chat context searches the local copy); `core/api/ui_routes.py` (email routes + operation patterns; send needs desktop key or near-PC pass); `core/api/system_brief.py` (Fix-it text); `scripts/connect_gmail.ps1` (app-password connect); `desktop/src/App.tsx` (Assistant › Mail tab, connect message); `desktop/src/core/bridge.ts`, `desktop/src-tauri/src/lib.rs` (comments; `/api/email` gets the 150 s timeout).
- Docs: `docs/EMAIL.md` rewritten; short section appended to the Master Build Plan (this branch's copy is v3.51; fold it into the current v3.6x plan when merging).

## Validation
- Python 3.11.18: `core.email_watch.imap_mail_test`, `core.email_watch.service_test`, `core.api.email_routes_test`, `core.api.near_pc_test`, `core.api.security_unlock_test`: 43 tests OK. The wider `core/api` suite's only failures were missing optional modules in the test container (PIL, typer, docx, soundfile) and Windows-only behavior, none in email code.
- Desktop: `tsc --noEmit` clean; browser Vite build OK; `assistant-actions` and `platform` script tests pass.
- Not done: Tauri native build, install, served-site refresh, live Gmail test (needs Grey's app password), gitleaks (not installed in the VM; a manual diff scan found no secrets).

## Next
1. Grey creates the app password and runs Fix it (or `scripts\connect_gmail.ps1`).
2. Live check: `python -m core.email_watch.imap_mail sync` → stored count rises; Assistant › Mail lists inbox; send one reply to himself and confirm "verified".
3. With Grey's approval: merge, build native + `desktop/dist-web`, install, restart the API server task, verify.
