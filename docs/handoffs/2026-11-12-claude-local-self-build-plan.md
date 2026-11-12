# ZAE self-builds on local models only: plan

Written by Claude, 2026-11-12, for Grey. Goal from Grey: *ZAE should not use Codex or Claude for her own builds, without losing accuracy or efficiency.* This feeds the October 2027 objective (Master Build Plan section 30). Codex implements and Claude reviews, per the new workflow.

## 1. Where it stands today (from the code)

`core/assistant_platform/build_helper.py`:
- `choose_tool` picks **Claude Code** for every medium or large request whenever `api.anthropic.com` is reachable. Aider runs locally only for small requests or when offline. There is no Codex path.
- The local path is Aider plus Ollama: `model_for("code")` = Study (`qwen3:14b`), retried once on Seek (`qwen3.5:9b`). That gives three tries, with the last one on the other model.
- Good safety gates already exist: a separate git worktree (`ZAENIA-Helper`), a locked-path list, "changed behaviour but no test" rejection, the full Python suite, security suites, UI checks and TypeScript, an advisory local review by Seek, and Grey's approval before merging. It also waits while a game is running.
- The PC has an RTX 4070 Ti SUPER (16 GB). Talk (`qwen3.5:4b`, ~3.3 GB) stays loaded, so Study (~9.3 GB) fits alongside it.

So the safety side is solid. What's missing is everything that helps a small local model get the change right the first time: the right context, small steps, a failing test first, and measurement.

## 2. The principle: accuracy comes from the process, not a bigger model

Cloud models win mostly on hard, large, vague tasks. Small local models do well when the task is small, the right code is in front of them, and a test tells them when they're done. So:

- **Accuracy is guaranteed by gates, not trust.** Nothing reaches Grey unless tests and security suites pass. A local model that fails costs time but never ships a bad change. If ZAE can't do something, she says so honestly instead of quietly calling the cloud.
- **"Not losing accuracy" is measured.** A task type moves to "ZAE handles it" only when its local success rate on a fixed benchmark meets the target. Until then, she breaks the task into steps or tells Grey it's beyond her for now.
- **Efficiency means wall-clock time and Grey's foreground.** Builds run in the background, pause for games and voice, and use the idle GPU overnight for hard work.

## 3. The design

### A. Local only, with no silent cloud (first, small change)
- `choose_tool` returns `aider` (local) always. Claude and Codex are removed from automatic selection. Delete the `online()` check from selection.
- Keep `wantedTool="claude"` only as an explicit per-request owner choice in Code Doctor, labeled "uses your Claude allowance", default off. Or remove it entirely if Grey prefers; it's one flag.
- Show "Local: Aider on qwen3:14b" on every build request, and record the model in the request history.
- Test: medium and large requests choose local even when online; no `claude` process is spawned unless explicitly chosen.

### B. Give the model the right context (biggest accuracy gain)
- **Code retrieval before editing.** Seek builds an evidence pack for the brief: the target files, the functions and callers involved (a symbol index over `core/` and `desktop/src`), the nearest existing tests, and one or two similar past changes from git history. This replaces today's `file_hints` keyword matcher. Reuse ZAE's existing self-map (`claude/code-doctor-plain-english`) and semantic index rather than building a new store.
- Pass Aider the exact files (`--file`) and read-only context (`--read`), not the whole repo, so a 14B model's context window holds what matters.
- **Learn from Codex's and Claude's real work.** Each weekly task's handoff and diff (the approved engineering-record path from section 30.3) becomes a retrievable example: "last time a page got a Back button, this is what changed." That's how ZAE learns the project's patterns without training a model.

