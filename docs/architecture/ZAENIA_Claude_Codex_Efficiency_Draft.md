# DRAFT — Efficient Claude Code and Codex development for ZÆNIA

Status: **proposed workflow for owner review**, 2026-11-02. This document records a draft; it does not enable automation, alter permissions, change subscriptions, or approve a production release. It supplements Master Build Plan sections 2, 11–13 and the existing three-engine/four-brain architecture.

## 1. Objective and recommended division of work

Use the existing Claude Pro and ChatGPT Plus subscriptions to deliver a reliable ZÆNIA v1 with less duplicated work and fewer wasted sessions. Give Codex primary responsibility for delivery. Reserve Claude Code for a difficult decision, reproduced blocker, or consequential review that benefits from a second analysis. Gradually make ZÆNIA's normal operation independent of both providers, then develop a separately verified local maintenance workflow.

This division responds to the owner's present Claude usage constraint. Change it when measured outcomes show another allocation works better. Neither assistant guarantees accuracy; a reproducible result and independent checks establish whether a change works.

| Participant | Default assignment | Required result |
|---|---|---|
| Owner | Select priorities, clarify important ambiguity, approve sensitive actions and releases | Agreed scope and observable acceptance criteria |
| Codex | Inspect relevant code; prepare task packets; implement ordinary features and fixes; run checks; prepare integration, documentation and release evidence | A bounded patch, actual check results, remaining limitations and recovery instructions |
| Claude Code | Resolve one difficult design question, diagnose one isolated blocker, or review a specified diff | Evidence with file/function references, severity, a proposed correction and how to verify it |
| Local tools and local models | File search, dependency maps, log filtering, formatting, deterministic calculations, preliminary analysis and sandboxed patch experiments | Reproducible artifacts; local-model findings remain advisory |
| Engine 3 | Enforce authentication, permissions and approved execution | A model's advice never grants authority |

Suggested starting allocation: roughly **80% of ordinary delivery work through Codex/local tools**, with Claude used selectively for the remaining difficult work. This is an adjustable work-allocation target, not a token forecast or a provider quota.

## 2. Subscription and spending rules

Codex is included with ChatGPT Plus, with finite usage. Check the account's usage dashboard; Codex CLI also provides `/status`. API-key sessions follow API pricing. Use subscription sign-in for this workflow and obtain owner approval before enabling additional paid usage. Do not assume either subscription covers arbitrary API requests from ZÆNIA. [Official OpenAI pricing and usage guidance](https://learn.chatgpt.com/docs/pricing).

Claude Pro usage is shared between Claude and Claude Code. Moving the same work between their interfaces does not create another allowance. Anthropic also documents that an `ANTHROPIC_API_KEY` environment variable can select API billing instead of subscription use. Confirm the authentication mode without displaying credentials. [Claude Pro and Claude Code access](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-max-or-ultra-plan).

Use Claude's `/usage` display to monitor the subscription allowance. Session cost estimates are not the Pro subscription bill. Keep context focused; save a handoff before clearing an unrelated task, and compact a continuing task when useful. These are context-management steps, not quota resets. [Claude Code usage and context guidance](https://code.claude.com/docs/en/costs).

Proposed operating budget: reserve approximately the final **25% of the displayed Claude allowance** for urgent blockers or consequential reviews. Check the current session and weekly indicators that the account actually provides. When capacity is low, continue suitable work in Codex/local tools or checkpoint the task. Extra credits, APIs and new subscriptions require an explicit spending decision.

## 3. Verified starting point in this repository

Read these files again before implementation; this is a source inspection, not a complete traffic audit or a new runtime test.

- `core/brain/brain_config.yaml` configures Ollama on loopback, local-first behavior and `send_conversation_to_cloud: false`. The Conductor and the latest historical local-model measurements are documented in `ZAENIA_Multi_Brain_Plan.md`, especially section 8.2.
- **Potential Claude usage source:** `core/assistant_platform/build_helper.py::choose_tool` automatically prefers Claude for non-small work when available, and can also choose it for small work when Aider is absent. `run_tool` can invoke Claude Code. Its local Aider path uses Ollama with `qwen3:14b`; the current helper has no Codex tool adapter. A local alternative existing in code does not prove it is installed and reliable on every task.
- `core/reasoning/providers.py` contains an optional OpenAI provider; `core/reasoning/__main__.py` exposes explicit provider selection for benchmarks. Its presence does not establish that normal chat currently calls OpenAI.
- The brain plan still requires live owner/other-speaker voice evidence. Historical speed measurements and passing builds are not evidence of complete offline endurance or independent recovery.
- The older development brief requested Python 3.11.9, while Master Build Plan section 24 records an intentional move of the runtime to Python 3.13.15. Reconcile environment records against the current approved runtime before packaging. Preserve the working environment until a migration is separately justified and approved.

