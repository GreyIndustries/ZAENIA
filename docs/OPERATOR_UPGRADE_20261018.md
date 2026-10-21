# ZAE operator upgrade — API 0.9.0

This implements practical first versions of the eight assistant gaps discussed
with Zack. Browser and documents come first, followed by spreadsheets, VS Code
and Blender. The existing amber/glass interface, movable windows, natural voice
attention and startup authentication remain in place.

## Start using it

Restart ZAE normally to load the new API and desktop build. The API was still
running 0.8.0 during the final read-only health check; it was not stopped or
changed to another authentication mode. Use the existing local passkey startup.

Open **Assistant → Operate**. In **Folders**, approve a specific existing local
working folder. These are separate from search/index permissions: they allow
controlled reads and creation of new output files. No folder has been approved
on the owner's behalf. Output operations preserve existing files.

In **Missions**, either describe a goal and ask ZAE to draft steps, or choose
operations and add their exact arguments. Save the draft, review each step,
check the review box, and run it from the paired desktop app. A local-model
proposal is never execution approval. Steps run sequentially; later steps can
use earlier evidence through `sourceStep` (zero-based). Mark a mission priority
when it should continue alongside conversation. Physical GPU resources can
still serialize model generation.

Example: read a public HTTPS page → summarize step 0 → create a new DOCX using
step 1. For research, substitute the public-search operation for the page read.
Every search query, URL and output destination is visible before execution.

Voice and typed chat share these entry points:

- “Research Python pathlib documentation” creates a research draft for review.
- “Draft a mission to …” queues a local structured proposal.
- “Show my mission progress” reads actual saved progress and the active session.

## What the eight additions do

| Area | Implemented | Practical boundary |
| --- | --- | --- |
| Verified task execution | Persistent exact-plan hash/revision approval, operation-specific permissions rechecked per step, progress, receipts, explicit priority, stop between operations, crash reconciliation. | Finite catalog, up to 20 sequential steps. No arbitrary shell/code execution. Model prose is not proof that work happened. |
| App operations | Separate browser reader/form preparation; TXT/MD/DOCX creation; TXT/MD/PDF/DOCX reads; XLSX reads/new workbooks/cell edits in copies; VS Code file/line requests; Blender scene inspection and object movement in a copy. | Browser submission/login and arbitrary app workflows are unsupported. Word layout fidelity is not automatically certified. Spreadsheet formulas are not calculated. VS Code focus is explicitly unverified. Blender work is performed in a separate background process. |
| Optional screen understanding | Choose one visible window, grant one capture, ask the installed local qwen3.5:4b model. HWND/PID/process creation time are checked; changed windows are rejected. | Off by default; one capture and two-minute expiry. No continuous watching, camera, raw-image storage or cloud vision. Credential-title filtering is a precaution, not a guarantee that a chosen window contains no private content. The interpretation can be wrong. |
| Long-term continuity | Owner-reviewed linked goals, people, projects, decisions, preferences and commitments; corrections, resolved/superseded states, source fields, relevant conversation retrieval, encrypted portable-profile round trip. | No silent import of an entire history or automatic invention of relationships. These records are separate from existing explicit facts and inferred key points. Correct/forget them in Continuity. |
| Proactive preparation | Factual suggestions for available project prerequisites, overdue saved tasks, upcoming event preparation, event overlaps, interrupted missions and selected daily availability. Dismissal persists. | Quiet in the Suggestions panel; no unsolicited speech or automatic external actions. Calendar checks use saved ZAE events, not a claim of a fresh Google sync. Existing notification quiet-hours settings remain separate. |
| Current research | Public search plus bounded, timestamped fetched pages, real URLs, retained source receipts, local evidence summaries, optional document output. | Search snippets are discovery hints. Retrieval verification proves the page was fetched, not that every claim on it is true. Model summaries are labeled unverified and retain source evidence. Sites can block access; PDFs go through Documents. |
| Cross-device handoff | Shared active session with summary, next step, optional mission, revision conflict detection, current mission progress and PC execution location. Phone uses existing authenticated web UI. Car-targeted handoffs enter the existing CarPlay audio briefing and deduplicate after playback. | No new public listener, credential migration or transfer of application windows. Phone cannot grant file/screen access or run desktop missions. Actual phone/CarPlay hardware acceptance remains necessary. |
| Recovery | Durable running markers before effects, saved verified receipts, dead/reused-process detection, queued cancellation reconciliation, uncertainty review, explicit safe resume, changed-file checks, source-snapshot rollback round-trip test. | No automatic replay of unknown changes. Existing Health controls handle service/model recovery; startup authentication is preserved. Source rollback does not restore installed applications, binaries or an OS. |

## Browser behavior

