# ZÆNIA Master Build Plan

**Living architecture, hardware, reasoning, memory and security guide**

Version: 3.79  |  Date: 2026-11-11 (v1.0: 2026-10-20)  |  Status: working proposal

> Canonical collaboration format: Markdown. Companion DOCX is a reading/export copy. Neither file automatically synchronizes with the local ZAENIA installation.

## 1. Purpose and document authority

This is the living architecture and development plan for ZÆNIA (ZAENIA in filesystem paths). It is intended to be readable and maintainable by Grey, ChatGPT, and Claude. It records desired architecture, verified observations, unresolved questions, approved design decisions, priorities, and acceptance criteria. It does NOT claim to replace a direct inspection of the live codebase.
Status: Proposed v1.0 integration guidance, drafted 2026-10-20. Existing code has not been modified by this document. The 2026-10-16 filesystem audit is the most recent cited codebase audit; its results may have changed.
Repository placement recommendation: C:\Projects\ZAENIA\docs\architecture\ZAENIA_Master_Build_Plan.md. Keep a corresponding .docx export for reading. Commit the canonical Markdown alongside the code and review changes by diff.

Current weekly execution plan: section 49 covers November 11-15, 2026, with a coordinated Sunday release target on November 15.

Current completion roadmap: section 29 integrates the owner's Complete Feature Blueprint, maps its twelve capability areas onto the existing architecture, and defines remaining work and acceptance evidence. Earlier dated entries remain historical records; use the latest relevant entry and actual code when assessing current status.

Owner's dated development objective: **October 2027**, recorded on 2026-11-04. Section 30 defines ZÆNIA's path to performing the coding, verification and upgrade workflow currently handled with Claude Code and Codex, using local models and owner-controlled integration. Capability and efficiency thresholds there are proposed acceptance targets, not achieved results.

Streaming extension requested 2026-11-06: section 31 and `ZAENIA_Stream_Studio_Plan.md` define the proposed Twitch/YouTube automation workspace and Streamer.bot migration. This is planned work; no live platform or OBS integration is claimed.

## 2. Non-negotiable architectural principles

A. Offline/local-first: core reasoning, memory, speech, authorization, and task execution must remain functional on the local computer without internet. Cloud models and synchronization are opt-in extensions, not critical dependencies.
B. Core-authoritative architecture: device clients (desktop, CarPlay/iPhone, watch, eventual remote node) are interfaces; ZÆNIA Core owns policy and canonical state.
C. Learning NEVER grants new execution authority. Only trusted explicit permission flows can authorize sensitive actions. Model output, memories, and retrieved documents are untrusted input to the permission engine.
D. System awareness initially limited to C:\Projects\ZAENIA; expand only to explicitly approved folders. Exclude secrets, dependencies, backups, artifacts, and build output from the active knowledge index.
E. Data minimization: derive useful patterns without keylogging, collecting passwords, recording authentication material, or persisting raw microphone audio. Support inspect, correct, disable, and delete for learned records with documented limits covering backups and exports.
F. Do not confuse a passing simulated test with a deployed and live-verified workflow. Label every feature planned, implemented, tested-in-isolation, integrated, or live-verified.
G. Explain implementation choices, commands, and files so Grey can learn Python and additional languages when appropriate. When handing off file changes, provide complete replacement file contents unless specifically asked for patches.

## 3. The three-engine architecture (core recommendation)

ENGINE 1 — REASONING AND PLANNING: Pluggable local inference provider; tokenizer and model runtime; prompt/context builder; intent and task decomposition; uncertainty signals; bounded planning; structured outputs; optional cloud adapter only upon explicit choice. Keep model selection independent from memory and policy. The currently reported local brain default was Ollama with qwen3:8b; verify before assuming it is still active.
ENGINE 2 — LEARNING AND MEMORY: SQLite-based canonical local event/personalization store initially; retrieval/index layer; explicit user facts; preferences; project knowledge; task history; correction events; derived behavior patterns with evidence, confidence, timestamp, provenance, retention, and scope. Do not assume every interaction is a fact. Use retrieval-augmented generation instead of constant retraining. Separate episodic memories, durable preferences, project facts, temporary working context, and inferred patterns.
ENGINE 3 — EXECUTION AND SECURITY: Tool and capability registry; authentication, authorization, action-specific fresh grants, consent and approval; protected-file boundary; dry run and effect preview; sandbox/allowlist; audit logs; rollback where feasible. Policy cannot be bypassed by language-model prompts, retrieved information, voice UI, or source-edit API routes.
ORCHESTRATOR: Takes an authenticated request; retrieves least-necessary relevant context; asks reasoning engine for a proposed plan; validates plan/actions against a deterministic tool schema and authorization service; executes permitted actions; observes results; stores only justified learning events. No direct unreviewed model-to-shell privilege.

## 4. Five-part intelligence model

1. Learned intelligence: pretrained model capabilities in language, abstraction, knowledge, reasoning patterns.
2. Working intelligence: conversation state, current task, short-term context, attention/KV caches where relevant.
3. Accumulated intelligence: validated long-term user memory, project knowledge, feedback and correction history.
4. Applied intelligence: tools, planners, environment observation, workflows, and end-to-end task execution.
5. Self-correcting intelligence: checks, uncertainty, tests, provenance, contradiction detection, human feedback, and measurable improvements.
These are practical engineering categories, not a universal scientific definition of intelligence. Systems are complementary: memory cannot substitute for reasoning, and sophisticated reasoning cannot substitute for deterministic permission enforcement. Measure performance by outcomes and correction reliability, not parameter count.

## 5. AI compute and memory guidance

GPU: many parallel arithmetic units and specialized tensor/matrix hardware; especially valuable for neural-net matrix multiplications. CPU: flexible orchestration, operating system, input handling, scheduling, data preprocessing, many utility services.
VRAM/HBM capacity: must fit weights, runtime workspace, active KV cache, and temporary tensors; memory bandwidth strongly affects token throughput. RAM: application, CPU-side model storage, preprocessing, indices, offload, scheduling; SSD/NVMe: persistent models, datasets, checkpoints, logs and memories. PCIe and inter-GPU communication can bottleneck offload and distributed compute.
Model-weight rough sizes: 70B parameters at FP32 ~280 GB, FP16/BF16 ~140 GB, INT8 ~70 GB, ideal 4-bit ~35 GB (decimal GB). Quantized formats have metadata and extra runtime overhead. Capacity alone does not establish speed or quality.
Training is different from inference. Training needs weights, gradients, optimizer states, activation storage and intermediate work. One illustrative Adam-like mixed-precision arrangement can take ~18 bytes/parameter for training state, ~1.26 TB for 70B parameters, excluding activations; actual strategies differ substantially. Inference commonly needs much less, but memory usage still grows with context and concurrency.
Attention KV cache grows with token count, model dimensions, active streams, and precision, depending on model architecture; grouped-query attention and KV quantization can help. Prompt processing and generated-token phases have different bottlenecks. Optimize separately.
Many GPUs can share work via data, tensor, and pipeline parallelism and sharding (FSDP/ZeRO). Their total memory does not automatically act like one transparent VRAM pool; networking and scheduling matter. Serving concurrency multiplies context memory and throughput needs; batching increases utilization but can affect latency.
Power/cooling are not peripheral. Factor GPU wattage, memory, CPU, network, redundant capacity, and cooling into any hardware plan. Do not choose parts on theoretical TFLOPS alone.

## 6. Quantization, inference and training strategy

Start with an existing appropriately licensed local model; benchmark relevant ZÆNIA tasks. Run small quantized options before investing in larger hardware. Existing default reported as qwen3:8b/Ollama, but verify.
Evaluate models on instruction reliability, long-context retrieval, structured tool calls, truthfulness, multi-step reasoning, latency, VRAM, idle RAM, peak memory, power and offline performance. Compare on the same dataset and prompts. Do not assume a bigger model wins all use cases.
Investigate 4-bit/8-bit weights, model distillation, FlashAttention or other efficient attention implementations, grouped-query attention, KV-cache quantization, caching, speculative decoding and model routing. Treat each as a testable optimization with quality and performance tradeoffs.
Use fine-tuning (LoRA/QLoRA) only when repeated measured failure modes cannot be solved well through prompts, retrieval, tools or schemas. Keep reversible datasets and train/evaluation splits; require documented consent for user-derived training data.
Training a new general-purpose foundation model is a long-term research program, not an initial dependency. For now, distinguish 'build our own AI system' from 'pretrain all neural weights from zero'. ZÆNIA can have independently authored orchestration, memory, policy and learning while using a replaceable local foundation model.

## 7. Initial hardware planning, not purchase instructions

Approximate 4-bit dense model weight floor: 3B 1.5GB; 7B–8B 3.5–4GB; 14B 7GB; 32B 16GB; 70B 35GB. Real inference footprints exceed weights alone because of overhead and context. Indicative VRAM planning bands: 3B 4–6GB; 7B–8B 8–12GB; 14B 12–16GB; 32B 24GB+; 70B 48–64GB+ depending on implementation/context. These are guides, not warranties.
Prioritize measurements on Grey's actual GPU/CPU/RAM before shopping; current exact GPU specifications and completed upgrades are not confirmed in this document. Consider greater system RAM and an internal NVMe as useful for indices/model files, but they do not fully replace GPU VRAM. Multi-GPU and cloud costs only after realistic profiling.
Benchmark matrix: model name/version/hash; quantization; context length; prompt tokens; output tokens; tokens/sec (prompt/decode separately); latency p50/p95; peak VRAM/RAM; power; accuracy on tasks; tool-use pass rate; errors; environment/build identifiers.

## 8. Memory and active-learning algorithm

Ingestion: approved events and explicit user statements -> privacy filter -> provenance classification -> candidate extraction -> duplicate/conflict detection -> tentative candidate -> validation/promotion -> searchable local store -> decay/review/retraction.
Memory classes: stable confirmed preferences; temporary task state; project-specific facts; episodic events; corrections; inferred patterns; discarded/no-store content. Record source, observed time, updated time, confidence, evidence IDs, last validated, expiration/retention, privacy class, and owner-editable status.
Contradictory memories: mark as disputed and favor the newest explicit confirmed instruction over older inferences. Never silently change explicit safety controls based on usage patterns. Prefer concise summaries derived from activity over invasive raw logging.
Personalization should adapt phrasing and helpful prompts, not invent permission. Include a 'why did you remember this?' trace, review/edit/delete actions, a no-learning mode and opt-in scopes.
Learning feedback loop: hypothesis -> offline candidate analysis -> eval against held-out tasks -> human approval when changing behavior -> versioned deployment -> monitor outcomes -> rollback. Avoid measuring progress solely by accumulated memory count.

## 9. Existing ZÆNIA subsystem integration

Local brain and reasoning: retain existing core/brain and core/reasoning boundaries; define a stable provider interface, context budget, retrieval contract, evaluation harness and policy handoff.
Voice: owner speaker verification must be consistent across dedicated listener and desktop UI; use Piper local/offline speech (preferred en_US-hfc_female-medium), Vosk and existing voice-gate components where verified. Do not persist raw audio by default. Keep CarPlay briefing accessible without the unnecessary passkey barrier previously identified; sensitive actions still require their policy checks.
UI: React/Tauri desktop remains a client of Core; edge launcher should appear only while full main UI is inactive. The UI aesthetic work is separate from authorization logic. Preserve the ZÆNIA acronym requirement.
Calendar/reminders/CarPlay: preserve standalone scheduling and delivery worker, multiple calendar entries with times, user-confirmed notification channels, Pacific timing behavior. Phone and watch are clients and must not become alternative policy authorities.
Files and system awareness: distinguish approved file management from a source-code editor. Restrict editing of enforcement modules and secrets. Index only active permitted project files by default.
Pattern recognition: implement derived usage and workflow patterns after the desktop UI is stable, with evidence limits and opt-out. No password capture, keylogging or raw microphone archive.
Future Amazfit T-Rex 3 Pro: watch client over Zepp/BLE to phone bridge to local Core, beginning with status/reminders and user-initiated talk; custom firmware can remain a separate later research track.

## 10. Prioritized remediation from the 2026-10-16 filesystem audit

P0 — Fix Windows path capitalization bypass in core/api/ui_files.py; canonicalize and check containment/link/reparse restrictions. Protect all code and config that controls authentication/authorization, including related API modules. Require fresh, action-bound owner approval for sensitive source changes. Preserve intentionally unattended low-risk briefing output.
P0 — Unify voice speaker verification for every entry point claiming owner-only access; differentiate typed or device-authenticated mode. Confirm live speaker acceptance and rejection.
P1 — Exclude generated Rust target output, build output, backups and historical snapshots from live retrieval; rebuild indices and isolate labeled historical lookup. Audit identified 4,261 system records and 6,282 semantic chunks, with extensive generated/backed-up content at that date.
P1 — Repair complete Windows dependency manifest and reproducible setup: sounddevicetzdata typo, duplicates, missing listed runtime packages and model installation steps; test clean installation.
P1 — Connect calendar events, notification-channel selection and persistent delivery worker; live-test 60-min, 15-min and event-time notices.
P1 — Upgrade task synchronization beyond 60-second polling if immediate live sync is required; retain full event history if permanent history is desired rather than capping at 60 entries.
P2 — Develop bounded general file operations, productivity summaries and anomaly detection only after enforcement gaps close.
Audit note: tests passing in isolation were not sufficient to prove live API, Ollama availability, production security, or real CarPlay/voice acceptance. Do not mark them as verified without new evidence.

## 11. Phased plan and acceptance gates

PHASE 0 — Stabilize security and source of truth: freeze baseline; fix protected-path and code-edit authorizations; integrate voice identity; rebuild retrieval; document install. EXIT: red-team/regression tests, protected routes, clean-install test, live owner/other-speaker trials pass.
PHASE 1 — Local brain reliability: provider interface, context budget and RAG, memory schemas, structured tool proposals, diagnostics. EXIT: offline cold-start, accurate project-file references, reproducible benchmark suite, clear error reporting, no unauthorized tool action.
PHASE 2 — Integrated desktop and voice: UI/Tauri contracts, local voice to reasoning to speech, connection indicators, owner-only voice policy. EXIT: live end-to-end tests, realistic latency logs, recoverable disconnected mode.
PHASE 3 — Learning and self-correction: episodic memory, verified preferences, proposal queue, pattern extraction, owner review, forget/rollback. EXIT: memory provenance demonstration, conflict handling, no-store test, permission non-escalation tests.
PHASE 4 — Action reliability: reminders, calendar, file operations, task state, CarPlay/phone bridge and workflow execution. EXIT: real-device deliveries and idempotent retries, reversible file operations, audited approvals.
PHASE 5 — Scale and optional cloud: model routing, optional external model API, mobile/watch access, networking, encrypted sync, backup/restore, benchmark larger models. EXIT: core remains functional during internet loss and cloud disconnect; well-tested reconciliation and failure isolation.
Each phase must publish actual evidence, not claims about model intelligence from simulated-provider plumbing alone.

## 12. Evaluation scorecard

Maintain baseline tasks spanning: reasoning accuracy; reading actual ZÆNIA project files; source citation fidelity; multi-turn continuity; retrieval freshness; memory confirmation; contradiction correction; sensitive request refusal; allowed task execution; action authorization; voice speaker identity; real reminder delivery; offline endurance; recovery after crash; model swap; latency; RAM/VRAM and power.
Record testcase ID, setup, input, expected output/side effect, observed output, pass/fail, severity, test type (unit/integration/live), code commit, model/version, date, and reviewer. Do not promote experiments to stable solely because they sound plausible or pass one demo.

Section 29 adds integrated completion scenarios and measurable requirements for decision continuity, usefulness feedback, simulation, new integrations, device reconciliation and independent local operation. Record results against those scenarios alongside this scorecard.

## 13. Collaboration contract for ChatGPT and Claude

CANONICAL SOURCE: Markdown file in the ZAENIA repository, version-controlled. DOCX is a reading snapshot. Each assistant must read current plan, newest audit, and relevant actual files before recommending edits; do not infer current implementation from prior chats.
CHANGE PROCEDURE: (1) describe objective and changed sections; (2) cite actual code paths and evidence; (3) propose a decision with tradeoffs; (4) label proposed vs implemented; (5) make one narrow change set; (6) run tests and record results; (7) append dated change log; (8) update phase tracker and open questions; (9) preserve rejected decisions and why; (10) bump version.
COLLABORATION RULE: Never silently replace another assistant's confirmed decision. Conflicts produce an ADR (architecture decision record) explaining options, evidence, and final user-approved choice. User approval overrides model preferences. No merge-by-memory: re-open the canonical file on every new work session.
HANDOFF TEMPLATE: Date; author (Grey/ChatGPT/Claude); repository commit; baseline version; task objective; exact files examined; verified findings; hypotheses; proposed actions; files changed; security effect; tests performed/results; rollback; next actions; unresolved questions.
VERSIONING: MAJOR for architecture/security contract changes; MINOR for new modules or accepted designs; PATCH for clarifications/corrections. Include timestamp and digest where possible. Future updates are manual/triggered by a session or repository workflow; this document does not self-update.

PROPOSED SUPPLEMENT — [Claude Code/Codex efficiency and local independence draft](ZAENIA_Claude_Codex_Efficiency_Draft.md). Prepared for owner review on 2026-11-02. It proposes Codex-led delivery, bounded Claude assignments, explicit development-tool dispatch, shared task packets, usage tracking and evidence gates for operation without OpenAI/Anthropic. This is a draft, not an adopted dispatch or authorization policy; no runtime configuration was changed.

## 14. Architecture decision log

ADR-001 | 2026-10-20 | PROPOSED | Three engines: reasoning, learning/memory, execution/security, coordinated by a deterministic orchestrator.
ADR-002 | 2026-10-20 | REAFFIRMED INTENT | Local/offline core; external services are optional, independently replaceable.
ADR-003 | 2026-10-20 | PROPOSED | Use existing pretrained local model as replaceable inference dependency; prioritize RAG/evals and only fine-tune for measured gaps.
ADR-004 | 2026-10-20 | PROPOSED | Store derived user patterns with provenance, review and retention controls; prohibit learning-triggered privilege escalation.
ADR-005 | 2026-10-20 | PROPOSED | Repository Markdown is canonical, DOCX is companion export; both assistants follow an explicit change/handoff protocol.
Pending user review: proposal statuses must not be converted to accepted without Grey's confirmation.

## 15. Open questions / decisions to verify

What are the current GPU model, VRAM amount, RAM amount, disk resources, OS version and local model benchmarks? Do not infer from past partial specs.
Which local model/provider configurations are currently operational under live conditions?
Where should the canonical Markdown be placed if the project repository already has a competing master plan? Merge rather than replace unseen decisions.
Which memory database and embedding index are currently authoritative, and how will stale indexes be migrated safely?
Which live voice and CarPlay end-to-end trials have passed since the 2026-10-16 audit?
How should proposed learned facts be promoted: automatic low-risk rules, owner review for all, or tiered review?
Which directory and device permissions should be available at each phase?
What constitutes passing reasoning quality for Grey's daily use, and what is the budget for optional cloud fallback?
Do ChatGPT and Claude each have access to the latest repository content in a given session? Verify every time.

## 16. Change log and session template

2026-10-20 | v1.0 | Initial integration of AI GPU/RAM/training/inference guidance, three-engine architecture, intelligence model, improvement/evaluation strategy, prior ZÆNIA requirements, 2026-10-16 audit priorities and multi-assistant edit process. Document-only change; no project files altered.

COPY FOR NEXT UPDATE:
Date / timezone:
Editor:
Starting document version and repository commit:
Modules or decisions affected:
Observed codebase facts + files inspected:
Requirements and user approval:
Proposed change and alternatives:
Security/privacy impact:
Implementation file list:
Tests / benchmark numbers:
Known failures and rollback:
Updated status and next step:
New document version:

## Appendix A. AI mathematical references and examples

Illustrative dense weight memory: parameter_count × bytes_per_weight. Example: 70B × 2 bytes = 140 GB for FP16 weight storage (decimal), before runtime overhead.
A conventional illustrative mixed-precision Adam configuration: FP16 weights 2B + FP32 master weights 4B + FP32 gradients 4B + Adam first/second moments 8B = 18 bytes per parameter, excluding activations. Alternative implementations differ.
Illustrative KV cache: 2 × n_layers × n_KV_heads × head_dim × cached_tokens × bytes_per_value × number_of_sequences. Model-specific tricks change the shape.
Serving approximate aggregate output rate: concurrent generating users × average output tokens/sec each. Required accelerator count cannot be inferred from this alone: actual batch throughput, prefix processing, latency, model size, memory capacity and availability matter.
Data parallelism boosts throughput through replicated models; tensor/pipeline parallelism distributes model computations; state sharding reduces optimizer/parameter duplication. High-speed interconnects reduce—but do not eliminate—communication costs.
Numerical hardware figures (illustrative published specifications from the prior discussion, subject to manufacturer SKU and revision): H100 SXM 80GB ~3.35TB/s; H200 SXM 141GB ~4.8TB/s; B200 SXM 180GB up to ~8TB/s. Validate product-specific specs when selecting hardware.
All numerical estimates are educational guides, not measured ZÆNIA runtime requirements.

## Appendix B. Sources and evidence discipline

Primary project evidence: 'ZAENIA-Filesystem-Audit-2026-10-16.md', a read-only snapshot and not a current re-audit. User requirements from prior ZÆNIA discussions, including local-first, approved-scope awareness, voice, UI, CarPlay, teaching style and learning/security boundaries. Technical hardware examples from the AI hardware explanation in this conversation and public manufacturer/engineering documentation. Re-check public hardware numbers and benchmarks at procurement time.
Evidence labels to use in future entries: USER REQUIREMENT / VERIFIED CODE / UNIT TEST / SIMULATED TEST / LIVE DEVICE TEST / HYPOTHESIS / PROPOSAL / DECISION / DEPRECATED. Never treat generated guidance as verification of actual installation.

## 17. Status update — Claude, 2026-10-21 (v1.1)