## 4. One task, one writer, one useful handoff

1. **Codex prepares the evidence.** Reproduce the issue or define the feature's success case. Identify the relevant call path, existing equivalent implementation and smallest useful change. Supply actual errors and concise logs rather than asking Claude to rediscover the whole repository.
2. **Choose one primary writer.** Assign the task to Codex by default. Claude may own a task when the problem is already well isolated and its expertise or fresh analysis is useful. Give each agent a separate branch/worktree based on a recorded commit; the reviewer remains read-only. Parallel work must have separate file ownership and explicit dependencies.
3. **Deliver a bounded patch.** Complete one coherent outcome before expanding scope. Record what was observed, what changed, which checks ran and what remains uncertain. Do not add unrelated cleanup to a bug fix.
4. **Use review according to risk.** Ordinary layout/copy changes receive relevant local checks. Authentication, execution permissions, sensitive file access, data migrations and cross-engine changes receive an independent review and the relevant security/integration checks. During this development phase, Claude is a candidate reviewer for those bounded diffs; an exhausted allowance is a reason to defer a consequential release.
5. **Resolve evidence-based findings.** Codex fixes supported issues and reruns affected checks. If a finding concerns design intent, the owner resolves the decision. Two assistants agreeing is not sufficient evidence by itself.
6. **Prepare one release.** Run focused checks while iterating, then build both the native app and `desktop/dist-web` for an application release. Install and verify the approved release, confirm the served bundle and retain a recovery copy. Record pending live checks honestly. Documentation-only drafts require no app rebuild.

