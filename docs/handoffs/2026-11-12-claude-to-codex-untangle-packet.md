# Codex task packet: one-time untangle and new collaboration rules

Written by Claude, 2026-11-12. Owner approvals (Grey, in the project thread, 2026-11-12 07:38 PT):
1. **Codex is the default builder and the release owner** (main, release branches, `versions.json`, staging, master plan entries).
2. **Do the one-time untangle, including the merge to `main` and the push at the end**, after the checks below pass.

Background and reasons: `ZAENIA_Codex_Claude_Workflow_2026-11-12.md` (same folder in project files, and `docs/handoffs/` in the repo).

## Goal

Every piece of finished work that is installed today (system 0.31.1, UI 0.26.0) is on `main` and pushed. After that, both assistants start every task from `main` or the current release branch, and nobody develops in `C:\Projects\ZAENIA`.

## State on 2026-11-12 (verify before acting; it may have moved)

- `origin/main` = `ccc3b93` (PR #8, 2026-11-04).
- `C:\Projects\ZAENIA` is checked out on `codex/stream-studio-plan` with about 242 changed paths (110 `desktop/src`, 26 `desktop/scripts`, 21 `core/api`, 17 `core/brain`, 12 `docs/architecture`, plus `.aider.tags.cache.v4` deletions).
- Unmerged work branches include `claude/core-behavior` (5a5c150, UI 0.26.0 C5 core), `claude/page-nav-split-screen` (6d73f6e, UI 0.23/0.24 page navigation), `claude/gmail-imap`, `claude/se-improvements`, `claude/research-upgrades`, `claude/code-doctor-plain-english`, `claude/brain-validation`, `claude/login-gate-phase1`, `codex/mission-deck-voice-snap-20261110`, `codex/map-navigation-workspace-2026-11-08`, `codex/mobile-pages-previews-20261110`, `codex/category-workspaces-orbit-20261109`, `codex/carplay-navigation-draft-2026-11-08`, `codex/pending-updates-2026-11-07`, `codex/enthon-research-se-2026-11-08`, plus the Nov 11 updater deployment-root repair and GODSPEED 0.16 aircraft work (find where they live; they may only be in the root WIP).
- C5 backups: `.tmp\core-c5-before-20261111-175652` and `-180951`. Leave them.
- Installed packages: `updates/installed/` (latest `ui-0.26.0-20261111-184427`, `system-0.31.1-20261111-124104`).

## Steps

1. **Save the root WIP.** In `C:\Projects\ZAENIA`, create `wip/shared-root-2026-11-12` from the current HEAD and commit everything there as-is, excluding only runtime data, secrets and tool caches that `.gitignore` should cover. Local only, no push. This is the safety net.
2. **Create `release/2026-11-15`** from `origin/main` in a new worktree, `C:\Projects\ZAENIA-codex\release`.
3. **Merge the installed work** into it: the branches above that are part of what's installed, then whatever is in the WIP commit and not on any branch (updater root repair, aircraft, anything else installed). Prefer merges from the clean branches. Take from the WIP only what's missing. Record in the handoff which source each area came from.
4. **Draft or experiment work is not installed** and stays out unless Grey picked it: Stream Studio plan code, CarPlay draft, login gate phase 1 practice mode. List what you left out.
5. **Check that it matches the install.** Build the native app and `desktop/dist-web` from the release worktree and compare against the installed UI 0.26.0 / system 0.31.1 behavior: the full Python suite, the security suites, the `desktop/scripts/*.test.cjs` checks, TypeScript, and the rendered navigation suite. Do not install. Do not stage unless this becomes the Sunday update.
6. **Add the collaboration rules** in this same release branch (text below): the AGENTS.md section, the short CLAUDE.md, `docs/architecture/WORKBOARD.md`, and the `updates/notes/` folder with a README. Move the long per-task history currently in CLAUDE.md into `docs/handoffs/2026-11-12-claude-md-history.md` so nothing is lost.
7. **Fix the duplicate section 47** in the master plan (Codex GODSPEED 47 and Claude's 47.1/47.2 UI notes) by renumbering, and add one short section recording these rules.
8. **Publication checks:** Gitleaks over the full diff from `origin/main`. Exclude private coding-tool artifacts (`.aider*`, Claude/Codex session files, `.tmp/`, runtime `data/`), as the 2026-11-07 publication note requires.
9. **Merge and push** `release/2026-11-15` to `main` and push. Grey approved this for this untangle once steps 5 and 8 pass. If anything fails, stop and report instead.
10. **Point the deployment at the real folder.** Coordinate with the open "Make weekly update install reliable" work so that `C:\Projects\ZAENIA` (now on `main`) is the deployment root and future builds never come from `.tmp` snapshots.
11. **Prune last.** Only after the push, remove worktrees and branches that are fully merged. Keep `wip/shared-root-2026-11-12` until Grey says it can go.
12. **Handoff:** `docs/handoffs/2026-11-15-codex-untangle.md`, covering what was merged from where, what was left out, check results and anything still open.

## Text to add

### AGENTS.md: new section near the top

```markdown
## How Claude and Codex work together (Grey, 2026-11-12)

- Codex is the default builder and the release owner. Only the release owner edits `desktop/src/config/versions.json`, runs `scripts/stage_update.ps1`, merges into `main` (with Grey's approval) and writes master-plan entries.
- Claude reviews security, authentication, execution and updater changes, designs new subsystems, takes bugs Codex has tried twice, and builds bounded features from a task packet.
- `C:\Projects\ZAENIA` is the run and integration folder. Never develop in it. Each task uses its own worktree: `C:\Projects\ZAENIA-codex\<topic>` on `codex/<topic>`, or `C:\Projects\ZAENIA-claude\<topic>` on `claude/<topic>`, started from the current `release/<sunday-date>` branch or `main`. Never build installers from `.tmp`.
- Before starting, add a line to `docs/architecture/WORKBOARD.md` (owner, branch, worktree, files or areas claimed). Hot files (versions.json, app shell and router, `core/api/server.py`, `core/api/ui_routes.py`, the master plan) need a claim or the release owner.
- Feature branches don't bump versions or stage. Put detailed release notes in `updates/notes/<branch-name>.json` and a handoff in `docs/handoffs/YYYY-MM-DD-<owner>-<topic>.md`.
- Weekly: Monday Grey picks a headliner and the release branch is cut. Feature freeze Friday evening. Saturday, Claude reviews `main...release/<date>`. Sunday the release owner stages one update for Settings > Updates.
- ZAE's own build requests run on local models only (see `docs/handoffs/2026-11-12-claude-local-self-build-plan.md`).
```

### CLAUDE.md: replace the body with

```markdown
# ZÆNIA: Claude development instructions

Read and follow AGENTS.md, especially "How Claude and Codex work together".
Then read WORKBOARD.md and the newest file in docs/handoffs/. Read master-plan sections by number when a packet names them; don't read the whole plan.
Work only in your own worktree on a claude/<topic> branch. Don't bump versions or stage. Leave a notes fragment and a handoff.
Older per-task history: docs/handoffs/2026-11-12-claude-md-history.md.
```

### `updates/notes/README.md`

```markdown
One JSON file per feature branch: {"branch": "...", "part": "ui|system|tab:<id>", "notes": [{"kind": "added|changed|fixed|removed|performance|security|known-limitation", "title": "...", "description": "..."}]}
The release owner merges all fragments into the -ReleaseNotesFile on Sunday, then moves them to updates/notes/released/<version>/.
```

### `docs/architecture/WORKBOARD.md`

```markdown
# Workboard (one line per active task; remove when merged)
| Owner | Branch | Worktree | Files / areas claimed | Status | Handoff |
|---|---|---|---|---|---|
```

## Review

Claude reviews the security-relevant parts of the release diff (updater, install scripts, auth, Engine 3, mail credentials) before step 9 if Claude capacity is available. If it isn't, note that in the handoff. Don't block the untangle on it unless something security-relevant changed since it was installed.
