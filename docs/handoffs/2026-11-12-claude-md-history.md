

\# ZÆNIA — Claude Development Instructions



Read and follow AGENTS.md.

## Accumulated source publication — 2026-11-07

Read Master Build Plan **v3.62, section 32**, and handoff section 26. Owner requested publishing remaining work. Use clean branch `codex/pending-updates-2026-11-07`, based on current main at `ccc3b93`; older shared-branch history contains private coding-tool artifacts and must not be pushed wholesale. Publication includes Brief/security/gesture/evaluation changes and the latest plans, preserving the already-published password/file/hand/Fusion integrations. Review corrections preserve Stop priority, phone Brief access, fresh repeated briefs and explicit unsafe benchmark execution opt-in. Authentication and Calm guards stay intact; Stream Studio/coder roadmap proposals are not activated. Source checks do not establish a live install or hardware trial; see the handoff for exact evidence.

## Stream Studio plan — 2026-11-06

Owner requested ZAE replace Streamer.bot for Twitch/YouTube automation. Read `docs/architecture/ZAENIA_Stream_Studio_Plan.md`, Master Build Plan **v3.61, section 31**, and handoff section 25. This is a documentation-only proposal on `codex/stream-studio-plan`; no live platform/OBS adapter was found in the source audit and no account connection, moderation, stream output or deployment was performed. Reuse existing jobs, three engines/four brains and owner authorization. Keep audience input/public context/overlay credentials/audio separate from private ZAE. Start with inventory, a known-good restore and deterministic replay/read-only OBS; migrate one workflow at a time with shadow mode and rollback. The October 2027 coder roadmap in section 30 remains canonical and unchanged. Preserve all earlier source WIP and inspect actual code before implementing.

## October 2027 development objective — owner direction, 2026-11-04

The owner told both assistants that ZÆNIA must be able to handle the coding/upgrading workflow used with Claude Code and Codex by **October 2027**, with high reliability and efficient resource use. Read the shared `C:\Projects\ZAENIA\docs\architecture\ZAENIA_Master_Build_Plan.md`, **v3.60, section 30**, and handoff section 24 before making another parallel plan. That section is canonical; merge additional agreed requirements into it after inspecting the latest file. It extends the efficiency draft and the existing three engines/four brains rather than creating a replacement development system.

Latest reconciliation: **v3.60, sections 30.3/30.7 / handoff section 24**. On **2026-11-05**, the owner selected local independence for supported tasks with optional cloud for larger work, and **both** reviewed sanitized engineering records and a future scoped local Claude/Codex session-log importer. The selected importer still requires review of its exact access/exclusions before reading private logs. No logs were read, ingestion enabled, cloud data disclosure approved or session-persistence setting changed by this planning update. Budget/hardware remain undecided. Keep local and cloud-assisted results separate and the draft's alternative metrics distinct from section 30.5. The previous stale-status/CI/ZAE-Bench reconciliation remains in handoff section 23.

Start with the clean-checkout fixture/test baseline and unit-test CI gate, then explicit local/cloud dispatch, tested-version approval integrity, real isolation, repository/test retrieval and verified release receipts through the current helper. Current source supports parts of the workflow, but end-to-end coding success is not yet measured. The proposed 95% routine / 85% medium targets, 100 held-out task families and 30-day trial are acceptance goals, not achieved results. Learn from the accepted engineering-record/importer design under its reviewed scope; retain owner approval and protected-code boundaries. This update is documentation only on `codex/october-2027-development-roadmap`; no app/provider/authentication settings changed and no new GitHub push was made.

## Latest shared owner update — 2026-11-03

Read `docs/architecture/HANDOFF_2026-10-30.md` and Master Build Plan **v3.54, section 29** in the current shared checkout at `C:\Projects\ZAENIA`. The owner confirmed Calm dashboard password setup is complete; enrollment is no longer pending (owner-reported, not a new independent live unlock test). The Complete Feature Blueprint additions are now in the roadmap, with existing implementations distinguished from planned work. Another worktree may contain an older copy; the current update remains uncommitted on `codex/calm-password-unlock`. Preserve separate feature work and existing approval boundaries.

Password implementation is published separately as `bbf3857` on `origin/codex/calm-password-feature`; inspect that branch before duplicating the work. The broader roadmap/draft updates above remain local, and `main` was not merged by this publication.

## File/web publication handoff — 2026-11-04

For the work requested in `docs/architecture/CLAUDE_TO_CODEX_COMMIT_REQUEST_2026-11-04.md`, read handoff section 19 and Master Build Plan **v3.55, section 28.59**. The publication branch is `codex/claude-file-web`, based on `bbf3857`, so it retains the password feature as well as the reviewed narration/web updates. Check the final verification/publication record before merging into your own branch. Existing runtime authentication stays unchanged; main-branch promotion is separate.

Publication completed and GitHub verified at `1097322` on `origin/codex/claude-file-web`. Use that branch for integration; the older branch pointer in the shared working checkout was preserved.

## Constellation Fusion model handoff — 2026-11-04

Read `docs/architecture/SE_FUSION_MODEL_HANDOFF.md`, handoff section 20, and Master Build Plan **v3.56, section 28.60**. The owner's combined design is now a real Three.js mesh model, integrated into the existing SE view with the original lightweight option retained. A portable GLB and synthetic preview are included; reuse the existing builder/viewer rather than rebuilding them or modifying SecurityModel. This work is on `codex/se-fusion-model` in the shared checkout, which retains substantial earlier uncommitted Claude/Codex work. Inspect current Git status before staging or integrating. No new merge or GitHub publication was performed by this task.

## MediaPipe hand-control handoff — 2026-11-04

Read `docs/architecture/MEDIAPIPE_HAND_CONTROLS_HANDOFF.md`, handoff section 21, and Master Build Plan **v3.57, section 28.61**. Two-hand local tracking, deliberate target/pinch manipulation, window and Fusion-model transforms, calibration and camera preferences are implemented on `codex/mediapipe-hand-control`. Reuse the controller in the existing `handGestures.ts`; no new MediaPipe version is needed. Pinch is reserved for grabbing; open palm means Stop. Physical owner-hand/camera validation remains separate from the passing synthetic/browser checks. Preserve Calm/password/auth boundaries and inspect the shared uncommitted work before staging.

**Published and remote-verified:** `20a703e42dc4636478f291c54acc66383513e1e8` on `origin/codex/mediapipe-fusion`, based on `1097322`. Use that clean branch for hand/Fusion integration; the shared root checkout remains separate with earlier WIP. The publish tree passed TypeScript, all 23 included desktop scripts, native/browser release builds and Gitleaks. It preserves the current Constellation-first selector and Fusion option; unrelated Brief, SecurityModel and backend changes were excluded. GitHub `main` was not merged, and this publication did not replace the running app/site/Core.



Before making changes, inspect the current

docs/architecture/ZAENIA\_Master\_Build\_Plan.md

and relevant source files.



Treat existing architecture decisions as authoritative

unless Grey approves a change.



Work on a separate feature branch.

Document all implemented changes and test results.

Never commit secrets or personal runtime data.



