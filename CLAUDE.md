

\# ZÆNIA — Claude Development Instructions



Read and follow AGENTS.md.

## Latest shared owner update — 2026-11-03

Read `docs/architecture/HANDOFF_2026-10-30.md` and Master Build Plan **v3.54, section 29** in the current shared checkout at `C:\Projects\ZAENIA`. The owner confirmed Calm dashboard password setup is complete; enrollment is no longer pending (owner-reported, not a new independent live unlock test). The Complete Feature Blueprint additions are now in the roadmap, with existing implementations distinguished from planned work. Another worktree may contain an older copy; the current update remains uncommitted on `codex/calm-password-unlock`. Preserve separate feature work and existing approval boundaries.

Password implementation is published separately as `bbf3857` on `origin/codex/calm-password-feature`; inspect that branch before duplicating the work. The broader roadmap/draft updates above remain local, and `main` was not merged by this publication.

## File/web publication handoff — 2026-11-04

For the work requested in `docs/architecture/CLAUDE_TO_CODEX_COMMIT_REQUEST_2026-11-04.md`, read handoff section 19 and Master Build Plan **v3.55, section 28.59**. The publication branch is `codex/claude-file-web`, based on `bbf3857`, so it retains the password feature as well as the reviewed narration/web updates. Check the final verification/publication record before merging into your own branch. Existing runtime authentication stays unchanged; main-branch promotion is separate.



Before making changes, inspect the current

docs/architecture/ZAENIA\_Master\_Build\_Plan.md

and relevant source files.



Treat existing architecture decisions as authoritative

unless Grey approves a change.



Work on a separate feature branch.

Document all implemented changes and test results.

Never commit secrets or personal runtime data.



