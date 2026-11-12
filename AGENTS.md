

\# ZÆNIA Development Instructions



\## Project

ZÆNIA is an offline-first personal AI assistant.



\## Source of truth

Read docs/architecture/ZAENIA\_Master\_Build\_Plan.md

before proposing architectural changes.

Read `docs/architecture/ZAENIA_Identity_and_Product_Charter.md` for ZÆNIA's canonical identity, Zack's interaction preferences, and product direction. The charter supplements the build plan; runtime security and authorization code remains authoritative for actions.



Inspect actual project files before modifying code.

Never assume earlier conversation details reflect current code.



\## Core architecture

1\. Reasoning and Planning Engine

2\. Learning and Memory Engine

3\. Execution and Security Engine



\## Security

\- Never commit secrets, credentials, or personal data.

\- Learning must never grant execution permissions.

\- Preserve authentication and authorization boundaries.

\- Obtain owner approval for sensitive operations.

\- Keep ZÆNIA functional without cloud services.



\## Development requirements

\- Explain code changes and their purpose.

\- Provide complete replacement files when requested.

\- Test modifications before claiming success.

\- Distinguish planned, implemented, and verified features.

\- Record relevant architectural decisions.

\- Update the master build plan when architecture changes.



\## Collaboration

ChatGPT and Claude must use the same repository history.

Develop changes on separate feature branches.

Do not overwrite another assistant's work without review.

Do not merge changes without owner approval.

## Latest handoff

Read docs/architecture/HANDOFF_2026-10-30.md first: it lists what Claude finished, how to build, test and install, and what is next.

## Release outputs

For every user-requested ZÆNIA application update, build both the native desktop app and the browser website (`desktop/dist-web`). Install the native build and refresh the served website when the user has requested the update be applied. Do not treat a source-only change as a completed app update.

**In-app updates (Grey, 2026-11-09):** from now on, stage updates instead of installing them. Bump the numbers and add a history entry in `desktop/src/config/versions.json` (UI-only changes bump `ui` and the changed tab; capability or security changes bump `system`; beta stays below 1.0), then run `scripts/stage_update.ps1 -Title "..." -Notes "first change|second change" [-Part ui|system|tab:<id>] [-RestartServer]`. It builds both outputs into `updates/pending/<id>/` without touching the installed app or the served site. Grey installs from Settings > Updates (Install, optional server restart), which runs `scripts/install_update.ps1`: hash check, backups in `backups/update-*`, close, install, mirror `desktop/dist-web`, optional restart, history in `data/updates/installed.json`, reopen.


## Detailed patch notes (Grey, 2026-11-10)
Every update in every ZAE component must include detailed categorized releaseNotes entries (kind, title, description) in version history or a JSON file passed to stage_update.ps1 -ReleaseNotesFile. Explain user-visible additions, changes, fixes, actual removals, performance/security effects and known limitations as applicable. Do not invent changes for empty categories. Preserve older notes and record new notes in staged manifests and installed history.

## Voice parity (Grey, 2026-11-10)
All past, present and new ZAE features must have a documented voice path. Route voice through the same guarded handlers as clicks; never grant permissions from recognition or learning. New UI features must expose named controls/page commands, examples and voice tests. Report coverage and platform-specific gaps honestly; native authentication, approvals and device dialogs retain their existing requirements. Contextual resume offers are voice-origin only and must respect later/not-now/dismiss replies without creating unrequested reminders.


## Weekly whole-system release cadence (Grey, 2026-11-11)
Sunday is the target for a substantial coordinated ZAENIA whole-system release. Plan and measure early in the week, freeze features Friday, validate the release candidate/recovery path Saturday, and release the verified scope Sunday through the existing authorization and owner-install workflow. Preserve accepted features and source provenance; include detailed patch notes, performance evidence, native/web artifacts, voice paths, known limits and rollback. Keep urgent fixes possible between Sundays. This week's plan is in the primary checkout's Master Build Plan, November 11-15 execution section.

## How Claude and Codex work together (Grey, 2026-11-12)
- Codex is default builder and release owner: versions, master-plan entries, staging and owner-approved main integration.
- Claude reviews security/auth/execution/updater changes and handles bounded architecture or difficult bugs from exact packets.
- C:\Projects\ZAENIA is the run/integration folder. Develop in C:\Projects\ZAENIA-codex\<topic> or C:\Projects\ZAENIA-claude\<topic>, on a separate feature branch from main or the current release branch. Never build installers from .tmp snapshots.
- Claim work in docs/architecture/WORKBOARD.md before touching shared files. Feature branches leave updates/notes/<topic>.json and a handoff; they do not bump versions or stage.
- Friday feature freeze; Saturday independent release review; Sunday one coordinated owner-installed release. Intelligence/learning does not grant execution rights.
- ZAE build requests are local by default. Explicit per-request Claude use is labeled as consuming the owner’s allowance; there is no silent cloud fallback.
