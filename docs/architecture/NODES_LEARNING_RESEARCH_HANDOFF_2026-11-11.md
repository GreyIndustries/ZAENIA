# Node navigation, learning and Research handoff

Status: implemented in an isolated candidate; not merged, installed or live-verified.

Branch: `codex/nodes-learning-research`.
Workspace: `C:\Users\zacka\.codex\worktrees\conductor-weekend\ZAENIA\.tmp\nodes-learning`.
Base commit: `cede912`, overlaid with the current primary checkout's source on 2026-11-11. The overlay includes pre-existing uncommitted Claude/Codex work; **do not commit or merge the whole workspace indiscriminately**. Integrate only the reviewed feature delta, preserving newer primary edits and remote history.

## Owner request and navigation

- Treat workspace tabs as nodes in presentation; preserve internal IDs for compatibility.
- Replace the duplicate top-level Health category with War Room; Fitness & Health remains unchanged in LIFE.
- LIFE contains Schedule Board (internal `plan`), Fitness & Health, Mail and GODSPEED. Mail moves from Assistant. Workbench moves from CREATE to BUILD.
- Arena is presented as LLM Training, opening its new Training modules screen first. Existing response comparison and benchmark tools remain available as evaluations.
- War Room contains Defense planning, Business plans and Cameras.
- Preserve accepted C1 core placement, current styles, F&H/GODSPEED implementation and owner data.

## Learning implementation and authority

Owner-authored lessons use the existing private PlatformStore with revisions, model assignments, protocol/action/response/correction categories, an example request and desired behavior, and an explicit enabled switch. Enabled examples can be retrieved for authorized conversation and local practice. Retrieval is bounded, relevant and scoped to the **actual selected model** at payload assembly. BrainService issues an ephemeral string-type marker only after its existing `memory.read` guard passes; ordinary chat/document strings cannot trigger those reads. Model contexts remain untrusted reference data and confer no execution permissions.

Practice runs up to three assigned, installed local chat models sequentially. A returned answer is marked `needs-owner-review`; there is no automatic pass, brain promotion, action execution, or weight modification. Reference learning is **not LoRA/QLoRA or foundation-model training**. Learning health reports actual insight-learning configuration and stored/reviewed counts; it deliberately does not call configuration alone a healthy worker.

## Research adaptation

All 47 supplied Quantum Python files were statically inspected (AST, declarations, dependency and data review); none were imported or executed. `QUANTUM_RESEARCH_REVIEW.json` records file hashes and declaration inventory. The original app's Tkinter windows, private paths, settings, HTTP wrappers and permission mechanisms are not installed in ZAE.

- Existing ZAE Library, news, translation, scripture, notebook, source fetching, watch and evidence machinery is retained.
- New Analysis workshop: deep dive, fact check, scenario check, timeline, source comparison and study guide/card drafts from pasted excerpts or an explicitly chosen saved topic. No automatic web search or memory save. Existing Web agent remains the online discovery path.
- Analysis uses the existing local model call and citation-support checker; caps excerpt budgets to leave context headroom. Labels excerpt sampling and distinguishes textual support from verified truth. Generated results are drafts; saving to Notebook is explicit.
- New offline Learning explorer: **1,557 reference entries in 15 categories**, extracted from literal data only. Includes alphabets, art, calendars, etymology, journeys, historical places/sites and other supplied learning material. Every imported entry is labeled unverified. Search, read and explicitly add to Notebook are supported.
- Study cards: saved questions, answers, source notes, reveal/hide and reviewed/reset state. These teach the owner, not model weights.
- The donor app's exact calendar-conversion algorithms, animated ancient-map borders/journeys, image-provider clients, spaced repetition, document-format export and every original widget are **not ported as equivalent features**. The review inventory is not a claim of full UI/algorithm parity. Public redistribution licensing for supplied content must be resolved before any public distribution.

## War Room

Business/defense plans have 19 individually editable sections: executive summary, problem/objectives, evidence, stakeholders, market/competitors, value proposition, products/services, pricing, marketing/sales, operations, team, financial assumptions, revenue/expense scenarios, funding/cash flow, risks, security/privacy, incident response/continuity, milestones/KPIs, and validation/open questions. Local drafts use owner-provided evidence and require an explicit Use draft / Save. Export is Markdown. Financial drafts are assumptions to validate, not market research or verified projections.

Camera registry stores explicitly entered HTTP(S) viewer links, names and locations. It rejects embedded credentials, query strings and fragments, does not scan networks or fetch camera endpoints, and labels connections untested. It provides explicit viewer links, **not live RTSP/ONVIF streaming, recording, motion alerts or active monitoring**. Device-specific camera integration remains subsequent work.

## Security, persistence and voice

New authenticated API routes reuse existing `memory.read`, `memory.write`, `status.read` and `chat.reply` scopes. Evaluation additionally checks read scope; analysis of a saved topic checks read scope. Unknown collections are denied; stale updates/deletions fail with 409. Camera passwords/tokens belong in the Vault, never in registry URLs. New features do not change auth, permission grants or protected execution paths.

Voice navigation uses the existing shared parser and guarded UI controls. Examples: “open LLM Training”, “open training modules”, “open learning health”, “open War Room”, “open business plans”, “open cameras”, “open Schedule Board”, “open mail”, “open analysis workshop”, “open learning explorer”, “open study cards”, “show nodes”, “close this node”. Named fields/buttons allow existing set/press commands, e.g. “set lesson title to …”, “press Save lesson”. Checkbox/model-choice voice behavior depends on the existing generic toggle handler; verify real recognized model names and select controls on owner hardware. Real microphone, physical phone, camera connections and production persistence remain unverified until observed.

## Candidate versions and validation

Candidate system **0.32.0**, UI **0.27.0**; LIFE, Research and LLM Training versions incremented, War Room 0.1.0; Core/memory/research module versions incremented. Reconcile against the latest accepted versions before integration. Detailed categorized notes: `docs/releases/NODES_LEARNING_RESEARCH_2026-11-11.json` and versions history.

Verified so far: 114 backend tests across new routes/tools, existing adaptive learning/review, Research, context budget, turn context, reply shape and Conductor; TypeScript; 15 new deterministic node/voice checks; existing nav/split (13) and page catalogue checks; six headless rendered desktop/phone checks. Native desktop and browser builds succeeded. One real synthetic lesson on installed `qwen2.5:1.5b` using CPU returned a nonempty answer with teaching examples; this establishes inference wiring, not general learning accuracy. Existing Vite large-chunk/static-dynamic import warnings and a Starlette TestClient deprecation remain; dependencies were not upgraded.

## Integration and release

No GitHub push, merge, owner install, live service restart or replacement of the served website is authorized by this handoff. Keep the running release untouched until owner-approved integration. Review only the feature delta against the primary snapshot; preserve Claude's in-progress files. After approval, integrate backend plus frontend together, run the documented checks against that result, stage desktop and web through the existing updater with `-RestartServer`, and let Grey install through Settings > Updates. An isolated review artifact is not an install-ready live update: the existing updater does not deploy new Core source by itself.

The Sunday whole-system target remains November 15. This feature supplements the performance/context sprint and does not replace its measurement/recovery gates.