### C. Small steps with a test first
- **Plan step (Study):** turn the brief into one to five steps. Each step names its files and its own check. Reject a plan whose single step touches more than about three files or about 150 changed lines. Split it instead.
- **Reproduce step:** for a fix, write or find a test that fails first and record that it fails. For a feature, write the acceptance test from the brief's "Done when". This makes "done" objective for a small model.
- **Edit and check per step**, keeping each passing step. A failure retries only that step with the exact failing output (today's retry already does this for the whole task).
- Run fast, targeted tests per step (the touched modules and the nearest UI script), then the full suite and security suites once at the end. That's a big time saving over running everything three times.

### D. Smarter retries and model use
- Try 1 on Study (`qwen3:14b`). Try 2 on Study, given the failing test output plus the reviewer's notes. Try 3 on a different model (today Seek; later a dedicated coding model *if* the benchmark shows it's better).
- **Overnight deep mode:** a request that fails all three daytime tries can be queued for idle hours on a larger model (`gpt-oss:20b`, ~14 GB, already planned for Study overnight) with Talk unloaded. It's only used when Grey isn't using the PC.
- **Candidate coding models are an experiment, not an assumption.** Benchmark one or two free coder models that fit 16 GB against `qwen3:14b` on ZAE-Bench before switching anything. No new downloads until Grey okays the disk space.

### E. Review that actually catches things
- Keep the local reviewer, but give it a checklist (permissions or auth touched, error handling, test really exercises the change, no weakened assertions), plus deterministic checks: diff size, test files changed, no test skipped or deleted, locked paths, Gitleaks.
- Detect "the test was weakened": a test removed or edited while the code changed gets flagged automatically.

### F. When ZAE can't do it
- After the retries (and overnight mode if enabled), ZAE stops and writes a **task packet** (the same format Codex and Claude use) to `docs/handoffs/zae-needs-help/`. Grey can drop it into that week's plan for Codex. ZAE never calls the cloud herself.
- This keeps accuracy: ZAE only offers changes that passed, and anything harder becomes normal weekly work.

### G. Measure everything (ZAE-Bench)
- Seed ZAE-Bench v0 with about 20 real, already-solved tasks from the last two weeks of Codex and Claude work (Back buttons on pages, mail folder paging, map tile fix, version notes and so on). Reset to the parent commit, give ZAE the brief, check her result with the real tests.
- Record for every build request: model, steps, tries, wall time, GPU time, tests passed first time, reviewer findings and Grey's approve or reject.
- A task type (UI copy and layout, a single-file Python fix, adding a test, a new page from a template) becomes "ZAE handles it" when its local first-pass-or-repaired success rate meets the section 30.5 target on held-out tasks. The dashboard in Code Doctor shows this.

## 4. Order of work

| # | Work | Owner | Size | Done when |
|---|---|---|---|---|
| 1 | Local-only `choose_tool`, model shown, explicit opt-in or removal of Claude | Codex, Claude reviews | Small; next weekly release | Medium and large requests run locally while online; tests updated |
| 2 | ZAE-Bench v0 from about 20 real recent tasks, plus a runner that scores today's loop | Codex | Medium | A baseline success rate and time per task type exists |
| 3 | Code retrieval evidence pack (symbol index, callers, nearest tests, past similar diffs) | Codex builds, Claude designs the retrieval contract | Medium | ZAE-Bench success goes up against the baseline |
| 4 | Plan into steps, failing test first, per-step targeted tests | Codex, Claude reviews | Medium | Fewer full-suite runs; higher first-pass rate |
| 5 | Reviewer checklist and weakened-test detection | Codex, Claude reviews (security-relevant) | Small | Seeded bad diffs get caught |
| 6 | "ZAE needs help" packets instead of failure dead ends | Codex | Small | Failed requests produce a usable packet |
| 7 | Overnight deep mode and coder-model trial | Codex runs, Grey okays downloads | Medium | Measured comparison; switch only if better |
| 8 | Route one or two of each week's small items to ZAE first | Grey and Codex, weekly | Ongoing | The local share grows week by week, per the section 30.4 milestones |

Steps 1 and 2 can go in the next one or two weekly releases. Steps 3 to 6 fit the Dec–Feb "local coding runner" milestone in section 30.4, and 7 and 8 lead into Mar–Jun.

## 5. What this won't promise

A 14B local model won't match Codex or Claude on large, vague, multi-file work this year. The plan keeps accuracy by shipping only what passes, measuring honestly, splitting work small, and sending anything too hard into the normal weekly Codex/Claude workflow. It doesn't pretend she can do it. Her supported scope grows as ZAE-Bench numbers prove each task type.
