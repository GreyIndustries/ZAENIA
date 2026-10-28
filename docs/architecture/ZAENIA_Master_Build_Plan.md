# ZÆNIA Master Build Plan

**Living architecture, hardware, reasoning, memory and security guide**

Version: 3.3  |  Date: 2026-10-26 (v1.0: 2026-10-20)  |  Status: working proposal

> Canonical collaboration format: Markdown. Companion DOCX is a reading/export copy. Neither file automatically synchronizes with the local ZAENIA installation.

## 1. Purpose and document authority

This is the living architecture and development plan for ZÆNIA (ZAENIA in filesystem paths). It is intended to be readable and maintainable by Grey, ChatGPT, and Claude. It records desired architecture, verified observations, unresolved questions, approved design decisions, priorities, and acceptance criteria. It does NOT claim to replace a direct inspection of the live codebase.
Status: Proposed v1.0 integration guidance, drafted 2026-10-20. Existing code has not been modified by this document. The 2026-10-16 filesystem audit is the most recent cited codebase audit; its results may have changed.
Repository placement recommendation: C:\Projects\ZAENIA\docs\architecture\ZAENIA_Master_Build_Plan.md. Keep a corresponding .docx export for reading. Commit the canonical Markdown alongside the code and review changes by diff.

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

## 13. Collaboration contract for ChatGPT and Claude

CANONICAL SOURCE: Markdown file in the ZAENIA repository, version-controlled. DOCX is a reading snapshot. Each assistant must read current plan, newest audit, and relevant actual files before recommending edits; do not infer current implementation from prior chats.
CHANGE PROCEDURE: (1) describe objective and changed sections; (2) cite actual code paths and evidence; (3) propose a decision with tradeoffs; (4) label proposed vs implemented; (5) make one narrow change set; (6) run tests and record results; (7) append dated change log; (8) update phase tracker and open questions; (9) preserve rejected decisions and why; (10) bump version.
COLLABORATION RULE: Never silently replace another assistant's confirmed decision. Conflicts produce an ADR (architecture decision record) explaining options, evidence, and final user-approved choice. User approval overrides model preferences. No merge-by-memory: re-open the canonical file on every new work session.
HANDOFF TEMPLATE: Date; author (Grey/ChatGPT/Claude); repository commit; baseline version; task objective; exact files examined; verified findings; hypotheses; proposed actions; files changed; security effect; tests performed/results; rollback; next actions; unresolved questions.
VERSIONING: MAJOR for architecture/security contract changes; MINOR for new modules or accepted designs; PATCH for clarifications/corrections. Include timestamp and digest where possible. Future updates are manual/triggered by a session or repository workflow; this document does not self-update.

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
