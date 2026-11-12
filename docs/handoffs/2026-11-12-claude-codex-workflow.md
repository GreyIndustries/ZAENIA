# How to use Codex and Claude to finish ZÆNIA

Recommendation written 2026-11-12 from the actual state of `C:\Projects\ZAENIA` (git branches, worktrees, `versions.json`, `updates/`, AGENTS.md, CLAUDE.md, the efficiency draft and Master Build Plan v3.78). Nothing was changed, staged, merged or pushed while writing it.

## 1. The short answer

1. **Codex is the builder and the release owner.** It does most implementation, owns `main`, the weekly release branch, version numbers, staging and the master plan. It has more usage headroom on Plus, and it already built the updater, install scripts and publication branches.
2. **Claude is the architect, reviewer and fixer for hard problems.** Use it for security/auth/execution diffs, cross-engine design, bugs Codex has failed on twice, and one bounded feature at a time in its own worktree. Every Claude session starts from a short task packet, not "read the repo".
3. **Local tools (Aider + Ollama, ZAE herself) take small edits and repeatable checks**, and every week's finished tasks become test cases for the October 2027 goal.
4. **Feature branches never bump versions or stage updates.** They leave a release-notes fragment. One person (Codex) combines everything into one update by Sunday.
5. **Before any of this, do a one-time untangle**: about nine days of work is spread across ~20 local branches and ~18 worktrees, and `origin/main` hasn't moved since Nov 4.

This is the existing Nov 2 efficiency draft (`docs/architecture/ZAENIA_Claude_Codex_Efficiency_Draft.md`, Codex ~80% / Claude selective) made concrete, plus the rules that would have prevented this week's collisions.

## 2. What is actually going on (why the collisions happen)

