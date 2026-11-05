

\# ZÆNIA — Claude Development Instructions



Read and follow AGENTS.md.

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

Publication requested: use clean branch `codex/mediapipe-fusion`, based on `1097322`, for the MediaPipe/Fusion source. It includes narrow Arena/Readiness wiring and the current Constellation/Fusion selector. Unrelated Brief, SecurityModel and backend WIP remain outside this branch. TypeScript and all 23 publish-tree desktop scripts pass; see handoff section 21 for release/publication evidence. The broader shared working branch remains uncommitted and is not the publication baseline.



Before making changes, inspect the current

docs/architecture/ZAENIA\_Master\_Build\_Plan.md

and relevant source files.



Treat existing architecture decisions as authoritative

unless Grey approves a change.



Work on a separate feature branch.

Document all implemented changes and test results.

Never commit secrets or personal runtime data.



