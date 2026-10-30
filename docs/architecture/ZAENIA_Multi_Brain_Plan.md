# ZÆNIA multi-brain plan

Version 1 · 2026-10-30 · Claude, from Grey's request · Status: proposal for Grey's approval

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
| **Talk** | Talks with Grey: answers from what it knows and from short context; confirms and asks short questions | qwen3:4b (or llama3.2 3B if faster on this card), always loaded | First words within 2 s | GPU, highest priority |
| **Seek** | Quick lookups: semantic and system indexes, notes, records, calendar, Open Food Facts, web search and page reading. Returns a short evidence pack with sources | qwen3:4b (shared with Talk) plus embeddings | 3–15 s | GPU, second priority |
| **Keep** | Background jobs: security checks, backups, news and watch topics, index freshness, pattern learning ("Grey logs food late on PT days") | qwen2.5:1.5b, or none for jobs that need no model | Unlimited, but pauses while Grey talks | CPU first, GPU only when idle |
| **Study** | Deep research: multi-step plans, many sources, cross-checking, long write-ups | llama3.1:8b or qwen3:8b, long context | Minutes | GPU when free; queues behind Talk |

**Memory budget.**
- Loaded together: Talk/Seek (about 2.5 GB), embeddings (0.3 GB) and Study (about 5 GB).
- With room for their KV caches, that's about 9–11 GB of the 16 GB.
- Keep stays on the CPU.
- Ollama setting: `OLLAMA_MAX_LOADED_MODELS=3` and a small `OLLAMA_NUM_PARALLEL`. If Study needs the memory, it unloads while Talk stays loaded.
- These are estimates. Phase 1 measures them on this PC.

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
| 2. Conductor and Talk | `conductor.py`, Level 0 and 1, filler lines, the shared memory. Wake and sleep phrases with the voice check | Wake and sleep tests pass. Another voice can't wake ZAE. Chat feels faster |
| 3. Seek | Evidence packs from the indexes and the web; handoff and replies with sources | Lookup questions cite sources. A thin answer says so |
| 4. Keep | Scheduler: security checks, backups, news and watch topics, pattern learning to `personal_memory` with evidence, confidence and dates. It pauses while Grey talks | Jobs run on time. No jobs run during speech. Learned patterns can be viewed and deleted in Settings |
| 5. Study | Long research jobs, using the existing research agent and Desk | Research reports with sources appear in Research |
| 6. Tune | Ollama settings, priorities, model swaps, the evaluation scorecard (section 12) | Scorecard recorded |

## 7. Decisions for Grey

- Talk's model: qwen3:4b or llama3.2 3B. Phase 1 measures both, then Grey picks.
- Pattern learning: what Keep may learn and how long it keeps it (the plan's default is to keep everything visible and deletable in Settings).
- Whether Study may use the web without asking each time (default: yes, for public pages only, never logged-in accounts).
