# ZÆNIA multi-brain plan

Version 2 · 2026-10-30 · Grey-approved direction; Phase 2 underway · Status: implementation in progress

## 1. What Grey asked for

Four brains that work as one:

1. **Talk.** Conversations. It is fast and light and knows the local data well. If it can't answer in 2 seconds, it says so ("I'm looking through our data" or "Checking online sources") and keeps the conversation going while another brain finds the answer.
2. **Seek.** Gets information quickly from this PC and from the web, and hands it to Talk.
3. **Keep.** Runs in the background:
   - security checks, backups, and news and info tracking;
   - learning Grey's patterns, behaviours and personality.
4. **Study.** Research that is as thorough and detailed as possible.

A multi-level reasoning layer connects all four, so ZAE answers with one voice.

The same layer drives the new wake-up and sleep phrases. Their responses depend on the situation, and Calm view and the dashboard react to them.

## 2. What exists today (checked 2026-10-30)

**Hardware and models:**
- GPU: RTX 4070 Ti SUPER with 16 GB of VRAM.
- Models in Ollama: llama3.1:8b (4.9 GB, the current brain), qwen3:8b (5.2 GB), qwen3.5:4b (3.3 GB), qwen3:4b (2.5 GB), llama3.2 3B (2.0 GB), qwen2.5:1.5b (1.0 GB) and nomic-embed-text for embeddings (0.3 GB).

**Code that already does part of each brain's job:**
- `core/brain/`: `brain_router.py` already routes some questions to a grounded, local-evidence path (`grounded_answer`, `hybrid_retriever`, `semantic_index`, `system_index`).
- Research: `core/research/agent.py` (the web agent and watch topics), `analyze.py` and `desk.py`.
- Background:
  - security self-checks and backups (Status & Security);
  - the tech news refresh;
  - screen watch;
  - `core/personal_memory` (owner profile and user learning).
- Voice: every app-mic turn is already checked against Grey's voice (decided 2026-10-28: keep every turn).

**What's missing:** one coordinator that runs more than one model at once, a time budget with filler lines, a shared working memory between brains, and a background scheduler that steps aside while Grey talks.

## 3. The four brains

| Brain | Job | Model (starting point) | Budget | Runs on |
|---|---|---|---|---|
| **Talk** | Talks with Grey: answers from what it knows and from short context; confirms and asks short questions | **qwen3.5:4b** in non-thinking mode (already installed, about 3.3 GB), always loaded | First words within 2 s | GPU, highest priority |
| **Seek** | Quick lookups: semantic and system indexes, notes, records, calendar, Open Food Facts, web search and page reading. Returns a short evidence pack with sources | **qwen3.5:9b** (about 6.5 GB, strong tool calling) plus nomic-embed-text | 3–15 s | GPU, second priority |
| **Keep** | Background jobs: security checks, backups, news and watch topics, index freshness, pattern learning ("Grey logs food late on PT days") | **qwen3:1.7b** on the CPU (qwen2.5:1.5b, installed, until then), or none for jobs that need no model | Unlimited, but pauses while Grey talks | CPU first, GPU only when idle |
| **Study** | Deep research: multi-step plans, many sources, cross-checking, long write-ups | **qwen3:14b** day to day (about 9.3 GB); **gpt-oss:20b** (about 14 GB) for overnight deep runs when Talk can unload | Minutes | GPU when free; queues behind Talk |

**Memory budget.**
- Loaded together: Talk/Seek (about 2.5 GB), embeddings (0.3 GB) and Study (about 5 GB).
- With room for their KV caches, that's about 9–11 GB of the 16 GB.
- Keep stays on the CPU.
- Ollama setting: `OLLAMA_MAX_LOADED_MODELS=3` and a small `OLLAMA_NUM_PARALLEL`. If Study needs the memory, it unloads while Talk stays loaded.
- These are estimates. Phase 1 measures them on this PC.