Date / timezone: 2026-10-21 UTC. Editor: Claude (working on Grey's PC). Starting version: 1.0. Repository commit: none yet (git initialised, nothing committed).
Scope: corrects facts that v1.0 marked "verify", records what was built 2026-10-17 to 2026-10-19, and fixes one P0 item. ADR statuses are unchanged; none are converted to accepted without Grey.

### 17.1 Verified environment (VERIFIED CODE / LIVE DEVICE TEST, 2026-10-21)

- GPU: NVIDIA GeForce RTX 4070 Ti SUPER, 16 GB VRAM. CPU: AMD Ryzen 9 7900X (12 cores). RAM: 32 GB (31.2 GB visible). C: free about 858 GB. OS: Windows 11 Pro.
- Brain (USER REQUIREMENT, live): Ollama with **llama3.1:8b** (Grey's choice, 2026-10-17), fallback qwen3:8b; core/brain/brain_config.yaml. context_window 8192, keep_alive 10m. Installed models: llama3.1:8b, qwen3.5:4b (photos and screen watch), nomic-embed-text (topic tracking), qwen3:8b, qwen3:4b, qwen2.5:1.5b, llama3.2.
- Voice output (USER REQUIREMENT, live): **Kokoro, voice af_heart** (core/voice_output/neural_voice.py); Piper is now only the fallback. Section 9's Piper preference is superseded by Grey's choice.
- Listening (USER REQUIREMENT): no wake word; the local brain decides what is meant for ZAE (ambient.require_name: false). The name still works.

### 17.2 Built since v1.0's audit baseline (labels per Appendix B)

| Feature | Where | Status |
|---|---|---|
| Owner profile recall and learning (user_understanding kit wired into the brain) | core/personal_memory/owner_profile.py | INTEGRATED, UNIT TEST |
| Conversation topics: continue, switch, resume, key points | core/brain/conversation_threads.py | INTEGRATED, UNIT TEST, live model spot check 16/16 |
| File sharing in chat (text, PDF, Word, Excel) | core/api/chat_files.py | INTEGRATED, UNIT TEST, live model check |
| Game mode (free the brain while a full-screen app is in front) | core/assistant_platform/game_mode.py | INTEGRATED, UNIT TEST, live detection check |
| Live monitor watching (opt-in, memory-only frames) | core/assistant_platform/screen_watch.py | INTEGRATED, UNIT TEST, live vision check |
| App keeps listening when PC Voice can't verify the owner | core/api/ui_voice.py, desktop/src/App.tsx | INTEGRATED |
| Ollama out-of-memory retry on CPU | core/brain/local_llm.py | INTEGRATED |

Learning in 17.2 never grants permissions. Profile records, topic notes, file contents and screen notes reach the model only as labeled reference data (principle C).

### 17.3 Section 10 P0 items

- **P0 path capitalisation bypass in core/api/ui_files.py: CONFIRMED and FIXED 2026-10-21.** Evidence: before the fix, `core/Foundation/rules/engine.py` resolved to a real file but `is_protected()` returned False, so the UI edit check could be bypassed. Fix: `is_protected()` compares case-insensitively and by resolved path, and fails closed on errors. The protected list now also covers the modules that map requests to operations (server.py, ui_routes.py, assistant/chat/operator/platform routes, mobile_auth.py, assistant_platform/capabilities.py). Tests: core/api/ui_files_test.py (3 pass). Rollback: backups/claude-protected-paths-20261021/ui_files.py.
- **P0 unify voice speaker verification: OPEN, needs Grey's decision.** PC Voice verifies the owner's voice (ECAPA). The desktop/phone app microphone is authenticated by the device (desktop key or API token), not by speaker verification. Since 2026-10-18 the app mic also listens when PC Voice keeps rejecting the owner. Live acceptance is currently failing: PC Voice rejected every turn (speaker_rejected), and calibration recorded from "Sonar - Stream" while verification used "Sonar - Microphone". The calibration recorder now uses the approved mic, but **recalibration (core.voice_security.calibrate) has not been run**, and the Sonar mic exists only while SteelSeries GG runs. Options: (a) keep the app mic as device-authenticated and label it so; (b) speaker-verify app mic turns too; (c) a mix, such as voice-verify only for actions.

### 17.4 Other observations

- Repository hygiene (P1-adjacent): git was initialised with everything staged and no commit. Staged files include user_understanding/ (full personal assessment), config/settings.yaml (contains a real database password), core/calendar_context/zaenia_calendar.yaml (real appointments), and a 2,953-file .venv_broken_20260829 folder that .gitignore does not exclude. Resolve before the first commit, and especially before adding any remote.
- Section 15 open question "where should the canonical Markdown live": placed at docs/architecture/ZAENIA_Master_Build_Plan.md. Existing docs/ZAE_OS_ROADMAP.md and docs/ASSISTANT_ROADMAP.md overlap in places and should be merged into this plan rather than replaced.
- The .docx beside this file is the v1.0 snapshot and does not include this section.

### 17.5 Change log

2026-10-21 | v1.1 | Claude | Verified hardware and model facts; recorded features built 2026-10-17 to 2026-10-19 with status labels; fixed P0 path-case bypass (code change: core/api/ui_files.py, test added); documented the open voice-verification decision and repository hygiene risks. ADR-001 to ADR-005 remain PROPOSED.

## 18. Tech news module — Claude, 2026-10-21 (v1.2)

Objective (USER REQUIREMENT, Grey 2026-10-21): "create a module for tracking tech news with the top 10 most credible and honest tech news sources."
Placement: an optional online data source alongside weather and traffic. It does not change the three-engine architecture. Feed text enters the Reasoning engine only as labeled reference data. It never reaches the Learning engine (no profile learning from news) or the Execution engine (no permissions).
Implementation (branch feature/claude-development, not merged): core/tech_news/ (service, sources.yaml, tests); API GET /api/news/tech and POST /api/news/tech/refresh (status.read); background refresh every 30 min in the API server; brain context only for news questions; Tech News window in the desktop and phone UI. Details and the source list: docs/TECH_NEWS.md.
Security effect: outbound HTTPS GET requests to 10 fixed public feeds; no user data sent; DTD/entity XML refused; 3 MB cap; cache in data/news (gitignored).
Tests: core/tech_news/service_test.py (8 pass); existing brain/API suites pass; desktop tsc, UI script tests and build pass. Live: 10/10 feeds reachable, 225 stories grouped in 2.1 s; local model answered news questions with sources named. Status: IMPLEMENTED, UNIT TEST, live-checked on the branch; not yet INTEGRATED in main.
Rollback: revert the branch commit.

2026-10-21 | v1.2 | Claude | Added tech news module (section 18). No ADR change.

## 19. Conversation-topic tracker fix — Claude, 2026-10-21 (v1.3)

Objective (approved by Grey 2026-10-21, assessment priority 1): make topic tracking hermetic. The 10/19 tracker read `data/conversation_memory.jsonl` and wrote `data/conversation/threads.json` itself, bypassing `BrainService.load_recent_messages()`. As a result `turn_context_test` failed (1 on the branch, 3 on main), and running the test suite could write test topics into Grey's live topic file.
Change (Reasoning engine, core/brain): `load_recent_messages()` rows now carry their timestamp (`at`). `prepare_turn()` gives the tracker only that history, and only when it is timed; untimed history (tests, old logs) keeps the plain behaviour and never touches topic state. `ThreadTracker.route(question, history)` builds exchanges from the history it is given, and the state file stays next to the log in use. New: recent exchanges that no topic holds yet (within 45 min) become the current topic, so a fresh log or pre-tracking turns still give follow-ups their context.
Files: core/brain/brain_service.py, core/brain/conversation_threads.py, core/brain/conversation_threads_test.py.
Tests: conversation_threads_test 9 pass (4 new); turn_context_test passes; full suite 503 run, 0 failures, 27 errors, all from personal files kept out of git (core/reasoning/cases.json, scripture manifest), which is priority 2. SHA-256 of the worktree's data/conversation files was identical before and after the full suite. Live: the two 8-message topic scenarios still score 16/16 against llama3.1:8b and nomic-embed-text. End-to-end through BrainService on a temp log: follow-up kept context, new subject started clean, "back to…" resumed with both earlier exchanges.
Security effect: none on permissions. It removes an unintended write path to personal runtime data during tests.
Status: IMPLEMENTED, UNIT TEST, live-checked on feature/claude-development; not merged.
Note: an earlier test run had already created C:\Projects\ZAENIA-Claude\data\conversation\threads.json (gitignored, test topics only). It was left in place, because deleting files needs Grey's OK.

2026-10-21 | v1.3 | Claude | Topic tracker made hermetic (section 19). No ADR change.

## 20. Three-engine improvements — Claude, 2026-10-21 (v1.4)

Requested by Grey on 2026-10-21 ("make as much needed changes to improve ZAENIA … authorization is given to update ZAENIA's app"). Each item below was measured first, then implemented on feature/claude-development, tested, and applied to the live install.

### 20.1 Reasoning engine: context budget (core/brain/context_budget.py)
Problem (measured): a multi-topic question built a ~7,500-token prompt for the 8,192-token window. Ollama drops the start of an over-long prompt, which is where the system prompt and charter guidance sit. Causes: an unbudgeted 8,000-character source-library dump matched on a single shared word; a raw YAML behaviour profile; stale state JSON.
Change: reference context is split into labelled sections with priorities and caps. The lowest-priority sections shrink first, then the oldest turns (the newest 4 always stay), and 1,100 tokens are kept for the answer. Applied in `local_llm.build_messages`, so every model path is covered. The source library now needs two shared content words before an excerpt is included.
Evidence: live context 7,478 → 5,118 tokens for the same question; context_budget_test 5 pass. Status: IMPLEMENTED, UNIT TEST, live-applied.

### 20.2 Learning and memory engine: ledger in the repo, owner review (core/personal_memory/ledger, owner_profile.py)
Problem: the memory ledger code lived only in `user_understanding/`, which is excluded from git as personal, so a clean checkout had no Learning-engine store. There was also no way for Grey to inspect or correct his long-term profile (plan §8: "why did you remember this?", review, edit, delete).
Change: the ledger (`user_learning.py`, `adapter.py`, extraction prompt, 42 tests), originally authored with ChatGPT, is vendored unchanged apart from imports. The personal seed and assessment stay local. Owner review was added: `records`, `explain` (evidence and source), `confirm` (candidate → active) and `forget` (deleted, and tombstoned so it isn't relearned). API: `GET /api/assistant/profile`, `GET|DELETE /api/assistant/profile/{id}`, `POST /api/assistant/profile/{id}/confirm` (memory.read / memory.write). UI: Assistant window → "What ZAE knows about you" (Known / To confirm, search, Why?, Confirm, Forget with a second tap).
Evidence: on a copy of the live profile (100+ known, 38 candidates), explain, confirm and forget all work, and a forgotten key is blocked from relearning. Ledger 42 tests (5 seed tests skip without the personal seed). Status: IMPLEMENTED, UNIT TEST, live-applied.

### 20.3 Execution and security engine
- **Clean-checkout test suite.** Added `core/reasoning/cases.example.json` (the benchmark with neutral place names, used when the personal `cases.json` is absent). The full-Bible-corpus test runs only when the downloaded corpus exists. Evidence: a fresh `git clone` with no personal files ran **551 tests, 0 failures, 0 errors** (13 skipped). This meets the plan's Phase 0 "clean-install test" for the test suite. Note: a clone under `AppData\Local\Temp` fails 11 document-tool tests by design, because the document tools refuse system folders.
- **Security activity view (read-only).** The audit log holds about 283,000 entries (49 MB), almost all routine allowed reads. `core/api/security_activity.py` reads the last 16 MB, counts routine allows, and lists notable events (denials, sign-ins, voice rejections, memory changes, actions, rules, pairing, screen watch). Exposed at `GET /api/security/activity` (status.read) and as a System window card. Tests: 3 pass. Permissions are unchanged: memory and learning still can't grant permissions, and no gate was altered.

### 20.4 Open decisions for Grey (not implemented)
1. **Audit log growth (~49 MB and rising).** Options: rotate by size, or stop logging routine *allowed* reads (denials and sensitive operations always logged). Either changes audit retention, a security-policy choice.
2. **App microphone voice policy (a/b/c)**, still pending from §17.3.
3. **`core/behavior/behavior_profile.yaml` is stale** (it still names Piper as the preferred voice and repeats rules now in the profile). It's protected identity configuration, so it waits for Grey's approval.

2026-10-21 | v1.4 | Claude | Context budget, ledger in repo with owner review, clean-checkout test suite, security activity view. No ADR change; ADR-001…005 remain PROPOSED.

## 21. News redesign, email summaries, audit rotation — Claude, 2026-10-21 (v1.5)

Requested by Grey on 2026-10-21: a fresh, inspiring glass layout for Tech News; an email feature that announces summaries of important mail; and continued three-engine work.

- **Tech News window (clients).** It's a glass magazine now: a masthead, topic pills, a hero story, a bento grid of frosted panels in wide, tall and regular sizes, and a "More headlines" list. Feeds now carry story images (media:content/thumbnail, enclosures, or the first `<img>`). Stories without a picture get a tinted panel per newsroom. On the phone app, external images are blocked by its CSP, so the tinted panels show there instead. Status: IMPLEMENTED, visually checked in preview.
- **Important-email summaries (new optional online integration, docs/EMAIL.md).** Gmail is read-only (`gmail.readonly`) with Grey's own OAuth client and a separate token. Quick rules come first, the local model triages borderline mail, and important mail gets a 1–2 sentence summary, posted as a spoken notice through the new `FollowThroughService.post()`. Bodies are never stored, and email text is untrusted: it can't instruct, act, or teach the profile. In a live triage check, an Army range change was flagged important, a store sale was not, and a prompt-injection phishing email was judged not important and summarised as phishing. Status: IMPLEMENTED, UNIT TEST (7); **waiting for Grey to enable the Gmail API and scope, then connect.**
- **Execution and security: audit rotation.** Above 32 MB, the audit log moves to `data/secure/audit_archive/` (nothing deleted) and a fresh file starts. This answers decision 20.4-1 with the non-destructive option. Tests: 2 pass.
- **Reasoning benchmark.** `python -m core.reasoning benchmark --provider local` needs the owner passkey gate by design, so a live baseline score for llama3.1:8b is still to be recorded by Grey (Phase 1 exit criterion).

Still open for Grey: app-microphone voice policy (a/b/c); stale `behavior_profile.yaml`; pushing feature/claude-development to GitHub.

2026-10-21 | v1.5 | Claude | Tech News redesign, read-only email summaries, audit rotation. No ADR change.

## 22. Status & Security tab and security self-check — Claude, 2026-10-24 (v1.6)

Requested by Grey on 2026-10-24: rename System Status to Status & Security, and let ZAE run security checks on herself, with every report shown on that tab.

- **Security self-check (Execution and security, read-only, `core/api/security_check.py`).** Each run does two things:
  - It runs the three existing isolated suites (`core.foundation.self_test`, `closure_check`, `integration_check`) as subprocesses. They use their own temporary data folders.
  - It checks the live setup read-only: data/secure is a plain folder; the passkey, salt, rules vault, moral-code vault and API token files are present (existence only, contents never read); `load_api_settings` binds to localhost; git ignores the private paths and tracks no secret-looking files (by name); the audit log is recording and rotating; and it counts failed sign-ins, denials and voice rejections over 24 h (thresholds give warnings).
  - A report (check names, pass/warn/fail, plain-language fixes) is saved to `data/security_checks/<UTC id>.json` (gitignored), and the newest 50 are kept. Each run writes one `security.self_check` audit event, which is labelled in Security activity.
- **When it runs:**
  - from the "Run security check" button;
  - from chat or voice ("run a security check", desktop app);
  - from the system brief's Fix it (suggested when no check has run for a week, flagged as attention when the latest failed);
  - automatically once a day while the server runs (first look 3 minutes after startup, then hourly).
  - One check runs at a time, and manual runs are limited to one per 10 minutes.
- **Routes:** `GET /api/security/checks`, `GET /api/security/checks/{id}` and `POST /api/security/checks`, all on the existing `status.read`. Grey chose this over a new desktop-only capability, so `auth.py`, capabilities, gates and rules are unchanged.
- **Brain:** when asked about her security checks, the latest report is given as reference context, and she reports only those results.
- **Clients:**
  - The tab is renamed Status & Security.
  - The tab shows the latest result, every saved report (expandable, grouped into isolated tests, live setup and last 24 hours) and the Security activity list, which moved here from the System window.
- **Tests:** `core/api/security_check_test.py` (10 tests) covers pass, missing setup, a failing suite, a missing test file, timeouts, pruning, report-id path safety, the rate limit, one-at-a-time runs, brain context and route capabilities. Full suite: 618 OK, 13 skipped. Desktop: tsc OK, 74 + 25 UI checks, build OK.
- **Real run against an empty isolated data folder:** 15 checks in 23 s.
- **Known limitation:** in this worktree the three suites stop on the gitignored private `core/foundation/moral_code/charter.json`, and the report names the missing file. On the live install, where the file exists, they are expected to run but were not run there in this session.

2026-10-24 | v1.6 | Claude | Status & Security tab, read-only security self-check with saved reports. No ADR change; no permission change.

## 23. Locked Security tab and live attack resistance — Claude, 2026-10-24 (v1.7)

Requested by Grey on 2026-10-24. Security becomes its own tab, opened only with the passkey or the spoken phrase. Status keeps only the overall security level. Grey's choices: the passkey is typed in an owner console window, never the app; the phrase works only together with his voice; the tab holds views plus owner actions; it locks after 10 minutes without activity.

- **Unlock (Execution and security, `core/api/security_unlock.py`).** The desktop app (desktop key required) asks for an unlock request, which is a random 32-hex id held in server RAM for 3 minutes. It then opens `scripts/security_console.ps1` through the Tauri command `run_security_tool`.
  - **Passkey:** the console checks it with `require_passkey` plus `consume_fresh_auth`, bound to `security.tab.open` and the request id. Rate limiting and auditing are unchanged.
  - **Spoken phrase:** one recording from the approved mic, kept in RAM only. It must match the phrase hash (`voice_passkey.phrase_matches`) **and** the enrolled voice (`mobile_auth.LocalSpeaker`, the account-sealed reference from `mobile_voice_profile`). The phrase alone never unlocks.
  - On success the console writes a one-time grant file in `data/secure/security_unlock/`. The server accepts it only for a request it issued, written after that request, then deletes it. It returns a session token once.
  - Sessions are kept in RAM as hashes, at most 3. Activity pings reset a 10-minute idle timer, and a restart locks the tab. Audit events: `security.tab_unlocked`, `security.tab_unlock_failed`.
- **Threat-model note.** A grant file can be written by anything already running as Grey's Windows account. That process could also read the desktop key, so the unlock is a UI-visibility gate on this PC, not a new privilege. The tab shows information and opens consoles. Every change (rotate or revoke the token, re-pair the desktop, set up or remove the phrase, change or remove the mic, turn the voice check on or off) still asks for a fresh passkey in its own console, using the existing CLIs.
- **Live attack resistance (`core/api/security_posture.py`).** Read-only, nothing secret is read. Each area is rated strong, fair or weak from live readings:
  - Network: the actual listening addresses on the API port (psutil), Tailscale serve and Funnel status, and the Windows Firewall profiles.
  - Passkey guessing: the sign-in counter (read-only SQLite), plus failed sign-ins and unlocks over 24 h.
  - Secrets at rest: presence of the secret files, and links.
  - App and phone access: API token and desktop key age, phone voice sign-in, and active phone sessions.
  - Voice impersonation: calibration genuine and impostor margins, and rejections over 24 h.
  - Server mode.
  - Security code tests and git privacy, both from the latest check.
  - Audit trail: last write and archive.
  - Signs of attack over 24 h.
  - Package vulnerabilities are marked "not measured", because they can't be checked offline, and are left out of the score.
  - The score averages strong 100, fair 60 and weak 20. Any weak area makes the overall level weak.
- **Recommendations:** weak areas and failed checks first, then fair areas and warnings, with duplicates removed.
- **Improvements:** each saved check now stores a compact posture, so the tab shows a strength trend and what got stronger, weaker, fixed or broken since the previous check.
- **Routes**, all on the existing `status.read`, so capabilities, gates and rules are unchanged:
  - `GET /api/security/summary`: level only, for the Status tab and the phone.
  - `POST /api/security/unlock`, `GET /api/security/unlock/{id}`, `POST /api/security/session` (activity), `POST /api/security/session/lock` and `POST /api/security/full`. These also need the desktop key, and `full` needs a live session.
  - The existing `/api/security/checks` and `/api/security/activity` stay on `status.read`, so chat and voice can still run and report checks.
- **UI:**
  - The Security tab (`components/security/SecurityPanel.tsx`) has a lock screen with two unlock buttons; then strength gauge and areas, recommendations, improvements, the security checks, the full activity log with filter and search, and the owner actions.
  - The Status tab shows `SecuritySummary`: level, score, areas to improve and last check, plus an Open Security button.
  - "Open security" works by voice or typing, and the core's security branch opens the tab.
  - The live app no longer offers the Preview (sample data) switch. Sample values remain only in the browser preview without a server.
- **Tests:** `security_unlock_test.py` (6) and `security_posture_test.py` (5). Full suite 629 OK, 13 skipped. In the worktree the foundation self-test and closure check stop at the missing local `charter.json`, a known worktree gap; they run in the live install's security check. Desktop: tsc OK, UI checks pass, web and desktop builds OK.
- **Verified live:** not yet. Live unlock by passkey and by phrase plus voice needs Grey at the PC.

2026-10-24 | v1.7 | Claude | Locked Security tab (passkey, or phrase plus voice), live attack-resistance assessment, recommendations, improvements; Status shows level only. No ADR change; no capability change.

## 24. Looks, background mode, conversation, voice turns, game coach, Python 3.13 — Claude, 2026-10-23/24 (v1.8)

Requested by Grey across 2026-10-23 and 2026-10-24. Grey's standing instruction (2026-10-24): finished work is merged into the live install without waiting for a GitHub merge; pushing still needs his word. Each item below was merged live, tested, and pushed with his OK unless noted.

- **Appearance (clients).** There are now 35 accent colours (27 new). Every module window can have its own window style (Aurora, Holo HUD, Midnight editorial, Neon bento) and its own colour, or follow the app. `data-look` sits on each `.glass-module`, and `tabAppearance()` sets `--accent`/`--accent-2`. HUD, Editorial and Neon had hard-coded colours, so tab colours never showed; all styles now draw from the window's accent. A "Core icons" choice can show all six orbs in the accent colour. Voice: "make the tasks tab pink", "make the core icons the same colour". Status: IMPLEMENTED, UI checks (25 appearance), preview-verified.
- **Background mode (clients, resources).** When the window is unfocused or hidden and ZAE is idle, the neural core stops requesting frames and keeps one still, glowing frame. CSS animations pause, and status and capability polling slow from 8 s to 32 s and from 2.5 s to 15 s (`core/appBackground.ts`). Everything resumes on focus or when she hears, thinks or speaks. Preview-verified: 0 running animations and an unchanged canvas while away.
- **Conversation (Reasoning engine).** The rules are J.A.R.V.I.S. composure plus F.R.I.D.A.Y. speed (`conversation_rules.py`).
  - `reply_shape.py` makes replies brief first and deeper only when he asks ("why?", "explain", "tell me more", "walk me through it"). A brief turn gets a short system line just before his message.
  - His message always reaches the model last and unchanged. `closure_check` enforces this, and it caught an earlier version that appended the cue to his message; that version was fixed the same day.
  - `personal_memory/speech_style.py` learns running averages only: message length, casual typing, his own shorthand, and speaking pace. No text is stored. It learns after `memory.write` and is read with `memory.read`.
  - App-mic transcripts are marked as spoken, so they aren't treated as casual typing.
  - Kokoro's speed moves toward his pace, within 0.92–1.12×, after 5 samples.
  - Live check on llama3.1:8b: a simple question went from 206 to 40–50 words, and "why?" still gives the full explanation.
- **Voice status.** The Voice module reports "Kokoro voice ready (af_heart), Piper as backup" instead of Piper.
- **One answer per spoken turn (Execution).** PC Voice reports `recognising` false after 3 misses, which hands listening back to the app mic. When it flipped back, both listeners heard the same sentence and both answered. Now each claims a turn before answering (`service_status.claim_turn`, `data/ui/voice_turn.json` with hashed words and a time, no text). The second listener drops the same words within 12 s. The app mic waits up to 2.5 s while the PC is still hearing, and only claims words meant for ZAE. Tests: 7.
- **Game coach (new, `core/assistant_platform/game_coach.py`).** It runs during game mode only, on by default, and "stop watching me play" turns it off.
  - Every 20 s the local vision model notes the moment. Frames are kept in memory only, and capture pauses for private windows.
  - When the game closes, the local brain reviews the session (style, decisions, strengths, mistakes, tips) and updates a per-game style profile in `data/gaming/`. "How did I play?" answers from it (`memory.read`). There is a System card and `/api/gaming/coach` (`status.read` / `assistant.desktop.manage`).
  - **Tuned 2026-10-24 from the first real session (Stellaris):** that session was judged "indecisive" from 6 main-menu frames, and a web look-up returned a bird. Fixes:
    - each note now starts with SCREEN: playing, menu, loading or paused;
    - only playing moments count or get reviewed;
    - non-play screens are checked every 60 s;
    - repeated identical notes are dropped;
    - web results must mention the game;
    - review items are flattened to plain sentences;
    - the review prompt forbids personality guesses from thin notes.
  - The misjudged Stellaris profile was backed up (`data/gaming/profile.before-tuning-20261024.json`) and cleared. Tests: 19.
- **Web look-ups (new optional online integration, `core/assistant_platform/web_lookup.py`).** Grey approved internet look-ups for what is on screen. Only a few search words leave the PC (a game, item or error code), never a picture or window text. Terms that look private (e-mail, URL, path, long number, password/bank words) are refused. Sources are DuckDuckGo instant answers, then Wikipedia full-text search, both keyless. Results are cached for a week in `data/web_cache/` and rate-limited to one per 20 s. Screen-watch notes may name one thing to look up. This is consistent with ADR-002 (optional, replaceable external service). Live check: Marvel Rivals, Elden Ring and Jeff the Land Shark resolved correctly.
- **Security self-check fix commands** now work as typed in PowerShell (`cd` to the project, venv Python).
- **Python 3.13.15 (runtime).** The live `.venv` moved from 3.11.0 (the first 3.11 release, with no security fixes since) to 3.13.15, with the same 109 packages and versions. Torch 2.11 is still CUDA 12.6.
  - Verified before switching: 629 tests, self-test 45/45, closure 63/63, integration 16/16, CUDA, Kokoro, Vosk, ECAPA on the GPU, Piper, 16 microphones.
  - Rollback: `.venv311_backup`.
- **Upgrades batch (2026-10-24):**
  - Six old `_backup_before_*` folders (gitignored, nothing imports them) moved out of `core/` to `backups/code-tree-backups-20261024/`.
  - Pygame's start-up banner and its setuptools `pkg_resources` warning are hidden via `core/voice_output/quiet_pygame.py`. Pygame already falls back cleanly when `pkg_resources` is gone, so audio can't break on a future setuptools.
  - Faster app start: the backdrop and preview images were converted to WebP (6.6 MB down to 0.67 MB), and seven module windows load when first opened. The main bundle went from 555 KB to 475 KB, so the 500 KB build warning is gone.
  - Reasoning benchmark: its self-test passes (38 checks). The live baseline still needs Grey's passkey by design (Phase 1 exit criterion).

- **Self-service (2026-10-24, Grey: "let me do the rest of the upgrades by myself").** `scripts/zae.ps1` (Start menu: ZAE Maintenance) does status, test (every test plus the three security suites and UI checks), update from a GitHub branch (restore-point tag `zae-rollback-*`, merge, install changed packages, test, automatic undo if anything fails, then build, install and restart), build, restart and rollback. It never touches `data/`. `docs/SELF_SERVICE.md` is the step-by-step guide (GitHub with `gh`, Python packages, troubleshooting, safety rules). Running `zae.ps1 test` on the live install found two real bugs, both fixed: ambient tests read the live game-mode file, and `applicationframehost.exe` (Windows Store app host) switched game mode on.

Still open for Grey: run voice training (B2 priority) and then measure recognition; start PC Voice with the passkey (it picks up the turn-claim fix on 3.13); set a new spoken phrase; Gmail API enablement (C1); run `.\.venv\Scripts\python.exe -m core.reasoning benchmark --provider local --limit 14` for the baseline.

2026-10-24 | v1.8 | Claude | Per-tab looks and colours, background mode, J.A.R.V.I.S./F.R.I.D.A.Y. conversation with brief-first replies and learned speech style, one answer per spoken turn, game coach with web look-ups (tuned), Python 3.13 runtime, start-up and housekeeping upgrades. No ADR change; no capability change (new routes use existing capabilities).

## 25. Personal workspaces and calendar completion — Codex, 2026-10-24 (v1.9)

Owner requested Workbench, Music, Fitness & Health, calendar completion checks in briefs, and current recommendations for iPad/Windows sketching and engineering tools. Implemented on `feature/codex-personal-workspaces-20261024`. On October 24, 2026, the owner explicitly approved merging and updating the desktop app; local `main` was fast-forwarded to the verified implementation, and the built release was installed and reopened through the existing updater.

**Implemented architecture, preserving the three engines:**

- Learning/Memory: Workbench projects, bounded vector sketches and validated PNG/JPEG references; music projects/releases/manual dated statistics; nutrition/exercise logs; training sources, editable plans and session history. These use the existing private transactional `PlatformStore`. Concurrent edits require the saved revision, lists paginate without downloading every drawing, archiving is reversible, and drafts stay in RAM across tab navigation. Nothing here grants execution permissions, automatically learns health information into the owner profile, or runs source instructions.
- Reasoning/Planning: explicit conversational reads of saved nutrition, music progress and Workbench search. Training-source extraction copies recognizable prescriptions from pasted text, public articles, TXT/Markdown/PDF/DOCX/SRT/VTT into an editable draft. It does not invent missing exercises. Video links are references until their transcript is supplied; scanned documents require OCR or readable text. No external model or credential is introduced.
- Execution/Security: existing authenticated `memory.read` / `memory.write` scopes protect personal records. Calendar completion reads use `calendar.read`, corrections use `ui.calendar.write`, and brief answers retain the existing session authorization. Public article retrieval reuses the existing SSRF protections. Images are raster-only, size and dimension bounded; source files never execute. Existing startup authentication and locked Security tab remain intact.
- Brief delivery: inspect timed occurrences today and yesterday that ended within the last 24 hours (use scheduled start if no end exists). Ask about at most one per requested brief; "not yet" and delivered questions have a 12-hour cooldown. An explicit affirmative saves completion durably. An unclear answer never completes anything. Calendar/provider events are not deleted or edited. Identity includes occurrence date/time, so a later recurrence stays independent. Playback alone does not imply completion, a late acknowledgement cannot undo it, and Calendar offers revision-checked Reopen. Browser answers keep the protected browser audio endpoint. All-day and unknown-time entries are excluded from automatic completion questions.
- Portability: encrypted profile v4 adds the new personal collections, sketches/images and calendar completion records; v1–v3 remain readable. Existing size limits and owner-authenticated export/restore remain. Machine grants, executable instructions and cloud tokens are excluded.
- UI: three lazy-loaded tabs use the existing shell, themes, per-tab appearance, resizing and voice layout commands. Desktop navigation scrolls when needed to keep all modules reachable. Saved workspaces now accept all twelve module IDs; inspection found the previous whitelist still stopped at the original seven.

**Scope limits:** song statistics are clearly marked manual, with source, date and reporting period; automatic YouTube/SoundCloud/Spotify/Apple Music analytics remain future integrations. Workbench provides concept measurements and scenario records, not an engineering solver. CAD/FEA tools are recommended separately and are not installed. Training source drafts require review; no automatic medical or nutrition prescription is made. Food intake minus exercise is displayed separately from estimated energy balance, which additionally requires the owner's non-exercise expenditure estimate. No maintenance cleanup or ZAE API/listener shutdown was performed.

**Verification:** targeted backend checks and web production build passed during implementation. Browser fixture confirmed sketch scale saving, music provenance, updated food totals, source extraction and separate session history. Full regression verification and responsive checks are recorded in `docs/PERSONAL_WORKSPACES.md`. The complete Python discovery run initially failed to import PyTorch because Windows reported `WinError 1455` (commit/paging allocation); this is an environment limit, not a successful audio regression run. The broad suite excluding `core/conversation_runtime` exposed one v3 schema assertion that was updated to v4 while preserving its exclusion checks. The preview fixture now also isolates the newer owner-profile ledger and tech-news module.

**Next improvements identified in actual files:** (1) measure Windows commit headroom alongside RAM/VRAM before concurrent model/build/audio workloads; (2) run the passkey-gated voice/reasoning baseline already outstanding in §24; (3) add source-specific, approved music analytics connections with account scopes, freshness and metric definitions; (4) expand long-term log capacity/indexed date queries before reaching the current 2,000 records per collection; (5) add reviewed CAD solver adapters and transcript/OCR adapters with real execution receipts, rather than presenting stored references as completed analysis. These are follow-on work, not verified capabilities in this change.

Initial verification for this branch: 661 Python tests passed with one skipped, excluding `core/conversation_runtime` because the full run could not allocate PyTorch DLL memory. Security regression suites passed 45 + 63 + 16 checks. All eight frontend scripts, production web build and the desktop frontend build passed. Phone preview at 390 × 844 showed no document-width overflow. The initial native Rust stage failed with a memory allocation error under Windows commit pressure; the successful retry is recorded below.

Memory-recovery follow-up: Grey explicitly approved temporarily stopping external capture helpers. After those helpers stopped, the complete automated Python discovery run passed (661 tests, one skipped, no module exclusions), including the formerly blocked PyTorch-dependent module imports. The optimized native release build then passed (`npm run tauri build -- --no-bundle`, one worker, cached dependencies); the artifact is `desktop/src-tauri/target/release/desktop.exe`. Manual microphone acceptance tests remain separate. ZAE's API, voice listener and startup authentication were not stopped or changed.

Owner-approved integration follow-up: merged into local `main` and installed through `scripts/update_desktop_app.ps1`. The previous installed executable was backed up; the replacement's SHA-256 matches the verified build. The reopened native app exposes Workbench, Music and Fitness & Health, and Workbench loaded its subject filters and local collection successfully. The running API exposes the new routes and rejects unauthenticated requests with HTTP 401. No API/listener restart or remote Git push was required. See `docs/PERSONAL_WORKSPACES.md` for the installation and rollback record.

2026-10-24 | v1.9 | Codex | Personal workspace tabs, occurrence completion in briefs, portable profile v4, explicit conversational reads, module whitelist repair and isolated preview updates. No ADR accepted; all routes retain existing capabilities.

## 25. Tasks & Calendar tab and ZAE's phone line — Claude, 2026-10-24 (v1.9)

Requested by Grey on 2026-10-24: combine the Tasks and Calendar tabs and tighten the layout; widen the sidebar by about 1 cm; give ZAE a phone number (calls and texts; her own number and his).

- **Tasks & Calendar (clients).** `components/plan/PlanPanel.tsx` shows the calendar and tasks side by side (stacked below 860 px), with a Both / Calendar / Tasks switch. Open task deadlines appear on their calendar day. Requests for the old "calendar" window or section open the combined tab (`useWindowShell` aliases). The layout is denser: compact counters, a one-line add form, and duty status in a details row. The sidebar is 245 → 283 px (200 → 238 px under 1270 px). Merged with the Workbench, Music and Fitness tabs that another session added on the live install the same day.
- **Phone line (new optional online integration, `core/telephony/`, docs/PHONE.md).** Twilio, with no Twilio library. Webhooks are `/phone/*` on the API server, made public only through Tailscale Funnel's `/phone` path. They are outside API-token auth, but every POST must carry a valid `X-Twilio-Signature` (HMAC-SHA1, verified against Twilio's published example), or it gets 403. Nothing is served (404) until set up and enabled.
  - **Calls from an owner number:** spoken phrase (Argon2 hash) **and** ECAPA voice (`LocalSpeaker`, phone audio resampled 8→16 kHz). An optional 6–8 digit phone PIN (Argon2 hash, one try per call) can stand in for the voice check only. Every turn is voice-checked again, and 3 misses end the call. Turns are recorded and transcribed locally with Vosk; Twilio's recording is deleted right after download. The brain answers in a background job polled with `<Redirect>` (Twilio's 15 s limit), and the reply plays in her Kokoro voice from short-lived, unguessable audio URLs.
  - **Other callers, and calls carrier-forwarded from Grey's number:** answering service. The message is transcribed, then sent to Grey as a text and an app notice, at most 3 per caller per hour. Callers never reach the brain.
  - **Texts:** from an owner number, answer-only (`remember=False`, no actions), because sender numbers can be forged but replies go to the real number. Texts from anyone else get no reply and are forwarded to Grey.
  - **Outbound calls and texts:** CLI only (`python -m core.telephony call|text`), with confirmation and a fresh passkey. `--as-me` uses Grey's number as a Twilio-verified caller ID.
  - The Twilio token is DPAPI-sealed (`data/secure/twilio_token.dpapi`). Setup (`python -m core.telephony setup`) needs the passkey, opens Funnel `/phone`, points the number's webhooks at this PC and sends a test text.
  - Status: IMPLEMENTED, UNIT TEST (19, including the signature reference example and router 403/404). **Not live-tested: waiting for Grey's Twilio account.** US texting needs A2P 10DLC registration.
  - Consistent with ADR-002 (optional, replaceable external service). Grey approved the integration on 2026-10-24 ("both for both questions").

2026-10-24 | v1.9 | Claude | Combined Tasks & Calendar tab, denser layout, wider sidebar, Twilio phone line (owner-verified calls, answering service, answer-only texts, passkey-gated outbound). No ADR change; no capability change (phone routes are signature-gated and use existing chat.reply and memory capabilities for the brain).

## 26. Research tabs and one News page — Claude, 2026-10-25 (v2.0)

Requested by Grey on 2026-10-25, modelled on the Quantum app's Research page. His answers: Research becomes **Notebook**, **Historical connections** (Quantum's History patterns) and **Library** (Books & archives) as left-sidebar tabs; News reader merges into Tech News, renamed **News**, with a longer page; summaries use her own brain.

- **Backend (`core/research/`, docs/RESEARCH.md).**
  - `library.py`: Gutenberg (gutendex), Open Library and Internet Archive, searched in parallel. Free books are sorted first, and catalogues that fail are reported as skipped. Wikipedia overview. Book text is read only from Gutenberg and Internet Archive hosts, with Gutenberg boilerplate removed.
  - `history.py`: Library of Congress date facets (one request per term), Internet Archive per-decade counts, and GDELT timelinevol by year. Rates are relative to cached baselines. Samples per period. GDELT world search is English only and limited to 1 request per 5 s.
  - `notebook.py`: topics, sources (20k-character excerpts) and notes, stored in `data/research/notebook.json`.
  - `analyze.py`: local brain tasks (summary, facts vs opinion, book scan, ask, "what happened then", and six notebook analyses). Material is wrapped as untrusted, and long text is sampled from its beginning, middle and end.
  - `web.py`: fetches only public addresses (no loopback, private, link-local or Tailscale ranges), re-checks after redirects, caps responses at 4 MB, retries dropped connections, and extracts readable text with lxml without running scripts.
- **Routes:** `/api/research/*` (`research_routes.py`), using existing capabilities: public reads `status.read`, the notebook `memory.read` / `memory.write`, and analysis `chat.reply`. The desktop bridge allows 300 s for `/api/research/analyze`.
- **Clients:**
  - Library, Historical connections and Notebook windows, with an SVG timeline chart and "Add to notebook" from every source.
  - News has 16 feeds (6 new world/US/science: BBC World, NPR News, Guardian World, Al Jazeera, PBS NewsHour, Science Daily), new topic pills, 50 stories, a world-search box and a reader pane (read, summarise, facts vs opinion, ask, open, add to notebook).
  - Notebook "Save to Vault" saves to ZAE Notes until a Vault tab exists.
- **Tests:** `research_test.py` (10: catalogue merge and skips, book host allowlist, private-URL refusal, readable extraction, per-million rates, GDELT averaging, notebook CRUD, untrusted prompt, route capabilities); tech_news source test updated to 16. Full suite 690 OK.
- **Live checks (2026-10-25):** Library 40 results in 15 s (Gutendex timed out, the same as in Quantum). Library of Congress facets ~1 s. Internet Archive decades ~56 s the first time, then baseline cached. LoC samples 23 s. GDELT 50 articles. Facts vs opinion on llama3.1:8b in 37 s, correct.

2026-10-25 | v2.0 | Claude | Research tabs (Library, Historical connections, Notebook) and one News page with world feeds, world search and a reader. New optional online sources (Gutenberg, Open Library, Internet Archive, Library of Congress, GDELT, Wikipedia), all keyless and read-only. No ADR change; no capability change.

## 27. Quantum-style tabs — Claude, 2026-10-25 (v2.1)

Grey compared ZAE with his brother's "Quantum" app and answered a question card about each of its sidebar tabs. His decisions: no full-page Chat; Protocols and Self-Sustain go inside Status; Reminders go inside Tasks & Calendar; the Vault goes in Settings (System merged into Settings); Tools and Labs (chemistry, physics) go in Workbench; Code Doctor (for his projects and ZAE's code), Suggestions and Arena become new tabs; Source merges into Files; keep the sidebar Run check box and a fuller status bar. Research is one tab with Historical Connections, Notebook, News and The Library as tabs along the top. A Scripture & ancient tab is offered on a card and waiting on Grey's answer.