Both assistants read the current master plan and latest handoff. Give them the relevant sections and file paths, and allow expansion when necessary for correctness. Persistent instructions should stay concise and point to procedures stored in the repository. [OpenAI task-context guidance](https://learn.chatgpt.com/guides/best-practices), [Claude Code instruction guidance](https://code.claude.com/docs/en/best-practices).

Cloud task packets use source code, redacted logs and sanitized fixtures. Credentials, production databases, calendars, assessments, nutrition records and voice samples stay outside those packets unless the owner explicitly authorizes the specific disclosure. Git worktrees isolate edits; existing tool/OS permissions must enforce data access. Learning never expands that access.

## 5. Make each Claude assignment precise

Use a specific question such as: “Does this diff allow a retrieved document to bypass `files.read`?” or “The reminder is saved, but retrying creates a duplicate; identify the failing boundary from this reproduction.” Supply enough surrounding code to inspect callers and invariants. Small packets should not hide necessary context.

Proposed stop rule: after two distinct diagnosis attempts without new progress, checkpoint the evidence and send one focused packet to Claude. Ask for a diagnosis or a patch, not both agents independently rebuilding the feature. Limit follow-up to the remaining unresolved point; if neither can reproduce or explain it, collect better evidence before another expensive attempt.

Use Claude agent teams, repeated whole-repository audits and automatic reviews only when their expected value justifies the allowance. Default to one targeted Claude session. Measure any parallel strategy against total usage and useful outcomes.

### Reusable task packet

```text
Task ID / goal:
Baseline commit and assigned branch/worktree:
Primary writer / reviewer:
Observed behavior and exact reproduction:
Expected behavior and acceptance cases:
Relevant files, functions, schemas and call path:
Existing implementation to follow:
Constraints: local operation, security boundaries, compatibility, scope:
Evidence: focused diff and redacted error/log excerpts:
Checks already run, commands, results and environment:
Specific unresolved question:
Allowed edits and requested output:
Stop condition and next owner:
```

A reviewer returns actionable findings with evidence, or explicitly says no finding was established in the reviewed scope. An implementer returns the patch, actual check results, recovery steps and the next action. Save that packet in the repository so either assistant can resume without the entire chat history.

## 6. First implementation tasks after this draft is accepted

| Order | Proposed task | Acceptance evidence |
|---|---|---|
| 1 | Make development-tool selection explicit in the existing build helper. Use a validated local tool for eligible work; require an owner-selected cloud task before invoking Claude. Show the selected tool/model, detect quota failures and stop instead of silently choosing another paid path. | A normal local build request launches no Claude/OpenAI process or call; an explicitly assigned Claude task is bounded and recorded. No bypass of existing edit/release permissions. |
| 2 | Add a small task queue and handoff record using existing project/job infrastructure where possible. Keep the same repository history and record baseline/patch commits. | Either assistant can finish a sample task from its packet without repeating a full audit. No concurrent writers in one directory. |
| 3 | Build a fixed v1 acceptance set from the owner's real workflows using sanitized fixtures. | Reproducible checks for conversation context, reminder persistence/delivery, memory references, food logging, authorized actions and recovery. Expected side effects are specified. |
| 4 | Inventory runtime and development provider dependencies, including subprocesses, optional adapters, fallback behavior, CI reviews, hooks, MCP connections and scheduled jobs. | A reviewed list of necessary local services, optional internet integrations, cloud calls and credential locations, with no secret values in the report. |
| 5 | Run the independence trials below; close measured gaps in small releases. | Recorded local results, observed network behavior, restore evidence and unresolved failures. |

Until tool dispatch changes are implemented, verify the chosen provider before using a Code Doctor/build request. An unverified automatic selection should not be treated as a free local job. Adding a supported Codex adapter later is a separate implementation task; this draft does not claim one exists.

## 7. Independence milestones and completion criteria

**Milestone A — Recoverable build knowledge.** Keep the architecture, dependency versions, model manifests/licenses, installation instructions, checks and runbooks locally in version control. Store confirmed decisions and sanitized examples. This supports retrieval and reproducible maintenance; saving conversations does not transfer proprietary model weights or guarantee equivalent capability.

**Milestone B — Provider-independent runtime.** Close Claude Code and Codex, make their credentials unavailable to the test environment without destroying them, and disable OpenAI/Anthropic adapters in a reversible test profile. Run the agreed core workflow suite and observe outbound traffic. Startup, local conversation, voice, approved memory/document retrieval, local reminders, food logs and permitted local actions must work without those providers or hidden cloud fallback. Model failure must produce an honest, recoverable result.

**Milestone C — Reliable local operation and restore.** Record offline cold start, restart/resume, interruptions, retries without duplicate actions, missing models, owner/other-speaker rejection and resource use under realistic load. All critical authorization and data-integrity checks must pass. Complete a proposed seven-day normal-use trial, with failed or unavailable functions logged. Restore the app and a sanitized profile in a separate environment from retained code, dependencies, models and backups. SSD/OS work follows reproducible restore evidence and a documented hardware/storage baseline.

**Milestone D — Local maintenance.** Validate the local coding tool on representative small fixes and reviews. Start with diagnosis and draft patches in an isolated workspace. Require checks, owner review and recovery before promotion. Broader refactoring authority depends on demonstrated results and must remain separate from learned preferences.

**Milestone E — Owner-controlled disconnection.** Once the owner accepts the runtime and restore evidence, remove ZÆNIA's automatic OpenAI/Anthropic development calls and runtime access. Verify there are no provider subprocesses or outbound requests during the core suite. Account/subscription cancellation is a separate owner decision. Optional web research, weather, calendar, OneDrive synchronization and phone delivery retain their individually documented network requirements; they must report unavailable data honestly during a full internet outage.

Runtime independence and advanced local coding ability are separate deliverables. Completion means the agreed ZÆNIA release works and is recoverable under these conditions; it does not promise every future feature or cloud-level coding performance on the current GPU.

## 8. Measure efficiency and keep the scope finishable

For the next ten completed tasks, record: primary tool, outcome, time to completion, Claude/Codex usage indicator before and after when available, number of handoffs, rework, check results and escaped defects. These are observations, not exact token accounting or guaranteed monetary savings. Adjust the split based on completed, reliable outcomes.

Define the v1 release scope before adding another large feature group. Prioritize reliable voice/context, durable authorized memory, reminders/actions, existing personal workspaces, recovery and provider independence. Keep optional experiments in the backlog so progress toward an independently usable release is measurable.

Draft acceptance would authorize the workflow direction only. Each proposed implementation remains subject to the project's existing approval and release rules. No provider, billing, authentication, model or runtime configuration was changed while preparing this document.