### 3.1 Best model for each brain (researched 2026-10-30)

Grey asked for the best model for each role. These are picks for this PC's 16 GB RTX 4070 Ti SUPER, from current published comparisons. They are not measured on this PC yet; Phase 1 times them here before anything is switched.

- **Talk: qwen3.5:4b (already installed).** Small enough to stay loaded beside the others, and fast with thinking turned off. Backup: llama3.2 3B (installed). Larger chat picks such as gpt-oss:20b (about 14 GB, reported 80–140 tokens a second on 16 GB cards) would leave no room for the other brains.
- **Seek: qwen3.5:9b.** The Qwen 3 family is the most often recommended for reliable local tool calling, and the 9B ran at about 91 tokens a second in a 16 GB test using 9.3 GB. It fits next to Talk (about 10 GB together). Needs a download.
- **Keep: qwen3:1.7b on the CPU.** Background jobs don't need speed, and keeping it off the GPU leaves the card for Talk and Seek. Most Keep jobs (backups, security checks, news refresh) need no model at all. Needs a download (qwen2.5:1.5b, installed, works until then).
- **Study: qwen3:14b, with gpt-oss:20b for overnight deep research.** qwen3:14b is the common pick for instruction-following at this size (about 62 tokens a second in a 16 GB test, 12 GB in use with its context). gpt-oss:20b is the strongest model that fits whole on a 16 GB card, but at about 14 GB it can only run when Talk and Seek unload, so Keep schedules it for overnight jobs or when Grey says "take everything to the background". Avoid models that spill past the card's memory: one 15 GB model fell to about 5.5 tokens a second.
- **Not chosen:** Phi-4 14B (reported weak at tool calling), DeepSeek-R1 14B (good reasoning but slow and chatty for tools), Gemma 4 26B-A4B (strong, but about 15 GB leaves no room for Talk).

**Memory plan with these picks:** Talk 3.3 GB + Seek 6.5 GB + embeddings 0.3 GB, about 10 GB loaded at once with their caches. Study's qwen3:14b loads when called, and Seek unloads to make room. Keep runs on the CPU.

**Downloads needed (about 17 GB in total):** qwen3.5:9b, qwen3:14b, qwen3:1.7b, and later gpt-oss:20b. Nothing has been downloaded; Grey approves first.

