# Approved assistant expansion — October 17, 2026

Zack selected all ten additions. Keep the current glass/amber UI, no wake-word
requirement and Kokoro af_heart. Latest owner selection: **keep current startup
authentication**. Voice-only migration remains inactive; do not enable the
Windows-protected snapshot or migrate credentials. Keep API/desktop credentials internal. Do not delete
cleanup candidates. A priority background analysis must continue alongside a
conversation, explain its current work and show measured progress; ordinary
background work may yield and obsolete automatic analysis may be cancelled.

## Delivery checklist

- [x] Ground conversational weather, calendar, tasks and system answers in actual sources.
- [x] Measure response latency and schedule background jobs with explicit priority/progress.
- [x] Optional local hand gestures, no face inference or recorded camera frames.
- [x] Allowlisted app/file launching and reviewed integration actions.
- [x] Named layouts and restorable work sessions.
- [x] Projects, milestones, dependencies and verified progress.
- [x] Search explicitly selected document folders with source/page references.
- [x] Configurable action approvals, receipts and conflict-aware Undo.
- [x] Component health, bounded recovery and pre-update rollback snapshots.
- [x] Encrypted portable profile, restore and SSD readiness checks.

These marks mean implementation and isolated verification, not completion of live
hardware/destination acceptance. See ASSISTANT_UPGRADE_20261017.md for limits.

## Remaining acceptance

- [x] Keep existing passkey startup, as selected by the owner; no migration ran.
- [ ] Restart API/listener and verify genuine/impostor speech on the approved mic.
- [ ] Try local camera gestures and tune comfort/dwell times as needed.
- [ ] Measure actual listening-to-speech latency on the owner's hardware.
- [ ] Export/restore and cold-start acceptance on the destination SSD/PC.

## Verification

Use isolated temporary stores, simulated process launches, fake camera landmarks
and source fixtures for automated checks. Never put test credentials in the real
profile. Run existing assistant/voice/UI regression suites, production builds,
and inspect the new controls in the unchanged visual shell. Physical camera,
microphone, and fresh-owner restore acceptance require the owner's hardware/session.

Source rollback copies: `backups/assistant-platform-20261017-200943/source/`.
This initial copy covers its listed source trees, not a complete installation or
all later-touched paths. Voice-only changes also have a separate before-copy at
`backups/voice-only-20261017/source/`. Do not treat either as a bootable backup.

## October 18 conversation continuity

Implemented bounded discussion anchors, relevant older exchanges, correction
guidance, topic changes and fresh-source temporal follow-ups. Grounded system
answers and typed fallback now retain the shared conversation context. Verified
with 250 isolated tests and four synthetic live-model cases. See
`CONVERSATION_CONTEXT_20261018.md`. Current startup authentication is unchanged.