The initial browser integration opens a separate ephemeral **Microsoft Edge**
window. It uses no daily-browser profile or cookies. JavaScript, service workers,
downloads, non-GET requests and cross-site resources are blocked. Each allowed
request is fetched through the public-HTTPS retriever, which checks DNS and pins
the connection to the checked public address with normal TLS hostname validation.
Ordinary exact-labeled text fields can be prepared and read back; nothing is
submitted. Credentials, payment and sensitive identity fields are blocked.

This supports public reading and preparation. Dynamic/logged-in sites need
site-specific integrations in a later increment. The installed Edge channel was
confirmed; actual interactive browser launch/fill and VS Code focus were tested
with mocks, not driven against the owner's applications in this upgrade.

## Storage, permissions and recovery

State is in the existing private `data/assistant_platform/platform.sqlite3`.
Missions, receipts, approved working folders, continuity, handoff and dismissed
suggestions survive API restarts. Screen grants and browser sessions are
process-local. Raw screenshots are neither persisted nor added to memory.
Mission source results are saved intentionally for task continuity; review their
contents before using external queries or creating documents.

Permissions use existing authenticated API scopes. Local grants, screen access,
execution and uncertainty resolution also require the paired desktop key. Each
execution is bound to its immutable reviewed plan. Revoking a folder or desktop
pairing stops later steps. Source/web/screen text cannot grant permissions.

Polling returns bounded history and omits large receipt bodies inside SQLite;
open a mission's receipts to load full evidence. Histories include the latest
30 missions and up to 24 additional actionable missions. Records remain stored;
a known older mission ID can be fetched through the authenticated detail route.

If a process exits during a change, inspect the actual file/app and choose
**accept existing result** or **allow retry**. Acceptance is labeled unverified.
No automatic Undo is claimed for these app operations. New output filenames and
copy edits preserve originals; existing supported task/calendar/memory Undo stays
in Assistant → Approvals.

Portable profile payload version 2 adds continuity; old version 1 exports still
restore. Working-folder grants, active execution recipes/receipts, screen access,
browser sessions and handoff execution state are not portable permissions.
Profiles retain the existing encryption and local owner-authenticated workflow.

Optional libraries are pinned in `requirements-operator.txt`. No new model was
downloaded: the existing qwen3.5:4b supplies local vision; the configured local
conversation model supplies drafts and summaries. No OpenAI key or cloud brain
was introduced.

## Verification

- **305 backend regression checks and 181 existing frontend checks passed.**
  TypeScript, the web build and the Windows release build passed. The built
  executable is `desktop/src-tauri/target/release/desktop.exe` (26,682,880 bytes).
- Live synthetic/public checks are saved in `operator-live-check.json`: real
  two-step DOCX mission; public HTTPS retrieval; three fetched research sources;
  local evidence summary; complete structured two-step mission proposal with
  priority preserved and no execution; generated test-image recognition; separate background
  Blender scene copy reopened and verified at location [1, 2, 3].
- Local summary measured about 0.95 seconds, structured planning about 8.77
  seconds and synthetic vision about 0.20 seconds in the final run. These are
  individual observations, not end-to-end voice
  latency or guaranteed response times.
- Browser UI QA used an isolated preview: draft save/review, linked continuity
  save, handoff save, and 390px phone layout without horizontal overflow.
  Screenshots: `operator-mission-preview.png`, `operator-handoff-preview.png`,
  `operator-mobile-preview.png`.
- Synthetic screen tests never captured owner pixels. App tests never changed
  an existing Blender scene, opened the owner's daily browser or entered a
  passkey. No cleanup candidates were deleted.
- The existing simulated CarPlay test passed. A bootable SSD OS, destination
  cold start, actual microphone/camera use, real selected-window acceptance,
  and live phone/CarPlay acceptance are still separate readiness steps.

Build hashes and validation details are in `operator-verification.json`.
The completed source snapshot is `e557619f84b844a88675742acda97a20`:
350 files / 2,481,689 bytes, with every saved hash validated. It is a verified
post-upgrade source baseline for future changes, not a claim that all prior
installation files or binaries can be rolled back from it.

Planning uses the local Ollama structured-output schema and temperature 0,
separate from conversational response style. It retains the finite tool catalog,
validates dependencies/arguments independently and allows at most one repair
attempt. Summaries preserve actual source metadata independently of model prose;
unsupported model-generated URLs are removed from exported text. Owner review
still matters: valid JSON alone does not prove a proposed plan fully captures
the intended goal.

Primary implementation references:
[Playwright browser options](https://playwright.dev/python/docs/api/class-browsertype),
[Pillow selected-window capture](https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html),
[Ollama local vision](https://docs.ollama.com/capabilities/vision),
[Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs),
[Blender script security](https://docs.blender.org/manual/en/5.0/advanced/scripting/security.html).
