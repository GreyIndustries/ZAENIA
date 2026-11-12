# ZAE: voice, personal memory, and follow-through

For the subsequent adaptive UI, natural voice attention, user-led responses and
verified cleanup review, see [NATURAL_ASSISTANT_UPGRADE.md](NATURAL_ASSISTANT_UPGRADE.md)
and [CLEANUP_REVIEW.md](CLEANUP_REVIEW.md). This document records the earlier
shared-actions, memory, and follow-through delivery; its verification counts
and deployment version below describe that phase.

Zack's target is a capable personal systems assistant with natural conversation,
useful memory, situational awareness, and dependable action. This upgrade keeps
the current local Ollama model, Vosk/Piper speech, moral compass, and owner controls.

## Shared actions in chat and verified PC voice

Chat and verified PC voice now use the same deterministic action preparation:

- `Add a task to inspect the car` prepares a Normal-priority task.
- `Schedule car inspection tomorrow at three thirty pm` prepares a single
  local calendar event at 15:30 Pacific.
- `Schedule car inspection tomorrow` asks for the missing time. An answer
  such as `three thirty pm` completes that same request.
- `Schedule car inspection at 3 pm` accepts `tomorrow` as the missing date.

Chat displays the exact action in a review card. Select **Create task** or
**Add to calendar** to save through the independently authorized endpoints.
Verified PC voice reads the exact proposed action; say **confirm that action**
or **cancel that action**. A new verified owner turn is required for confirmation.
Voice proposals expire after 90 seconds and cannot cross voice sessions.
Incomplete calendar drafts expire after five minutes; a different request or
explicit cancellation clears them. Chat drafts are isolated by client/session.

Times are interpreted in America/Los_Angeles. Missing meridians, invalid/past
times, ambiguous daylight-saving times, and unsupported duration/location/
attendee/recurrence details require clarification. Speech normalization only
changes explicit time slots; it does not rewrite personal memory values.

Model prose cannot execute a tool. Every saved action uses an allowlisted
handler and a current operation-specific permission check. Sensitive file,
security, credential, arbitrary command, and external-message actions remain
outside these voice actions. Actual saved results supply confirmations.

## Lasting personal memory

Examples:

- `Remember my preferred response length is short` prepares a memory review.
- `Remember my running goal is finish a 5K` saves a named goal after approval.
- `What do you remember about my running goal?` reads the saved information.
- `Forget my running goal` prepares an exact-key removal after approval.

The **Assistant** area lets the owner add, review, correct, or forget facts,
preferences, goals, people, and commitments. The same key updates an existing
record without creating a competing fact. Each record retains explicit-owner
provenance and creation/update timestamps. No automatic personal profiling is
enabled. Credentials are rejected by both request parsing and storage validation.

Memory is local SQLite in `data/personal_memory/memory.sqlite3`, in a private
OS-owner/SYSTEM directory. It is distinct from credentials and source-code
retrieval. Model context includes bounded relevant facts plus at most two exact
communication preferences; all records are framed as reference data, never
instructions or authority. Reads and writes have separate permissions.

Forgetting removes the curated personal-memory record; it does not erase the
separate ordinary conversation history or statements previously spoken.
Explicit memory commands/results are not copied with their values into a second
conversation log. `memory.long_term_memory_enabled` in brain_config.yaml controls
automatic BrainService retrieval; the review panel remains separately available.

## Proactive follow-through

The local API owns a durable background worker and inbox at
`data/assistant_followthrough/inbox.sqlite3`. It reads saved ZAE scheduling
events and tasks with deadlines, without fetching external calendars per tick.

- Calendar events: one hour before, 15 minutes before, and scheduled start.
- Task deadlines: one hour before and once overdue.
- Catch-up is bounded to 24 hours. Obsolete lead stages are suppressed.
- Editing/deleting an event, completing a task, or clearing its deadline
  reconciles stale reminders.
- Database identities and a worker lease deduplicate polls and restarts. A replacement worker waits and takes over after a crashed process lease expires.

The Assistant inbox supports **Mark read** and **Snooze 15 min**. Settings enable
or pause local follow-through, opt into spoken reminders, and set quiet hours.
Defaults: enabled, speech off, quiet hours 22:00-07:00 Pacific. Due items remain
in the inbox during quiet hours. Connected visible apps show eligible new
notices; optional speech waits for idle interaction and uses an atomic shared
claim so PC voice and connected apps do not automatically announce the same
item twice. Snoozing permits a new announcement after the snooze ends.

The API must be running to generate reminders. App banners require the app to
be open and connected; optional PC speech requires the verified voice runtime
to be running. This upgrade does not configure external email, phone push, or
OS notification delivery. Saving an event confirms persistence, not that an
audio or external notification has been delivered.

## Build, verification, and use

From `C:\Projects\ZAENIA`:

```powershell
.\.venv\Scripts\python.exe -m unittest core.assistant_dialogue_test core.api.assistant_actions_test core.api.assistant_stream_test core.api.assistant_upgrade_test core.personal_memory.memory_test core.assistant_followthrough.service_test core.voice_security.actions_test
.\.venv\Scripts\python.exe -m core.voice_security.self_test
```

From `C:\Projects\ZAENIA\desktop`:

```powershell
npm run test:actions
npm run build
npm run build:web
npm run tauri build -- --no-bundle
```

The Windows build is `desktop/src-tauri/target/release/desktop.exe`. Existing
installed shortcuts are not replaced. Reload the new frontend and restart the
local API in its existing mode to activate backend changes. Full mode retains
its owner passkey requirement. Start **PC voice** from the app and enter the
existing passkey locally to bind the new narrow voice capabilities. No password
or microphone enrollment is changed by this upgrade.

Verified: 141 isolated Python tests, 50 existing simulated voice-security
checks, and 74 frontend validation checks passed. The Assistant panel, chat
memory review/save, and calendar clarification/save were also checked against
temporary data in a local preview. A sample-data screenshot is stored as
`docs/assistant-ui-preview.png`. Live microphone acceptance and physical audio
delivery still require the owner's normal PC voice startup and hardware.

Source backups are under `backups/assistant-upgrade-*` and
`backups/shared_voice_*`. The preview helper `scripts/assistant_ui_preview.py`
uses disposable data and a known test token, and must not replace the production
server.

## Further work

Extend conversational task completion and event edits with exact item selection,
add richer project follow-up and conflict detection, and measure real microphone
latency. Add additional model backends only after comparing quality and speed on
the owner's hardware.

Deployment verified: local API version 0.6.0 is running in its previous unattended mode on localhost:8766, and the health check reports the follow-through worker running. The Windows release executable was rebuilt successfully. Existing installed shortcuts were not replaced.