| Finding | Evidence | Effect |
|---|---|---|
| Nothing has reached `main` in over a week | `origin/main` = `ccc3b93` (PR #8, Nov 4). Since then work sits on `claude/page-nav-split-screen`, `claude/core-behavior`, `claude/gmail-imap`, `claude/se-improvements`, `claude/research-upgrades`, `codex/mission-deck-voice-snap-20261110`, `codex/map-navigation-workspace-2026-11-08` and more | Each assistant starts from a different base, so each one's "latest" is different |
| The main folder is a shared pile nobody owns | `C:\Projects\ZAENIA` is checked out on `codex/stream-studio-plan` (a docs branch) with **242 changed files** (110 in `desktop/src`, 21 in `core/api`, 17 in `core/brain`) | Both assistants edit and build from it; neither can safely commit it |
| Version numbers are bumped by whoever stages | `updates/installed/` has UI 0.23.0, 0.24.0 (Claude), system 0.31.1 with combined UI 0.25.0 (Codex) and UI 0.26.0 (Claude) all on Nov 11 | Claude's 0.24 work was renumbered to 0.26 after Codex took 0.25 |
| Installs came from build snapshots | The installed app embedded `.tmp/claude-nav-split-build/...`, so Install looked in the snapshot (Codex's "Updater deployment-root repair" note in the master plan) | The 0.24.0 install landed in a build copy instead of the real folder |
| The shared docs are expensive and collide | Master plan is **310 KB**, has two section 47s; CLAUDE.md has grown into a long per-task history that every session reads | Each session spends tokens re-reading history; both assistants append to the same file |
| ZAE's own build requests spend Claude usage | `core/assistant_platform/build_helper.py::choose_tool` picks Claude Code for any non-small build request whenever it's online, and has no Codex adapter | Code Doctor / build requests from inside ZAE silently draw on the same Claude Pro allowance that ran out (`extra_usage_unavailable`) |

None of these are code-quality problems. They're coordination problems, and they're all fixable with ownership rules.

## 3. Who does what

| Work | Owner | Why |
|---|---|---|
| Routine features, UI pages, Map/Mail/LIFE polish, tests, previews, screenshots | **Codex** | Most volume; Codex has the capacity |
| Integration: merging feature branches, resolving conflicts, `versions.json`, `stage_update.ps1`, release notes, master plan entries, handoff index | **Codex (release owner)** | One writer for shared files ends the numbering and install collisions |
| Security, authentication, Engine 3 permissions, protected paths, updater/installer changes | **Codex writes, Claude reviews** (or the reverse) | Project rule: consequential changes get an independent review |
| New subsystem design (Conductor routing, memory links, local coding runner isolation, Stream Studio) | **Claude designs a short spec, Codex implements** | Spends Claude's capacity on thinking, not typing |
| A bug Codex has tried twice without progress | **Claude, with Codex's evidence packet** | The draft's stop rule; avoids two agents rediscovering the same thing |
| One bounded feature when Codex is busy | **Claude, in its own worktree, from a packet** | Fine, as long as it claims its files and doesn't stage |
| Small edits, formatting, running test suites, log filtering | **Local (Aider/Ollama) or scripts** | Free, and it builds toward October 2027 |
| Picking the weekly headliner, approving merges/pushes/installs, live voice and device trials | **Grey** | Owner control |

Claude should not run long builds, installs or Remote Control sessions on the PC. Those burn allowance on waiting. Let Codex or a script build; give Claude the diff to review.

## 4. Rules that stop the clashes

**a. Folders.** The main folder `C:\Projects\ZAENIA` becomes the *integration and run* folder only. It holds `main` or the current release branch, and it's what the installed app and served site point at. No one develops features in it. Each task gets its own worktree:
- Codex: `C:\Projects\ZAENIA-codex\<topic>` on `codex/<topic>`
- Claude: `C:\Projects\ZAENIA-claude\<topic>` on `claude/<topic>`

Stop building releases out of `.tmp\...` snapshots. Staging happens only from the release worktree.

**b. Branches.** Every feature branch starts from the current week's release branch (or `main`), never from another assistant's feature branch. If you need the other assistant's unmerged work, say so in the packet and wait for the release owner to merge it.

**c. Versions and notes.** Feature branches never touch `desktop/src/config/versions.json` and never run `stage_update.ps1`. Instead each branch adds `updates/notes/<branch-name>.json` with the detailed categorized notes (kind, title, description) the 2026-11-10 rule requires. On Sunday the release owner bumps the numbers once and passes the merged notes with `-ReleaseNotesFile`. That alone makes the 0.25/0.26 problem impossible.

**d. A workboard.** One small file, `docs/architecture/WORKBOARD.md`, one line per active task: owner, branch, worktree, files/areas claimed, status. Check it before starting. Hot shared files (`versions.json`, the app shell/router, `core/api/server.py`, `core/api/ui_routes.py`, the master plan) are edited only by the release owner, or by someone who has claimed them on the board.

**e. Handoffs.** One short file per task in `docs/handoffs/YYYY-MM-DD-<owner>-<topic>.md`, using the task-packet template from the efficiency draft (goal, base commit, branch, files, what changed, checks run with results, what's left). The release owner adds a short master-plan entry when the work merges, so each assistant isn't appending to a 310 KB file. Trim CLAUDE.md and AGENTS.md back to rules plus a pointer to the latest handoff; the per-task history moves into the handoffs folder.

## 5. Spending Claude's limited capacity well

1. **Stop the silent drain.** Change `build_helper.choose_tool` so Claude is used only when explicitly chosen (`wanted="claude"`), default to Aider/local, show which tool ran, and stop with a message on a quota failure instead of falling back to another paid path. This is task 1 in the efficiency draft and is a Codex job with a Claude review. It changes runtime behavior, so it needs Grey's OK.
2. **Packets, not exploration.** A Claude session gets the exact files, the reproduction or diff, and one question. Don't ask it to read the whole master plan; name the sections.
3. **One Claude thread per goal**, and avoid running several Claude threads in parallel on the same week.
4. **Keep a reserve.** Hold back roughly the last quarter of the weekly allowance for Saturday's release review and any emergency.
5. **Know when to hand back.** If Claude's allowance runs low mid-task, it writes the handoff file and Codex continues. Nothing should depend on Claude being available on Sunday.

## 6. The weekly rhythm (Sunday deadline)

| Day | Grey | Codex | Claude |
|---|---|---|---|
| Mon | Picks one headliner and up to three small items | Merges last week's release to `main` (after approval), cuts `release/<sunday-date>`, fills the workboard | Writes a short design packet for the headliner if it needs one |
| Tue–Thu | Answers questions when asked | Builds the headliner and most items in its worktrees | One bounded item or the hard part of the headliner |
| Fri evening | | **Feature freeze.** Merges finished feature branches into the release branch, resolves conflicts | Hands off anything unfinished; it waits for next week |
| Sat | | Runs tests, Gitleaks, builds native app and `desktop/dist-web` | Reviews the combined release diff, focusing on security, auth, execution and regressions; reports findings |
| Sun | Presses Install in Settings > Updates (optional server restart) | Fixes findings, stages **one** update with combined notes, writes the release handoff | |

Mid-week fixes for something broken become a patch release (0.x.**y**), staged only by the release owner. Unfinished work rolls to next week instead of being squeezed in.

## 7. This week: the one-time untangle

Do this before starting the rhythm. Codex is best placed to do it; Claude reviews.

1. **Save the shared pile.** Commit the 242-file WIP in the main folder onto its own local branch (for example `wip/shared-root-2026-11-12`) so nothing can be lost. Local and undoable. The C5 backups in `.tmp\core-c5-before-*` stay where they are.
2. **Build one catch-up branch from `main`** containing everything that's actually installed (system 0.31.1, UI 0.26.0): the Codex map/mission-deck/updater work plus `claude/page-nav-split-screen`, `claude/core-behavior`, `claude/gmail-imap`, `claude/se-improvements`, `claude/research-upgrades`. Rebuild from it and confirm it matches what's installed.
3. **Grey approves merge to `main` and push**, after Gitleaks and excluding private coding-tool artifacts (the Nov 7 note warns older shared history contains some).
4. **Point the installed app at the real folder.** This is the open "Make weekly update install reliable" thread, which is waiting on a folder approval.
5. **Only then** prune merged branches and the old `.tmp` worktrees.

Done this way, Sunday Nov 15's update is the catch-up release, and next Monday both assistants start from the same `main` for the first time in over a week.

## 8. Order for the rest of the build

This follows Master Build Plan sections 29.4 (core completion) and 30.4 (October 2027 milestones). Optional extras stay out of the core gate.

**Nov–Dec 2026: foundation**
1. Untangle plus weekly release machinery: notes fragments, workboard, release branch (Codex).
2. Explicit tool choice in the build helper (Codex, Claude reviews).
3. Clean-checkout test baseline and a unit-test check that runs on every release branch (Codex). GitHub Actions' free private-repo minutes should cover this; it's worth confirming before relying on it.
4. Finish the open threads: Mail and Map for chat and phone, and the weekend headliner (Codex, after Grey's picks).
5. Live voice trial and the reminder/calendar scenario end to end (Codex builds the test, Grey does the live trial, Claude reviews).

**Jan–Feb 2027: execution and independence**
6. Meal and project-goal-to-saved-result scenarios, restart continuity, cancellation without duplicate actions (Codex builds, Claude reviews the execution/security parts).
7. A local-independence test profile with cloud credentials unavailable (efficiency draft Milestone B).
8. The local coding runner through the existing build helper: isolation, approval integrity, checkpoints. Claude designs the isolation and approval part; Codex implements.

**Mar–Aug 2027: ZAE starts doing the routine work**
9. Turn each week's finished, sanitized tasks into ZAE-Bench task families (the approved engineering-record path). The weekly rhythm produces these for free.
10. Each week, route one or two small items to ZAE's local runner first, with Codex as fallback. Record first-attempt and repaired results separately, per section 30.5.
11. Medium multi-file features, verified install receipts and rollback, following the section 30.4 schedule.

**Sep–Oct 2027:** 30-day supervised trial, release-candidate freeze by Sep 30, held-out acceptance in October.

**On hold until the core passes:** Stream Studio, personal finance, OS/SSD packaging, new visual redesigns.

## 9. Ready-to-use prompts

**Monday kickoff (Codex):**
> Read AGENTS.md, WORKBOARD.md and the latest file in docs/handoffs. Merge last week's approved release to main if Grey approved it. Cut release/<sunday-date> from main. This week's headliner is ___ and the small items are ___. Put each on the workboard with an owner, branch, worktree and the files it touches. Don't touch versions.json until Sunday.

**Claude task packet:**
> Goal: ___. Base: release/<date> at <commit>. Your worktree: C:\Projects\ZAENIA-claude\<topic> on claude/<topic>. Files: ___. Reproduction or diff: ___. Question or acceptance cases: ___. Don't stage, don't bump versions; add updates/notes/claude-<topic>.json and a handoff in docs/handoffs when done.

**Saturday review (Claude):**
> Review `git diff main...release/<date>` for security, authentication, execution-permission and regression problems only. Report findings with file and line and how to verify each. Don't edit.

## 10. What needs Grey's decision

1. Codex as default builder and release owner, with Claude as reviewer and hard-problem fixer.
2. The one-time untangle in section 7, including the merge to `main` and push at the end.
3. Changing the build helper so ZAE's own build requests stop using Claude by default.

Once these are agreed, the rules in section 4 go into AGENTS.md and CLAUDE.md (short form) and the workboard is created, on a branch for review.
