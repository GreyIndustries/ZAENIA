# ZAENIA assistant upgrade — October 17, 2026

Latest owner decision: **Keep current startup authentication.** No migration ran
and no DPAPI startup snapshot exists. Retain passkey startup plus per-request
speaker verification. The migration described below is an inactive optional
implementation, not a required setup step or permission to activate it.

The current UI, floating windows, no-wake-word attention routing, concise
conversation style, Kokoro af_heart and personal-memory tools are preserved.
New tools live inside Assistant. API version is 0.8.0.

| Area | Delivered behavior | Practical limit |
| --- | --- | --- |
| Grounded answers | Weather, calendar, saved tasks and local status use source routes with check times; unavailable/denied sources do not fall through to model guesses. | Weather uses the configured place and daily forecast; no hourly prediction or arbitrary-place lookup. Live external sources need a network connection. |
| Speed and priority | Bounded foreground/intent/background scheduling, measured timings, persisted jobs, explicit priority and cross-process cancellation. | Priority work remains eligible alongside conversation; the installed model server/GPU can still serialize inference. Cancellation waits for a local step to yield. No fabricated progress percentages. |
| Hands | Optional local worker, bundled hand model, point/pinch/resize/fist/open-palm controls, frame disposal and camera shutdown on hide/failure. | Physical camera acceptance is pending. No face inference, saved video or cloud frame transmission. Open palm stops speech without cancelling priority work. |
| Apps | Register exact local executables/documents/folders, fingerprint targets, open reviewed or explicitly automatic proposals. | No arbitrary shell commands/arguments. App-specific editing requires a supported integration; launching alone does not provide general control of every app. |
| Workspaces | Named layouts, apps, project link and where-you-left-off notes; bounded restore with revision checks. | App grants remain machine-local. Restoring apps requires explicit selection/current authority. |
| Projects | Editable milestones, prerequisites, deadlines, statuses, real completion counts and next unblocked step. Local model can draft a plan for review. | Model drafts cannot claim completed work or execute steps; saved progress comes from updates. |
| Documents | Owner-selected folders, bounded local text/PDF/Word indexing, source paths/actual PDF pages, stale-file exclusion and grant revocation. | No OCR for scanned PDFs. Selected input/index size limits apply. Removing a grant does not delete source files. |
| Approvals/Undo | Separate voice/chat automatic-action policies, receipts and conflict checks for supported Undo. | Forgetting remains reviewed. Undo covers unchanged supported local actions, not arbitrary app actions or connected Google calendar writes. |
| Health/recovery | Model/listener/API probes, bounded local model warm-up, manual service restart, optional recovery of previously token-mode API, hashed source snapshots. | No blind model downloads, service killing, or unattended fallback from owner-policy startup. Source rollback needs rebuild/restart and is not executable/OS rollback. |
| Portability | Encrypted .zae-profile export/restore, merge/replace-conflicts choices, encrypted pre-restore recovery point and current-install readiness checks. | Excludes credentials, biometric enrollment, app grants, document roots, dependencies and model weights. Destination round-trip/cold-start/offline tests remain required. This is not a bootable OS. |

## Voice-only normal startup

The owner explicitly requested routine voice use without repeated passkey
prompts. `core.voice_security.voice_only` implements Windows-current-user DPAPI
protection of a narrow startup snapshot: enrolled speaker template and validated
rule/moral policy. It never stores the passphrase, owner proof or vault decryption
key. Normal PC voice still checks the enrolled speaker on each utterance; API
clients still need their existing token and privileged desktop actions their
paired desktop key. A process already running as the same Windows user can use
that user's DPAPI protection: this mode relies on the Windows account boundary.
Speaker verification is not an anti-replay guarantee.

The existing enrollment is encrypted with the original passkey. It must be
unlocked once to migrate; a voice recording cannot decrypt that existing file.
In Assistant → Health, select **Set up voice-only startup** and enter the existing
passkey in the real local console. Alternatively run:

```powershell
Set-Location C:\Projects\ZAENIA
.venv\Scripts\python.exe -m core.voice_security.voice_only enable
```

The desktop migration console requests API/listener startup after success.
If running the Python command directly, start those services normally afterward.
Startup automatically uses the
Windows-protected snapshot. Changes to enrollment, microphone binding, owner
credential, capabilities or protected policies invalidate it and require refresh.
A corrupt/stale snapshot fails closed instead of silently choosing another mode.
The one-time migration has not been completed by the coding agent: no owner
secret was requested in chat, read from a process or entered on the owner's behalf.
Encrypted portable backups retain their independent encryption/recovery needs.

The owner-approved API/listener pause succeeded. These real services remain
stopped until local migration/restart; the UI fixture is separate and disposable.
Codex's own action approval review is outside ZAENIA and cannot be disabled by
changing project settings.

The final native build succeeded at 21:57 local time. Automatic approval review
blocked launching the migration console because this exact Windows-protected
startup change and automatic service start need action-time confirmation. No
migration ran, no Windows-protected startup snapshot was created, and the real
services were not restarted through migration. The owner selected keeping current
authentication instead. Existing-authentication API and voice startup consoles
were opened locally afterward; their passkey entry stays in those consoles.
API startup is awaiting the owner's private passkey entry. The voice process
exited before authentication because its configured approved microphone was
missing or ambiguous; profile and calibration files are present. No fallback
microphone was selected and no microphone recording was made by the check.
The build and unrelated verification are done.

## Verification

- 234 isolated backend tests passed across assistant, API, memory, attention,
  follow-through, platform and voice-only changes.
- 50 simulated voice-security checks passed; live mic/latency acceptance pending.
- 181 interface checks passed: actions 74, platform/gestures 25, attention 18,
  workspace behavior 33, layout commands 18, appearance 13.
- Production web build and native Windows release build passed. Executable:
  `desktop/src-tauri/target/release/desktop.exe` (launch the rebuilt copy).
- Browser fixture verified project progress, persisted priority-job completion,
  named workspace restore and phone-width layout. The bundled hand worker loaded
  its model and detected no hands in a synthetic blank frame; camera stayed off.
- Window controls skip the focus-raising pointer handler, so closing/minimizing
  a window does not move it under the pointer before the click completes.
- Current warnings concern existing FastAPI startup events/httpx deprecations;
  these checks did not require owner credentials or real external calendar writes.

The original source copy at
`backups/assistant-platform-20261017-200943/source/` covers the directories recorded
when it was made, not every later-modified file or the entire installation.
`backups/voice-only-20261017/source/` separately retains the prior identity/API
sources. Keep these until live acceptance; use the new source-snapshot tool before
future upgrades.

Cleanup candidates and their exact paths are in `docs/CLEANUP_REVIEW.md`.
Nothing from that review has been deleted. This upgrade does not enable automatic
deletion of project files.