Sources: [Best LLMs for Ollama on 16GB VRAM GPU (benchmarks)](https://www.glukhov.org/llm-performance/benchmarks/choosing-best-llm-for-ollama-on-16gb-vram-gpu/), [Ollama models by VRAM](https://computingforgeeks.com/ollama-models-cheat-sheet/), [Best local LLMs for 16GB VRAM in 2026](https://runaihome.com/blog/best-local-llm-16gb-vram-2026/), [Best Ollama models ranked (October 2026)](https://www.morphllm.com/best-ollama-models), [Best Ollama model for tool-calling agents](https://webscraft.org/blog/yaku-model-ollama-obrati-dlya-agenta-z-tool-calling-porivnyannya-i-benchmarki?lang=en).

### 3.2 Phase 1: measured on this PC (2026-10-30)

Grey approved the downloads; all four are installed. Each model was loaded alone, then given three short prompts (4,096-token context, thinking off where the model allows it). Graphics memory is what loading the model added.

| Model | Role | Cold load | First word | Speed | Graphics memory |
|---|---|---|---|---|---|
| qwen3.5:4b | Talk | 4.6 s | 0.07 s | 122 tokens/s | 3.7 GB |
| qwen3.5:9b | Seek | 6.1 s | 0.09 s | 79 tokens/s | 6.3 GB |
| qwen3:1.7b | Keep | 7.6 s | 0.04 s | 245 tokens/s (on the card) | 1.7 GB |
| qwen3:14b | Study | 16.0 s | 0.06 s | 54 tokens/s | 8.9 GB |
| gpt-oss:20b | Study, overnight | 25.0 s | 2.67 s (it always reasons first) | 121 tokens/s | 12.3 GB |
| llama3.1:8b | today's brain | 4.3 s | 0.04 s | 108 tokens/s | 4.9 GB |

**What this means:**
- Talk (qwen3.5:4b) easily meets the 2-second rule, with the first word in under a tenth of a second once loaded.
- Talk and Seek together take about 10 GB, and Talk with Study (qwen3:14b) about 12.6 GB, so both pairs fit on the 16 GB card.
- gpt-oss:20b is fast once it starts, but it reasons before every answer and needs 12.3 GB, so it stays an overnight Study model as planned.
- The phase 1 exit criterion (Talk's first words in under 2 s) is met.
- Phase 2 is implemented on `codex/conductor-weekend-2`: desktop/browser chat and owner-verified PC voice route through Talk (qwen3.5:4b); warm Talk gets a 2-second first-text budget and a cold Talk load gets up to 8 seconds, based on Ollama's local `/api/ps`. If Talk times out or fails, the Conductor retries through Seek (qwen3.5:9b). Wake/sleep replies also use Talk. Thirty-one focused API, voice and Conductor tests pass. Live local turns measured 3.91 s on the cold Talk load and 0.16 s warm; an actual Seek handoff returned a correct answer with `execution_authorized=false`. Live speaker-authentication trials remain.

## 4. Multi-level reasoning (the Conductor)

One coordinator, `core/brain/conductor.py`, takes every turn (typed, app mic or PC voice) through these levels. It stops at the first level that can finish the turn.

- **Level 0: Reflex** (rules, no model, under 50 ms).
  - Wake-up and sleep phrases, "stop", tab and layout commands, and the exact-phrase actions that already exist.
  - Checks the speaker's voice first, so wake-up and sleep phrases only work for Grey.
- **Level 1: Talk** (2 s budget).
  - Classifies the turn as chat, quick fact, needs lookup, research, an action or a background request.
  - Answers directly if it can.
  - If it isn't sure within 2 s, it speaks a filler line that fits the need, such as "I'm looking through our data" (local) or "Checking online sources" (web), and hands off to Seek.
- **Level 2: Seek** (evidence).
  - Builds an evidence pack: facts, sources and confidence.
  - Talk turns it into the reply in ZAE's voice, citing where things came from.
  - If the evidence is thin, Talk says so plainly instead of guessing.
- **Level 3: Study** (deep).
  - Used when Grey asks for research, or when Seek finds the question needs many sources.
  - Talk confirms ("I'll dig into that properly; it'll be in Research when it's ready"), and Study runs as a job.
  - The result goes to Research › Desk or the Evidence board, plus a short spoken summary.
- **Background: Keep.**
  - Scheduled and triggered jobs.
  - It writes findings to the shared memory and never speaks unless something needs Grey: a failed check, a reminder, or a new item on a watched topic.

**The shared working memory (the "blackboard").**
- It is one small store for the current situation:
  - the active tab;
  - what is running;
  - the last few turns;
  - the latest evidence packs;
  - Keep's recent findings;
  - the time, the calendar and the training day.
- Every brain reads it. Only the Conductor writes "decisions" to it.
- This is how the four brains stay in step and talk as one ZAE.

**Rules that don't change.**
- Brains only propose. Actions still go through Engine 3 (permissions, fresh grants and audit), and nothing a model writes can skip it.
- Web and book text stays untrusted data and is never treated as instructions.
- ZAE never claims human feelings or experiences. Grey makes the decisions.

## 5. Wake-up and sleep phrases (uses Level 0 plus Talk)

**Wake-up calls.** They only work in Grey's voice, from any screen.
1. "Wake up sleepy, we have work to do"
2. "Sleeping on the job?"
3. "The boss is here"
4. "Zae, you're still there?"
5. "The day is not yet over" / "The night is still young"

**How a wake-up works.**
- Matching is fuzzy, so small wording changes still count. If the voice isn't Grey's, nothing happens and nothing is said.
- Calm view always exits to the dashboard, whatever screen was open before.
- Talk writes the reply from the situation: the time of day, how long ZAE was calm, what Keep found while calm, what's next on the calendar, and any jobs that finished.
- Replies are short, either a statement or a question, in a JARVIS-style tone, for example:
  - Morning, after a long calm: "Morning. Three things moved overnight; the backup is done and PT is at 8:30. Shall I brief you?"
  - "The boss is here" in the evening with work open: "Welcome back. Your weekly reset is still open and due at 9:55."
  - "Sleeping on the job?" with nothing new: "Never fully. All quiet; nothing needed you."
- The dashboard opens to match the reply. If the reply mentions PT, the calendar card is highlighted. If it mentions a finished job, its result card is shown first.

**Sleep phrases:**
1. "Take everything to the background"
2. "I'm going to sleep"
3. "Let's put a pin in this and continue tomorrow"
4. "Calm view"

**How a sleep phrase works.**
- Running work moves to Keep and Study as background jobs and continues while calm.
- Anything that can't safely run alone is paused and noted.
- Talk answers to fit what was happening:
  - "I'm going to sleep" at night: "Good night. I'll finish the research and have it ready at 7."
  - "Put a pin in this" in the middle of a task: "Pinned. I saved where we were in Workbench."
- ZAE then switches to Calm view.

Phrases, the speaker check and the replies all go through Level 0 and Talk. The fixed phrase lists live in one settings file, so Grey can add his own.

## 6. Phases

| Phase | Builds | Done when |
|---|---|---|
| 1. Measure | Time each model on this PC: time to first word, tokens per second and VRAM. Pick Talk's model | A table in this doc. Talk's first words land in under 2 s for 9 of 10 test questions |
| 2. Conductor and Talk | `core/brain/conductor.py`, Level 1 Talk and Seek retry, filler, bounded in-memory blackboard; Level 0 remains in deterministic permission-checked routes. Wake/sleep replies use Talk | Merged to `main`, built and installed. 35 focused Python Conductor/Seek/Keep/Research tests pass. Warm Talk and real Seek handoff verified locally. Live speaker rejection remains to verify |
| 3. Seek | Evidence packs from local indexes and explicitly requested web lookups; handoff and replies with sources | Merged to `main`, built for desktop and browser, and live on Core. Current/online lookup routes to Seek, gathers up to four public sources, labels page text untrusted, and returns source references to chat. Local grounded-system answers expose verified index paths. No-source lookups return a deterministic cannot-verify answer. Verify live citation quality |
| 4. Keep | Existing startup services handle security checks, backups, news and watch topics; pattern learning uses evidence-reviewed `personal_memory`. Keep is pinned to qwen3:1.7b on CPU, and model calls use the background priority gate | Merged to `main`, built and installed. Insight rules reject sensitive/unsupported facts and provide review/delete controls. Focused tests pass; verify Keep preemption while speaking |
| 5. Study | Long research jobs, using the existing research agent and Desk | Merged to `main`, built and installed: web-agent research uses qwen3:14b through local background-priority model calls and keeps source links in the report. Keep watch summaries use its CPU model. Tests pass. Overnight gpt-oss:20b scheduling remains a later optional optimization |
| 6. Tune | Ollama settings, priorities, model swaps, the evaluation scorecard (section 8) | Initial measurements are recorded below. Live voice rejection, citation quality, Keep preemption, and the 9-of-10 Talk evaluation remain |

## 7. Decisions for Grey

- Approve downloading the picked models (qwen3.5:9b, qwen3:14b, qwen3:1.7b; gpt-oss:20b later). Phase 1 then measures them on this PC before switching.
- Pattern learning: what Keep may learn and how long it keeps it (the plan's default is to keep everything visible and deletable in Settings).
- Whether Study may use the web without asking each time (default: yes, for public pages only, never logged-in accounts).

## 8. Evaluation scorecard — 2026-10-30

| Measure | Current evidence | Status |
|---|---|---|
| Talk warm first text | 0.16 s measured locally; target under 2 s | Pass on the sampled turn; 9/10 evaluation set still needed |
| Talk cold first text | 3.91 s measured locally; cold window is 8 s | Pass on the sampled cold turn |
| Seek handoff | Real local qwen3.5:9b answer returned in about 1.02 s when loaded | Pass on the sampled handoff |
| Seek evidence and citations | 10 focused tests cover public source bounds, untrusted text, source refs and empty-source refusal | Automated pass; live web citation quality not yet measured |
| Keep memory safety | Evidence must quote an owner statement; sensitive categories are rejected; inferred points remain reviewable/deletable | Focused tests pass; model is pinned to qwen3:1.7b CPU |
| Keep priority | Existing coordinator tests verify ordinary background work yields to foreground slots; new Keep/research calls use that gate | Automated pass; verify live speech under load |
| Study reports | Research agent uses qwen3:14b locally and preserves source links; prior local measurement was 54 tok/s at 8.9 GB VRAM | Integration tests pass; fresh timing not collected |
| Action authority | Conductor tests assert `execution_authorized=false`; existing Engine 3 routes remain unchanged | Automated pass; no model output is an execution grant |
| Voice owner rejection | Existing design checks the enrolled speaker before admitting PC voice | Live owner/other-speaker trial pending |

This is an initial scorecard, not a claim of production-complete evaluation. Core has been restarted and the new build is installed; complete the remaining live checks on this runtime, starting with owner/other-speaker rejection.

## 9. Claude handoff — next actions, 2026-10-30

The Conductor implementation through Phase 5 is merged, installed and live. Continue with verification and tuning; do not rebuild those phases from scratch.

1. **Start at the shared head:** fetch `origin/main` at `faaddbc`, then create a new feature branch. The recovery point `zaenia-pristine-2026-10-30` (`d84d62b`) is pushed to GitHub. The earlier `codex/conductor-weekend-2` branch is stale after merge. Do not merge without owner approval.
2. **Voice gate:** test enrolled-owner acceptance and other-speaker rejection through the current voice recognition path. Keep startup authentication, passkey behavior, thresholds and Engine 3 permissions unchanged. Record the test conditions and observed outcomes.
3. **Seek citations:** in the running app, ask a question that explicitly needs current public information. Confirm source references reach the UI as links, empty evidence yields the cannot-verify response, and page text cannot cause an action. Do not test using private or logged-in pages.
4. **Keep preemption:** run a background Keep task while Talk is responding and audio is active. Confirm foreground Talk wins, stale work can yield/cancel as designed, and background work reports progress when the owner marked it priority. Add focused regression tests for any defect found.
5. **Phase 6 scorecard:** use a fixed nine-prompt Talk set; record warm first-token latency for all nine and cold start separately. Record Seek handoff, Keep CPU load/preemption, and Study latency/VRAM with model versions and machine conditions. Update section 8 with measured results; leave unmeasured cells pending. `gpt-oss:20b` overnight scheduling is still optional future work.
6. **Release only if code changes:** run affected tests, `npm run build`, `npm run build:web`, and `npm run tauri build -- --no-bundle`; update `desktop/dist-web` and the installed app only under `AGENTS.md` release instructions. Preserve the recovery tag and never commit secrets, credentials or personal data.

**Runtime:** the production Core is live on `127.0.0.1:8766`; the Vite development server on `127.0.0.1:1420` is stopped. In the current sandbox, Python fixture tests must set `TEMP` and `TMP` to a writable directory inside the project. Latest verified build/test status is in `HANDOFF_2026-10-30.md` section 7.