- **Page tabs** (`components/shell/PageTabs.tsx`) for Status (Overview / Protocols / Self-Sustain), Settings (System & appearance / Vault), Workbench (Projects / Tools / Labs), Files (Files / Source) and Research.
- **Protocols** (`protocols.py`): phrase-started routines made of fixed safe steps (say, open tab, remind, ask, headlines, game coach, stop screen watch). They run in the chat path before the brain. Steps can't run programs, change security or send messages.
- **Reminders** (`reminders.py`): "remind me in N minutes / at TIME [tomorrow] to …" plus a Reminders view. Each reminder fires as a follow-through notice (spoken when that's on) and, optionally, as a text from the phone line.
- **Self-Sustain** (`selfcare.py`):
  - nightly zip of `data/` to `%USERPROFILE%\ZAENIA Backups`, keeping 14 (models, voices and caches are left out);
  - Back up now;
  - an optional 5-minute watchdog scheduled task (`scripts/zae_watchdog.ps1`) that restarts the server in token mode after two missed health checks;
  - health warnings;
  - restore only from the console, with the passkey.
- **Vault** (`core/api/vault.py`): AES-256-GCM items, titles included, under a random key sealed with DPAPI. It needs the desktop key and the Security tab's unlock session. Opening, saving and deleting items is audited. Notebook "Save to Vault" uses it.
- **Workbench Tools** (`core/science.ts`, client-only):
  - a safe calculator (recursive-descent parser, no `eval`);
  - a 13-category unit converter, a timer and stopwatch, Ohm's law and number bases;
  - CODATA constants and 18 science/tech resource links.
- **Workbench Labs:**
  - a 118-element periodic table;
  - molar mass and moles, ideal gas law, dilution and pH;
  - a projectile simulator, pendulum, energy and wave calculators;
  - Ask ZAE.
- **Code Doctor** (`code_doctor.py`): a static scan that never runs project code (Python ast checks, JSON/YAML loading, TODOs, secret-looking strings, large files). Projects are limited to C:\Projects, Documents, Desktop, source and ZAE herself.
  - Explain and Fix use her local brain.
  - A fix is shown as a diff and applied only from the desktop app, with a backup and a hash check against the reviewed file.
  - Her security code (core/foundation, voice_security, telephony, auth, vault, security routes) and `data/` are review-only.
- **Suggestions** (`suggestions.py`): her brain proposes up to 5 ideas from her calendar, tasks, reminders, health and game-coach notes. Each needs Grey's approval: an approved "day" idea with a time sets a reminder, and approved "ZAE" ideas form an improvement list.
- **Arena** (`arena.py`): sends the same question to 2–3 local models in turn, using ZAE's system prompt, with timing and tokens per second. Grey's votes feed a leaderboard. "Use as her brain" writes `data/ui/brain_model.json`, which `local_llm.get_brain_settings` prefers; the configured model stays the fallback.
- **Status bar and Run check:** `/api/status/bar` reports the model and whether it's loaded, voice, PC voice, mode, CPU, RAM, GPU (nvidia-smi), disk, last backup, phone line and game mode. The sidebar box shows the latest security self-check and a Run check button.
- **Historical Connections extras:** a per-term summary (total, first seen, peak, spikes, trend), a newspaper language filter, and Suggest keywords and Translate titles (her brain).
- **Capabilities:** existing ones only. Files and her brain can be changed only through the desktop key (`/api/code/apply`, `/api/arena/brain`).
- **Tests:** selfcare_test 7, vault_test 2, tools_test 6, science.test.cjs 18. The full suite is 705 OK.

2026-10-25 | v2.1 | Claude | Quantum-style tabs per Grey's answers: Research page tabs, Status (Protocols, Self-Sustain), Reminders, Settings with the Vault, Workbench Tools and Labs, Code Doctor, Suggestions, Arena, Source in Files, status bar, Run check. No ADR change; no capability change.

### 27.1 Scripture & ancient, layout clean-up — Claude, 2026-10-25 (v2.2)

- **Scripture & ancient** is the fifth Research tab; Grey picked "Add it" on the card. `core/research/scripture.py`:
  - **Passages:** passages up to 30 verses (a whole chapter stops at its last verse). Each verse shows the offline STEP interlinear (Hebrew TAHOT / Greek TAGNT: transliteration, gloss, Strong's number, morphology), offline ASV 1901 and WEB Classic, and online public-domain KJV, YLT, BBE and Darby from bible-api.com.
  - **Search:** offline word search across the corpus.
  - **Bookmarks:** "My marks" in `data/scripture/marks.json`.
  - **Ancient texts:** a list of public-domain works (Apocrypha, Enoch, Josephus, the Apostolic Fathers, Eusebius, Philo, the Talmud and others) found through the Library catalogues.
  - **ZAE explains:** Explain, Traditions, Compare wording, Cross-refs, Word study (click an original word) and Translate original, all on her local brain. Read aloud uses her Kokoro voice.
  - **Routes:** `/api/research/scripture*`, using memory.read / memory.write like the existing scripture route.
- **Layout (Grey: "no empty spaces"):**
  - Module windows use their full width; the 810 px and 1120 px caps no longer apply inside glass windows.
  - Settings and Assistant cards flow in 2–3 columns with no gaps, and the appearance block spans the full width.
  - The Run check box moved to the bottom of the sidebar.
  - The status bar uses larger chips.
- **Tests:** scripture_test 4. The full suite passes.


### 27.2 Translate tab, Jewish texts and the Quran — Claude, 2026-10-25 (v2.3)

- Grey answered "both" on the card offering the two extras seen in the Quantum screenshots.
- **Translate** is the sixth Research tab (`TranslatePanel.tsx`, `POST /api/research/translate`, chat.reply; `GET /api/research/translate/languages`, status.read):
  - Paste text or give a web address (fetched through `web.safe_url`, read as text).
  - From (detect or one of 30 languages, including Latin, Ancient Greek, Biblical Hebrew and Aramaic), To, and Style (natural, literal, with notes).
  - `analyze.translate` runs on her local brain only, in paragraph pieces of about 3,500 characters, up to 40,000 characters. The text is wrapped as untrusted data.
  - Copy, swap languages to translate back, and Add to notebook.
- **Scripture source picker:** Bible, Jewish texts or Quran.
  - **Jewish texts:** Sefaria's free API (Mishnah, Talmud by daf, Midrash, Pirkei Avot and more), Hebrew/Aramaic beside English, up to 30 segments. Footnotes, markup and cantillation are stripped. Search uses Sefaria's search API (`web.post_json`, same public-address rule).
  - **Quran:** alquran.cloud. Uthmani Arabic, transliteration, Pickthall, Yusuf Ali and Saheeh International; references like `2:255` or `36:1-12`. Search uses its English search.
  - **Bible:** a new Hebrew column gives full Masoretic verses from Sefaria for the Old Testament.
  - Right-to-left columns render right to left. Marks remember their source. "Traditions" now covers Jewish commentators and Sunni, Shia and Sufi tafsir. "More sites" adds Quran.com.
- **Tests:** scripture_test 7, research_test adds translation. The full suite passes (713).

### 27.3 Suggestions for upgrades and new features — Claude, 2026-10-25 (v2.4)

- Grey asked for her suggestions to also cover upgrading the system and new features.
- **Kinds of suggestion:** each suggestion is now one of three kinds: *Your day*, *Upgrade* or *New feature*. Older "ZAE herself" items show as features.
- **What upgrade ideas are based on:** `gather_system_context()` gives her:
  - Python, her key packages and Ollama, each against its latest release. Package versions come from PyPI and the Ollama version from GitHub releases; both are public and cached for 12 hours in `data/ui/upgrade_check.json`.
  - Her local models and the brain model in use.
  - RAM, GPU memory and free disk; Node; and her health issues.
  - The list of what the app already has, so she doesn't suggest existing features.
  - Earlier upgrade and feature ideas, so she doesn't repeat them.
- **Detail on upgrade and feature ideas:** each carries *how* (one or two sentences) and *effort* (small, medium or large).
- **Upgrade plan:** approving an upgrade or feature puts it on her upgrade plan. "Copy upgrade plan" gives a list to paste to Claude or Codex.
- **Page:**
  - The buttons are Think of suggestions, Upgrades & new features, and Just my day; these call `POST /api/suggestions/think` with `{focus}`.
  - Filters are All, Your day, Upgrade and New feature.
- **Tests:** tools_test adds two tests.

### 27.4 Web agent and watch list — Claude, 2026-10-25 (v2.5)

- Grey asked for an agent that takes information from the internet, and chose "Both" on the card: research on request plus a watch list.
- `core/research/agent.py`:
  - **Research:** `Agent.start(question)`:
    - Her brain plans up to 3 search queries. It is given today's date, and years she adds on her own are dropped, because her model's knowledge is dated.
    - Search uses DuckDuckGo's plain HTML results (POST, honest ZAENIA user agent). Ads, video sites and PDFs are skipped.
    - She reads up to 6 pages, at most 2 per site, through `web.safe_url`.
    - The answer comes from her local brain, with [n] citations. Page text is wrapped as untrusted data.
    - It runs in the background, and a follow-through notice is posted when it's done.
  - **Watch list:** `Watch`:
    - Up to 30 topics, each checked about once a day by a server thread that runs every 30 minutes and skips while a game is running.
    - Sources: Google News' RSS search feed (past week) and recent DuckDuckGo results.
    - Only unseen links are summarised. "NOTHING NEW" means no finding.
    - New findings go to follow-through, a line in the full spoken briefing, and the Suggestions context.
  - **Chat and voice commands:** "research …", "look into …", "watch the topic …", "keep an eye on news about …", "stop watching the topic …". These go through `ui_chat_stream._protocol_or_reminder` and need chat.reply or memory.write.
- **Routes:** `/api/research/agent` (GET list, POST start, DELETE id) and `/api/research/watch` (POST add, POST {id}/check, DELETE id).
- **UI:** "Web agent" is the first Research tab. It shows the answer with clickable citations, the sources, Add to notebook, the watch list with Check now, and earlier research.
- **Not used:** sending a browser-like user agent to get Bing's news feed was refused as bot-check circumvention. ZAE identifies herself honestly.
- **Tests:** agent_test 6. A live run took 16 seconds and gave a cited answer from 6 pages.

### 27.5 PC specs — Claude, 2026-10-25 (v2.6)

- Grey asked for ZAE to know his computer's specs.
- `core/assistant_platform/pc_specs.py` reads the PC with one PowerShell CIM query plus nvidia-smi:
  - CPU, RAM sticks, GPUs with VRAM, driver and display, motherboard and BIOS, drives and free space, and the Windows build.
  - It never reads serial numbers, user names or network details.
  - The result is cached for a day in `data/ui/pc_specs.json` and warmed at server start-up.
- **Where ZAE uses it:**
  - **Her answers:** `pc_context()` adds the specs, plus live load from the status bar, to her brain context. This only happens when a question is about the PC, its parts or what it can run.
  - **Upgrade suggestions:** the suggestions context also gets the specs.
- **Route:** `GET /api/pc/specs[?refresh=true]` (status.read).
- **UI:** Status > This PC shows the parts, with a "Read again" button.
- **Tests:** pc_specs_test 2.

### 27.6 Cross-tagged projects, reading links, clarifying questions — Claude, 2026-10-25 (v2.7)

- **Cross-tags (Workbench):**
  - A project keeps its main subject and can also be tagged with any of the other subjects (`Project.tags`, at most 8).
  - It shows under each tagged subject's filter, and its card lists every subject.
- **Reading links:** `core/research/links.py`. A chat message with up to 3 links has each link read and answered through the shared-files path. The content is data only, never instructions.
  - **TikTok:** caption, author, length and sound, plus the spoken words from TikTok's own auto-captions (the public WebVTT track the page lists). No video is downloaded.
  - **YouTube:** title, channel, length and description. YouTube doesn't hand its captions to plain readers, and ZAE says so.
  - **Other pages:** readable text, or og:title and og:description when the page is mostly script.
  - **Unreadable links:** she says she couldn't read it and doesn't guess.
- **Clarifying questions:** a request to make something personal (a program, plan, routine, schedule, diet, budget…) first gets 2–4 multiple-choice questions from her brain.
  - **Pop-up:** they appear in the `ClarifyCard` pop-up. Each question has its choices plus a free-text box and an "Ask ChatGPT" button, which opens chatgpt.com in his browser with the question and context filled in.
  - **Sending:** "Send answers" re-sends the request with "My answers to your questions:"; "Skip, just do it" says to use her judgement.
  - **Prompt note:** the questions prompt is framed as "write clarifying questions". Asked to "make a fitness program", llama3.1:8b sometimes refused outright.
- **reply_shape:** requests to make a program, plan and the like, and answered questions, get the full answer, not the two-line brief.
- **Tests:** links_test 5; personal_tools_test adds cross-tags.

### 27.7 Reading any file — Claude, 2026-10-26 (v2.8)

- Grey asked for ZAE's reader to read any file. `core/api/file_reader.py` extends `chat_files.extract_text`, which already read text, code, PDF, Word and Excel.
- **New document formats:**
  - PowerPoint (slide text from the pptx XML).
  - OpenDocument text, spreadsheets and slides.
  - E-books (epub).
  - HTML (all text, paragraphs kept).
  - RTF, with font and colour tables removed.
  - Jupyter notebooks.
  - E-mail (.eml headers, body and attachment names).
  - Old Office files (.doc, .xls, .ppt, .msg): the text strings found inside.
- **Archives and databases:**
  - zip: names plus the text of small text files inside.
  - tar and gz.
  - SQLite: tables, columns, row counts and the first rows, opened read-only from a temporary copy.
- **Images:** gif, bmp, tiff and others (png, jpeg and webp still go to the photo path) are described, and their text copied, by the local vision model qwen3.5:4b.
- **Audio:** wav, mp3, flac, ogg, opus and aiff are transcribed on the PC with the Vosk model (first 10 minutes). m4a, aac and wma need a converter the PC doesn't have, and ZAE says so.
- **Video:** not watched yet (there is no ffmpeg); she asks for the audio or a screenshot instead.
- **Anything else:** its likely type (from magic bytes) and the readable strings inside.
- **Tests:** file_reader_test 6; chat_files_test updated.

### 27.8 Saving to tabs, voice pacing, FFmpeg — Claude, 2026-10-26 (v2.9)

- **Saving to tabs** (Grey: she wrote a plan and then claimed she'd added it to Fitness, but nothing was saved): `core/assistant_platform/tab_actions.py`.
  - **Phrases:** "add it / save that / put this to my fitness tab, workbench or notes (as a training plan / project / note)" and "save it as a training plan".
  - **What it saves:** her last answer becomes a real record. The day headings and the exercises with sets and reps are parsed into plan steps. The shared link becomes the plan's source, and her brain writes a short title.
  - **After saving:** the tab opens and its list reloads (`zae:records-changed`).
  - **Permission and honesty:** the action needs memory.write. A new conversation rule forbids claiming a save, sync or change the app didn't do.
- **Voice pacing:** she says "One sec." if nothing has arrived after 1.6 s, and the server can send a spoken status (a `say` event; "One sec, I'm reading that." for links). She then speaks about 240 characters, finishing the sentence, and ends with "The rest is on screen." The written reply and the Play button are unchanged.
- **FFmpeg:** if installed (found on PATH or where winget puts it), she transcribes M4A, AAC and WMA audio. For video (mp4, mov, mkv…) she transcribes the speech and describes four moments with her vision model. Without FFmpeg she says it's needed.
- **Tests:** tab_actions_test 3; file_reader_test updated.

### 27.9 Training program (live daily tracker) and phone notifications — Claude, 2026-10-26 (v3.0)

- Grey asked for a live daily tracker: a calendar, calories to eat and burn based on the video, weight, height, steps and cardio, several source links, and phone reminders. His fitness-app screenshots are a soft reference.
- **Tab:** Fitness & Health now opens on **Training program**. The old plan editor is "Edit plans".
- `core/assistant_platform/training.py`, stored in `data/fitness/program.json`.
- **Calendar and daily tracker:**
  - The active plan's days ("Day 1 Chest and Triceps (Gym)") are grouped from its steps, dropping notes and titles.
  - Days map to weekdays, defaulting to gym and home days or to Mon–Sun, and can be re-mapped.
  - The month calendar shows each day's workout and how much of it is done, plus weigh-in and cardio marks.
  - The daily tracker has check-offs and set logging (reps × lb), plus weight, body fat, steps, lifting minutes and cardio (type, miles, minutes).
- **Targets:**
  - Mifflin-St Jeor BMR × activity outside workouts gives maintenance.
  - The goal pace sets the deficit (1 lb/week = 500 kcal/day), split into a burn target (40% of the deficit, 250–600) and an eat target (maintenance + burn − deficit, floored at 1500/1200).
  - Protein is 1 g per lb of goal weight.
  - Missing age, sex, height or weight are named rather than guessed.
- **Burn estimates:**
  - Steps: stride from height, 0.3 kcal/lb/mi.
  - Runs: 0.63 kcal/lb/mi.
  - Other cardio by net MET.
  - Lifting: MET 5 × minutes, or 3 min per logged set.
  - Food eaten and logged exercise come from the Log page.
- **Dashboard:** weight trend, 30-day habit grids (workouts, weigh-ins) and weekly sets per muscle group (exercise keywords mapped to muscles).
- **Sources:**
  - Several links per program, read with `links.read_link` (TikTok spoken words included).
  - Her brain extracts the target height, weight and body fat and the advice ("Use as my goal weight").
  - "Improve my program from these sources" writes a new plan, keeps the old one and makes the new one active.
- **Phone notifications** (`core/api/web_push.py`):
  - Web Push with VAPID; the private key is DPAPI-protected and subscriptions are kept in `data/secure`.
  - `public/sw.js` shows the notifications and `core/phonePush.ts` subscribes. On iPhone this needs iOS 16.4+ and ZAE opened from the Home Screen.
  - What gets pushed:
    - Every follow-through notice (reminders, e-mail, research ready), via `FollowThroughService.post`.
    - Daily training reminders at his times (workout on training days, weigh-in if not logged, food).
  - Routes: `/api/push/key|subscribe|unsubscribe|test`.
  - Package: pywebpush (installed in the live venv, added to requirements.txt).
- **Tests:** training_test 7, including push and reminders.
- **Update (same day):** Grey asked ZAE to ask the setup questions herself as a pop-up, with the answers going to her.
  - **`TrainingSetup` pop-up:** age, sex, height, weight, body fat, goal (the video's figure is offered), pace, activity, gym and home days, and reminder times. Saving it fills in his stats and goal.
  - **When it opens:** by itself while the calorie math is missing inputs, from a button, when he says "set up my training" (stream event `form`), and after "add it to my fitness tab" saves a plan while setup is incomplete.
  - **What her brain gets:** `training_context()` gives it his stats, targets, weekly schedule, today's workout and what's done, today's calories eaten and burned, recent weigh-ins and weekly muscle sets. This only happens when the conversation is about fitness, and needs memory.read.
  - **Body map:** a front and back figure lights each muscle by its weekly sets.

## 28. Browser phone notifications — Codex, 2026-10-25 (v3.1)

USER REQUIREMENT: send actual phone notifications through the browser for reminders and other assistant updates. Baseline inspected: main `855db5a`; Claude's existing Web Push, reminders, training, phone hosting, follow-through and permission routes were reviewed and extended on `codex/browser-phone-notifications`.

- **Decision:** retain the existing opt-in VAPID/DPAPI browser integration. A separate delivery worker reads the canonical follow-through inbox, so calendar/task notices and posted reminder/email/research/training notices share quiet hours, pause, snooze, read state and expiry. It checks existing notification capabilities; learning grants no authority. Core remains usable offline, while remote Web Push requires internet and the PC/API running.
- **Delivery:** durable per-device claims, bounded retry/backoff and provider-result metadata in private ignored SQLite; expired subscriptions removed, permanent failures reported; stable notification tags and TTL bound to notice validity. Provider acceptance is distinguished from actual phone display. No raw notice contents or endpoints in the delivery ledger or status response. No claim of guaranteed or exactly-once display.
- **Security:** validate browser-provider HTTPS endpoints and real encryption keys; refuse redirects and bound request timeouts. Retain sealed VAPID key, private subscription storage and existing API/startup authentication. Use the app's HTTPS origin as VAPID contact rather than localhost. Owner must grant the browser notification permission directly on the phone.
- **Clients:** shared **Phone notifications** panel in Settings → Notifications, Tasks & Calendar → Reminders and Training program. Per-device category choices and opt-in message previews, reconnect/disable, targeted test and truthful delivery status. The service worker displays visible notifications and opens only this app when tapped; it caches no private API data.
- **Regression support:** isolate push storage/sender in the API lifecycle test. Correct an existing profile test to attempt relearning in the same scope it forgot, rather than assuming the current private fixture record is global; production memory logic is unchanged.
- **Verification:** full Python discovery passed (758 tests, 1 skipped); security self-test/closure/integration checks passed (124); browser-side test scripts passed; `npm run build:web` and `npm.cmd run tauri build -- --no-bundle` passed. `git diff --check` passed.
- **Rollout status:** committed as `3032cd8`, fast-forwarded into local `main`, and installed to the Windows desktop app on 2026-10-25. During rollout, the API was healthy in full mode; `/api/push/status` and `/api/push/device` were registered, and `/app/` returned HTTP 200 over the existing private Tailscale HTTPS route. An authenticated test was accepted by the browser push service; actual phone display is not confirmed. No remote Git push or authentication-policy change was made.

Implementation, setup, exact limits, primary browser references and rollback: `docs/BROWSER_NOTIFICATIONS.md`.

### 28.1 Connected notes and live transcripts — Claude, 2026-10-26 (v3.2)

- **Shared notes:** one set of notes is used by Notes, the Research notebook and Workbench.
  - **Research notebook:** each topic's notes are a note (`topic.noteId`). Old topics get their note the first time they're opened. Deleting a topic keeps its note. "Use one of my notes" makes an existing note a topic, and "Add analysis & sources to the note" appends to it.
  - **Workbench:** projects link notes (`Project.noteIds`). Project notes can be edited in place, created ("New note for this project") or linked from existing notes.
  - **Notes tab:** each card is tagged "Research" or "Workbench: <project>".
- **Live transcripts:** `LiveTranscript` records in Notes, the Notebook and Workbench project notes.
  - The microphone is turned into text on the PC every 6 s via `POST /api/voice/dictation` (memory.write) and appended to the note.
  - Any speaker works, for lectures and meetings. It returns words only, never a command or a chat turn, and has no speaker gate.
- **Chat commands:**
  - "add this to notes[: text]" makes a new note from the text, or from ZAE's last answer.
  - "update my <name> note with this[: text]" or "add this to my <name> note" appends with a timestamp. The note is found by title; if there's none, it's created.
- **Notes tab look:** a pinboard. Cards come in three sizes (from length and id) and five tints, slightly tilted.
- **Notes API:** `Notes.create`, `set_body`, `append` and `find`; `POST /api/platform/notes/{id}/append`. Listing items carry `chars` and `tags`.
- **Tests:** research_test (shared notebook notes), tab_actions_test (note commands), personal_tools_test.

### 28.2 Everything from chat — Claude, 2026-10-26 (v3.3)

- Grey asked to be able to do everything the tabs do from chat as well. Tasks, events, reminders, notes, plans, research and watch topics already had chat handlers. `core/assistant_platform/chat_actions.py` covers the rest:
  - **Fitness:** open a source-backed, review-before-save meal flow for food; log exercise, weight/body fat/steps, cardio and sets; and check off today's workout exercises.
  - **Tasks and reminders:** mark a task done, change its priority or deadline, cancel a reminder.
  - **Workbench and Music:** new project, change its stage.
  - **Research:** translate text, find books in the Library.
  - **Training program:** add a source link, improve the program from its sources.
  - **Suggestions and Code Doctor:** think of suggestions, run Code Doctor on ZAE's code.
- **How it decides:**
  - A word check (an instruction verb plus a tab topic, not a question) decides whether to ask her brain at all.
  - Her brain picks ONE action from the fixed catalogue as JSON, or "none". Unknown names are refused.
  - Each action checks its permission (ui.tasks.write, memory.write, chat.reply, assistant.desktop.manage).
  - The reply says exactly what was done and the tab opens.
  - Nothing is deleted except a reminder he names.
- **Tests:** chat_actions_test 4 (prefilter, catalogue-only classification, fitness logging, projects and tasks).

### 28.3 Design principle: a system that helps people — Grey, 2026-10-26

- Grey: "We cannot add human elements to AI. We have to keep the system a system that helps humans."
- **What's fine:** natural talking, speaking and actions.
- **What's not allowed:** ZAE must never claim feelings, moods, wants, a body, a life story or personal experiences, and must never present herself as human.
- **Where this is enforced:** it's the first conversation rule (`conversation_rules.RULES`).
- **Future features:** they follow the same line. Persona elements stay as interface style (voice, wording, look), never as claimed inner life.
- Grey, same day: "Humans need to work and AI needs to be a system that can assist." ZAE prepares, informs, reminds and carries out what he asks. The work and the decisions stay his, and features assist rather than replace him. This is added to the same rule.

### 28.4 Nutrition records, recipes and structured training plans — Codex, 2026-10-26 (v3.4)

- **Fitness & Health tabs:** add Recipes and Scan food beside the existing Log, Edit plans, Targets and Training program pages. Preserve the existing dark-blue / amber interface and API token/authentication boundary.
- **Food records:** retain the existing calorie, protein and fiber fields; add carbohydrates, fat, saturated fat, sugars, sodium, cholesterol, per-item source URLs and checked-at times. Nutrients not reported by a source remain unknown and are displayed as “not fully reported”, not silently treated as zero.
- **Meal logging:** chat descriptions open a review in Fitness & Health. The meal parser splits quantities into items; generic and branded food searches use USDA FoodData Central, and each result is explicitly selected and scaled to an owner-confirmed gram amount. Meal totals are reviewed before a single meal record is committed. Missing calories, protein, fiber or serving amounts block logging and direct the owner to clarify or read the label. The chat classifier's estimate is never persisted.
- **Barcode / photo:** barcode lookup uses the Open Food Facts product API. Label photos are passed only to ZAE's configured local vision path, raw image bytes are not retained, and extracted values require owner review before logging. Manual barcode entry and photo upload remain fallbacks where camera scanning is unsupported.
- **Recipes:** local, profile-portable `fitness_recipe` records hold ingredients, amounts, servings, instructions, nutrient values and source strings. Recipe math sums entered ingredient values per batch and serving. Recipes remain editable and owner-controlled. No previously discussed recipe ingredients or quantities were found in the current local memory/recipe records; the protein pancake button starts an empty recipe for owner-provided values.
- **Plan editor:** retain the legacy `exercise` and `prescription` fields for existing plans and daily tracker compatibility. New optional sets, rep range, duration, rest, equipment and coaching notes are additive. Day cards group the existing day-heading rows, with per-day completion, movement controls and day duplication.
- **Authority and storage:** source lookups require `memory.read`; saving a meal or recipe requires `memory.write`. Learning does not grant permissions. Existing SQLite profile capture automatically includes the new personal collection. Local recipe editing and manual food logs remain usable offline.
- **External source behavior:** USDA FoodData Central's API requires a Data.gov key and its documented `DEMO_KEY` has lower quotas. ZAE reads `FDC_API_KEY` from the local environment when configured and uses the demo key otherwise; no key is stored in source control. Open Food Facts values are community-contributed, so barcode results always retain a label-verification prompt. Primary references: [USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide/) and [Open Food Facts API documentation](https://openfoodfacts.github.io/openfoodfacts-server/api/).
- **Verification status:** frontend TypeScript/Vite build, 13 focused nutrition/chat/storage tests, Python compilation, diff check, and the FastAPI read/write authorization integration test pass. Catalog network calls use mocked data in tests; live catalog lookup and camera hardware were not exercised.
- **Windows desktop rollout (2026-10-26):** built the native Tauri release from `codex/fitness-nutrition-workflow`, installed it with `scripts/update_desktop_app.ps1`, and reopened ZAE. The installed executable SHA-256 matched the release build.
- **Activation (2026-10-27):** the live local API reports ready on port 8766 in full owner-authenticated mode (version 0.9.1). OpenAPI exposes meal preview/log, barcode, label, search, recipe math, and the generic personal-record routes. The installed desktop process is running and its SHA-256 still matches the release build. Startup authentication remains unchanged.

### 28.5 Code Doctor Playground — Claude, 2026-10-27 (v3.5)

- Grey asked for a Code Doctor sub-tab to write code and test it before implementing it. New tab: Code Doctor > Playground.
- **Run:** Python, JavaScript (Node) or PowerShell, in a fresh temporary folder that is deleted afterwards (`core/assistant_platform/playground.py`).
  - Time limit 5 to 60 s; the whole process tree is stopped when it runs out.
  - Output capped at 100 KB.
  - Minimal environment: none of ZAE's tokens, keys or settings are passed in.
  - Desktop app only (`require_desktop`).
- **Tests:** test code runs after the code in the same file; exit code 0 means they passed.
- **ZAE assists:** explain an error and fix it, review and improve, write tests, or answer a question. Her code is shown separately; Grey chooses "Use as code" or "Use as tests".
- **Snippets:** saved in `data/playground/snippets.json` (last 200).
- **Implement:** writes the code into a project file under the Code Doctor roots.
  - A new file is created.
  - An existing file must be loaded first; it is only replaced if it hasn't changed since (SHA-256 check), and the old version goes to `backups/playground/`.
  - ZAE's security code is refused. Each implement is audited.
- **Routes:** `POST /api/code/run`, `/api/code/playground/ask`, `GET/POST/DELETE /api/code/snippets`, `POST /api/code/load`, `/api/code/implement`.
- **Tests:** playground_test 13; full suite 776 OK (14 skipped); UI script tests and `tsc` pass.

### 28.6 Training: what was actually done — Claude, 2026-10-28 (v3.6)

- Grey asked that ZAE change the day's training from context when Grey does something other than the plan (example: an ACFT in the morning), and use it for burned calories.
- **From chat:** describing what was done (any length, up to 4,000 characters) picks the new `workout.actual` action. ZAE turns the description into activities: name, type, detail, minutes, miles and effort (MET). Distances Grey states win over her guess. "Back to the plan" (`workout.plan`) undoes it.
- **In the Training program:** a "Did something different? Tell ZAE" box does the same for any date. The day then shows the activities in place of the plan, each with editable minutes or miles, its kcal, a remove button and "Back to the plan". The plan itself is never changed.
- **Burn:** stored as `actual` on the day's log (`training.clean_actual` clamps minutes to 300, MET to 1.5–14, at most 30 items). When present it replaces the lifting estimate: runs and walks by distance (0.63 or 0.3 kcal per lb per mile), everything else by (MET − 1) × kg × hours. Steps and separately logged cardio still count. All labelled as estimates.
- **Route:** `POST /api/platform/personal/training/actual?day=` (memory.write).
- **Tests:** training_test ActualWorkoutTest 2; full suite 786 OK (14 skipped); tried on Grey's ACFT text with the local model (classified as workout.actual, five activities, 2.0 mi run).

### 28.7 Training: times, pace and loads — Claude, 2026-10-28 (v3.7)

- Grey asked ZAE to use stated times, pace and weights (ACFT example: 240 lb hex bar × 3, 31 push-ups in 2 min, SDC 1 min 98 sec, plank 1:98, 2-mile run in 16:30).
- **Read from Grey's own words, not the model's guess** (`training.apply_measured`), per bulleted line (or by name, or the whole message for one activity):
  - Times: `16:30`, `1:05:00`, "1 min and 58 sec", "two minutes", "45 seconds". Overflowing seconds roll over (1:98 = 2:38).
  - Loads: a number before lb/pounds or before bar/hex/dumbbell/kettlebell/sled; the heaviest is kept.
  - Reps: "three clean reps", "31 push-ups".
- **Into the burn:** a stated time sets the minutes. Runs show pace and speed, and their MET follows speed (Compendium, about 1.53 × mph + 0.4), though the burn stays distance-based. Lifts use load relative to bodyweight for effort (MET 3.5 + 2.5 × load/bodyweight, capped).
- **Shown:** each activity has a stats line (`training.describe`), e.g. "16:30 · 8:15/mi · 7.3 mph" or "240 lb × 3 reps (1.23× bodyweight)", in the Training program and in ZAE's chat reply.
- **Tests:** training_test adds parsing of times, loads, reps and pace; full suite 787 OK (14 skipped). `assistant_stream_test.test_task_execution_requires_separate_permission` failed in 2 of 3 full runs and passes alone (order or timing dependent, not related to this change).

### 28.8 Food numbers Grey states are logged directly — Claude, 2026-10-28 (v3.8)

- Grey asked that when they say how much protein, fiber, calories or carbs they ate, ZAE logs it without searching.
- **Rule:** `chat_actions.stated_nutrition` reads only numbers in Grey's own words: calories, protein, fiber, carbs, fat, saturated fat, sugars and sodium (mg), as "150g protein", "2,100 cal" or "carbs: 220". If any are present, `food.log` saves them as said, sourced "Told ZAE in chat", with no lookup and no estimate.
  - If calories aren't given but protein, carbs and fat are, calories are worked out as 4/4/9 and labelled as such. Otherwise none are counted, and the reply says so.
  - The food name is the one Grey gives, or "Logged in chat" for plain totals.
- **Unchanged:** a food named without numbers still opens Codex's sourced meal review (28.4), so a model estimate never silently becomes a health record.
- **Tests:** chat_actions_test adds stated-nutrition parsing and direct logging (including the macro-derived calories); full suite 788 OK (14 skipped).

### 28.9 Phase 0 pass: stabilize security and source of truth — Claude, 2026-10-28 (v3.9)

Grey asked to start the phased plan (section 11) at the first step. Status of each Phase 0 part, with evidence:

| Part | Status | Evidence |
|---|---|---|
| Path capitalisation bypass (P0) | DONE 2026-10-21 | §17.3, ui_files_test |
| Protected code and code-edit approval (P0) | FIXED now | Code Doctor fixes and Playground "Implement" used a shorter list than the file tools: they could edit `ui_routes.py`, `platform_routes.py`, `server.py`, `ui_files.py` and `capabilities.py` (the modules that map requests to permissions). `code_doctor.protected` now includes everything `ui_files.is_protected` covers, compares case-insensitively, fails closed on errors, and also protects `code_doctor.py` and `playground.py`. Test: code_doctor_protected_test 4. |
| Voice speaker verification (P0) | DECIDED: option (b), every app-mic turn | Grey chose (b) on 2026-10-22 (commit f934611, `core/voice_security/app_mic.py`, `app_mic.require_owner_voice: true`) and reconfirmed it on 2026-10-28 ("keep every turn"). §17.3 and §20.4 item 2 were out of date. Left for the exit: Grey runs voice training (say "train my voice", or Security > Voice training: re-enroll, calibrate on the approved mic, refresh the app-mic reference), then live owner and other-speaker trials. |
| Retrieval excludes generated/historical content (P1) | CONFIG DONE, REBUILD PENDING | The saved index (2026-10-17) had 8,583 chunks, about 4,300 of them from backups, UI backups, Tauri build output and lock files. `system_awareness_config.yaml` now excludes `*backup*`, `restore*`, `target`, `dist`, `dist-*`, release snapshots, cleanup review, web cache, chat files, and lock files. Test: system_awareness_config_test 3. The rebuild (`python -m core.brain.system_index build`, then `core.brain.semantic_index build`) is owner-gated by the passkey, so Grey runs it. The backups stay on disk; a separately labelled historical lookup is not built. |
| Dependency manifest and install doc (P1) | DONE except the clean-install test | The typo was already fixed. Ten packages live code imports were missing from requirements.txt: lxml, soundfile, scipy, pygame, kokoro-onnx, silero-vad, torch, torchaudio, speechbrain, huggingface_hub (pinned to the live versions). Added `docs/INSTALL.md` (tools, PyTorch CUDA index, Ollama models, Vosk/Kokoro/Piper/ECAPA model locations, builds, tests) and `scripts/check_install.py` (read-only: packages and pins, tools, Ollama models, local models). The live install passes it. Test: check_install_test 3. A fresh-venv install test downloads several GB and waits for Grey's OK. |
| Regression tests | FIXED a flaky test | `assistant_stream_test.test_task_execution_requires_separate_permission` failed in about 2 of 3 full runs: "Add a task to inspect the car" reached the chat-actions classifier, and the live model sometimes picked `task.update`, so no task proposal was shown. `chat_actions.maybe` now leaves creating tasks, events, reminders and notes to their own handlers. 3 of 3 full runs pass: 799 tests OK (14 skipped). |

Phase 0 exit (red-team/regression tests, protected routes, clean-install test, live owner/other-speaker trials) is not met yet: it waits on voice training and the live owner/other-speaker trials, and the index rebuild. Grey declined the clean-install test from PyPI (2026-10-28), so that exit item stays open.

### 28.10 Sidebar icons and the Music studio — Claude, 2026-10-28 (v3.10)

- **Icons:** Code Doctor shows code brackets, Music a music note, Arena a brain and Research a pen.
- **Tab reworks:** Grey asked for three preview directions per tab before any rework. They're on the "ZAE tab rework previews" design canvas. For Music, Grey chose B (dashboard) as the main view, with A (studio pipeline) and C (song workspace) as sub-tabs, plus room for live analytics connections.
- **Music studio** (`desktop/src/components/music/MusicStudio.tsx`) replaces the single-form Music panel. It has four sections:
  - **Dashboard:** in-progress and released counts, studio time this week, and the next release. A card per platform shows the total of its main measure (Spotify, SoundCloud and Apple Music plays; YouTube views), a trend and the change over 7 days, 30 days or all time. Songs are ranked by total (click one to open it). Also a release calendar with checklist items left, and quick number logging.
  - **Studio:** six stage columns. Drag a card to change its stage. Cards show BPM, key, progress (stage plus checklist) and the next step.
  - **Song:** a workspace with title, BPM, key, release date, GarageBand reference and card colour; a clickable stage tracker; lyrics and session notes; the release checklist; studio sessions (date, minutes, note); release links; the song's numbers; and archive.
  - **Connections:** a card per platform showing its status (all not connected) and what live data would need, stated as checked. YouTube Data API key: public view counts. SoundCloud API app: plays, and new apps need approval. Spotify: the Web API has no stream counts and Spotify for Artists has no public API, so it would be a CSV export. Apple Music for Artists: no public API, so a CSV export. Nothing connects yet. Statistics stay `method: "manual"`, and the dashboard marks each platform "Manual" until a connector exists.
- **Data:** the `Music` record gains `lyrics`, `releaseDate`, `checklist` (fixed items: Lyrics final, Vocals recorded, Mix approved, Master exported, Artwork ready, Distribution submitted), `sessions` and `art`. All are optional, so existing songs load unchanged. `GET /api/platform/personal/music/overview` (memory.read, existing pattern) returns active songs in full plus the checklist and the connection info. Saving uses the existing revision-checked PUT.
- **Tests:** personal_tools_test adds the workspace fields, validation and overview; full suite 800 OK (14 skipped); UI script tests and `tsc` pass. Not checked visually: the dev browser has no live API without the app's credentials.

### 28.11 Appearance for reworked tabs, and Tasks & Calendar — Claude, 2026-10-29 (v3.11)

- **Grey's picks** (preview canvas, boards renamed with numbers): every tab keeps all three previews as sub-tabs in the numbered order. The full list is in project memory (`tab-rework-picks`).
- **Customisations carry over:**
  - `desktop/src/styles/look-styles.css` defines shared tokens (`--zx-panel`, `--zx-inset`, `--zx-line`, `--zx-radius`, `--zx-shadow`, `--zx-title-font`, `--zx-btn-case`, `--zx-gap`, `--zx-pad`) for each window style (Aurora, HUD, Editorial, Neon). They're built from the window's `--accent`, so a tab's own colour applies too.
  - The Music studio and new tabs use these tokens.
- **New Appearance options** (saved per device, voice commands included):
  - Spacing: compact, comfortable or spacious.
  - Corners: the style's own, sharp, soft or round.
  - Panel solidity: 50–100%.
  - Motion: full or reduced. Reduced turns off transitions and animations app-wide.
- **Tasks & Calendar** (`components/plan/PlanStudio.tsx`) has four sub-tabs, all on the existing tasks, calendar, reminders and training data:
  1. **Week** (main): seven day columns with events, tasks due, the training day and reminders; a bar showing how booked each day is; open a day; tick off tasks.
  2. **Priorities**: four boxes (Do now = Critical, Schedule = High, Quick wins = Normal, Later = Low). Drag a task to change its priority; done, open and overdue counts for the week.
  3. **Day**: a mini month, list counts, an hour timeline (drag a task onto an hour to set its time) and the day's tasks.
  4. **Month & reminders**: the previous panel (month grid, duty status, completions, reminders), so nothing is lost.
- **Quick add** (`core/quickTask.ts`): "call bank fri 3pm !high" understands today, tomorrow, tonight, weekdays, dates, 3pm or 18:30, and !critical, !high or !low.
- **Tests:** `scripts/plan-quick.test.cjs` 6 and appearance 31 checks; `tsc`; full Python suite unchanged.
- **Gotcha:** `.gitignore` ignores `*token*`, so a file named look-tokens.css was silently untracked. It was renamed look-styles.css.

### 28.12 Fitness & Health rework — Claude, 2026-10-29 (v3.12)

- `components/personal/FitnessStudio.tsx`, in Grey's order (B, A, C). All three use the look tokens and are labelled as estimates.
  1. **Progress:** weight since the start of the range, workouts and weigh-ins over 30 days, the 7-day protein average against target, and the 7-day deficit (maintenance + exercise − eaten). A weight chart against the plan line (rate per week), calories eaten vs burned over 7 days, and sets per muscle.
  2. **Today:** eat, burn and protein rings against targets; weight and steps logged in place; goal date; today's workout with checkboxes, or the activities logged instead; today's food.
  3. **Day log:** a timeline of weigh-in, food (with times), activities, cardio, the workout and steps; where today stands (kcal and protein left, open exercises, goal date); upcoming fitness reminders; a "log anything" box.
  4. **Training program** and 5. **Logs & plans** (the existing Log, Recipes, Scan food, Edit plans and Targets) stay, kept mounted so ZAE's setup and meal-review events still reach them. `FitnessPanel` gained `embedded`, which hides its own duplicate Training program page.
- **Log anything:** `POST /api/platform/personal/training/quick-log` (memory.write) uses `chat_actions.fitness_quick_log`. It only runs fitness actions. Food is logged only with numbers Grey states; otherwise it points to the Log review.
- **Food listing** now includes `createdAt`, so meals show their time.
- **Tests:** chat_actions_test quick-log; full suite and UI checks pass; `tsc` clean.

### 28.13 Recipes: ingredient search as you type — Claude, 2026-10-29 (v3.13)

- Fitness › Logs & plans › Recipes. Each ingredient (`components/personal/RecipeIngredient.tsx`) searches as Grey types (3+ letters, 0.5 s pause) through `POST /api/platform/personal/nutrition/suggest` (memory.read, `nutrition.search_products`). Results are cached for an hour.
  - Sources: Open Food Facts packaged products (search.openfoodfacts.org, falling back to the classic search) and USDA FoodData Central. If one source is offline, the other's results still show, with a note saying which didn't answer.
- **Picking a match** fills nutrients per 100 g, scaled to the amount: g, kg, oz or lb, ml counted as grams, or "serving" when the product states its serving weight. The source link and name are kept.
- **Editing:** every value stays editable. An edited value is marked "edited" and kept when the amount changes, and "Reset to source" restores the source values.
- **Running totals** for the recipe and per serving update live ("—" until every ingredient has that value). "Log one serving" sits next to the totals.
- **Fix:** `search_food` sent `dataType` as repeated parameters, which FoodData Central rejects with 400. It now sends one comma-separated value; this also affects the meal review.
- **Note:** the shared `DEMO_KEY` is rate-limited (429 seen while testing). A free personal FoodData Central key in the `FDC_API_KEY` environment variable makes USDA reliable.
- **Tests:** nutrition_test SearchProductsTest 2; `scripts/recipe-ingredient.test.cjs` 7.
- **More sources (same day, after Grey said the search didn't know his ingredients):**
  - `search_products` asks four sources at once (threads, 15 s each): Grey's saved recipe ingredients (per 100 g; worked out from his own amounts when no source was picked); a built-in list of 39 common whole foods with typical USDA reference values (`nutrition_common.py`, works offline, labelled "typical values · check your package"); Open Food Facts' new search service and its classic search (merged without duplicates); and USDA FoodData Central.
  - Ranking: his own ingredients first, then names containing every typed word (plurals folded), then names starting with it, generic foods before brands.
  - Search starts at 2 letters. Results show inline under the field, not as a pop-up that could be clipped, with a status line naming the sources and any that are busy. "Search again" re-runs it.
- **Tests:** nutrition_test 3 (merge and ranking, one source offline, offline with saved and common foods).
- **By serving (Grey: "have it by serving size"):**
  - The search list shows each food per serving, e.g. "1 large egg (50 g): 72 kcal · 6.3 g protein". It falls back to per 100 g only when the source states no serving.
  - Picking a food sets the unit to "serving" with 1 to start, and the source line says what one serving is.
  - Serving weights come from the label (Open Food Facts `serving_size`; USDA `servingSize` and `householdServingFullText`), or from a typical serving for each of the 39 common foods (`nutrition_common.SERVINGS`).
  - Values are still stored per 100 g underneath, so g, oz and lb keep working. UI checks: recipe-ingredient 14.
- **Real products with label servings (Grey: fairlife whole milk had no serving, and too many near-identical results):**
  - The Open Food Facts search index leaves out serving sizes and full names. The top 8 products are now read from their full label record (`/api/v2/product/{code}`, in parallel, 6 s each), which gives the real name ("fairlife Whole ultra-filtered milk"), package size (52 fl oz) and printed serving ("1 portion (240 ml)").
  - When a label lists no serving, a typical one by food category is used and marked "(typical serving)": milk 1 cup, yogurt 1 container, cheese 1 oz, nut butter 2 tbsp, and so on.
  - Near-duplicates (same name and calories) merge, keeping the most complete record. A repeated brand ("Chobani Chobani") is tidied.
  - Ranking prefers names with the most typed words, then US products and ones with a serving. The list shows at most 10, each with its package size.
- **Store data:** store sites (Walmart, Target) have no open nutrition data. Kroger has a free developer API (needs a key) if Grey wants store listings later.
- **Tests:** nutrition_test ProductLabelTest 2.
- **Websites (Grey: "use website for all foods, products or stores"):** `nutrition_web.py`, `POST /api/platform/personal/nutrition/web` (memory.read). After the quick results, the recipe row asks for website labels and adds them under "From websites".
  - **FatSecret's public food pages** cover brand and store products. Each gives the label serving (with grams, from the product page) plus calories, fat, carbs and protein. Fiber, sugars and sodium aren't on those pages, so they stay blank to fill in, and the result says so.
  - **Brand or store pages** found by a web search are read in parallel for a label: schema.org NutritionInformation first, then the Nutrition Facts text, then the local model for that part of the page only.
  - Pages or search engines that block automated readers are skipped; the reader is never disguised. DuckDuckGo was showing a bot check while this was tested, so FatSecret is the dependable source and brand pages appear when the search lets the reader through.
  - Each result names the website it came from, and every value stays editable.
- **Tests:** nutrition_web_test 5 (label panel, serving grams, JSON-LD, FatSecret parsing, page reader).

### 28.14 Meals from one sentence — Claude, 2026-10-29 (v3.14)

- Grey's breakfast sentence in Log › "Describe a meal" didn't log. "3 eggs with tomatoes, onion, mushrooms, and cheese" was read as one food, every item without an amount stopped for a question, and household units (cup, strips) had no weight.
- **`nutrition.plan_meal` (rule-based):**
  - Splits "with" add-ins. Following short items join the add-in list only when the list closes with "and …".
  - Keeps the amounts and units Grey said, and reads "25 g protein shake" as a stated 25 g of protein.
  - The local model was tried for this but dropped amounts, so it isn't used.
- **`preview_meal`:**
  - Looks up every item in parallel with `search_products` (his recipes, common foods, Open Food Facts, USDA), plus the website lookup when the top matches lack fiber.
  - Prefers a match with a serving size when no amount was said, and one that reports calories, protein and fiber.
  - Portions come, in order, from the weight said; household units (cup ≈ 240 g, or the label's 1-cup serving); count × label serving (3 × 1 large egg); a typical add-in amount (cheese 28 g, jelly 20 g, others 30 g); or one serving.
  - Each item carries a note saying how its portion was worked out ("added in: about 30 g (estimate)"). The review shows it, and every match and weight stays editable.
- **Common foods:** added cooked potatoes, cooked bacon, bagel, jelly or jam, mushrooms, granola, applesauce, apple and orange juice, white and whole-wheat bread, and a typical ready-to-drink protein shake, all with typical servings.
- **Result:** Grey's sentence gives 14 foods, about 1,590 kcal and 94 g protein, complete and ready to log after review. The review's "Search nutrition sources" now uses the multi-source search.
- **Tests:** nutrition_test updated (offline questions, catalog values) plus the one-sentence breakfast.

### 28.15 Research rework: Desk, Reader, Evidence board — Claude, 2026-10-29 (v3.15)

Grey's picks from the preview canvas, in his order: A (Desk) first, then C (Reader), then B (Evidence board). Every existing Research tool stays as a later sub-tab (Web agent, Historical Connections, Notebook, News, The Library, Scripture & ancient, Translate). All three new views use the look-styles tokens, so window style, per-tab colour, density, corners, panel solidity and motion apply.

- **Desk** (`ResearchStudio.tsx`, opens by default):
  - One search box runs the Library, world news, scripture and the notebook side by side (`core/research/desk.py`, `GET /api/research/desk`). Each source answers on its own; one that fails or is slow is named and the rest still show. Source chips choose which run; recent searches are kept on this PC.
  - "Sum up with ZAE" writes a short summary from the encyclopedia overview and the results, naming which source each point comes from, and can be saved to the notebook.
  - Each result can be read in the Reader, opened on its site, or added to a notebook topic. Notebook hits open that topic's Evidence board.
  - "Show mentions over time" draws the old-newspaper mentions chart for the search (Historical Connections data), only when asked, because it is slow.
- **Reader:** one calm reading view for news articles, free library books, scripture hits and saved notebook sources (`GET /api/research/notebook/{topic}/sources/{source}` returns a source's kept text). A shelf keeps the last 12 things read, the reading position is remembered per item, and a progress bar shows time left. Selecting text offers Save highlight (kept per item, and appended to the chosen topic's note), Explain and Translate. The side panel has ZAE (summarise, explain the highlight, facts vs opinion, compare with my notebook, ask about this page), Highlights and Translate.
- **Evidence board:** each notebook topic is an investigation with a question (`PUT …/question`) and claims sorted into Supports, Contradicts and Open questions (`POST/PUT/DELETE …/claims`). Grey adds, moves and deletes claims. "Ask ZAE to suggest claims" (`POST …/claims/suggest`, `analyze.suggest_claims`) proposes up to 8 from the topic's sources; nothing is added until Grey presses Keep. "Weigh the cards" gives a one-or-two-sentence answer and how sure she is, built only from the cards. Source text stays untrusted data.
- **Capabilities:** desk and reading a source are memory.read; question and claims are memory.write; suggesting claims is chat.reply.
- **Tests:** `core/research/desk_test.py` (6): sources answer independently with timeouts, chosen sources only, notebook word matching, question/claims/source reading, suggested-claim parsing, route capabilities.

### 28.16 Overview blended with Grey's reference dashboard — Claude, 2026-10-29 (v3.16)

Grey asked to keep the existing Overview (the Neural Core) and blend it with a reference dashboard: a glowing sphere as the hero, cards on both sides, a context line and actions under the sphere, a status bar along the bottom. This replaces the earlier plan (C first, A's cards behind its buttons, B last) with one page that holds all three: the calm core (C) as the centre, A's context cards around it, B's mission-control numbers inside those cards.

- **`components/overview/OverviewFrame.tsx`** wraps the Neural Core on the Overview:
  - Left: **Today** (open, due-today and overdue tasks, the next event and reminder), **Fitness & health** (kcal left of target, eaten and protein meters, today's workout), **System health** (security score ring, CPU, memory and GPU meters).
  - Right: **ZAE's systems** (the core modules with ready/working/waiting states, like the reference's agents), **Ask ZAE** (suggested actions built from the calendar, overdue tasks and food left today, each sends a chat request), **Music & news** (songs in progress, next release, top stories).
  - Under the core: a greeting with the weather, one line on what's next and what's due, and the four quick asks (Brief me, Plan tomorrow, Log food, Start workout).
  - The existing status bar stays at the bottom. Every card's ↗ opens its tab.
- **Calm view** hides the cards and leaves the core alone (remembered on this device). Phones and narrow windows always show the core alone. While windows are open and the core docks in a corner, the cards step aside.
- **Data:** read from ZAE's own routes (calendar, tasks, reminders, training day, status bar, security summary, music overview, tech news, weather), refreshed every minute and when records change. A missing value shows "—", never a made-up number.
- **Look:** built on the look-styles tokens with the Overview's own tab colour, so window style, density, corners, panel solidity and motion apply.

### 28.17 Overview as a phone app screen (iPhone 16 Pro) — Claude, 2026-10-29 (v3.17)

Grey asked for the Overview to fit an iPhone 16 Pro like an app. Before, phones showed the core alone.

- On phones the Overview is one scrolling screen between the header and the chat bar, sized for 402 × 874: a smaller core (up to 290 px tall), the greeting and next-up line, the quick asks as one swipeable row, four widget tiles two across (Tasks, Calories left, Security, ZAE's systems; each opens its tab), then Today, Ask ZAE and Music & news as full-width cards.
- Touch targets are at least 40–48 px, text is larger than on desktop, and the bottom edge fades so the list reads as scrolling under the chat bar. Calm view works on the phone too.
- The desktop and phone layouts share the same card pieces and data, so both always show the same numbers.
- Checked in the preview at 402 × 874: no sideways scrolling, top and scrolled views.

### 28.18 Overview: week trends, cycling Calm view, idle setting — Claude, 2026-10-29 (v3.18)

Grey's notes on the blended Overview: add more like the reference's bottom row; the tab strip covered the Calm view switch; Calm view should come on by itself after a set idle time (set in Settings); keep the core the same size in both views, and have Calm view cycle through important info.

- **Bottom row under the core:** Tasks done this week (a bar for each day, from completed tasks), Weight trend (30-day line, latest weight and change, workout dots for the week), and Notes & research (counts of notes, topics and sources, the latest notes). Each opens its tab.
- **Calm view switch** moved from the top of the core (under the Manage tabs strip) to the end of the quick-ask row. The modules count lives in the ZAE's systems card.
- **Same core size:** Calm keeps the three columns and fades the side cards out, and its spotlight takes the bottom row's exact slot, so the core doesn't move or resize (checked in preview: 1090 × 612 in both).
- **Spotlight:** cycles every 8 seconds through Next up, Tasks, Fitness & health, the top three news stories, Music and System, with dots to jump and pause-on-hover. Tapping it opens that tab.
- **Idle Calm view:** Settings (System & appearance) has "Calm view when idle": Off, 1, 2, 5 (default), 10, 15 or 30 minutes. After that long with no key, click, touch, scroll or mouse move, the Overview goes calm; any touch brings the cards back. Saved on each device. Checked in preview with 1 minute.
- **Phone:** the week row stacks under the other cards, and Calm view shows the spotlight under the quick asks.

### 28.19 Scan food barcodes with the phone camera (Fitness & Health) — Claude, 2026-10-30 (v3.19)

Grey asked to read barcodes with the phone in Fitness & Health. Before, Scan food only took a barcode photo and read it with the browser's BarcodeDetector, which iPhone Safari doesn't have, so it always failed there.

- **`desktop/src/core/barcode.ts`:** ZAE's own reader for EAN-13, UPC-A, EAN-8 and UPC-E (returned as the full 12-digit UPC-A). It samples rows and columns across the middle of the picture, turns each into bar and space widths, matches digit patterns and keeps only codes whose check digit is right. It reads upside-down and sideways codes. BarcodeDetector is still tried first where it exists (Android Chrome). No new dependency.
- **`BarcodeScanner.tsx`:** full-screen camera with a guide box (back camera, about 8 reads a second, a light button where the phone supports it, Cancel, a short buzz on success). Frames stay on the phone; only the digits go to the existing Open Food Facts lookup. It needs ZAE's secure https address and camera permission, and says so plainly if either is missing.
- **Where:** "Scan barcode" on Fitness › Today, a "Scan" button in the Day log's quick-log bar, and "Scan barcode with camera" on Logs & plans › Scan food. All open the camera and show the product for logging. Photo upload stays as a fallback and now uses the same reader.
- **Tests:** `scripts/barcode.test.cjs` (12): check digits, UPC-E expansion, EAN-13/UPC-A/EAN-8/UPC-E lines, reversed and noisy lines, a whole image and a sideways image. In the browser the reader also read a tilted, blurred test barcode from a canvas. The camera itself is blocked in the preview pane, so it still needs a try on the phone.

### 28.20 Calm view cycle fix — Claude, 2026-10-30 (v3.19)

The spotlight paused while the mouse was over it, and when Calm view comes on from idle the mouse is usually resting there, so it stuck on one item. It now always cycles every 8 seconds; picking a dot holds that item for 20 seconds. Five new Overview directions (Command Deck, Orbit, Flight Board, Editorial, Holo HUD; each with a dashboard and a Calm view) are on the preview canvas page "Overview v2 · pick one" for Grey to choose from.

### 28.21 Navigation rework, merges, Assistant front page, multi-brain plan — Claude, 2026-10-30 (v3.20)

Grey's direction after the Overview v2 previews: dashboard of 1 (Command Deck) and 3 (Flight Board), the quick-ask chips kept, the flight board made a small panel; the core's six icons become six categories that every tab fits in; no sidebar on the dashboard (only inside a tab); chat on every screen; clicking the core lists every tab; picking a category zooms in toward the core; Assistant like preview 4 (Editorial); Code Doctor and Files merged; F&H "Logs & plans" sub-tabs and the T&C nested sub-tabs flattened; Overview reached from a Home item in the ZÆNIA menu; News only inside Research with more stories and right-click show more / less; three Calm view previews combining 1 and 2; wake-up and sleep phrases; a multi-brain plan.

- **Six categories** (`desktop/src/core/categories.tsx`, default "by what you're doing" until Grey picks on the card): Plan (Tasks & Calendar, Notes), Health (Fitness & Health), Know (Research, Assistant), Create (Music, Workbench), Build (Code Doctor & Files, Arena), System (Status, Security, Settings). The core shows them on the dashboard; while windows are open the docked core keeps its module icons.
- **Core navigation** (OverviewFrame): a category zooms the core in (scale and glow, 0.65 s; instant with motion off), then opens its only tab or shows its tabs as large tiles. Clicking the sphere lists every tab grouped by category, with the sidebar's icon size. Escape or a click outside closes.
- **Sidebar only in a tab**: hidden on the dashboard (desktop); Overview left the sidebar and is "Home" at the top of the ZÆNIA menu. The phone keeps its bottom bar. The chat bar stays on every screen.
- **Day board**: a small flight-board panel (time, item, status) leads the dashboard's bottom row, from events, overdue and due tasks, and reminders.
- **Merges**: Code Doctor & Files is one tab (Code Doctor, Suggestions, Playground, Files, Source) with a new icon (the Code Doctor brackets inside a file). News left the sidebar and lives in Research; "open news" / "open files" still work and jump to that sub-tab (`zae:page-tab`).
- **F&H**: Food & exercise, Recipes, Scan food and Plans & targets are F&H tabs (Edit plans and Targets merged), next to Progress, Today, Day log and Training program.
- **T&C**: the Both / Calendar / Tasks / Reminders switch became the Month (calendar with tasks) and Reminders tabs.
- **News**: up to 150 stories at once (route limit 200). Right-click a story: Show more like this / Show less like this / Open story. Feedback weights the story's words and newsroom (`data/news/preferences.json`, on this PC), which reorders headlines and hides strongly disliked ones. Test: show_more_and_less_like_this.
- **Assistant**: first sub-tab "Today's edition" is The ZAE Daily (lead = next up, columns for fitness, news and the studio, by the numbers, briefs from ZAE's follow-ups, Ask the editor); the existing tools are the second sub-tab.
- **Calm view previews**: A Split, B Halo, C Horizon on the preview canvas page "Calm view · pick one". Calm view build and the wake-up / sleep phrases wait on Grey's pick.
- **Multi-brain plan**: `docs/architecture/ZAENIA_Multi_Brain_Plan.md` (Talk, Seek, Keep, Study; the Conductor's levels; shared working memory; wake and sleep phrase handling; phases and Grey's decisions).
- **Tests**: Python 819 OK (14 skipped); desktop type-check and node tests pass; checked in preview (no sidebar on the dashboard, six categories, zoom then tiles, the full tab list, Code Doctor & Files sub-tabs).

### 28.22 Calm view A, wake-up calls and sleep phrases, best model per brain — Claude, 2026-10-30 (v3.21)

Grey picked core icons option 1 and Calm view 1 (A, Split), and asked for the best model for each brain.

- **Calm view A** (`components/overview/CalmView.tsx`): a full-screen layer over any screen. The left side holds a dimmed core, three rings (waking day 6 AM to midnight, calories eaten of target, today's tasks done) and the clock. The right side shows one important item at a time, cycling every 9 seconds (Next up, Tasks, Fitness & health, top three news stories, Studio, System), each with three facts, plus a progress strip and the next four queued. It starts after the idle time set in Settings (now counted on every screen, not only the dashboard), from the Calm view button, or from a sleep phrase. **Rule:** leaving Calm view always goes to the dashboard. The old in-dashboard calm mode is replaced by this layer.
- **Wake-up calls** (`core/calmPhrases.ts`, 18 checks): "Wake up sleepy, we have work to do", "Sleeping on the job?", "The boss is here", "Zae, you're still there?", "The day is not yet over" / "The night is still young". Small wording changes match; long sentences that only contain the words don't. They are accepted only from the app mic after the turn passed Grey's voice check, so typing them or another voice does nothing. While calm, all other speech is ignored. If the mic is off, holding Wake for two seconds is the fallback (a short press does nothing).
- **Sleep phrases**: "Take everything to the background", "I'm going to sleep", "Let's put a pin in this and continue tomorrow", "Calm view", spoken or typed. Running background jobs keep going while calm.
- **ZAE's replies** (`core/assistant_platform/wake.py`, `POST /api/assistant/wake`, chat.reply; 6 tests): the app sends the situation (time, how long she was calm, next event, due and overdue tasks, calories left, news count, security score, jobs finished while calm or still running, current tab). Her local brain writes one short JARVIS-style line from only those facts, as a statement or a question, never claiming feelings; if it takes over 4 seconds, a written line from the same facts is used. She speaks it. On waking, the dashboard shows her line and the card she talks about glows (tasks, calendar/day board, fitness, news or system), chosen from her actual words. Live trial with llama3.1:8b: replies in 0.3–0.7 s once loaded (the first, cold call used the written line).
- **Best model per brain** (in the multi-brain plan, section 3.1, with sources): Talk qwen3.5:4b (installed), Seek qwen3.5:9b, Keep qwen3:1.7b on the CPU, Study qwen3:14b with gpt-oss:20b for overnight deep runs. About 17 GB of downloads, waiting on Grey's OK; Phase 1 measures them on this PC first.
- **Tests**: Python 824 OK (14 skipped); node tests including calm-phrases pass; preview checks: Calm view layout, hold-to-wake (2 s only), typed sleep phrase opens Calm view.

### 28.23 Category zoom into the core, panels of recent things — Claude, 2026-10-30 (v3.21)

Grey: the zoom should end with us close to that part of the core as the background, and a category should show panels of recent things from its tabs, not the tabs themselves (reference: a large sphere filling one side of the screen).

- Picking a core category now scales the core about 3.4x around that icon (0.9 s ease, instant with motion off), dims it, and keeps it as the background; the side cards, hero and bottom row fade away. Panels appear on the icon's side; "← Core" or Escape zooms back out.
- `components/overview/CategoryPanels.tsx` reads recent items from each tab: Plan (coming up, open tasks, reminders, recent notes); Health (eaten today, today's training, today so far, recent weigh-ins); Know (research topics, top stories, web research, from ZAE); Create (songs in progress, releases, workbench projects); Build (Code Doctor ideas, file changes, Arena leaderboard); System (this PC now, security, recent security activity). Each panel has "Open <tab>"; a source that doesn't answer says so instead of guessing.
- The category tab-tiles sheet is gone; clicking the sphere still lists every tab. Checked in preview: zoom origin at the Plan icon, panels on the left, back restores the dashboard.

### 28.24 Brain models installed and timed; the rest of the new tab screens — Claude, 2026-10-30 (v3.22)

Grey approved downloading the four picked models and asked to finish the new screens so every new look loads.

- **Models:** qwen3.5:9b, qwen3:1.7b, qwen3:14b and gpt-oss:20b are installed in Ollama. Timed on this PC (multi-brain plan 3.2): Talk qwen3.5:4b gives its first word in 0.07 s at 122 tokens/s using 3.7 GB, and Talk + Seek fit together in about 10 GB. Chat still uses llama3.1:8b until the Conductor (phase 2) is built.
- **Code Doctor (picks A, C, B):** Health first (score out of 100, errors, warnings, notes, secrets, size, problems worst first, problems over the last 10 scans, biggest files, with vendored files skipped; `code_doctor.scan` now returns `biggest`). Then the Review queue: fixes and ZAE's ideas one at a time; a fix is written, shown as a diff and saved only on "Approve and apply" (desktop app, backup kept, protected files refused); ideas can be approved or dismissed. The Playground is the editor (B). The old Scanner, Suggestions, Files and Source follow.
- **Notes (A):** Board, a pinboard of notes tinted by tag, pinned or long notes larger, #tag filters, and a quick-add box (the first line becomes the title). "All notes" is the editor.
- **Workbench (A):** Project lab, project cards with a grid cover, stage badge, subject chips and stage progress. "Projects" is the editor.
- **Status (B):** Live first: CPU, memory, GPU memory and disk gauges, a 10-minute CPU and GPU chart (sampled every 5 s while open), and the biggest programs by memory (`GET /api/status/processes`, names, CPU and memory only).
- **Arena (A):** Head to head, the same question to two hidden models, then vote (A, B, tie, both bad). Leaderboard & brain is the next tab.
- **Security (A):** Shield, the overall level and score, last full check, "Run a full check", and the eight areas the level covers. Each area's own result and the fixes stay behind the passkey in Details.
- **Settings (A):** Control center, working switches (listening, speak replies, core motion, hand controls, sidebar in tabs, Calm view when idle, Calm view now, PC voice), accent colour and text size, and links to Appearance, Notifications and the Vault.
- **Checks:** the type-check and node tests pass. In preview, each tab opens on its new first view (Settings showed every switch). Views that read records need the server, so they were checked for opening, not for data.

- 2026-10-30: Calm view now shows the dashboard's own core (the same canvas and six category icons), dimmed to about 40% brightness and not clickable; the day, calorie and task rings moved to small gauges under it.

### 28.25 Anatomical heart icon for Health — Codex, 2026-10-30 (v3.23)

- Replaced the generic heart glyph used for the Health category on the Neural Core with a custom anatomical heart line icon, including major vessels and internal contours. It uses the existing SVG stroke and category color so the visual treatment remains consistent with the other core icons.

### 28.26 Conductor Phase 2: Talk routing and shared working memory — Codex, 2026-10-30 (v3.24)

- **Isolated baseline:** left `main` at commit `d84d62b` unchanged and verified the local tag `zaenia-pristine-2026-10-30` points there. Work proceeds on `codex/conductor-weekend-2`, based on that commit. Existing local `core/api/chat_files.py` changes were not copied or edited.
- **Level 0:** existing deterministic protocol, reminder, screen-watch, photo/file and action-proposal routes stay ahead of model chat. Sensitive changes still use their current permission and approval routes; the Conductor never executes actions.
- **Talk:** `core/brain/conductor.py` routes ordinary desktop/browser chat and owner-verified PC voice turns to `qwen3.5:4b` with a two-second first-text budget while resident and a cold-load window when it is not. `local_llm.model_is_loaded()` checks Ollama's loopback `/api/ps`; a cold start receives an 8-second first-text window and a 15-second HTTP timeout, while warm turns keep the 2-second budget. The live cold Talk trial took 3.91 seconds to first text; the next warm turn took 0.16 seconds. If Talk times out or fails before speaking, ZAE sends a short spoken status and retries through `qwen3.5:9b`. The real Seek handoff returned the correct answer and `execution_authorized=false`. Both models use local Ollama and the existing `BrainService` grounding/live-data paths. A per-turn timeout and stop event bound each attempt.
- **Shared working memory:** the Conductor keeps the last three user/assistant exchanges and the last route/evidence references per authenticated conversation in process memory, capped at 128 sessions and a 30-minute idle lifetime. It is temporary, never grants permissions, and is not persisted. The model receives it as context explicitly marked as untrusted conversation context.
- **Wake and sleep:** the situation-based wake/sleep reply now uses the Talk model. Existing phrase matching and voice checks remain in place.
- **Scope:** this starts Phase 2. The Seek model handoff is currently a model retry through `BrainService`; the evidence-pack search pipeline remains Phase 3. Keep scheduling/pattern learning and Study jobs are not yet connected to the Conductor.
- **Dev server:** `desktop/vite.config.ts` binds the standalone browser development UI to `127.0.0.1:1420` and proxies `/api` to the existing token-protected Core on `127.0.0.1:8766`. Tauri can still supply its explicit host for remote HMR.
- **Verification:** 31 focused Python tests passed (`conductor_test`, `assistant_stream_test`, `assistant_upgrade_test`, `fluid_runtime_test`); all 14 desktop Node test scripts passed (424 counted checks). Local model trials verified Talk cold and warm starts plus a real Seek handoff. The broader core run executed 811 tests, with 4 failures, 7 errors and 13 skips: document-folder fixtures reject this worktree because it is under the protected `.codex` directory. TypeScript, `npm run build`, `npm run build:web` and `npm run tauri build -- --no-bundle` succeeded after the final Conductor change. Live speaker-authentication trial remains pending. No server restart or install replacement has been performed from this feature branch.

### 28.27 Conductor Phase 3: source-backed Seek lookups — Codex, 2026-10-30 (v3.25)

- **Explicit online routing:** `core/brain/seek.py` recognizes direct online, current and research requests. Seek searches only the user's stated query, reads at most four public pages through the existing safe research agent, and does not send private memory or the Conductor blackboard to the web.
- **Evidence handling:** the local Seek model receives page excerpts as untrusted data with inline citation instructions. Missing evidence is stated plainly in the prompt. Web page text cannot grant permissions or authorize actions; the final event always carries `execution_authorized=false`. Existing grounded local-system answers keep their verifier and now carry their local index paths through the stream.
- **Sources in chat:** the stream's `done` event includes bounded source references. The desktop and browser chat render external HTTPS sources as links and local evidence as labels.
- **Keep and Study roles:** Keep's existing evidence-checked insight learner now defaults to `qwen3:1.7b` with Ollama `num_gpu: 0`; configured research watches use that model. Existing scheduled backup, security, news, and topic-watch services remain intact. Research-agent long reports use local `qwen3:14b` through background-priority model calls and preserve their source list. `gpt-oss:20b` overnight scheduling remains future work.
- **Checks:** 35 focused Seek, Conductor, Keep learning, and research tests pass; all 14 desktop Node test scripts pass. `npm run build`, `npm run build:web` and `npm run tauri build -- --no-bundle` succeed. The browser/native production outputs were generated. The separate `core.api.assistant_stream_test` stalls at its first calendar permission test in this managed checkout; the full core suite also has the path-related fixtures documented in 28.26. Next: verify live voice speaker rejection, live source citations, and Keep preemption while speaking; then tune the multi-brain scorecard. No merge or installation has happened from this feature branch.

### 28.28 Conductor promotion, recovery baseline, and live release — Codex, 2026-10-30 (v3.26)

- **Promotion:** Conductor Phases 2–5 and the anatomical Health heart icon were merged into `main` and pushed to GitHub as `ec608d2`. The fetched GitHub head (`88a1a1f`) was an ancestor of local `main`, so its history was preserved by the fast-forward push.
- **Recovery:** the untouched baseline remains pinned locally and on GitHub at tag `zaenia-pristine-2026-10-30` (`d84d62b`). Pre-promotion unrelated/local edits, including `core/api/chat_files.py`, remain in the recoverable stash `Prepromotion local WIP preserved 2026-10-30`; they were not merged or discarded.
- **Release:** rebuilt the native desktop app and browser site from promoted `main`. The installed `%LOCALAPPDATA%\Programs\ZAENIA\ZAENIA.exe` matches `desktop/src-tauri/target/release/desktop.exe` by SHA-256. Rebuilt `desktop/dist-web` is served by the restarted local Core on port 8766. `/health` and `/app/` both returned HTTP 200; health reports token-protected unattended mode and running assistant follow-through.
- **Verification:** 35 focused Python Conductor/Seek/Keep/Research tests pass when the temp directory is pointed into the writable project workspace. All 15 desktop Node test scripts pass. TypeScript, desktop Vite build, browser Vite build, and Tauri release build pass. Vite reports the existing 580 KB main JavaScript chunk warning.
- **Remaining validation:** live speaker rejection, live web citation quality, Keep preemption while speaking, and Phase 6 multi-brain tuning/scorecard remain to be checked. The standalone Vite development server on port 1420 is not running.

### 28.29 Conductor validation, four fixes, Phase 6 scorecard — Claude, 2026-10-30 (v3.27)

I followed Codex's handoff (multi-brain plan, section 9), validating on a fresh branch from `main` and then merging into the live install.

- **Fixes:**
  - Talk no longer races Seek. After 2 s it says "I'm looking through our data." and keeps going, and Seek steps in only if Talk fails or stays quiet for 25 s.
  - Time words no longer send personal questions to web search.
  - Keep's insight learner no longer waits on its own model slot.
  - Pages without a header charset read correctly.
- **Results:** Talk was 8 of 9 under 2 s (median 0.39 s; before the fix, 0 of 9), with a 3.5 s cold start. Seek's web lookups give cited sources, it says "can't verify" when there are none, and page text that tries to give orders is ignored. The full scorecard and conditions are in multi-brain plan section 8.1.
- **Tests:** 842 OK, 14 skipped.
- **Pending:** the live owner/other-speaker voice trial with Grey at 17:00.

### 28.30 Phone version: app-style swiping and sizing — Claude, 2026-10-30 (v3.28)

Grey: the mobile version should differ slightly for size and look, and the web version should swipe like an app.

- **Swiping** (`desktop/src/core/swipe.ts`, phones only): a quick sideways swipe (at least 60 px, mostly horizontal, under 0.7 s) moves to the next or previous sub-tab. Past the first or last sub-tab it moves to the neighbouring tab, in bottom-bar order first (Core, Plan, Fitness, Research), then the rest. Swipes that start in text fields, the chat box, Calm view, the barcode camera, the category panels or anything that already scrolls sideways are ignored. The page slides in from the swipe direction (transform only; off with motion off). 10 checks in `scripts/swipe.test.cjs`.
- **Phone look** (`desktop/src/styles/phone-app.css`):
  - Sub-tab rows are one swipeable strip that stays at the top while scrolling, with a fading edge to show there's more.
  - The active tab scrolls into view.
  - The page header is compact (small title, no description).
  - Buttons are at least 36 px tall.
  - Fields use 16 px text, so iPhone doesn't zoom in.
  - Sideways overscroll is turned off.
- **Checked at 402 × 874 in preview:** swiping from the dashboard went to Plan and then Fitness, then through Fitness's sub-tabs and back.

### 28.31 Phone as a remote for the PC — Claude, 2026-10-30 (v3.29)

Grey: make the web version a remote for the PC, and let the phone confirm things when it's near the PC.

- **Remote tab** (phone and browser only; hidden in the desktop app): `desktop/src/components/studios/RemotePanel.tsx`. It shows whether the PC app is connected and what it's on, the PC's open tabs (show, hide, close each), big buttons for Calm view / Wake, Dashboard and Restore all, and a grid of tabs to open on the PC.
- **Server** (`core/api/remote_control.py`, routes in `ui_routes.py`):
  - `POST /api/remote/commands` (operation `assistant.desktop.manage`, audited) queues one command from a fixed list: open, close, minimize (a real tab name only), show_desktop, restore_all, calm, wake. Anything else is refused.
  - `GET /api/remote/collect` and `POST /api/remote/state` need the desktop key, so only the paired desktop app on the PC takes commands or reports state.
  - `GET /api/remote/state` (status.read) tells the phone what's open and whether the PC reported in the last 15 s.
  - Commands live in memory only, are handed out once, and are dropped after 2 minutes, so an old tap never fires later.
- **Desktop app**: checks for commands every 1.5 s and reports its tabs and Calm state when they change (or every 8 s). It carries out only the listed screen commands.
- **Not on the remote**: saving files, launching apps, restoring workspaces and approvals. They still need the desktop key at the PC. Letting the phone approve them when it's near the PC waits on Grey's choice of how ZAE knows the phone is there (code on the PC screen, same Wi-Fi, or code plus voice).
- Tests: 4 in `core/api/remote_control_test.py` (only listed actions and real tab names, hand-out-once and expiry, state and connection, route permissions).

### 28.32 Phone confirms at the PC: code plus voice — Claude, 2026-10-30 (v3.30)

Grey chose "code plus voice, in either order" for letting the phone confirm things when it's at the PC.

- **How it works** (`core/api/near_pc.py`):
  1. In PC remote, the phone taps **Confirm from this phone**. The server makes a pass and returns its secret to the phone only.
  2. The PC app shows a 6-digit code in a box at the bottom right. The code changes every minute. The box also has a "That's not me, cancel" button that ends the pass from the PC.
  3. The phone does two steps, in either order:
     - It types the code (`POST /api/near/code`).
     - It passes a voice check: the six spoken words plus the local speaker check, the same check as voice sign-in, through `POST /api/auth/voice/near`. This check signs nothing in.
  4. Both steps must finish within 3 minutes. The pass is then on for 10 minutes.
- **Limits:**
  - Five wrong codes end the pass.
  - Only one pass exists at a time. It is kept in memory only, so a server restart ends it.
  - Every step and every use is audited.
- **What the pass allows:** with the `X-ZAENIA-NEAR-PASS` header, the phone can do these confirms, which otherwise need the desktop key:
  - approve a waiting file change
  - apply a Code Doctor fix
  - open a registered app
  - restore a workspace with its apps

  Engine 3 still authorizes each operation as before.
- **Still desktop-only:** direct file edits, code run and implement, folder grants, approval settings, operator missions, Security, the Vault, the passkey and pairing. The phone-side pass is held in page memory only.
- **Phone UI:** a **Phone confirms** card in PC remote shows both steps with ticks and a countdown, plus Turn off. On the phone, Files shows **Approve and apply** while the pass is on.
- **Tests:** 7 in `core/api/near_pc_test.py`. They cover code then voice, voice then code, a wrong pass, a wrong code and an old code, 5 strikes, expiry and replacement, and an end-to-end HTTP run. That run shows approval is refused until both steps are done and allowed after, the voice step sets no sign-in cookie, direct edits are still refused, and ending the pass stops it.

### 28.33 Phone confirms: random order — Claude, 2026-10-30 (v3.31)

Grey clarified that "either order" means ZAE should pick the order of the two steps at random.

- **Server:** each new pass picks code-first or voice-first at random (`secrets.choice`), and the second step only opens after the first:
  - A code sent too early is refused with "Do the voice check first this time." That doesn't count as a wrong code.
  - The PC shows no code until it's the code's turn.
  - The voice step is refused until its turn.
- **Phone:** the card numbers the steps in the chosen order and greys out the second one ("Opens after the code" or "Opens after the voice check").
- **Tests:** 9 in `near_pc_test.py`. They now also check that both orders come up and that the second step waits for the first.

### 28.34 Phone confirms: random QR code — Claude, 2026-10-30 (v3.32)

Grey asked for the PC code to be a random QR code and approved two packages: `qrcode` 1.5.4 (draws it on the PC) and `jsqr` 1.4.0 (reads it on the phone). Both are MIT-licensed, run on the device, and are pinned exactly. `@types/qrcode` was added as a dev dependency.

- **PC:** the box shows a QR code holding `zae-near:` plus a random 24-byte key. It changes every minute, together with a small 6-digit backup code (`NearQr.tsx`, dark on light).
- **Phone:** the QR step opens the full-screen camera. `BarcodeScanner` gained a `qr` mode with a square guide box, using jsQR via `core/qr.ts`. "Camera won't focus? Type the code" shows the backup field.
- **Server:** `submit_code` accepts the current QR key or the current 6-digit code. Wrong ones count toward the 5 tries, and both stop working when the minute is up.
- **Tests:**
  - 10 in `near_pc_test.py`. This adds a check that the QR key works and that an old QR key doesn't.
  - `scripts/qr.test.cjs` has 3 round trips confirming that a QR drawn by `qrcode` is read back by `jsQR`.
- **Note:** `npm audit` reports a high-severity issue in the existing dev-only `vite` 8.3.x, not in the new packages. Fixing it is a separate vite update.

### 28.35 Core zoom plays in reverse on the way back — Claude, 2026-10-30 (v3.33)

Grey: coming out of one of the six category icons back to the core should play the zoom in reverse.

- `OverviewFrame.tsx`: "← Core", Escape and the sphere all play the zoom in reverse.
  1. The category panels slide away toward their side (0.26 s).
  2. The core pulls back out from the same spot it zoomed into (0.9 s). The zoom origin is kept through the return with the `ov--returning` class, where before it jumped to the centre.
  3. The dashboard cards fade back in from 0.5 s, as the core settles.
- Opening a tab from a panel still goes straight there.
- The steps run on timers that are cleared if you pick another category mid-way. Motion-off and reduced-motion settings make it instant.
- Checked in preview (1440 × 900):
  - The panel exit plays.
  - The core's transition runs from scale(3.4) to none at the original origin.
  - The cards' transition delay is 0.5 s during the return.

### 28.36 Every tab's 2nd and 3rd designs built — Claude, 2026-10-30 (v3.34)

Grey approved building the remaining picks from the preview canvas. All of them use real data and the look-styles tokens. They are in `components/studios/SecondViews.tsx`, `SecondViews2.tsx` and `ThirdViews.tsx`, with CSS in `SecondViews.css` and `ThirdViews.css`.

**Notes**
- **Notebook (B):** three panes. Folders on the left are All, Pinned, This week, ZAE can read, and your tags. The list is in the middle and the editor on the right. Pin, ZAE-readable and Save work in place.
- **Map (C):** the 18 most recent notes are joined by a shared tag or by shared words. A side panel lists the linked notes. "ZAE noticed" points out notes that share words but no tag.

**Workbench**
- **Blueprint (B):** a full grid canvas on each project's existing `strokes`, with pen, line, box and measure tools and 5 inks. It shows live lengths in the project's units. Undo, Export SVG and Save are included. Project-note lines starting with "- " show as the parts list.
- **Experiments (C):** a new `experiments` personal collection, using the `Experiment` and `Reading` schemas in `personal_tools.py` (memory.read and memory.write routes). Each experiment holds a hypothesis, what changes, what's held the same, what's measured, and up to 4 groups. It has a readings chart, a log and a result.

**Arena**
- **Leaderboard (B):** win rate, wins, speed and size, with "Make ZAE's brain" (desktop only).
- **Test set (C):** `core/assistant_platform/arena_bench.py` and the `/api/arena/bench*` routes. It holds up to 30 of your questions, each with what a good answer mentions (comma-separated). Runs go one model at a time in the background. A mention of every phrase grades ✓, some grades ½, none grades ✕.

**Security** (both stay behind the same passkey or phrase unlock as Details)
- **Activity (B):** notable events per day for 7 days, plus a filterable log.
- **Plan (C):** posture areas in three columns (who can get in, what it can touch, if something goes wrong) with "How to fix".

**Status**
- **Readiness (A):** the status modules plus the desktop-app and backup checks, in three groups. Voice has a Start button.
- **Uptime (C):** `core/api/uptime.py` checks the server, local brain, desktop app and backups every 5 minutes. It keeps 30 days of per-day counts and a list of changes, including times the server was off. The data lives in `data/ui/uptime.json`, and history starts from this update.

**Settings**
- **Search (B):** real switches with live values, plus places that open the right tab.
- **Make ZAE yours (C):** a live preview of window style, accent, font, glow, text size, panel see-through, corners, spacing and motion. Nothing changes until you press "Use this look".

**Code Doctor**
- **Side by side (C):** the files to fix, then Write the fix, then the changed area before and after, then Approve and apply. Applying needs the desktop key or Phone confirms.
- **Editor (B):** the file list with finding counts, a code view with finding lines highlighted, ZAE's notes with Explain and Write the fix, and a scan summary bar.

**Assistant**
- **Memory & rules (A+C):** saved facts and learned patterns with Keep and Forget, plus your rules: talking (live switches), acting and notices, and the first rule.

**Tests:** 5 new in `core/api/second_views_test.py` (uptime counts, changes and server gaps; test-set grading and runs; the experiment record; routes). The full suite passes: 861 tests, 14 skipped. A smoke test in preview opened every new sub-tab without errors.

### 28.37 Barcode lookups fixed, and barcodes from photos — Claude, 2026-10-30 (v3.35)

Grey reported that scanned barcodes did not pull up the product, and asked to use photos for barcodes.

- Cause: `nutrition.barcode_lookup` called Open Food Facts API v3.6. That version answers US 12-digit UPCs with `status: "success_with_warnings"` (it pads them to 13 digits), which the code treated as "not found", and it returns `nutriments` empty, so even found products had no nutrition. A missing product also came back as HTTP 404, which surfaced as an error instead of the "not in the catalog" message.
- Fix: the lookup uses API v2 (`status` 1/0, full nutriments), treats a 404 as a miss, and retries once with or without the leading 0 (12 ↔ 13 digits). Checked live against Diet Coke (049000028911), Doritos (0028400090896) and Nutella (3017620422003); two new tests in `nutrition_test.py`.
- Photos: the live scanner has a **Use a photo** button that opens the photo library. The Scan food page's photo field no longer forces the camera (`capture` removed), so the phone offers both taking a photo and picking one. `readPhoto` also tries five closer crops, so a small barcode in a wider photo is found.
- Tests: 863 Python tests pass (14 skipped), type check clean, node tests pass.

### 28.38 Brain tuning finished, voice trial ready, category zoom fills the screen — Claude, 2026-10-31 (v3.36)

Grey asked to finish brain tuning (multi-brain plan Phase 6) and get the owner/other-speaker voice trial ready, then to make the category zoom's tiles fill the screen and the zoomed core look better.

- **Talk stays loaded:** `TALK_KEEP_ALIVE` is 24 h. Game mode still frees it: an explicit keep-alive now goes through `_game_keep_alive` in `local_llm.chat_payload`, which it previously bypassed.
- **Study unloads after each research job:** `research.agent._study_done` unloads qwen3:14b, reloads Talk (`local_llm.set_residency`, with chat's `num_ctx` so Ollama doesn't reload it again) and warms the topic embedder. Not done in game mode.
- **Topic checks use Talk's model:** `conversation_threads._chat_json` (the "does this continue the subject?" judge) used the old default llama3.1:8b, which loaded 5 GB next to Talk on many turns and cost about 5 s after research. It now uses qwen3.5:4b with chat's context size.
- **Measured (multi-brain plan 8.2):** Talk warm 10 of 10 under 2 s (median 0.64 s, max 0.74 s); cold 3.7 s; first reply after a research job 0.85–1.9 s (was 5–10 s); Seek web 5.0–11.0 s to first text with sources shown as links in chat; Study 18.2 s for 241 words.
- **Voice trial:** Status › Readiness has a Voice trial card. A round ("You" or "Someone else", 10 tries) records each app-mic voice check: accepted or not, the reason and the score; no audio or words. `core/voice_security/voice_trial.py`, `GET/POST /api/voice/trial` (POST desktop-only). The gate, threshold and rejection behavior are unchanged; starting a round clears the 45 s short-reply window, and any short reply still accepted during a round is counted. Pass = at least 5 checked tries each, owner let in 8 of 10 or better, nobody else let in. Results in `data/voice_trial.json`.
- **Category zoom:** the tiles take two-thirds of the screen at full height (first panel spans two rows with 3 or 5 panels, 3 columns with 6) and show up to 8 items. The core zooms to 2.2× instead of 3.4× with a slight depth-of-field blur, a slow drift and a scrim behind the tiles. A failed panel retries once and has a Try again link.
- **Tests:** 872 Python tests pass (14 skipped); type check clean.

### 28.39 Calm view hears the PC voice — Claude, 2026-10-31 (v3.37)

Grey: "mic is listening but calm says mic is off". When ZAE's PC voice service has the microphone, the app's own mic is switched off (so two mics don't answer the same sentence). Calm view only looked at the app mic, so it said "The mic is off", and wake-up calls said to the PC voice never reached it.

- Calm view counts the PC voice as listening.
- `core/voice_listener/calm_state.py`: the app's Calm state is written to `data/ui/calm.json` through `/api/remote/state` (it counts for 30 s, so a closed app can't leave the PC voice deaf). In the PC voice service, a verified turn goes to `calm_turn` first: a wake-up call while calm, or a sleep phrase while not, is written to `data/ui/calm_event.json` and handed to the app through `/api/remote/collect` (`calmEvent`), which wakes or calms as if the app mic had heard it. While calm, other speech is ignored, as with the app mic. Only turns already verified as Grey's voice reach it.
- The phrase lists are copied from `desktop/src/core/calmPhrases.ts`; a test fails if they drift apart.
- Tests: 873 Python tests pass (14 skipped), `calm_state_test` 5; type check and node tests pass. The PC voice service must be restarted to pick up the change.

### 28.40 Darker dashboard cards, the core in its own panel — Claude, 2026-10-31 (v3.38)

Grey asked for darker backgrounds on the panels around the core and the core in a panel of its own. Dashboard cards (`.ov .ov-card`) now lay a dark tint (rgba 4,8,15 at 74%) and a backdrop blur over the look's panel color, so they stay readable whatever the window-opacity setting. The core's stage on the dashboard is a rounded panel with a dark radial background, a faint accent glow behind the sphere, a border and a shadow; it turns transparent during the category zoom and in calm mode. CSS only (`OverviewFrame.css`), checked in the preview at 1920 × 1040.

### 28.41 Wake-up calls and sleep phrases by meaning, not wording — Claude, 2026-10-31 (v3.39)

Grey: "wake up calls and sleep calls will not be word for word but be more flexible. The only thing zae is actually looking for is my authentic voice."

- `calm_state.intent(text, calm)` decides for a sentence that already passed Grey's voice check (app mic or PC voice). The exact phrase lists still match first.
- **While calm:** any sentence wakes ZAE unless Talk (qwen3.5:4b) judges it is plainly said to another person ("hey mom…", "hold on babe"). Her name always wakes her; if Talk can't be asked, his voice is enough.
- **While awake:** a sentence with a rest cue (`SLEEP_CUE`: bed, goodnight, call it a night, that's it for today, background, standby…) goes to Talk, which decides whether he is wrapping up ("I'm heading to bed") or just talking about rest ("how much sleep do I need"). Only a yes starts Calm view. "Go quiet" is left to the existing background command.
- The app mic asks `POST /api/assistant/calm-intent` when Calm view is up or a rest cue is heard; otherwise the turn carries on as before. The PC voice uses the same function in `calm_turn`. Typed sleep phrases still need the listed wording.
- Live check with Talk: 12 of 12 sample sentences decided correctly, about 0.1–0.5 s each. Tests: 874 Python OK (14 skipped); `SLEEP_CUE` and the phrase lists are checked against `calmPhrases.ts`.

### 28.42 One reply when both mics hear Grey — Claude, 2026-10-31 (v3.40)

Grey heard two replies at once. When PC voice keeps rejecting his voice, the app keeps its own mic on too, so both can hear a sentence; `claim_turn` should let only one answer. It missed when (a) the PC was still checking and transcribing a long sentence after the app had waited its 2.5 s, or (b) the two transcribers worded the sentence differently enough to fall under the 0.5 word-overlap mark.

- PC voice reports "hearing" again right before it checks and transcribes a finished sentence (`runtime.feed`), so the app waits for it.
- The app waits up to 6 s (was 2.5 s) while the PC is hearing; word overlap of 0.34 counts as the same sentence (was 0.5).
- The app acts on a wake-up call or sleep phrase once even if both mics report it within 8 s.
- Tests: 876 Python OK (14 skipped), two new `voice_turn_test` cases. Needs a PC voice restart.

The other finding from the same report: since 23:00 UTC the voice check rejected 56 of 91 app-mic sentences and 45 PC-voice sentences as not Grey's voice. The profile was calibrated 2026-10-13 from 5 samples (threshold 0.363). Grey was offered retraining (recommended) or turning off the app-mic voice requirement; awaiting his choice. The threshold is unchanged.

### 28.43 Spoken requests to the PC voice run in the app — Claude, 2026-10-31 (v3.41)

Grey: telling ZAE by voice to log something or do an action in the app didn't do it; he wants it done and shown for confirmation. Cause: the in-app actions (`chat_actions`: food, exercise, weight, workout check-offs, task changes, Workbench/Music, research…) run only in the app's chat stream (`ui_chat_stream.py`). The PC voice service answers through its own brain stream, which has only its small voice action set (tasks, calendar, memory, apps, workspaces), so other requests got a spoken answer and no action.

- While the desktop app is open (it has reported its state in the last 20 s), a verified PC-voice request that is meant for ZAE is handed to the app (`calm_state.hand_to_app` → `data/ui/voice_handoff.json` → `/api/remote/collect` `voiceTurns`) and runs through `submit` exactly like a typed or app-mic request: the action happens, the chat shows what was done, and the reply is spoken when Voice is on. A pending PC "confirm that action" flow still finishes on the PC. With the app closed, the PC voice answers by itself as before.
- Only turns that passed the owner voice check, the attention filter and the one-reply claim are handed over; requests older than 30 s are dropped.
- Tests: 878 Python OK (14 skipped), new runtime and hand-off tests. Needs a PC voice restart.

### 28.44 Requests that really happen, shown and lit up — Claude, 2026-10-31 (v3.42)

Grey: "when i tell her to log something, she says she saved it locally but its not showing in its respected tab." What should happen: say "log something / make a note / open research project / open song…", she answers, the matching tab opens and the item done glows.

- **Why it failed:** several requests never reached an app action, so they fell to the chat brain, which answered as if it had saved them. "Make a note that…", "note to self…", "write down…" weren't recognised (only "add this to my notes"); "open the song X" / "open my research project on X" had no handler; "log …" without a known topic word ("log that I drank two glasses of water") skipped the action check.
- **Now:** `tab_actions.parse_note` accepts natural note wording; `tab_actions.parse_open` + `open_record` find a song, Workbench project, research topic or note by name (exact, starts-with, contains, then shared words) and open its tab; any request starting with log/track/record gets the action check.
- **Show and glow:** the chat stream's `protocol` event carries `focus` (the item's title, or the name/exercise/task from the action). The app opens the tab and `core/glow.ts` finds that item on screen (skipping chat lines; retrying while the tab loads; falling back to the longest word) and gives it a pulsing accent outline for about 5 s, scrolled into view. Applied task and event cards open Tasks or Calendar and glow the new item too.
- **No false claims:** `conversation_rules` now says the chat brain can't save, log, add, open, change or delete anything itself and must never say it did unless the app's report is in the conversation.
- Tests: 880 Python OK (14 skipped), new `SpokenRequestTest`; type check and node tests pass.

### 28.45 Dashboard without blank space — Claude, 2026-10-31 (v3.43)

Grey: "Lets fill in the blank spaces" (the dashboard, with empty rail space under the cards, an empty band at the bottom of the core's panel and a one-line day board).

- **Left rail:** after Today, Fitness and Health come **Coming up** (the rest of the week's events; the calendar fetch is now 7 days) and **From ZAE** (her latest follow-ups from the Assistant inbox).
- **Right rail:** after ZAE's systems, Ask ZAE and Music & news comes **Research & notes** (the two latest web-research jobs and the four latest notes).
- The last card in each rail stretches to the bottom.
- **Day board:** up to 5 rows; when the calendar is light, open tasks fill the rest.
- **Core panel:** the greeting moves up into the bottom of the panel (up to 84 px, less on short screens), not in calm or zoom.
- Checked in the preview at 2000 × 1088; type check clean.

### 28.46 Home in the top bar — Claude, 2026-10-31 (v3.44)

Grey asked for Home out of the ZAENIA menu and into the top bar next to the ZAENIA box. Home is now its own button right of that box (icon over the word, accent underline while the dashboard is showing); the menu no longer lists it. Desktop only; the phone keeps its bottom bar. Checked in the preview.

### 28.47 New name, and Ædaptive: reading how Grey sounds — Claude, 2026-10-31 (v3.45)

Grey renamed the acronym: **ZÆNIA = Zack's Ædaptive Neural Intelligence Assystem**. Ædaptive means emotional adaptability, "able to detect through my voice any emotional or contextual info and knows how to respond to assist me"; Assystem means assistant system.

- **Name:** the header subtitle, the identity reply ("what does ZAENIA stand for?") and the reasoning engine's instructions use the new wording.
- **Ædaptive (`core/personal_memory/voice_tone.py`):** for every spoken turn that passed Grey's voice check (app mic in `ui_voice.transcribe`, PC voice in `runtime.deliver`), four measures are taken from the audio: loudness, median pitch, pitch movement and pace. Each is compared with his own running average (8 turns before anything is judged; turns that stand out move the average less). Clear differences (pace ±20 %, loudness ±4 dB, pitch +1.5 semitones, pitch movement ±30–40 %) become a tentative reading: rushed or under pressure → brief, calm, direct; tired or low → gentle and short, offer to take something off his plate; energized → match the energy; and so on.
- The reading lasts 45 s and reaches the brain as one context paragraph next to "how Zack talks" (`brain_service`), telling it not to name or diagnose his mood unless asked, never to claim feelings itself, and to let his words win.
- Only the four numbers and the turn count are stored (`data/personal_memory/voice_tone.json`); no audio, no words. The last reading is shared between the app server and the PC voice through `data/ui/voice_tone_now.json`.
- Tests: 885 Python OK (14 skipped), `voice_tone_test` 5 (synthetic voices: pitch and loudness found, nothing judged before the baseline, a rushed turn and a tired turn, numbers only). Needs a PC voice restart.

### 28.48 ZÆNIA identity and product charter — Codex

Created `docs/architecture/ZAENIA_Identity_and_Product_Charter.md` as the durable, shared explanation of Zack's intended identity, the meaning of “Ædaptive” and “Assystem,” conversation and privacy rules, the three-engine/four-brain architecture, and the collected product brainstorm. It separates capabilities described as implemented in the current history from roadmap requests and runtime validations still pending. This is a documentation/source-of-truth addition; it does not change model prompts, code behavior, permissions, or the installed app. The runtime implementation remains in the files listed by the charter, with this document serving as the product reference for future Codex and Claude work.
### 28.49 Automation Center, weekly rollup and independent code review — Codex, 2026-11-01 (v3.46)

The Status page now has an **Automations** subtab that consolidates ten existing assistant workflows: project checkpoints, change review, readiness/preflight, phrase routines, event follow-through, background work, quiet notifications, weekly review, health/recovery, and reviewable workflow learning. Each card links to its existing control surface. Status is read from local Core endpoints; the weekly summary is a read-only view over recent task history, deadlines, project next steps, and background jobs. It writes no state.

The isolated build-request pipeline runs a bounded second pass on the local Seek model after checks pass. It redacts common credential patterns and refuses non-loopback Ollama endpoints. Findings are advisory and cannot change, accept, reject, or authorize a patch. If the local reviewer is unavailable, the build remains ready for owner review with that limitation shown. Engine 3 authorization and owner approval remain authoritative.

Files: `desktop/src/components/status/AutomationCenter.tsx`, `desktop/src/App.tsx`, `core/assistant_platform/build_helper.py`, `core/assistant_platform/build_helper_test.py`, `desktop/src/components/tools/BuildRequests.tsx`. Verification: 13 focused Python tests passed; TypeScript and all 17 desktop Node test scripts passed; desktop Vite, browser Vite, and native Tauri builds passed. The native installer saved the previous executable, installed and reopened the new build; executable SHA-256 matches. The local Core was restarted; `/health` reported success with protected routes still requiring authentication, and `/app/` returned HTTP 200. Vite reported the existing ineffective dynamic import and large-chunk warnings.

### 28.50 Weekly meal planner, pantry portions and scheduled check-ins — Codex, 2026-11-01 (v3.47)

Fitness & Health now has a Monday–Sunday meal planner. Each recipe can be tagged for any combination of breakfast, lunch, and dinner. Foods added by barcode or nutrition-label photo can be stored in pantry inventory or assigned to a selected meal. Owner-confirmed serving size and nutrition facts are stored with the pantry item. Weekly assignments reserve servings; the planner calculates remaining stock after consumption and reservations, and the owner can record other consumed amounts by voice (for example, “I used two servings of Greek yogurt”) or from the inventory UI.

The planner schedules a screen-and-speech reminder for each future meal. The reminder asks whether the meal was eaten; only an explicit “I ate this” confirmation logs its nutrition and consumes its pantry servings. “Skip” records the skipped slot without nutrition. Facts must include calories, protein, and fiber before a meal can be logged; recipe nutrition is computed from its saved ingredient sources. Existing personal-memory read/write authorization applies to the two new local record collections, `fitness_inventory` and `fitness_meal_plan`.

Files: `desktop/src/components/personal/MealPlanner.tsx`, `FitnessStudio.tsx`, `PersonalPanels.tsx`, `FitnessStudio.css`, `core/assistant_platform/personal_tools.py`, `chat_actions.py`, `personal_tools_test.py`, `chat_actions_test.py`, and `core/api/platform_routes.py`. The focused Python tests (24 total, including the existing build-helper, meal-plan validation and full chat-action suites), all 17 desktop Node test scripts, TypeScript, desktop/browser Vite production builds, and native Tauri build pass. Gitleaks reports no leaks in the staged change. `desktop/dist-web` was rebuilt and its Fitness bundle returned HTTP 200 with the planner and fact-review UI. The native executable was installed and reopened through the repository updater; its SHA-256 matches the built executable. The existing authenticated/token-mode Core scheduled task was started without changing authentication; `/health` and `/app/` both returned HTTP 200. Commit `4fa18ea` fast-forwarded GitHub `main`; no merge commit or history rewrite was used. Existing Vite warnings remain for the ineffective dynamic import and large JavaScript chunk.

### 28.51 Reminder requests open the Reminders view — Codex, 2026-11-01 (v3.48)

Typed or spoken requests that mention a reminder were incorrectly mapped to Assistant by `windowForText`, despite reminders being stored by the reminder service and shown under Tasks & Calendar. Reminder-related terms now route to Tasks & Calendar, and the app selects its Reminders sub-tab before opening it. A `zae:plan-tab` event also switches an already-mounted PlanStudio window to Reminders. Assistant remains the destination for memory and follow-through review.

Files: `desktop/src/App.tsx`, `desktop/src/components/shell/WindowShell.tsx`, and `desktop/src/components/plan/PlanStudio.tsx`. Verification: TypeScript and desktop/browser Vite production builds passed; a retry completed the native Tauri build in 1m33s. The rebuilt browser bundle is live: `/health` and `/app/` returned HTTP 200, and the served JavaScript contains the reminder route and tab event. The normal Windows install path still has the previous executable because the installed app remained open after graceful close requests; it was not force-terminated. No GitHub promotion was performed.

### 28.52 Natural reminder commands create real reminders — Codex, 2026-11-01 (v3.49)

The reminder parser now accepts direct commands such as “put a reminder on the 8th for GitHub 2FA,” “set a reminder for GitHub 2FA on November 8 at 3 pm,” and “remind me to call the dentist on the 8th of November.” An omitted time defaults to 9:00 am local time; a day-of-month without a month resolves to its next upcoming occurrence. Requests that omit the reminder text or a usable date/time are intercepted before normal model conversation and ask for the missing information. ZÆNIA confirms a reminder only after the authorized reminder store call succeeds, and opens Tasks & Calendar.

Files: `core/assistant_platform/reminders.py`, `core/api/ui_chat_stream.py`, `core/assistant_platform/selfcare_test.py`, and `core/api/assistant_stream_test.py`. Verification: 6 focused reminder/parser/routing tests passed. Existing website output already includes the UI navigation fix; the backend change requires the Core process to load the updated Python module. The native app process remains open and has not been force-terminated.

### 28.53 OneDrive photo references and Study deep analysis — Codex, 2026-11-02 (v3.51)

The Assistant › Documents panel can discover local OneDrive subfolders and let the owner approve a specific folder. The document index now accepts JPG, JPEG, PNG and WebP; the local vision model extracts searchable text from approved photos. Images are not copied to the index, and extracted content is explicitly treated as untrusted reference data. Existing document retrieval already supplies selected-folder excerpts to chat. Fitness & Health can list unchanged indexed photos and read a selected label image locally into the existing owner-review nutrition form, where the user confirms serving values before saving to pantry or a meal. This is intended for package/barcode/nutrition-label photos and other owner-chosen references. OneDrive files must be made available offline before indexing; a barcode UPC can still be scanned live using the existing barcode scanner.

Assistant › Work adds a default-on **Extensive analysis** option. It runs the local Study model (`qwen3:14b`) as a background task, gathers up to eight excerpts from approved local folders when document permissions allow, and requests a structured report covering findings, analysis, counterpoints, assumptions, uncertainty, conclusions and citations. Study output remains analysis only; it cannot grant actions or alter permissions. No selected-folder source means the report labels its conclusions as unverified general knowledge.

Limits: images must be JPG/JPEG/PNG/WebP and at most 8 MiB each for local vision reading; indexing keeps text only. The OneDrive discovery lists immediate subfolders (not the full OneDrive root); the owner should choose a dedicated, small reference folder. The OneDrive path on Grey's PC has not yet been selected or indexed. Python syntax compilation, TypeScript, desktop/browser production builds and the Tauri release build succeeded. Native executable installed and reopened; its SHA-256 matches the build. The existing Core task was restarted after owner approval, with unattended token mode preserved; `/health` and `/app/` returned 200, while the new photo endpoints returned 401 without credentials, confirming their routes are loaded and protected. Runtime tests were not run. Next owner step: approve the desired OneDrive child folder, index it, and review a saved label photo through Fitness & Health.

### 28.54 Mouse side-button page navigation — Codex, 2026-11-02 (v3.50)

The standard mouse Back side button (mouse button 4) returns to the previous ZÆNIA workspace page; Forward (button 5) reopens the next page. Navigation history is in-memory, capped at 100 pages, and resets on app restart. The app captures the mouse press so the desktop webview does not navigate away from ZÆNIA. This covers workspace pages, including opening and focusing desktop windows; sub-tabs within a workspace are not separate history entries. No appearance or authorization behavior changes.

Verification and deployment: TypeScript, desktop/web Vite, and Tauri builds succeeded. Commit `bf4013e` was pushed to the feature branch; the remote `main` branch was not changed. The installed executable hash matches the release build. The existing Core task is running; `/health` and `/app/` returned HTTP 200, and the served bundle contains the handler. Health remains in unattended mode with protected routes authenticated. A local passkey console was left untouched.

### 28.55 Draft: efficient Claude/Codex development and provider independence — Codex, 2026-11-02 (v3.52)

Added `ZAENIA_Claude_Codex_Efficiency_Draft.md` for owner and Claude review. It allocates ordinary implementation and verification to Codex/local tools, reserves Claude for bounded difficult work and independent review, and defines separate runtime-independence and local-maintenance gates. The draft records that `build_helper.choose_tool` can automatically select Claude today and proposes explicit, budgeted dispatch as the first implementation task. Existing local brain paths and the optional OpenAI adapter are recorded as inspected code, not proof that all runtime traffic is already local.

Status: documentation-only proposal. No coding-agent settings, provider credentials, authentication, production processes or app binaries were changed for this draft. It is linked from section 13 without adopting its proposed policies.

### 28.56 Calm-view password return when the microphone is off — Codex, 2026-11-02 (v3.53)

Replaces the hold-to-Wake button with a password form while the microphone is off. Security › Calm password opens a fixed local console for creation, change or reset; the console requires fresh existing owner-passkey authentication and hidden entry of a separate 12–128-character dashboard password. The primary passkey is never sent to the page. Calm-password verification grants no owner session or execution authority. Salted Argon2id hashes and persistent failed-attempt state use the existing protected atomic storage under ignored `data/secure`; five failures trigger a 30-second throttle. Browser password entry requires a secure context.

Before enrollment, Calm view stays disabled with the mic off, keeping the dashboard accessible while the owner defers creating a password. After enrollment, the view's active flag persists on the device; verified wake-up voice or successful password verification returns to the dashboard. Ordinary remote wake/open and mouse-history actions do not dismiss an active Calm view. A session-bound callback rejects stale password responses; keyboard focus stays inside the view. Calm still displays its summary slides: this is a UI return gate, while Windows locking and existing API authorization remain separate controls.

Verification: eight isolated backend tests passed (owner proof, hashing, cancellation, reset, throttling, route dependency registration and no password echo); full ASGI transport stalled in this environment, so these are not live authenticated-HTTP enrollment tests. TypeScript and selected existing Calm/voice/layout/tab/browser regression checks pass. Desktop/web Vite and Tauri release builds passed; the app is installed and reopened with its SHA-256 matching the build. Core reloaded through its existing unattended scheduled task. `/health` and `/app/` return HTTP 200, both new password endpoints return 401 without credentials, and the served bundle contains the new form and no old Hold Wake message. At deployment, owner password enrollment and live password entry were pending. On 2026-11-03 the owner reported password setup complete; this is owner-reported completion, with no additional independent live unlock test recorded.

Publication validation, 2026-11-03: microphone error/blocked states now expose password entry and recovery, and entry accepts the same maximum 128 Unicode code points as enrollment. Nine isolated backend tests include a maximum-length emoji password. The isolated `codex/calm-password-feature` publish branch excludes Claude's narration WIP and unrelated planning drafts; TypeScript, selected UI regression scripts, desktop/browser Vite and native Tauri release builds pass. The source-only staged Gitleaks scan found no leaks. The publication build is retained under ignored `.tmp`; the running app, served website and Core were not replaced by this GitHub task.

### 28.57 Complete Feature Blueprint merged into the roadmap — Codex, 2026-11-03 (v3.54)

At the owner's request, section 29 incorporates the additive requirements from the supplied **ZÆNIA — Complete Feature Blueprint**. Existing capabilities are mapped to their current modules and plan entries rather than scheduled for a second implementation. Additions cover linked decision rationale, optional personal finance, outcome-based feedback, explicit simulation and plugin acceptance contracts, disconnected-device reconciliation, and an integrated definition of completion. Existing three-engine authority, four brain roles, conversation preferences and owner-controlled release procedures are preserved.

Status: documentation integration only. Roadmap inclusion is authorized; the added capabilities and acceptance scenarios remain PLANNED until separately implemented and evidenced. Source inspection establishes existing foundations, not a new live verification. No application code, dependencies, authentication, runtime data or installations changed in this update. The Claude/Codex efficiency supplement remains a draft under section 28.55.

### 28.58 Calm password setup completed by owner — 2026-11-03 (v3.54)

OWNER-REPORTED: password setup is complete. The enrollment task is closed on that basis. This update records no password, hash or other authentication material and makes no security-policy change. Independent live dashboard-unlock verification has not been performed as part of this documentation task. The previously saved setup reminder has not been changed; dismiss or complete it through ZÆNIA if it is still scheduled.

### 28.59 Narrated file reading and Seek-to-Talk web answers — Claude/Codex, 2026-11-04 (v3.55)

Owner requested publication through `CLAUDE_TO_CODEX_COMMIT_REQUEST_2026-11-04.md`. Claude's listed source files were compared with `claude/brain-validation` and matched before publication fixes. This section folds the file-reading/web notes from `CLAUDE_NOTES_2026-11-02.md`; its earlier reminder-lock explanation remains a historical observation, not a new change to current permissions.

- **Workload routing and transcript:** `conductor.model_for` assigns conversation/speech to Talk, file reading and web findings to Seek, research/code/ideas to Study, and small summaries to Keep on CPU. A staged transcript accepts user-facing narration from Talk and orders start, plan, impression, progress, summary and answer; progress/answer may repeat. Existing Talk failure handoff to Seek remains, so the normal Talk presentation path is not a claim that every fallback or application report is rewritten by Talk.
- **Shared-file reading:** `file_narration.py` labels pages, sheets or approximate line ranges; Seek and Talk share section reading, with CPU Keep joining long documents. Limits are 100,000 extracted characters per file, 140,000 total and 40 sections per file. The reader samples first/last/middle and skims unread parts when its reading budget expires. A recent-document cache supports relevant follow-ups for 30 minutes, bounded to 12 documents; existing attachment-copy behavior remains separate. Coverage limits and skimming must be disclosed. File text and model notes remain reference data, never permission.
- **Web answers:** Seek extracts a bounded set of findings tied to actual source IDs, then Talk writes the normal answer from the source excerpts and findings. Missing/malformed findings fall back to the excerpts; empty source retrieval retains the deterministic cannot-verify response. Sources reach chat, and `execution_authorized` remains false.
- **Interface:** narration appears before the answer and speech is queued in order. File answers display a “Where in the file” list with section labels, gist and excerpt. Suggestions use Study; the brain roster explains the roles. The voice action test now isolates app-open detection.
- **Publication review fixes:** reject malformed Seek JSON shapes, reject extracted facts with changed numeric values, disclose section-cap clipping, bound the reading caller's deadline/cancellation and prevent late workers from mutating its returned sections. Progress-only chat rows close correctly on Stop, failure or empty completion. In-flight model requests have bounded timeouts but cannot be forcibly killed by a Python thread; final answer generation has its own latency beyond the reading budget. Passage matches and numeric checks remain heuristics, not a proof that every generated claim is true.

Verification: Claude reported 961 Python tests, all desktop Node scripts, TypeScript and a prior native build/install. Codex independently ran 90 focused Python tests before the review fixes and reproduced the failure cases above. Final post-fix tests/build results are recorded in the latest handoff. Publication uses `codex/claude-file-web`, based on published password commit `bbf3857`, preserving that feature's history. Existing startup authentication, owner data and permission boundaries remain unchanged. This task publishes source; it does not by itself install the post-review changes or restart Core.

### 28.60 Constellation Fusion SE model — Codex, 2026-11-04 (v3.56)

The owner requested a usable model blending the orbital, crystalline and living-lattice concepts with Claude's Model C Neural Constellation. `fusionModel.ts` implements real mesh geometry for Talk, Seek, Study and Keep around the Conductor, with a separate execution gate. `SEFusionCanvas.tsx` adds WebGL rotation, zoom, picking, accessible controls and bounded animation. The existing SE view in Arena and Readiness defaults to Fusion, retaining Claude's original lightweight constellation as an option. This is frontend presentation; the three engines, model routing, authentication and Core authorization remain authoritative.

The portable `desktop/public/models/zaenia-se-fusion.glb` uses ordinary meshes/materials and no external textures. The app uses the procedural builder for live brightness and signals. Its roster activity remains an Ollama keep-alive heuristic, not exact internal telemetry. Geometry is 56 meshes / 51,852 triangles; the lazy viewer caps continuous animation at 30 FPS and suspends it for hidden/offscreen/reduced-motion/background states. A synthetic, API-free development preview and actual capture are included.

Read `SE_FUSION_MODEL_HANDOFF.md` for Claude's source/asset map, API contract, rebuild steps and limitations. TypeScript, all 22 desktop Node scripts, the GLB round-trip and desktop/mobile visual interaction checks pass. Final desktop/browser build and application-install status are in handoff section 20. Changes remain separate on `codex/se-fusion-model`; no merge or new GitHub publication is implied.

### 28.61 Deliberate two-hand controls — Codex, 2026-11-04 (v3.57)

The owner approved the proposed MediaPipe control upgrade. The existing local 1.1.1 runtime and bundled assets now detect two hands. `HandMotionController` extends `handGestures.ts` with stable hand continuity, point/pinch activation, calibrated/smoothed cursor motion, pinch/release hysteresis and bounded two-hand center/scale/twist transforms. `handTargets.ts` limits manipulation to title bars, the Fusion model and an explicit presentation action menu. App uses existing bounded shell updates; the model receives visual transforms only. Pinch no longer closes tabs, and open palm consistently means Stop. Nonconflicting older gestures remain in a separately selected shortcut mode.

The camera HUD adds device/hand selection, sensitivity and comfortable-reach calibration. Tracking loss, target removal, stale/stalled results and view/context changes cancel manipulation. Controls stop when hidden, unfocused, in Calm or during the existing authentication prompts. Hand activity prevents unintended idle transitions without unlocking Calm. Frames stay in RAM, local CPU processing retains one in-flight frame and the existing 30 FPS capture cap, and no execution/authentication privileges or dependencies are added.

Read `MEDIAPIPE_HAND_CONTROLS_HANDOFF.md` and handoff section 21. TypeScript and all 25 desktop Node scripts pass. A real local worker processed a blank image, and synthetic browser replays moved/resized an actual window and turned/scaled the model. Physical hand/camera accuracy and calibration are not yet live-verified. Final native/browser build and install evidence is recorded in the handoff. Branch: `codex/mediapipe-hand-control`; no new GitHub merge/publication is implied.

## 29. Integrated completion roadmap — Complete Feature Blueprint

Source: owner-supplied **ZÆNIA — Complete Feature Blueprint**, incorporated on 2026-11-03. Its twelve systems describe product capabilities served by Engines 1–3, the Conductor and Talk/Seek/Keep/Study. The interfaces, local services and optional cloud adapters retain their existing boundaries. Illustrative external image links are not implementation evidence and are omitted.

### 29.1 Capability coverage and existing foundations

The foundations below were identified in current source or the cited build history. Their presence does not certify each complete user workflow. New work in the last column is PLANNED; previously recorded test results retain their original scope and date.

| Blueprint capability | Existing foundation to extend | Remaining requirement or validation |
|---|---|---|
| 1. Cognitive core | `core/brain/conductor.py`, reasoning/context modules; sections 28.26–28.29 and the Multi-Brain Plan | Validate goal interpretation, evidence selection, resource use and uncertainty across complete workflows; retain explicit choice for optional cloud use. |
| 2. Long-term memory and knowledge | `core/personal_memory/ledger/user_learning.py`, insights, approved document retrieval and operator continuity records | Link decisions to rationale and supporting knowledge; verify correction, forgetting and restart continuity across those links. |
| 3. Goal-based execution | `core/assistant_operator/service.py`, planner and controlled tool catalog | Demonstrate reviewed multistep work, verified effects, cancellation and recovery without duplicate actions. |
| 4. Natural voice and conversation | Conversation continuity, flexible attention/wake intent, voice turn handling and charter sections 2–3 | Complete live owner/other-speaker trials, interruption handling and contextual follow-ups; keep answers free of generic follow-up invitations. |
| 5. Visual and environmental awareness | `core/assistant_operator/screen.py`, opt-in screen watch, photo references; sections 17.2 and 28.53 | Verify selected-window scope, revocation and uncertain visual interpretation in real use; each additional camera/app observation adapter needs an explicit scope. |
| 6. Active learning and patterns | Reviewable insights, memory provenance and existing feedback controls | Measure whether suggestions helped and whether corrections reduce recurring failures, without changing permissions. |
| 7. Security, identity and permissions | Engine 3, existing owner authentication, device scopes, protected paths and audit | Carry authorization/revocation checks through every workflow and adapter; voice or learned confidence never substitutes for required approval. |
| 8. Executive assistant | Calendar, reminders, completion checks, tasks, priorities and proactive suggestions | Coordinate conflicts, dependencies, urgency and owner-set priorities; verify completed occurrences stop generating follow-up. |
| 9. Personal finance and wellness | Fitness & Health, recipes, meal planning and training; sections 25, 28.4 and 28.50 | Add optional private finance tracking and projections with separate data access; connect supported health devices only through reviewed adapters. |
| 10. Multi-device intelligence | Phone remote, operator handoff, CarPlay/watch plans and encrypted profile portability | Define and test disconnected state, synchronization conflicts and reconnect behavior; Raspberry Pi voice hardware remains an optional later client. |
| 11. Diagnostics and development | Health/recovery services, Code Doctor, isolated build requests and local review | Verify recoverable failures and restore; add reviewed integration proposals through the controlled development path. |
| 12. Adaptive personality and interaction | Identity charter, voice-tone hints and existing dynamic workspace/core | Check consistent identity, task-state indicators and response detail under load; treat emotional cues as tentative and preserve the established UI design. |

### 29.2 Additive requirements

**A. Linked knowledge and decision rationale.** Extend the existing owner-reviewable continuity records before introducing another memory store. Connect goals, projects, people, documents, events and decisions using stable references. A decision should carry a concise reason, relevant constraints, considered alternatives, assumptions, evidence/source references, dates and review status. Explain why a record was retrieved. Corrections and forgetting must update or invalidate dependent summaries and links; expired or disputed information must remain clearly labeled. A graph database is an implementation option to evaluate, not a new dependency required by this plan. These records provide context and never authorization.

**B. Optional personal finance workspace.** Plan manual entry and explicitly approved imports for balances, budgets, spending categories and debt-repayment projections. Separate observed amounts from estimates and record source/date/currency. Keep financial access separately scoped and opt-in. Banking connections, transfers and payments are not established by this roadmap; any future transaction capability needs its own reviewed adapter and explicit action approval. Wellness continues through the existing Fitness & Health modules, with estimates and device limitations visible.

**C. Outcome-based self-evaluation.** Evaluate requested outcomes using saved receipts, observable state, tests and owner feedback. Track useful/dismissed suggestions, corrections, repeat failures, completion limits and recovery success alongside latency and resource use. Compare changes against fixed regression tasks. A model's self-rating is advisory and cannot certify success, promote its own changes or alter security rules. Use relevant supported feedback rather than unrestricted activity collection.

**D. Simulation and new tools/plugins.** Extend Engine 3's existing preview and dry-run requirement with an explicit contract: show proposed effects and permission requirements, use isolated fixtures/copies where supported, and label predicted effects separately from observed results. A passed simulation does not guarantee a live outcome; unsupported previews must say so. Generated tools remain proposals until their versioned schemas, declared file/network access, dependencies and tests are reviewed. Activation goes through the existing controlled development/release path and Engine 3 tool registration, with failure isolation, audit and rollback where supported. Neither generated code nor a plugin manifest can grant itself capabilities.

**E. Disconnected-device continuity.** Extend existing encrypted sync and handoff goals with versioned records, source device, freshness indicators, reviewable conflicts and deletion/revocation behavior. Define which data and actions each client supports offline. Reconnection must recheck permissions and reconcile state without replaying a side effect twice; ambiguous results require inspection. Core remains authoritative for canonical state and policy. Pairing, a device label or an existing handoff record alone does not establish secure synchronization or local inference on that device. Validate each iPhone, CarPlay, watch or optional Raspberry Pi adapter on its actual supported platform.

### 29.3 Definition of complete and acceptance scenarios

Completion means ZÆNIA reliably **understands a goal, retrieves relevant knowledge, plans supported work, obtains the required authorization, performs the actions, verifies their effects, preserves justified context and continues core operation locally**. Optional finance, additional devices and other later extensions do not block completion of the agreed core scope. Existing local models remain replaceable dependencies; custom foundation-model training is not a prerequisite.

Use synthetic fixtures first and owner-assisted live trials where needed. No scenario is marked passed by this documentation update. For each result, record the build/commit, model versions, setup, expected effects, actual receipt/state, timing, limitation and test type under section 12.

| Scenario | Required evidence |
|---|---|
| Natural reminder and calendar follow-through | Interpret date/time/timezone correctly, save the intended record once, show it in the correct view and verify the requested delivery. A completed calendar occurrence stops its completion follow-up while later recurrences stay independent. |
| Food reference to weekly meal | Read an approved label/photo or recipe, resolve material serving ambiguities, distribute portions correctly and preserve inventory totals. A scheduled check-in logs intake only after explicit eaten confirmation; retries do not double-log. |
| Project goal to saved result | Retrieve permitted evidence, draft supported steps, bind review to the exact plan, perform authorized work and verify the saved artifact. Clearly separate successful file creation from any model-written claims that remain unverified. |
| Continuity after restart or device handoff | Resume the same goal with current constraints, decision reasons, source references and next step. Keep temporary chat context, durable memory and action receipts distinct; do not repeat an already completed action. |
| Cancellation, failure or revoked access | Stop or suspend appropriately; preserve useful progress; label ambiguous side effects for review. Recheck authorization before resuming and show partial completion honestly. |
| Local independence and recovery | In a reversible isolated setup, make cloud-provider credentials unavailable and verify no provider calls/fallback during local startup, conversation, approved-document use and supported tasks. Separately test internet loss, unavailable sources and recovery from a known-good backup without overwriting the live profile. |

Core acceptance also includes the outstanding live voice trial, source fidelity, foreground/background priority and the existing Multi-Brain Plan latency/resource scorecard. Distinguish unit tests, integration tests and owner/device trials; preserve failed or unmeasured results. “No internet” does not imply access to fresh web facts or remote devices. Runtime independence and local development independence remain separate gates as described in the efficiency draft; its usage allocations are still proposals.

### 29.4 Development order within the existing phases

1. **Foundation — phases 0–1:** update capability evidence from actual code, finish outstanding security/voice checks, establish reproducible local/offline and recovery results. Preserve the known-good baseline.
2. **Interaction — phase 2:** verify contextual voice/text turns, interruption, bounded observation and accurate visual task state through the existing UI.
3. **Execution — phase 4:** validate the reminder, meal and project scenarios end to end, including duplicate prevention, failure and exact-plan approval.
4. **Learning — phase 3:** extend decision links and usefulness feedback using existing stores; prove correction, expiry, forgetting and permission non-escalation.
5. **Expansion — phase 5:** add optional finance, approved integrations and disconnected-device reconciliation after their core prerequisites pass.
6. **Maturity — across all phases:** repeat outcome/performance checks when changes warrant them, document dependencies and prove a separate restore before SSD/OS packaging.

These are delivery priorities mapped onto section 11, not a second phase-numbering scheme. Start with a bounded capability/evidence update and one complete project workflow using existing modules. Keep optional extensions separate from the core completion gate. Architectural implementation choices, dependency changes and production promotion retain the existing review and authorization requirements.

## 30. October 2027 objective — ZÆNIA develops and upgrades her own application

**Owner direction, 2026-11-04:** by October next year, ZÆNIA should be able to perform the development work Grey currently carries out with Claude Code and Codex, with high success and efficient use of resources. The owner has also given this direction to Claude. The target month is **October 2027**. Working scheduling assumption: prepare a release candidate by **2027-09-30** so it is available at the start of October; complete owner acceptance during October. These are delivery targets, not a guarantee of capability or authorization to release.

This section is the canonical dated development roadmap. It extends sections 2, 11–13, 29.2C/D and 29.3, plus the local-maintenance milestones in `ZAENIA_Claude_Codex_Efficiency_Draft.md`. Existing runtime/development-provider independence gates remain separate. No additional engine, replacement memory store or unrestricted self-modifying controller is approved by this plan.

### 30.1 Required end-to-end behavior

An ordinary request such as “add weekly meal-planning summaries” or “fix this reminder opening the wrong page” should become a traceable development task:

1. Understand the intended outcome and existing behavior; ask only for missing details that materially change the result. Produce editable acceptance cases, constraints and scope.
2. Inspect the current repository, relevant call paths, schemas, callers, tests and architecture decisions. Identify existing equivalents and dependencies before proposing new modules.
3. Explain a bounded plan and which local model/tool will perform each stage. Keep foreground conversation responsive and honor owner-set background priorities.
4. Work in an isolated, sanitized development environment based on a recorded commit. Write the patch, add meaningful checks, run them and diagnose failures within a fixed repair budget.
5. Obtain an independent review, resolve supported findings and demonstrate the requested UI/API behavior. Separate observed results from model judgments and unverified assumptions.
6. Present the exact reviewed diff, test results, limitations, resource use, desktop/web artifacts and recovery procedure. Owner approval remains necessary before integration or deployment.
7. After approval, an authorized deterministic release path checks the tested version, builds/installs the approved outputs, verifies actual effects and records a release receipt. Failure leads to a controlled stop or tested recovery, with honest status.
8. Retain justified, sanitized engineering lessons and a resumable task packet. Later requests should benefit from those lessons without acquiring permissions through learning.

By the target date, the agreed local maintenance suite must work with Claude/Codex closed and their provider credentials unavailable in a reversible test environment. Optional online research and external services retain their own access requirements. Owner approval, material clarification and normal priority choices remain part of the workflow; owner-written repairs are recorded as technical assistance.

Initial supported scope: routine and medium ZÆNIA frontend/backend features, bug fixes, integration changes, tests, documentation and release preparation. Large architectural migrations remain separately evaluated work. Security-policy, authentication, secrets and protected-path changes retain their existing dedicated review/approval paths. Broad project ability must be demonstrated by new task cohorts before being claimed.

### 30.2 Verified foundations and gaps to close

The following observations come from source inspection on 2026-11-04, not a new live coding or deployment trial. Reinspect the actual branch before implementation.

| Foundation already present | Current limitation / required improvement |
|---|---|
| `core/assistant_platform/build_helper.py::write_brief`, `file_hints` | Briefs and up to eight filename-matched files exist. Add bounded symbol/call/dependency/test retrieval, source references and index invalidation. Acceptance prose needs executable behavior checks. |
| `make_copy`, `run_tool`, `run_checks`, `BuildRequests.process` | Worktree-based coding, Claude/Aider adapters, checks and bounded repair retries exist. Worktrees/filtered environment/dependency links share Windows-user permissions; establish reviewed process, filesystem and network boundaries with sanitized fixtures. |
| `choose_tool` | Medium/large tasks can automatically prefer Claude. Add explicit provider selection and a validated local default; no hidden paid/cloud fallback. No Codex/OpenCode/native ZAE development adapter is established by this inspection. Extend the existing service rather than duplicate it. |
| `review_change_locally` | Seek performs a bounded, redacted loopback review. Review is advisory and an unavailable review can still leave a change ready. Define review completion/findings and risk-specific gates; self-approval is never a release condition. |
| `BuildRequests.approve`, `undo`, `core/api/build_routes.py` | Owner-controlled integration and code Undo exist. Revalidate tested base, dirty state, dependencies, patch and resulting tree before promotion. Approval must bind to exact hashes; code reversion does not establish safe reversal of a data migration. |
| `rebuild_app`, `desktop/src/components/tools/BuildRequests.tsx`, `scripts/zae.ps1`, native updater | Build/install paths exist. Track building, installing, verified, failed and recovered states through final health/hash receipts; an approved commit or detached rebuild process is not a verified release. |
| `core/brain/conductor.py`, existing job/continuity/memory services | Code/research routes to Study and the architecture already separates reasoning from authority. Add development task packets, checkpoints, cancellation, evidence retrieval and outcome learning using these existing boundaries. |
| `core/assistant_platform/build_ideas.py::NightlyIdeas`, Core startup registration | Evidence-based improvement suggestions and a nightly service already exist in source. Evaluate and strengthen them rather than rebuilding the earlier option-3 proposal. Their current live quality/scheduling is not reverified by this inspection; suggestions never authorize coding or promotion. |
| `.github/workflows/zaenia-ci.yml` | Current workflow checks Python syntax, builds the frontend and scans with Gitleaks; it has no unit-test job. Establish sanitized clean-checkout fixtures and an automated unit-test gate. Historical assessment test/error totals are not current clean-clone evidence. |
| `scripts/model_bench/`, Claude notes “Coding-model experiment” | A 38-task small-function benchmark and Claude-reported runs exist. This is a useful candidate-model pilot, not an independently reproduced real-repository upgrade success rate. It does not justify a model switch or frontier-level coding claim. |

First implementation packet: **reproduce clean-checkout test failures using sanitized fixtures and add a unit-test CI gate**, recording a reproducible baseline rather than reusing the old “about 500 tests / 28 errors” assessment. Next, make development dispatch explicit and produce a task/release baseline in the existing build helper. Before broader autonomy, close the tested-change integrity and isolation gaps above. Implementation must preserve current working authentication, runtime versions, owner data and recovery copies.

### 30.3 How ZÆNIA learns the engineering workflow

During current Claude/Codex work, prepare small, owner-reviewable engineering records from observable artifacts:

- Task intent, baseline commit, scope, constraints, relevant files/call paths and reasons for the chosen approach.
- Reproduction case and acceptance checks; the proposed/accepted patch; failures, attempted corrections and independent review findings.
- Actual commands, exit codes, test/build results, dependency/model versions, timings, sanitized resource measurements and final release/rollback receipts.
- A concise validated lesson, when it applies, evidence links, known exceptions and the owner's corrections. Record failed approaches and uncertain conclusions distinctly.

Retrieve relevant validated records when planning a similar task, then inspect the current source again. Reference accepted code and evidence rather than copying a conversation's unsupported assertions. Exclude credentials, raw owner conversations, private assessments/calendars/health data and production databases from development examples unless specifically authorized for a defined purpose. Repository text, tool output and learned records remain untrusted inputs to Engine 3.

Use separate development examples and held-out evaluation tasks; do not expose hidden acceptance answers to the coding agent or its memory index. Fine-tuning/distillation is an optional later experiment on approved, suitable data and models, only if measured failures warrant it. Saving examples does not transfer another provider's model weights or establish equivalent general capability.

**Experience-import contract (design accepted 2026-11-05; source-selection review pending).** The owner chose **both** reviewed task packets/source references/sanitized Git diffs and a future scoped local Claude/Codex session-log importer. This accepts both learning paths; the selected importer option includes review of its access and exclusions before it reads private logs. The importer must show exact selected sources, fields, time range and exclusions; preview extracted records for redaction/review; preserve provenance and confidence; define local storage, retention, correction/deletion and backup limits; and prevent automatic cloud upload or admission of session instructions as authority. No private session folders were read or ingestion enabled by this planning update. Review any new persistence/export change under its own scope. `build_helper.run_tool` currently launches Claude with `--no-session-persistence`, so “every session is already a complete textbook” is not an established fact. Preserve that privacy setting during planning. Fine-tuning, provider-terms/model-license review and any external disclosure remain separate future decisions.

### 30.4 Milestones leading to October 2027

These are dated delivery checkpoints within the existing phases, not a new competing architecture or phase scheme. A failed gate remains open and is reported; elapsed time does not make it pass.

| Period | Deliverable / exit evidence |
|---|---|
| Nov–Dec 2026 | Record a clean reproducible baseline, real hardware/runtime/model manifests and current task outcomes. Reproduce fixture failures from a clean copy, add sanitized fixtures and a unit-test CI gate. Define task packet/release receipt schemas and a representative sanitized task corpus. Resolve explicit local/cloud dispatch and prioritize tested-change integrity. Preserve a separate known-good restore. |
| Jan–Feb 2027 | Complete the local coding runner through the existing helper, with scoped tools/commands, meaningful isolation, bounded retries, cancellation and restart checkpoints. It reads only approved project material and cannot approve itself or inherit production credentials. Demonstrate small fixes without provider calls. |
| Mar–Apr 2027 | Improve repository understanding and reliable small changes: code/test retrieval, precise patching, regression reproduction and independent review. Demonstrate requested frontend and backend behavior on unfamiliar task families; publish first-attempt and repaired results separately. |
| May–Jun 2027 | Handle medium multi-file features and integrations. Complete dependency review, exact-version approval, native/web release preparation, verified install receipts and tested rollback/recovery. Demonstrate failures such as stale branches, interrupted builds and unavailable models. |
| Jul–Aug 2027 | Tune the local planner/coder/reviewer choices and context budgets on identical workloads. Test difficult edge cases, interruptions, revoked access and compromised/untrusted task inputs. Rehearse the maintenance suite with cloud development tools/credentials unavailable and restore in a separate environment. |
| September 2027 | Run a 30-day supervised normal-use trial, resolve release-blocking failures and freeze the release candidate by September 30. Include routine real requests, local operation, restart/resume, missing dependencies and recovery evidence. |
| October 2027 | Run the frozen held-out acceptance suite, review measured reliability/resource use and obtain owner acceptance of the supported scope. Verify provider-independent maintenance and recovery before deciding on disconnection or SSD/OS packaging. If gates fail, retain the last known-good release and name the unresolved gaps. |

### 30.5 Acceptance scorecard — proposed targets, not achieved results

Use at least **100 distinct held-out repository-change task families**, with routine/medium categories and task-type quotas fixed before evaluation (initial allocation: 60 routine, 40 medium). Cover Python/backend, TypeScript/UI, integrations and regressions. Add a separate safety/fault/recovery suite and exploratory large changes. Repeated runs of one task are not independent tasks. Keep tuning/examples separate; contaminated tasks need replacement before a new acceptance run.

Initial numerical goals below are planning targets for owner review. Establish actual baselines first and record any target revision before the evaluated run, with its reason. Do not change denominators or success definitions after seeing results.

| Measure | Proposed acceptance target / definition |
|---|---|
| Routine changes | At least 95% technically complete within an initial attempt plus at most two repair attempts; first-attempt target at least 80%. Completion requires the requested behavior, relevant checks, resolved blocking review findings and a reviewable release package. |
| Medium multi-file changes | At least 85% technically complete within the same repair budget. Report first-attempt performance separately; do not extrapolate routine scores to medium/large work. |
| Release integrity | Every accepted release has an exact baseline/patch/artifact receipt, required checks and explicit owner approval before effects. All required authorization/data-integrity tests must pass, with no observed critical secret exposure or unauthorized action in the acceptance suite. |
| Escaped regressions | Zero unresolved critical regressions during the 30-day trial. Record all other escaped regressions, severity, affected releases, repair time and owner rework; agree the noncritical release threshold before the trial. |
| Independence | The supported maintenance suite completes without required Claude/Codex processes, provider calls or hidden fallback in the isolated independence trial. Loss of an optional online source is reported honestly. |
| Recovery | Exercise each declared rollback class in a separate environment. Native/web artifacts, source/dependency versions and state-compatibility checks must be recoverable. Non-reversible migrations require an approved backup/restore plan; Undo is not assumed sufficient. |
| Efficiency | Compare identical task families on the measured workstation: median/p95 completion time, CPU/GPU/RAM/VRAM, model calls/tokens, repair count, peak disk and observed energy where available, **per accepted task**. Set hardware-specific numerical budgets from the baseline; maintain reliability and security floors while optimizing. |

For each cohort report raw passed/attempted counts and task-level uncertainty, first-attempt success, success after each repair, human-assisted results, unresolved failures, refusals/unsupported tasks, timeouts, cancellations and escaped regressions. A critical review or environment failure must remain visible. Correct refusal is scored in the safety suite and must not inflate coding success. An in-scope task remains in its denominator after a failure; unexplained timeouts/abandonment count as unsuccessful. Owner approval alone is not technical assistance; owner/Claude/Codex corrective coding or hidden-test hints are.

The 95% routine and 85% medium numerators include only technically complete outcomes without that corrective assistance. Assisted completions are reported separately while the assigned tasks remain in their original cohort denominators. Owner approval and material requirements clarification are allowed. Efficiency per accepted task uses total cohort cost, including unsuccessful/abandoned work and every repair attempt, divided by accepted outcomes; report unsuccessful-task timing separately alongside successful-task median/p95 so wasted work remains visible.

“Technically complete” is distinct from “approved and deployed”: report both. Owner-declined or deferred releases retain their technical result and never count as installed. Existing tests alone, a plausible diff, model agreement or an assistant's success statement cannot establish that the requested behavior works. Independent review combines deterministic checks with a separate review context/model where useful; related local models may share failure modes.

#### ZAE-Bench protocol (planned)

Use **ZAE-Bench** as the name of the repository-task evaluation program, extending `scripts/model_bench/` where suitable. The existing small-function benchmark remains a separate pilot cohort. There is no claim that a complete repository-upgrade harness or new CI job has been implemented by this roadmap.

- Curate historical Claude/Codex/ZÆNIA changes into development replays using the pre-change baseline, a sanitized requirement and verified behavioral checks. Select coherent, reproducible task families; exclude mixed changes, merges, no-op/tool-junk commits, secrets/private data and cases whose intended behavior cannot be established. Do not automatically turn every commit into an example.
- Aim for an initial approximately 50 usable **development** task families after inventory, growing toward approximately 150 combined development/evaluation families by October 2027. Reserve at least the 100 held-out families specified above. Inventory may show more examples are required; these counts are collection targets, not existing assets.
- A task's behavior specification is the oracle. Validate that the known-bad baseline fails the relevant check and a reviewed reference solution passes. Post-change tests alone are insufficient; include edge cases and regression expectations, accept alternative correct patches, and keep evaluator fixtures/tests outside the coder's writable scope.
- Separate weekly development replay/tuning from the final frozen holdout. A task or related task family admitted into experience memory or used for tuning cannot remain a hidden final examination. Block access to post-task diffs, future Git objects/refs/branches, session examples and hidden evaluator answers in the evaluated coding environment. A shared worktree alone does not provide that isolation. Version and replace contaminated cases before the next scored acceptance run.
- Record baseline/patch/reference/evaluator/dependency/model versions, environment, task size fixed before execution, allowed tools/provider, initial result and each repair result. Preserve raw counts and task-level uncertainty. An owner approval is a separate receipt; it must not redefine which technical attempt was first.
- Report local unassisted, hybrid/cloud-assisted, owner-assisted, technically complete, approved and verified-deployed results separately. Cloud fallback after two local failures remains a cloud-assisted result, even if it eventually passes. It cannot count toward local-independent coding success.
- Weekly paired checks compare the same task families and conditions against the retained baseline. Require critical safety gates and report cohort-specific quality/resource changes and uncertainty. “Overall score did not drop” alone must not hide a safety failure, a weak task type or a large efficiency regression; predeclare release thresholds and do not promote on noisy aggregate scores alone.
- Also track live approval without redo, seven-day code-Undo/rollback rates and root causes, cloud-task share/spend and routine completion times. Owner-declined scope/style and deferred decisions are distinct from technical defects. A seven-day observation window must mature before its release contributes a final Undo rate. Measure cloud share over all assigned in-scope task families, including failed/fallback attempts, and include all cohort costs in efficiency.

### 30.6 Efficiency strategy and model roles

Keep the current three engines and four brain roles. Talk explains progress and results; Seek retrieves relevant code/docs/evidence; Study plans or implements coding work using the best **measured** local candidate; Keep maintains small checkpoints/summaries when resources permit. The Conductor schedules work, preserves foreground/owner priorities and enforces context/time budgets; Engine 3 retains execution authority. Planner, writer, tester and reviewer are development task roles, not automatically four additional resident models.

Use deterministic search, parsers, type checking, formatters and test runners for work they can verify directly. Retrieve bounded relevant context with provenance and invalidate caches when source/dependencies change. Start with focused checks during repair, then required broader/security/integration checks before release. Avoid repeated identical retries; preserve an evidence checkpoint when the repair budget is exhausted. Cancel outdated work and retain owner-prioritized background work through the existing job system.

Compare local model candidates on actual repository changes before switching the code worker. Load models within measured RAM/VRAM headroom and pause/yield background work as necessary. Quantization, specialized coder models, caching and later training are experiments with quality/resource tradeoffs. No model size, new GPU, subscription or paid API purchase is implied by this roadmap. Reassess capabilities and hardware needs at the dated checkpoints using evidence.

Claude and Codex remain development teachers/reviewers during the transition, assigned bounded work according to the efficiency draft. Their contribution produces reviewable artifacts and checks; ZÆNIA's own unfamiliar-task performance decides when each workflow is independent. Owner-approved production integration, protected-code review, secret handling and spending decisions remain in force after October 2027.

Coding is a scheduled background development **job** through the Conductor/existing job services; it is not assigned to the Keep model merely because it runs in the background. Study or a separately benchmarked coding candidate performs the heavy work; Keep supplies small summaries/checkpoints. Pause/yield for foreground conversation and gaming according to the existing priority policy, preserving background work the owner explicitly marks as priority. Phone/voice/chat requests retain authenticated origin and existing start permissions. Phone requests/review never substitute for PC release approval, and nightly ideas do not start coding tasks by themselves.

### 30.7 Reconciliation of the supplied “Self-Upgrading Coder” draft

The owner supplied Claude's draft labeled “Nov 5, 2026.” It was incorporated/source-inspected on **2026-11-04**, using the owner's client date at that time; the follow-up owner choices below were confirmed on **2026-11-05**. Its disciplined read/search/plan/precise-edit/test/review/handoff loop, experience retrieval, named benchmark and clean-checkout/CI priority are adopted as planned requirements above. Small precise patches are preferred; an intentional whole-file replacement is not categorically forbidden when justified and reviewed.

Correct stale starting-state claims: the coding helper, nightly ideas and four-brain Conductor have implementations in current source; implementation is distinct from complete live validation. Configured roles are Talk `qwen3.5:4b`, Seek `qwen3.5:9b`, Study `qwen3:14b` and Keep `qwen3:1.7b`. Latest Claude notes report testing `qwen2.5-coder:14b` without replacing Study. Actual installed models, hardware availability and clean-checkout test totals require fresh measurement; do not treat old proposal lists or historical errors as today's inventory. The missing unit-test CI gate is confirmed in the inspected workflow. No source, model or live-system change is made by this reconciliation.

The assertion that a 16 GB local model will or will not match a future Claude/Codex system is not an established result. Measured memory headroom and task outcomes determine supported scope and routing. A sanitized copy without `data/` or `.env` is useful, but cannot by itself stop an unrestricted Windows-user subprocess from reading other private files or disclosing sensitive source/history. Close the actual isolation/disclosure gaps before increasing tool autonomy.

Keep alternative metrics and authority decisions explicit:

| Item from supplied draft | Reconciled status |
|---|---|
| 85% small / 70% medium / 60% large on the first approved try, plus ten points after repairs | Alternative first-attempt/hybrid planning targets, not measured results or a replacement for section 30.5's 95% routine / 85% medium within two repairs. Define first technical attempt separately from approval; large hybrid work remains a separate exploratory cohort. Resolve final numerical targets before a scored release run. |
| Routine work under five minutes; cloud share under 30%; approval without redo at least 80%; regressions/Undo under 5% | Proposed operational targets awaiting workload/hardware baselines and agreed denominators. They do not relax zero unauthorized effects, critical regression gates or independent technical acceptance. Report median/p95, failed-attempt costs and mature observation windows. |
| Local first, required cloud for larger October work | **Owner selected 2026-11-05: local independence for supported tasks; optional cloud for larger work.** The supported-task acceptance suite must work without required Claude/Codex calls. Larger-work cloud help is an optional path under existing task/disclosure/spending permissions and is scored separately; a cloud-written patch does not count as local coding independence. |
| Read Claude/Codex session folders or turn on persistence | **Owner selected 2026-11-05: both reviewed engineering records and a future scoped local session-log importer.** Its access/exclusion review remains part of the selected importer design before private logs are read. This does not enable ingestion, change session persistence, authorize unrelated folders, approve fine-tuning or permit cloud upload. No private logs were inspected during this planning update. |
| Monthly cloud budget | No new paid usage is authorized by the supplied draft. Record an owner-selected cap and billing mode before enabling paid dispatch; exhausted/unavailable capacity must checkpoint rather than silently switch providers or spending paths. |
| A 24–32 GB GPU upgrade | A possible later option, not a purchase recommendation or approved change. Decide after measured task-quality, latency and memory constraints; preserve the free-first plan meanwhile. |

The owner answered both design choices on **2026-11-05**: local independence with optional cloud for larger work, and both learning paths with the scoped importer's access/exclusion review retained. Budget, hardware, exact import-source scope and any additional data disclosure remain separate decisions. Section 30 remains the shared source of truth for Claude/Codex rather than creating a second competing phase plan. These accepted design choices do not mark coding independence or the importer as implemented or verified.

## 31. Stream Studio — Twitch and YouTube automation

**Owner request, 2026-11-06:** use ZÆNIA for Twitch and YouTube as a replacement for Streamer.bot. Detailed scope, official API references, architecture, migration and acceptance gates are in [ZAENIA_Stream_Studio_Plan.md](ZAENIA_Stream_Studio_Plan.md). Status: **proposed, not implemented**. This request is for a plan; it does not enable account connections, moderation, platform writes or deployment.

Read-only source inspection found existing Conductor, background jobs, game-mode/model coordination, action-history/approval patterns, owner-authenticated controls, speech queues and private notifications. No Twitch, YouTube Live Chat, OBS WebSocket or Streamer.bot adapter was found in the searched application code/docs. Music platform records currently describe disconnected project/release tracking and do not establish streaming integration. These are source observations, not live verification.

### 31.1 Architecture and interface

Add a proposed **Stream Studio** workspace under **Create**, preserving the existing appearance. It provides combined/platform chat, deterministic command/action editing, alerts/overlays, allowlisted OBS controls, moderation review, connections and measured session reports. OBS continues capture/encoding/transmission; simultaneous video distribution and account eligibility are separate prerequisites.

Use platform adapters → normalized event inbox/state → deterministic rule/role checks → bounded action queues → platform/OBS/public-output adapters → effect receipts/recovery. Reuse the three engines and current four-brain Conductor. CPU-based commands/alerts must work with all models unavailable; optional local AI drafts only within approved public context. Keep Study/development work off-air by default, reconcile existing game mode, honor owner priorities and measure game/OBS resource impact.

Viewer input is untrusted and cannot access owner tools, memory, calendar, health, files or private chat routes, sessions, retrieval namespaces or caches. Public clients never receive owner API credentials. Broadcast TTS/alerts require their own audio route and a verified stream/recording isolation test; capturing a shared assistant process or broad desktop audio can leak private speech. Provide an independent OBS-native public-source mute fallback. Preserve owner authentication and Calm/password boundaries. Learning cannot authorize stream actions or alter security policy.

### 31.2 Platform and migration constraints

Twitch uses installed-client OAuth/EventSub WebSocket plus supported chat/moderation endpoints with feature-specific scopes. Handle duplicates, revocation, reconnect gaps and delivered-action results. Rewards created through another application may require reviewed recreation/mapping before ZAE can manage them. YouTube uses `liveChatMessages.streamList`, continuation tokens and a rate/quota-aware fallback; account writes require OAuth. Preserve membership/subscriber distinctions, initial-history handling and gift-combo update semantics. Do not promise complete per-viewer likes/watch time or identical native rewards across platforms. Recheck official API capabilities during implementation.

Inventory the owner's required Streamer.bot workflows before implementation. Preserve and restore-test the known-good setup; import only reviewed disabled drafts and manually map custom scripts/plugins. Replay sanitized fixtures, run read-only shadow mode with all effects suppressed and separate test counters/ledgers, rehearse public/private output separation, then transfer one workflow at a time with one executor. Retire Streamer.bot after required parity, at least three successful full sessions and a recovery/rollback trial. Never present a temporary bridge as a completed independent replacement.

Combined chat is owner-only. Review current simulcast terms and the owner's applicable agreement before enabling any public cross-platform activity or destination-promoting commands. Shared OBS audio/video reaches every configured destination; public projections need explicit destination policy, while private combined chat/moderation panels remain excluded from capture.

### 31.3 Delivery order and evidence

1. Scope, test baseline and known-good backup/restore; review account identities, public context and permissions.
2. Local deterministic rules, bounded queues, synthetic replay, read-only OBS health, UI preview and emergency public-output stop.
3. Twitch read-only pilot, then specifically enabled commands/alerts/OBS actions after audio and authorization checks.
4. YouTube live chat/events, quota reporting, combined chat and migration parity.
5. Reviewed moderation/reward management, owner voice/phone controls, then optional public AI and efficiency profiles.
6. Workflow cutover, measured live sessions and documented rollback/release receipts.

Evidence must cover duplicate/update/history handling, queue expiry, token/quota failures, restart/reconnect, ambiguous external results, viewer injection, private audio/credential isolation and 10× measured normal event load. Report source/unit/replay/integration/live status separately. Native desktop and `desktop/dist-web` builds plus owner-authorized install/served-site verification apply to implementation releases; this documentation update needs no app build. Section 30's October 2027 coder objective and clean-checkout/CI priorities remain intact. No installation, new dependency, subscription, account change, production action, commit, merge or push is performed by recording this plan.

## 32. Publication of accumulated assistant updates — 2026-11-07

**Owner request:** commit and publish remaining local work to GitHub. Publication is prepared on `codex/pending-updates-2026-11-07` in `.tmp/pending-updates-publish-20261107`, based on current `origin/main` at `ccc3b93`. Password, narrated-file and MediaPipe/Fusion changes are already in that main history; preserve them rather than replaying older local files over them. This publication request does not activate Stream Studio or the October coding roadmap, and does not request a live Core restart or installed-app replacement.

### 32.1 Included changes and review corrections

- Publish accumulated Brief-by-phrase controls, phone access, read-only SecurityModel/group rendering, SE terminology, configurable hand shortcuts/taught poses/snap detection, tool-artifact filtering and prototype local evaluation source. Existing authentication, owner proofs and Calm guards remain in force.
- Explicit repeated Brief requests generate a fresh briefing; the existing in-flight guard prevents duplicate requests. Pass the phone condition explicitly so the phone retains its button while the desktop uses requests by words.
- Open-palm Stop takes priority over taught/custom shortcuts, including two-hand shortcut mode and ordinary action cooldowns. Reset clears taught-pose timing, preventing tracking interruptions from resuming a stale partial hold. A simultaneous Stop suppresses the custom action.
- Preserve the already-published Constellation/Fusion selector and synthetic model-practice target. Older local copies that removed those shipped integrations were reviewed and corrected before publication.
- Generated-code benchmarks are disabled by default and require explicit `--allow-unsafe-local-execution` throughout the Python/TypeScript paths. Python `-I`, timeouts and Node `vm` are not OS isolation. Correct the documentation; reference-only checks use fixed trusted repository fixtures. Gate regressions mock candidate execution and do not run models, generated candidates or owner records.
- Include the October 2027 roadmap decisions, efficiency draft, Stream Studio proposal and Claude/Codex handoffs with their planned/implemented distinctions intact. No new subscriptions, dependencies, platform credentials or raw session-log access are authorized.

### 32.2 Publication privacy and evidence

An unpublished local commit contains coding-tool history and binary caches. The clean publication uses reviewed source changes on current main and does not inherit that commit or publish its private artifacts. Do not push the older shared branch wholesale. Do not rewrite existing remote history; existing tool-artifact filtering also does not claim to sanitize historical commits.

Completed checks: 112 focused backend tests; 9 generated-execution-gate tests; all 28 desktop Node test scripts; TypeScript; 427 Python source files parsed with Python 3.11 grammar. Runtime tests use the installed project Python **3.13.15**; the launcher reports no registered Python 3.11 runtime, so actual 3.11 execution is not independently verified. Initial sandbox temporary-file permission errors were resolved by keeping test fixtures in an isolated writable worktree directory, without changing production permissions.

Final release checks passed: browser Vite build to `desktop/dist-web`, desktop Vite build and native Tauri release build (`--no-bundle`), including the preserved lazy Fusion viewer; staged Gitleaks found no leaks. Existing chunk-size/dynamic-import warnings remain nonfatal. Native output is in the shared ignored Cargo target; website output is in the isolated publication worktree. No camera/microphone trial, real Brief generation, password enrollment/unlock, model inference, streaming account connection, live app installation or served-site replacement is claimed by these source checks.

## Gmail over IMAP/SMTP with a local mail copy — Claude, 2026-11-09 (branch `claude/gmail-imap`)

- Decision (Grey, 2026-11-09): replace the Google Cloud Gmail API connection with IMAP/SMTP and a Google app password, keep a full local copy of mail for offline search, and allow replies only after owner approval. Goal: less cloud dependence and no Cloud Console limits.
- Engines: Learning and Memory (local copy `data/email/mail.db`, SQLite FTS5, reusing the pattern already used by documents/knowledge); Execution and Security (send route gated by the paired desktop key or near-PC pass, the same boundary as applying a file change; app password sealed with DPAPI via the existing `windows_protection.protect`). No new dependencies: Python stdlib `imaplib`, `smtplib`, `email`, `sqlite3`.
- Authorization: reuses existing operations (`notifications.read` for reading, `notifications.write` for drafts) plus the desktop/near-PC proof for sending. No new operations or policy changes. Dedicated `email.read`/`email.send` operations could be added later if Grey wants finer token scopes.
- Status: implemented and unit tested; not live-verified, not merged, not installed. Details: `docs/EMAIL.md`; handoff: `docs/architecture/CLAUDE_GMAIL_IMAP_HANDOFF_2026-11-09.md`.

## 33. Code Doctor Plain English tab — 2026-11-08

**Owner request:** a Code Doctor tab that translates ZAE's code into plain English, and lets Grey write plain English that becomes Python for ZAE's system. Implemented on `claude/code-doctor-plain-english` (worktree `.tmp/plain-english`), based on `codex/pending-updates-2026-11-07` at `9af7887`.

- **Read ZAE's code:** file list from the existing Code Doctor scan (`scan()` now also returns `files`). Picking a file returns an outline built from the code without a model (Python `ast`; TS/JS top-level declarations) and a plain-English explanation from Study (`qwen3:14b`). Long files are explained in parts of about 12,000 characters (up to 12 parts). Explanations are cached in `data/ui/plain_english.json` by the file's exact contents, so an unchanged file is never explained twice. "Translate all" walks the filtered list one file at a time, with progress and a Stop button.
- **Write in plain English:** instructions (optionally fitted to an existing `.py` file) become a Python draft, `assert` tests, a step-by-step plain-English walk-through and stated assumptions. A draft is text only. "Test in Playground" loads it into the existing Playground, whose runs still need the desktop app. "Send to Build requests" uses the existing tested-copy and owner-approval flow. Nothing in this tab runs code or writes project files.
- **No new routes or permissions:** reuses `/api/code/explain` (`mode: "plain"`) and `/api/code/playground/ask` (`mode: "english"`). Their existing operation entries in the protected `ui_routes.py` are unchanged, and `read_file` keeps the same allowed folders and size limit.
- Module: `core/assistant_platform/plain_english.py`. UI: `desktop/src/components/tools/PlainEnglish.tsx`.

**Checks:** 7 new tests in `plain_english_test.py` plus the existing Code Doctor tests pass; the full Python suite ran 986 tests, of which 11 operator/document tests fail only because this worktree sits under a dot-folder (`.tmp`) that those tests' fixture-folder guard refuses; TypeScript, all 28 desktop scripts and the desktop Vite build pass. The UI was exercised in a browser against mocked API responses (file list, explanation, draft, Playground hand-off). Explanation quality on real files with the local model is not yet measured, and the change is not installed in the running app.

## 34. ZAE self-map: what's inside her and what isn't — 2026-11-08

**Owner request:** ZAE should know what is and isn't inside her whole system, especially the UI app. Implemented on the same branch as section 33 (`claude/code-doctor-plain-english`).

- `core/brain/self_map.py` generates the map from source files, not by hand. App pages come from `App.tsx`'s sidebar list and page descriptions. Each page's sub-tabs are read from its `PageTabs` list or from the page component it renders (plain and lazy imports; object and tuple tab lists). Server areas come from the `*_routes.py` docstrings and `component_registry.yaml`. The map is rebuilt whenever one of those files changes.
- `core/brain/self_map_planned.yaml` is the hand-kept "not built" list: planned (Stream Studio, personal finance, linked decisions, offline device sync, health devices), partial (local self-coding by October 2027) and ideas (plant growing systems, home security, OS replacement). Remove an item when its feature ships; the generated map then lists the feature.
- **In conversation:** every system prompt gets a one-line-per-page summary (about 1 KB) with a rule against inventing pages or features. The stale hand-written page list in `UI_CAPABILITIES` now points to it. Questions about herself (do you have…, where is…, which tab…, or a question naming one of her pages) also get the full map (at most 6,000 characters) in the existing "Reference context only" message, counted in the prompt budget. The map is reference text and never grants an action.

**Checks:** 7 new tests in `self_map_test.py` (fixture app, fall-through cases, rebuild on change, question detection, prompt placement, the real app covering every sidebar page) pass. The full suite ran 993 tests, with the same 11 worktree-location failures as section 33. `closure_check` (63), `self_test` and `integration_check` (16) pass with the check-only files lent as Build requests do. Asked live of the Talk model (`qwen3.5:4b`):
- It correctly said there's no hydroponics tab (an idea), no Twitch connection (Stream Studio planned), no finance tracker (planned) and no home cameras (an idea).
- It placed workouts in Fitness & Health > Training and reminders in Tasks & Calendar > Reminders.
- It wrongly said Code Doctor "lives in the Files tab", confusing the page name "Code Doctor & Files". The 4B model sometimes simplifies the map; the Seek and Study brains were not tried.

## 35. Research upgrades: passages, citation checks, free sources, saved research — 2026-11-08

**Owner request:** of the research recommendations, do 1 (read the relevant part of pages), 3 (check citations), 4 (add as many free research sources as possible) and 6 (remember research). Implemented on `claude/research-upgrades` (worktree `.tmp/plain-english`), on top of sections 33–34.

- **Free sources** (`core/research/sources.py`, all free with no account or key, 20 in total):
  - General: Wikipedia, DuckDuckGo instant answers, OpenAlex.
  - Science: arXiv, Crossref, Semantic Scholar, DOAJ, PLOS.
  - Health: PubMed, Europe PMC, ClinicalTrials.gov. Drugs: openFDA.
  - Tech: Stack Overflow, Hacker News. News: GDELT, Google News.
  - History and books: Library of Congress, Open Library, Project Gutenberg, Internet Archive.
  - `pick()` always uses the general sources and adds a group when the question is about it. `search_all()` runs them in parallel; a failure is recorded and skipped. Rate-limited sources (GDELT, Semantic Scholar) get one query per job. Search words are cleaned of punctuation that breaks API query syntax.
- **Passages and ranking** (`core/research/evidence.py`): pages are read in full (up to 40,000 characters), split into passages, and the best-matching ones are kept (BM25, up to 1,800 characters per source). Results are ranked on title, snippet and opening text; ones under 30% of the best score are dropped. Up to three web pages are kept alongside the abstracts. A source that already returned an abstract of 600 or more characters isn't opened. Seek's quick in-chat web lookups use the same passage picking.
- **Citation check:** every cited sentence is compared with its cited source(s): word overlap, plus any number in the claim must appear in the source. Up to 4 borderline claims are asked of Study. Unsupported claims are marked `[unverified]` in the answer, and the job keeps a report and summary. Lines that only describe the sources aren't checked. It is advisory only.
- **Saved research:** each finished job becomes a Research notebook topic (the answer and citation summary as the topic's note, each source as a source). A new question that shares most of its words with an earlier finished one includes that answer as clearly labelled context. Topic notes aren't marked for ZAE to reference in chat; Grey keeps that choice in Notes.
- **Web search robot check:** when DuckDuckGo answers with a robot check, ZAE stops asking it for that job, records "skipped (robot check)" and continues with the other sources. She never tries to get around the check. A self-hosted SearXNG would give a reliable free web search but needs installing, so it is left for owner approval.
- **UI:** the Web agent shows each source's name and date, `[unverified]` marks, the citation check summary, whether the research was saved or built on earlier research, and a "Searched N sources" list with each source's status.

**Checks:** 26 research tests pass (including 12 new ones), as do the Seek tests. The full suite ran 1,004 tests with only the 11 known worktree-location failures (section 33). `closure_check`, `self_test` and `integration_check` pass. All 19 API source connections were exercised live on 2026-11-08: most returned results; Semantic Scholar and GDELT rate-limited; the Library of Congress and Gutenberg were slow but answered with a longer timeout. Data.gov's API returned 404 and was replaced by the Internet Archive and openFDA. Live end-to-end jobs on Study took 12–43 seconds, read 7–8 sources, and saved notebook topics. The creatine question checked 8 of 8 cited claims as supported. In the hydroponics question the check correctly flagged EC ranges the model attributed to sources that don't contain them. DuckDuckGo began showing a robot check after repeated test searches, and those runs relied on the free sources. Not installed yet.

## 36. Synergized Encephalon improvements — 2026-11-08

**Owner request:** do all ten improvements from the SE review. Implemented on `claude/se-improvements`, on top of sections 33–35.

1. **One model table.** `conductor.WORKLOADS` now names every job, and a test fails if a model name is written elsewhere in `core/` (Arena's own model list excepted). The unlisted default was `llama3.1:8b`. On 50 labelled action messages: `qwen3.5:9b` 50/50, `qwen3.5:4b` 49/50, `llama3.1:8b` 47/50, so the default is now Seek's `qwen3.5:9b`. An Arena choice (`data/ui/brain_model.json`) still takes precedence; none is set.
2. **Turn records.** `core/brain/turn_log.py` records route, model, level, first-text and total time, filler, fallback, source count and citation-check counts, never the words. Only the real server writes `data/ui/se_turns.jsonl`. Shown in Arena > SE & tools through the existing `/api/brains`.
3. **Study context.** `context_for` gives Study 16,384 tokens only when the prompt needs it. Measured on this card, any window above 8,192 pushes Talk out of graphics memory (Study used 9.0 GB at 8,192, 9.7 GB at 16,384), so everyday work stays at 8,192. Code Doctor now puts its task after the file and caps the file text.
4. **Honest fallback.** The 2-second filler no longer claims a search. When Talk fails, Seek gets earlier research and notes marked for reference (`seek.gather_local_evidence`, requires memory.read), and only then says it is looking through saved work. Notes marked "reference" had no effect in chat before this.
5. **Checked web answers.** Web answers are held until `check_citations` has run, so an unsupported claim is marked `[unverified]` before it is shown or spoken. This delays the first text. Seek writes the answer when accuracy matters (numbers, health, money, law, safety), which relaxes the 2026-11-03 "only Talk writes" rule at the owner's direction.
6. **Routing and escalation.** `core/brain/router.py` picks chat, web, deep or local with rules. 70 labelled messages in `router_eval.py` pass 70/70, after fixing two bugs the set exposed in the old web rule ("weather" contained "eat", "AI " contained "i "). Deep questions start a Study research job and Talk says so. A deep question must already qualify as an online request, so nothing new leaves the PC. No model classifier was added.
7. **Working memory.** Each turn also gets the open tab, running research and builds, and the latest watch-list findings (labelled untrusted), only with memory.read. Named conversations persist to `data/ui/working_memory.json` for 12 hours; only the real server writes it.
8. **Local coding checks.** A Build request is rejected and retried when it only changes whitespace, when Aider claims an edit with no real change, or when behaviour changes with no test. The last local retry uses `code_retry` (Seek's model). Replaying the two bad builds' shapes in tests rejects both.
9. **Transcript.** Conductor progress lines now go through the Transcript (`drain()` for single-thread use), so nothing is said twice or out of order.
10. **Overnight model and voice trial.** Nightly ideas use `gpt-oss:20b`, free its memory afterwards, bring Talk back, and fall back to Study. A live call returned correctly in 12.5 s including load; idea quality isn't measured. **The owner/other-speaker voice trial needs Grey and a second person** (Status > Readiness > Voice trial) and was not run.

**Checks:** 18 new SE tests and 4 new Build tests pass. The full suite ran 1,026 tests with only the 11 known worktree-location failures. `closure_check` (63), `self_test` and `integration_check` (16), TypeScript, 28 desktop scripts and the desktop build pass. Live turns through the real Conductor and models: chat 0.89 s to first text; web answer on Talk 10.4 s with 2 of 2 citations matching; web answer on Seek 8.2 s with 1 citation unclear; deep question handed to Study instantly (the job itself was stubbed). Not measured: answer quality across many real questions and the live fallback path with a real Talk failure. Not installed.

## 37. ENTHON, research and SE source publication — 2026-11-08

Owner requested commit and push. Clean publication branch `codex/enthon-research-se-2026-11-08` preserves all six Claude commits through `09fd055`, including `150a2c6` (Plain English), `84facb8` (self-map), `e8f62df` (research), `f2971ca` (ENTHON naming) and `2900a1c` (Build quality/retry). These extend published `9af7887`; no older private tool-history branch is merged or pushed. `CLAUDE_INSTALL_NOTE_2026-11-08.md` preserves Claude's earlier installation report separately from this publication's independent checks.

Publication review corrected three defects in the clean copy: Python build-change comparison now uses ASTs to preserve meaningful literal-space and indentation edits, with conservative comparison for other formats; citation numbers use complete tokens and differing negation cannot auto-pass wording overlap; long source sentences retain their tails and selected passages respect their exact character budget. Added focused synthetic regressions. Citation checking remains advisory, not proof that a claim is true; unclear/partial support stays `[unverified]`. Existing authentication, protected paths, approval gates and model-routing permissions are preserved.

Independent checks on the publication tree: **118 focused backend tests**, **all 28 desktop Node test scripts**, TypeScript, browser Vite, desktop Vite and native Tauri release (`--no-bundle`) builds pass. **438 Python files** parse with Python 3.11 grammar; runtime tests use installed project Python **3.13.15**, not an independently verified 3.11 runtime. The initial TestClient stall under the process sandbox was resolved by running mocked API regressions outside that sandbox with isolated writable fixtures. No live model calls, generated candidate execution, private owner records, platform connections or physical voice trials were used for these checks. Existing nonfatal frontend chunk/dynamic-import and TestClient deprecation warnings remain.

The six incoming commits pass Gitleaks; final staged changes are scanned before push. Source publication does not merge `main`, install the application, replace the served website, restart Core or change owner credentials. Earlier live results and install reports in sections 33–36 and Claude's install note are attributed historical evidence, not newly repeated validation. The clean worktree is `.tmp/enthon-research-se-publish-20261108`; preserve Claude's independent working branch.

## 38. iPhone and CarPlay navigation source draft — 2026-11-08

**Owner request:** write navigation code for review before approval. Status: **isolated source draft; no native iOS compilation, owner promotion, Apple entitlement approval, installation or driving validation**. Branch `codex/carplay-navigation-draft-2026-11-08`, based on published `1a5f43e`, worktree `.tmp/carplay-navigation-draft-20261108`.

`ios/ZAENIANavigation/` contains a native UIKit/SwiftUI iPhone app and CarPlay navigation scene, an Xcode project with a shared scheme, a local dependency-free Swift package for spherical route geometry/progress, and an offline interactive browser design illustration. MapKit supplies the first destination-search/routing provider; its road data is not generated by the language model. A normalized route model permits a later provider adapter without fabricating `MKRoute` objects. Phone/CarPlay share ephemeral trip state; Core remains authoritative for canonical preferences and protected assistant actions.

Source paths cover explicit location permission, destination selection, route preview/start/end, ordered maneuver mapping, route rendering, progress, installed-iPhone-voice prompts, debounced off-route rerouting, repeated-fix arrival, and GPS-loss guidance pause. Canceled/superseded requests cannot install old routes. Start checks whether the preview origin is still current. Turn prompts are marked announced only when accepted; critical prompts may replace obsolete speech, and old cancellation callbacks cannot release new audio. Rejected GPS fixes do not refresh accepted-progress freshness. Both map renderers stop their own live location tracking on pause/end. These are code-review observations, not proof of real driving behavior.

**Preserve parallel work:** shared checkout inspection found Claude's pending `core/maps/`, `core/api/map_routes.py`, `desktop/src/components/map/` and `HANDOFF_2026-11-09_map_traffic.md`. That existing map/traffic/GraphHopper work was not copied, overwritten or installed. A future authenticated mobile provider should reuse its route contract. No duplicate Python endpoint, desktop credential, transport-security exception, preference/history sync or new permission authority is added. The existing CarPlay briefing API stays unchanged.

**Verification:** Windows packaging checks pass for plists, scene wiring, Xcode project/source references, local package and shared scheme; ten Node browser-preview interaction tests pass, and the desktop design illustration was rendered in an isolated headless browser and visually inspected. Gitleaks reports no secrets in the new draft folder. **Eighteen Swift XCTest methods are written but not run**: Swift, Xcode and Apple's SDK are unavailable on this host. The phone/iOS build, simulator/real CarPlay, background location/audio, maneuver timing, route deviation and reconnect transitions remain to validate on a Mac and approved device. Search/new routes need Apple's servers; this is not offline map downloading or offline rerouting. Speech is installed iPhone TTS, not Kokoro or connected ZAE conversation. ETA is a route/progress estimate; lane guidance and production road matching are not implemented.

The CarPlay entitlement is an unapplied example until Apple approves the App ID/provisioning setup. The requested artifact is a review draft, not an applied desktop/website release; neither release output was changed or installed. Review `ios/ZAENIANavigation/README.md` and `Preview/index.html` before deciding whether to promote this work. Owner approval is still pending for publication/integration/application; Apple approval and real-platform validation are separate requirements.

## 39. Desktop/browser navigation workspace — 2026-11-08

Owner requested improving Claude's existing map with the approved CarPlay preview's black-and-amber controls, clear street/satellite imagery, multi-stop routes, traffic, aircraft, ship information and weather. Implemented on `codex/map-navigation-workspace-2026-11-08` from safe published `1a5f43e`. No iOS deployment, merge or GitHub push is part of this update.

- Preserve Claude's Map/Satellite/Dark styles, WSDOT lines/incidents, landmarks, radar/NWS weather and OpenSky aircraft. The actual MapPanel now includes floating route/instruction preview cards, estimated time/distance/arrival, fit/clear route, step previews, larger controls and container-responsive layout. Traffic colours remain green/orange/red; amber identifies the planned route. This is route planning/preview, not continuous GPS driving guidance.
- Explicit Search/Enter replaces prohibited public-geocoder autocomplete. Stop-key/request generations reject late search/route results, every stop must resolve, optimized responses are validated, and incomplete middle stops cannot disappear silently. Shared tile completion wakes reopened panels. Traffic proximity tests segments instead of vertices; unavailable data does not claim clear roads. Local optimization/cache work is bounded and its fallback is explained.
- Sea panel and markers use the authenticated `/api/map/marine` read route. Public AISStream WSS stays on Core, with the key from `AISSTREAM_API_KEY`, no key sent to clients, finite viewport/position checks, bounded RAM-only records, idle worker expiry, coalesced subscriptions and reconnect backoff. No account/key was created or inspected. Actual live ship positions require local key configuration and provider coverage; no military/complete-vessel coverage or navigational accuracy is promised. Existing websockets 17.1 satisfies optional `requirements-map.txt`; no package was installed.
- Backend review also fixed wide-area landmark allocation, radar-host trust, location-aware geocoder caching and unbounded feed-cache growth. Existing authentication, owner proofs, passwords and protected assistant actions remain intact. Claude's already installed Mail feature was preserved; the older Gmail branch/private-tool-history ancestry was not merged. Existing non-map shared working files were not overwritten.

Verification: **45 map/backend/authentication tests**, **all 29 desktop Node test scripts**, TypeScript, browser Vite, desktop Vite and native Tauri release builds pass. Actual React UI checks with synthetic data verify explicit search, destination selection, route/step review, clearing, stale-result rejection, incomplete-stop blocking, Sea panel and 390px overflow. Desktop/mobile renders were inspected. Gitleaks reports no secrets in new map backend/frontend folders. Python runtime is 3.13.15; Python 3.11 grammar compatibility is checked separately, not claimed as 3.11 execution.

Applied locally with scoped source-hash preconditions and rollback copies. Native installed/build SHA256: `8ad7b1a1da0169c21b8e902bec3f3bca5bc49cd04f59e6d322189cf60fb7abaf`. Previous installed executable: `backups/desktop-installed-20261108-233359`; previous website: `backups/map-web-before-20261108-navigation`; original map sources: `.tmp/map-before-navigation-upgrade-20261108`. Core was restarted through its existing task; health is ready/HTTP200, served website/new MapPanel asset return HTTP200 and unauthenticated marine requests return401. Existing voice listener/authentication settings were not changed. The existing local GraphHopper engine was started; a public-landmark test produced a local 2,056m /214s route (online fallback was also observed while it was stopped). No owner locations or live authenticated ship/air/weather feeds were used for these tests. Native owner interaction remains a separate live-use check.

Read `MAP_NAVIGATION_WORKSPACE_HANDOFF_2026-11-08.md` for integration, setup and rollback. The source remains uncommitted in the isolated feature branch and scoped working copies in the shared checkout; preserve both before publishing. Never push the old shared branch wholesale.

## 40. Versioning and owner-installed updates — 2026-11-09

Decision (Grey): updates are staged and appear in Settings > Updates for Grey to install, with an optional server restart; assistants no longer install releases directly. Versions are tracked in `desktop/src/config/versions.json`: a whole-system version for capabilities and security, a separate UI version for interface-only changes, and one version per tab, plus module and brain (node) versions shown in Settings > About. All versions stay in beta (0.x) until 1.0. Starting values: system 0.27.0, UI 0.16.0. Install runs only from the desktop app (Tauri `install_update` → `scripts/install_update.ps1`), verifies the staged exe hash, backs up the app and phone site, and records history in `data/updates/installed.json`; the read-only `GET /api/updates` grants no execution authority. Implemented in source 2026-11-09; first staged release pending Grey's install.

## 41. Keyless basemap tile correction — 2026-11-09

Owner screenshot showed CARTO's API KEY REQUIRED watermark on desktop and phone. Earlier mocked image/UI tests missed the real provider response. CARTO now requires a basemap key; the separate AISStream ship key does not fix street maps.

Street styles now use standard OpenStreetMap tiles; Dark applies a filter to base imagery only, preserving traffic/route/marker colours. Satellite uses USGS Imagery Topo with built-in labels and removes the key-gated CARTO overlay. Correct provider attribution remains visible. A versioned public-basemaps-v2 cache namespace bypasses old watermarked images, including offline fallback; legacy files are preserved. Street/dark share the same server cache. Existing limited concurrency, on-demand viewing and 30-day caching remain; no bulk map download was added.

Independent checks: 47 mocked map/API tests, including old-cache rejection and source selection; 8 focused frontend checks; live public Seattle street and USGS satellite tiles downloaded to an isolated test cache and visually inspected without a watermark. No owner location, credential or live private record was used. Python runtime 3.13.15. Native/web release builds are staged through the new owner-controlled update workflow, with RestartServer required to load the changed provider. System 0.27.1, UI 0.16.1, LIFE 0.13.1, maps 0.3.1. No installed-app replacement, served-site refresh, Core restart, merge or GitHub push is part of staging. Install from Settings > Updates, then refresh the phone page. Packaging verified: native Tauri release and browser Vite builds passed. Staged update `system-0.27.1-20261109-101757`, executable SHA256 `8c459f4efa8be22e83a59ea36c1080808d3560a4df0777c4ecb35f753c8e3e3a`, matches its manifest; restartServer=true. All 29 desktop Node test scripts pass. Pre/post-stage hashes confirm the installed executable and served website are unchanged. Owner installation and a live app/phone check are still pending.


## 42. Familiar route planning — 2026-11-09

Owner requested Google Maps-like route options. Reuse the existing authenticated map API and local GraphHopper/online OSRM routing; no new permission authority or dependency. Photon now supplies typing suggestions after a 1.1-second pause, with server-wide rate limiting, no request queue, five-minute bounded RAM caching, approximate map-area bias, configurable HTTPS/loopback endpoint and explicit failure states. Public Nominatim remains explicit-submit only. Typed partial queries are not saved to disk. Photon demo is a light-use service, not guaranteed production infrastructure.

Origin requests device location with normal OS/browser consent. No location is fabricated from Home; denial/timeout permits manual start. Async location cannot overwrite a manually edited origin. The UI shows accuracy and a position dot, swap, removable/reorderable intermediate stops, keyboard-accessible suggestions, local-device recent destinations with Clear, and route cards for up to three engine-provided alternatives (two endpoints only). Alternatives do not add routing requests; none are fabricated. Desktop directions move to the left; mobile remains map first.

Route colours: blue for reported regular traffic, orange slower, red heavy, dark red stop-and-go; unknown/stale/saved-only coverage is dashed grey. WSDOT geometry matching is approximate (nearby parallel road segments, no lane/direction guarantee), regional and timestamp gated. ETA is not live-traffic-adjusted. Session connection reuse reduces repeated provider handshakes; cached suggestions were measured at 0.00001 seconds after a 1.104-second public Space Needle query returning six matches. No private owner location was used in testing.

Verified: 56 mocked backend/API tests, 10 focused frontend checks, all 30 desktop frontend test scripts, TypeScript, actual synthetic React browser flows (location, denied permission, delayed-location race, debounce, keyboard selection, swap/invalidation, route card and mobile overflow), and inspected desktop/mobile screenshots. New clients enable typing requests only after authenticated /map/home advertises support, so an older Core never receives autocomplete on its explicit-only Nominatim adapter. Desktop/mobile screenshots were inspected; the narrow-width map-collapse issue was corrected and now has an explicit 300px-minimum visible-map test at a 390px viewport. Final packaging verified: native Tauri and browser Vite builds pass; staged `system-0.28.0-20261109-233353` (system 0.28.0), executable SHA256 `b28c6790fb06bf4da4e1d5c689a1b7860febd7351929d4aba6b1f402db9e8cd9` matches manifest, RestartServer=true. The packaged browser assets contain the mobile-width fix and older-Core capability guard. Installed native and served website hashes remain unchanged. Owner installation and live-device usage remain pending; no merge or GitHub push was performed. Stage only under AGENTS.md; owner installs through Settings > Updates with Restart server. No merge/push or automatic install/restart.

Remaining replacement milestones: continuous GPS follow with tested road snapping, off-route detection/rerouting, background/voice maneuver guidance, live-traffic-aware ETA/rerouting and broader licensed traffic coverage, supported avoid-toll/highway/ferry preferences and travel modes, offline regional search/navigation packs, and real-device/road validation. Existing functionality is route planning/preview, not a verified full Google Maps replacement.


## 43. Category workspaces and orbital navigation — 2026-11-09

Owner selected option 1 for top categories, option 5 for the core with recent activity, and large mobile tiles. Shared `NavigationHub` replaces hover dropdowns and the core's compact every-tab list. Top categories open full workspaces with large app cards and the existing authenticated `CategoryPanels` records; selecting the core opens six orbital category cards, app search and recent apps. Phone uses a responsive two-column tile sheet. Fitness remains an alias into LIFE; Settings retains status/security/updates. No new engine, inference call, permission or dependency was added.

Navigation is a temporary surface: existing windows, unsaved drafts and selected sub-tabs remain intact. Covered workspace controls are inert; header categories remain usable. Core/category Back, Escape and mouse Back return through navigation before page history. Keyboard focus returns to the opener; reduced-motion preferences disable launcher motion. The live core is reused and temporarily centered/shrunk while the launcher is open; its dock returns afterward. Calm/password and pending owner-authentication prompts disable the launcher; authentication is unchanged.

Recent activity includes existing category data and a device-local list of at most ten unique app visits (IDs and timestamps only, no chats/document contents). History is clearable, does not sync to the server/cloud, rejects malformed/unknown/future records and tolerates unavailable browser storage. Actual notes/projects remain read through existing protected APIs, not copied into visit history.

Verified: TypeScript, all 30 desktop Node scripts, history regression checks and an isolated real-React browser run with synthetic fixtures. Browser checks cover no hover dropdowns, category switching, app/alias opens, draft preservation, record panels, clear history, focus/Back, security suspension, reduced motion, and 390px tile/workspace overflow. Desktop and phone renders inspected. No owner records, signed-in browser, camera or model inference used. UI 0.17.0 and Home 0.8.0; system stays 0.27.1. The shared checkout concurrently received the separate familiar-directions update (system 0.28.0 / UI 0.18.0). Navigation source remains scoped to this branch; the combined staged release preserves that newer map work. Native and website packaging receipt follows when staging finishes. Owner installs from Settings > Updates; no automatic install, Core restart, merge or push.

Packaging verified: staged `ui-0.18.0-20261109-232915` with native SHA256 `cfec617869946b11ddff07d76a673e38c8c2b3f4874db76f226b921f5678c989` matching the manifest. Both native Tauri and browser Vite builds and TypeScript passed. Combined current-source Node suite: 30/30 scripts pass. Staged website contains the workspace/orbital/recent-history controls and the reduced-motion fix. RestartServer flag is enabled for the preserved concurrent map backend changes; no restart is performed during staging. Installed executable unchanged: True; served website unchanged: True. Owner installation and live app/phone use remain pending.


Owner naming/version decision — 2026-11-09: Map & traffic is **GODSPEED**, maps module **v0.14.1**. LIFE displays GODSPEED using its existing map sub-tab ID; LIFE patch version 0.14.1, UI 0.18.1, system remains 0.28.0. This is a label/version correction over the tested directions upgrade, with no routing or authentication change. Both outputs are rebuilt and staged; owner installs from Settings > Updates with Restart server to include the pending backend upgrade.

GODSPEED packaging verified: both builds pass; staged `tab-life-0.14.1-20261109-234112` titled GODSPEED v0.14.1; native SHA256 `ba981314533d897856b8ca967892c1db9cf53595c9a661fadc3d50ef060784d0` matches manifest. Browser assets contain GODSPEED/0.14.1. Ten map frontend regressions pass. Owner installation remains pending; keep Restart server checked for the included map backend upgrade.


## 44. GODSPEED trip progress and detailed release notes — 2026-11-10

GODSPEED 0.15.0 adds explicit Start/Pause/Resume/Reset foreground GPS tracking, route-geometry progress, completed shading, percentage, traveled/remaining distance, proportional remaining time, follow/recenter, advancing route instructions, accuracy/stale/off-route/jump handling and explicit arrival. GPS is owned by an app-session singleton, continues across map unmount/remount, and stops on pause/reset/arrival/permission denial/phone disconnect/app close. Released watcher callbacks are ignored. Raw fixes/progress remain RAM-only. Weather uses rounded current-area alerts plus a separate destination-point check; saved-home conditions and radar age remain labeled. Traffic can refresh manually and colors expire with their timestamps. Added per owner follow-up: repeated accurate off-route readings trigger bounded reroutes preserving unvisited stops; late replies are rejected and failures keep the old route. An explicit auto-reroute switch, wake-lock status, and partial-coverage flow-category ETA estimates are included. Reliable locked-iPhone background GPS, lane-level matching, spoken navigation, provider-measured congestion ETA and complete route-wide weather are not claimed.

All ZAE releases now carry categorized detailed releaseNotes (kind, title, description), validated before packaging, displayed before/after install and retained in installation history. Older notes remain readable. Publication still uses owner-installed staged native/web outputs; metadata changes grant no new execution authority. Read docs/releases/GODSPEED_0.15.0.json for exact changes and limitations. Synthetic verification/build evidence is added after checks complete.


Verification update: pure geometry/GPS tests, persistent-session and reroute-race/stop-preservation tests, traffic ETA coverage tests, detailed-note rendering tests, PowerShell AST/invalid-note checks and synthetic mounted-React GPS/browser lifecycle checks pass. Real React unmount/remount retains a live trip without a second watcher. Source is scoped to the map feature branch and matching app files; unrelated work is preserved. Packaging evidence follows after final release checks.


Final release verified: staged `system-0.29.0-20261110-003630`, GODSPEED 0.15.0 / system 0.29.0. TypeScript, browser Vite and native Tauri release builds pass. Native SHA256 `7939552a95bbe1a2d639988b5c207e0d1724bcd2c3f356344e516b0d5de224ce` matches manifest; RestartServer=true. Browser assets include trip/reroute/ETA, destination weather, logout cleanup and detailed-note UI. Manifest contains 17 categorized entries and 17 complete legacy-viewer explanations, exactly matching release JSON. All 33 frontend script suites pass (the logout mock was updated for the newly verified Event notification); 56 existing backend map/API tests pass. Synthetic React/GPS tests cover progress, accuracy rejection, completion, restart/reset, cross-tab unmount/remount persistence and mobile geometry. Pure session tests cover preserved-stop rerouting, cancellation, permission loss and wake locks. Real-road and locked-iPhone validation remain pending. Installed/served outputs unchanged during staging: {'installed': True, 'site': True}. No automatic install, Core restart, commit, merge or push.


## 45. Workspace context previews and visible page navigation — 2026-11-10

Owner requested previews of what an app was last doing, a fix for the collapsed mobile tab strips in Research/LIFE, and five visual alternatives in which every app/subpage has its own screen. Implemented on `codex/mobile-pages-previews-20261110`; preserve the separately implemented GODSPEED trip/session and detailed-release-notes work.

Implemented: workspace app cards display validated saved view labels, last-opened time when available, and context from existing authenticated category records. Cards and CategoryPanels share one read-only request batch; stale category responses cannot replace the selected category. No app screenshots or private content snapshots are captured/stored. Missing data stays explicitly unavailable. Resume uses the existing saved-view state, not an exact document cursor or cross-device session.

The new PageNavigator presents a non-shrinking title, a 44px-minimum page chooser, and previous/next controls instead of the affected horizontal tab strips. It is shared by PageTabs, Research, Music, Plan, Fitness (including Food and Training), Code Doctor and assistant tools. Visible page content is labeled as a region; existing keep-alive page drafts stay mounted. Legacy rows retain a minimum height. Swipe follows the page chooser and stops at subpage boundaries rather than jumping apps. Existing aliases, settings/security gates and execution permissions are unchanged. No new runtime dependency, inference call or backend route was added.

Designs for review: Focus Pages, Split Navigator, Activity Trail, Mission Deck and Quiet Reader. Each covers 13 apps (including browser-only PC remote) and 107 app/subpage destinations: 535 local navigation checks. They use clearly labeled synthetic data and distinct layouts with phone/desktop views. Standalone URL-shaped paths in these concepts are illustrative; production URL routing and removal of the desktop window system are NOT implemented by this release. The existing app structure is retained while one page is shown at a time.

Verification: TypeScript and all 34 current frontend test scripts pass. An isolated real-React browser check verifies the visible 390px page chooser, 44px targets, Research Library switching, one active region, invalid-jump rejection, draft preservation, last-view context and one shared category read. All 535 concept destinations and mobile overflow checks pass; actual mobile UI and phone/desktop concept renders were visually inspected. No owner records, signed-in browser, credentials, camera or inference were used. UI 0.20.0; affected tab versions advance with categorized detailed notes. Native and website builds are staged through Settings > Updates; packaging receipt follows. No automatic install, Core restart, merge or GitHub push.

Packaging verified: `ui-0.20.0-20261110-112626` native SHA256 `4e2043b1601de95b6ef0a1e4fcdad1c162e1f1bf98d52c89d85f5f61bdffc908` matches its manifest. Native Tauri and browser Vite builds and TypeScript pass; packaged assets contain the page navigator, last-view previews and all six categorized release-note entries. The final shared-source suite passes 34/34 scripts. Installed executable unchanged: True; served website unchanged: True. Owner installation/live-device use remain pending.


## 46. Mission Deck, contextual voice resume and snap layouts — 2026-11-10

Owner selected preview 4 (Mission Deck), contextual recent-work cards on app pages, Windows-style two/three/four internal app-window layouts, and voice access to existing and future features. Development uses `codex/mission-deck-voice-snap-20261110` in an isolated worktree based on published `1a5f43e`. Scoped source was applied to the shared checkout only after verifying the prior file hashes; accumulated Claude/Codex work is preserved. No merge or GitHub push is included.

Implemented: the existing core, colour preferences and app features remain, with raised workspace cards, page directories and compact parent navigation. One page remains active at each level; existing mounted drafts are retained. Each shared page header shows its previous observed work. The activity observer stores only page identifiers, a page label, an explicitly supplied work title where available, interaction type and time. It never copies field values, document bodies, audio or credentials. Metadata is device-local, limited to 100 page records and 90 days, with a visible/voice clear command. An edit or control interaction is not presented as proof of a successful save. Recipe editors supply their title; other pages use their page-specific work label. Resume returns to a saved page or retained draft, not an exact document cursor or a cross-device session.

Spoken offer: returning to relevant work **by voice**, with spoken output enabled, may say “You were recently working on [context], sir. Would you want to continue?” Click/typed navigation does not add that spoken question. The offer is remembered by page and work subject, not the changing timestamp. Later/not now/busy/doing something else/after-work replies defer it for at least 24 hours; the same running session stays quiet. Don't ask again/completed suppress that retained context. A different work subject can qualify again. Offer state survives reload, is bounded/aged with the metadata, and clears with recent-work history. A pending answer lasts 90 seconds; deferral does not create a reminder, and explicit reminder commands retain their normal handling. “Continue” returns to that work without automatically modifying it.

Layouts: titlebar and tab-manager snap controls, plus the shared voice handler, support two equal side-by-side panes, a large-left pane with two stacked-right panes, and four quadrants. Named app order is preserved. Other windows minimize rather than close. Undo restores previous geometry/minimization for still-open windows while preserving later opens/closes and drafts. These are ZAE windows, not arbitrary Windows applications. Fixed `arrange_2/3/4` and `undo_arrange` actions can be queued through the existing authenticated phone remote route; named targets are distinct bounded allowlisted IDs, with existing expiry. Calm/password and pending owner-authentication flows block interference. Background/listening animation pauses cannot leave the arranged panes transparent.

Voice parity: recognized PC-listener turns and the app microphone share deterministic UI routing for page paths, recent work, resume, layouts, page choices, next/previous, ordinary named buttons, native fields and checkboxes. Filling a field does not submit it. Hidden/disabled/ambiguous controls are refused. Protected actions and credential/file controls retain dedicated authenticated interactions; generic voice control is an additional UI guard, never a new permission grant. No model inference, cloud call, dependency or microphone configuration change was added. The current catalogue has **13 apps / 106 page destinations**: the earlier 107 included an erroneous Workbench Playground entry; actual Playground remains under Code Doctor. Catalogue parser coverage is not a claim that every legacy workflow is acoustically verified. AGENTS.md records the standing requirement to document and test voice paths, and report remaining platform/control gaps.

Examples: “Open Research Library”; “What was I working on here?”; “Put Notes and Research side by side”; “Arrange four windows”; “Undo window arrangement”; “Set [field] to [value]”; “Press [ordinary button]”. Custom canvases, native file pickers, approvals and device authentication retain their dedicated interactions. Future work should add explicit semantic handlers for remaining legacy features rather than claim universal natural-language control.

Verified: TypeScript and all **35 frontend test scripts** pass against the final shared source; **5 remote-control backend tests** pass under the actual project Python 3.13.15 environment. Isolated real-React browser checks with synthetic fixtures cover controlled field filling/Save, metadata exclusion, protected-control rejection, contextual requested speech, later/reload/dismiss/new-context suppression, named two-pane order, three/four panes, geometry Undo, titlebar picker and 390px mobile navigation. Tests inject recognized text and capture TTS requests; real microphone/acoustic recognition, live paired-phone operations and owner-installed native use remain unverified. No owner records, signed-in browser, private session logs, camera or inference were used.

Release verified: **system 0.30.0 / UI 0.21.0**, staged `system-0.30.0-20261110-134916`, title “Mission Deck, contextual voice resume and window layouts”. Native Tauri and browser Vite builds pass. Native SHA256 `29c56e2c6783c04e024bdbfb4a1360ba8a92f61fe16bf2b7a8d8670807b5394e` matches the manifest; nine categorized detailed notes are included, with `restartServer=true`. Packaged assets contain the resume offer, page navigator and snap controls; test-only bridges are absent. The installed executable and served site hashes are unchanged. Under the owner's current staged-update workflow, install from **Settings > Updates**, leaving **Restart server** enabled for the remote-command schema/action change, then refresh the phone page. No automatic install, restart, merge or push was performed.


## 47. GODSPEED 0.16.0 moving aircraft — 2026-11-11

Owner requested visibly moving live aircraft. Reuse the existing authenticated OpenSky read adapter and 30-second polling; add per-aircraft positionAt/lastContactAt and feed observation/fetch separation. A bounded client-only motion layer predicts from reported speed/heading for at most 45 seconds, corrects over 1.2 seconds, fades after 60 seconds and expires after 120. Ground, unknown-time and invalid-motion aircraft do not extrapolate; old observations never overwrite newer ones. Actual report time is retained across cache hits. The render loop is isolated from the main map, capped at 20 FPS and paused while hidden/disabled. No new provider, credential, dependency, permission or inference path.

Named control/voice path: open GODSPEED, Press Air, Turn on Animate aircraft / Turn off Animate aircraft. Uses the ordinary guarded checkbox path; OS reduced motion keeps reported positions stationary. Scope is smooth estimated movement between reports, not a new radar stream. Synthetic math/backend/browser/recognized-voice checks and native/web staging evidence follow. Read docs/releases/GODSPEED_0.16.0_AIR.json for detailed notes. Owner installs with Restart server; no automatic install/restart/merge/push.


Aircraft motion release verified: `system-0.31.0-20261111-121818` (GODSPEED 0.16.0 / system 0.31.0); native SHA256 `7feb6e3a3486ed3757342a24b87b0dd67ac99fc4b98e1632cb93d2e5e2ececf5` matches manifest, RestartServer=true, eight detailed categorized entries match the release JSON. TypeScript, native Tauri and browser Vite builds pass; all 36 frontend scripts and 58 backend map/API tests pass. Actual synthetic React browser checks verify moving markers between reports without extra feed calls, recognized-voice on/off through the guarded native checkbox, reduced motion, legacy-Core unknown timestamps and 390px layout. Desktop/mobile renders inspected. New pure tests cover capped extrapolation, smoothing, duplicates/out-of-order reports, stale/future/invalid data, poles and date-line normalization. Live public Seattle/Tacoma check returned 97 aircraft with true timestamps, 77 within 45 seconds; no owner location/credential was used. Installed/served files unchanged during staging: {'installed': True, 'site': True}. Owner installation and live-device validation remain pending. No automatic install, Core restart, merge or GitHub push.


## Updater deployment-root repair — 2026-11-11
Installed binary embeds `.tmp/claude-nav-split-build/desktop/src-tauri`; its native Install looked in the build snapshot while Core lists primary-checkout staged packages. Main last-install receipt had no new attempt. New native helper searches validated build ancestors outer-first, with an optional absolute trusted ZAENIA_PROJECT_ROOT override; client IDs remain restricted and confirmation/hash/installer safeguards unchanged. A backed-up legacy installer forwarder plus discovery manifests lets the existing installed native app reach the primary installer on the next owner-confirmed click. Compatibility CheckOnly verifies the staged executable without installing/restarting. Six standalone Rust root-resolution tests pass; packaging/full-path checks follow. No auto installation, restart, merge or push. Voice path remains Open Settings Updates; installation retains its dedicated desktop confirmation.


Updater repair release verified: `system-0.31.1-20261111-124104`, system 0.31.1 / combined UI 0.25.0; native SHA256 `b3e7fd4111ff9d308424aff15c0abbab08bc5189925d5788bd092f6486a29437` matches manifest; five detailed notes, RestartServer=true. Six standalone Rust deployment-root/ID tests pass. 37 pure frontend scripts pass; the rendered navigation suite run explicitly against the combined loopback preview passes 33/33 checks, including the installed desktop screen tabs, drafts, per-pane Back, page search, phone layouts and resume suppression. Separate actual React aircraft tests still pass after the clean three-way merge of Claude’s map page-navigation delta with moving-aircraft code. Latest installed UI0.24 source was preserved across 47 files; no dependency changed. Old downgrade-prone packages were withdrawn to `.tmp/updater-root-before-20261111/withdrawn`. The old native app’s exact discovery path has the new manifest; its backed-up fixed-root forwarder CheckOnly validates the actual staged executable and canonical installer without installation. Native installed hash remains unchanged; last real install receipt is still UI0.24 at 09:27. No app close, install, Core restart, merge or push was performed. Owner should reopen ZAE to refresh Updates, select the preserved-screens repair, leave Restart server enabled and use the existing two-step Install confirmation.

## 48. One neural core and C5 "Core in the mic" — UI 0.26.0 (Claude, 2026-11-11)

Owner focus: how the core acts on each page; Grey then picked core concept C5 "Core in the mic". Branch
`claude/core-behavior` (worktree `.tmp/claude-core-behavior`), built on the UI 0.24.0 source (`6d73f6e`) and applied to
the primary checkout on top of the installed UI 0.25.0 / system 0.31.1.

- **One instance:** `components/core/CoreStage.tsx` renders the single `NeuralCore` through a portal into a host element
  that moves between `CoreSlot`s: Home centre (priority 0), chat mic (2), Calm view (3). Moving the DOM node never
  remounts it. A move between two visible places glides with a FLIP transform (0.55 s, cubic-bezier(.2,.8,.2,1)).
- **C5 placement:** Home keeps the hero core and its state label. Off Home (any open window, the category sheet, the
  tab manager; on the phone any section but Home) `components/core/MicCore.tsx` puts the core in a fixed 150 px layer
  centred on the chat mic (desktop `.home-chat__mic`, phone M5 `.bx-vbar .bx-mic`, falling back to the chat bar),
  shown at 46 px. Voice phases burst it to 150 px with the state word on its left (10.5 px, .16em, accent); listening
  pulse rings, thinking orbiting dots, speaking a pulsing ring (gentle pulse; no output level exists). The layer has
  `pointer-events: none`; the mic keeps its click target and label. Reduced motion: no burst, state colour only.
- **Colour:** off Home the canvas is tinted with `moduleMeta(app).accent` (LIFE #5fd39a, Notes #a68bff, Research
  #4fd1c5, Assistant #f07fb8, default #e0a353).
- **Pause rules:** `core/coreVisibility.ts` (pure, unit-tested) + `NeuralCore` pause the loop when the core is
  detached, off-screen (IntersectionObserver), zero-sized or fully under an opaque surface (five-point hit test),
  re-checked on layout events only. Drawing buffer follows the on-screen scale; resizes redraw immediately.
- **Also:** orbit view hides the state line under "CORE"; Tabs strip no longer overlaps the Today card; security
  readout regex fixed; unused HUD CSS removed; tab manager reports its state as `zae:tab-manager-state` (the existing
  `zae:tab-manager` command still opens it).
- **Evidence:** TypeScript; unit suites incl. `scripts/core-visibility.test.cjs`; mobile-browser; rendered nav/split
  33/33; rendered C5 checks at 1440x900 and 390x844 (no reset Home↔pages, mic placement on category/app/record/split/
  Settings/tab manager, each voice burst and word, accent per module, mic click passes through, reduced motion).
  Screenshots: `docs/previews/core-behavior/c5/`. Not verified: real microphone/speech, installed-app GPU, physical
  phone. The burst ring is kept on screen by `burstFit` (shift toward the middle within the viewport minus safe-area
  insets, shrink only if the screen is narrower than the ring); checked at 390x844 and 360x780.


## 49. Weekly whole-system release: November 11-15, 2026

Status: execution plan and proposed performance targets, not completed work or a release receipt. Owner direction: every Sunday is the target for a substantial coordinated whole-system update. This week ends Sunday, November 15, America/Los_Angeles. Work uses current subscriptions; Claude Ultra is not assumed activated. Existing authentication, release controls and owner-controlled installation remain in force.

### Sunday outcome and scope

Ship one coherent accepted system with (1) measured responsiveness/idle-load improvements, (2) stronger follow-up context and truthful action completion in daily tasks, and (3) a reproducible development and release gate. Preserve the current accepted Preview 05/M5 screens, C5 single-core/mic work, GODSPEED motion/progress, owner data and all other accepted features. Inspect the actual pending/installed state before treating any earlier staged receipt as installed. Assign the release version from the latest accepted baseline at feature freeze; do not reserve conflicting version numbers now.

### Day-by-day work

| Day | Codex lead | Claude lead | Required evidence |
|---|---|---|---|
| Wednesday Nov 11: baseline and scope | Inventory source branches, installed app, served site and pending builds; establish one integration baseline; record a repeatable performance protocol and critical workflow list. Preserve recovery copies and reconcile release-root provenance. | Review the bounded sprint scope and current C5/UI changes; identify fragile existing context/voice call paths. Supply a concise design/acceptance packet, not a new architecture. | Shared task ownership and base commits; current-state matrix; baseline timing/CPU/RAM/VRAM samples; agreed 20-case daily-workflow suite. |
| Thursday Nov 12: performance and context | Measure listening/STT, routing, model first token, speech start, page opening and idle render load. Fix the largest measured bottlenecks using existing Conductor/priority/cache/visibility machinery; avoid speculative model/dependency changes. | Implement the bounded context-continuity packet in a separate worktree: refer to the current task/event/document, honor explicit corrections, request clarification for ambiguity, and preserve approved task context through restarts where applicable. | Before/after traces under comparable warm/cold/load conditions; synthetic context examples; no permission expansion, memory contamination or duplicate actions. |
| Friday Nov 13: close workflows and add gates | Add sanitized clean-checkout critical Python tests to CI, run existing frontend checks and secret scanning, and integrate reviewed commits through one integrator. Add source/version/deployment-path consistency checks to the release procedure. | Review performance/concurrency and action/persistence changes; finish context examples and voice parity; fix regressions in already accepted UI/C5 work. | Reminder/action/persistence receipts, documented voice paths, meaningful CI checks, independent review findings resolved. Feature freeze Friday evening. |
| Saturday Nov 14: release candidate | Build one desktop and browser candidate; test actual installer discovery/hash/backup/restore path safely; run desktop/phone synthetic checks and failure/restart/offline tests. | Independently inspect candidate behavior, mobile UI, voice/context edge cases and release notes; flag limits honestly. | Release candidate with known-good recovery path, performance comparison and passing critical gates. Owner performs a short real-PC/phone/voice trial. Only release-blocking fixes enter after freeze. |
| Sunday Nov 15: whole-system release | Publish the reviewed, secret-scanned source and stage the coordinated desktop/web outputs under the existing authorization workflow. Record exact commit, versions, artifact hashes, restart requirement, detailed notes and rollback. Verify the served site/Core after owner installation. | Final risk/behavior review and plain-English patch-note check; compare owner observations with the acceptance cases. | One weekly release receipt; installed and live-verified states recorded separately from staged/synthetic checks; carry unresolved experiments into next week without claiming completion. |

These assignments are proposed work ownership, not a claim that Claude was contacted or automatically scheduled. Do not let both assistants edit the same working directory. Each task has one writer, a reviewed baseline, a short handoff and a single release integrator. Existing in-progress accepted UI work is preserved; new visual redesigns are outside this week's performance/context scope.

### Performance scorecard

Measure first; targets are provisional until baseline is recorded. Use a fixed synthetic command set, at least 30 warm samples and five cold-start samples, and distinguish model-only first-token time from full microphone-to-spoken-answer latency. Record hardware/load, models/settings, samples and failures, with median and p95. Never discard slow failures to improve the result.

- Target at least a 20% reduction in the selected user-visible warm-latency bottleneck, with no material cold-start regression. Choose the actual bottleneck after measurement instead of promising every stage improves by 20%.
- Target at least a 25% reduction in idle UI CPU where the baseline shows avoidable work; if the existing C5 visibility changes already make idle low, preserve that result and report the floor rather than fabricating savings.
- Keep foreground conversation responsive during permitted background work, honor owner priority settings, and record peak RAM/VRAM. No unmeasured four-model residency or new hardware purchase is required.
- Show timings and pending work through existing Status/Assistant tooling where possible. Prefer bounded instrumentation over another dashboard or duplicate scheduler.

### Flagship assistant acceptance cases

The 20-case suite covers a bounded set of everyday commands, with at least: a reminder saved to the correct date/time and page; a contextual follow-up moving that same reminder; explicit corrections; an ambiguous reference requiring clarification; stop/cancel; a retry without duplicate effects; an authorized memory correction; task-context recovery after restart; and denied sensitive actions without a grant. A response claiming success requires a real storage/API receipt. Follow-up references use the correct conversation/task and do not merge unrelated personal/project facts. The owner leads conversational follow-ups; no generic closing questions are added.

Voice and typed commands share their guarded handlers. Test recognized-text routing separately from real acoustic/owner-speaker trials. Native credentials, file pickers and release approvals retain their dedicated interactions. Real PC/phone/voice trials need the owner's devices and remain unverified until observed.

### Release gates

All critical workflow cases pass, with no unexplained failures or skipped critical cases. Clean-checkout CI runs a documented sanitized critical backend suite plus frontend checks and secret detection; historical fixture failures are listed separately and never relabeled passed. Desktop and browser packages come from the same reviewed source with the accepted installed UI preserved. Confirm deployment-root discovery and the staged executable hash; preserve and demonstrate the recovery path. Document source, dependency/runtime versions, source provenance, installation state and known limits.

Detailed release notes explain Added, Changed, Fixed, actual Removed items, Performance, Security/privacy and Known limitations as applicable. Whole-system means a coordinated Core/desktop/web release and compatibility checks across existing modules; it does not require rewriting every tab every week. Native Apple/watch releases require their own supported build/device evidence. Safe urgent fixes may ship between Sundays. The Sunday release contains the verified scope; incomplete or failing work remains isolated and explicitly recorded.

### Explicitly later work

This week does not promise full autonomous self-coding, a new OS/SSD migration, guaranteed locked-iPhone background navigation, complete national traffic data, multiple new external platforms or a wholesale brain/UI rewrite. Keep the October 2027 local-maintenance roadmap, and turn this week's repeatable task/review/test/release records into sanitized engineering examples for that later work. Do not read private assistant session logs under this plan without the separately reviewed access scope.
