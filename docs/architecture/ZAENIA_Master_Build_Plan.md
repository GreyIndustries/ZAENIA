# ZÆNIA Master Build Plan

**Living architecture, hardware, reasoning, memory and security guide**

Version: 1.4  |  Date: 2026-10-21 (v1.0: 2026-10-20)  |  Status: working proposal

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
