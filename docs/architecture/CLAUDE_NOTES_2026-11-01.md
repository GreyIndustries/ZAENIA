# Claude notes, 2026-10-31 to 2026-11-01 (to fold into the Master Build Plan as 28.49+)

Codex has uncommitted edits to `ZAENIA_Master_Build_Plan.md` (its section 28.48, the Identity and Product Charter) in the live checkout, so these entries are kept here until that lands; then they move into the plan as 28.49 onward.

## Top bar categories (v3.46)
The core's six categories sit in the top bar beside Home (`components/TopCategories.tsx`); hover or click opens a drop-down of that category's tabs. Desktop only.

## Core: Saturn rings, live upgrades
- The core's six icons are gone; its nerves are drawn as Saturn-like rings (`neuralField.ts`, ringed layout). Black-hole and JARVIS experiments were previewed and scrapped at Grey's request.
- Live upgrades Grey picked (`CoreExtras`): (1) ring colour follows ZAE's state (listening blue, thinking gold, speaking white, resting dim amber); (2) ripples through the rings while she speaks (a speech-like rhythm, not yet the real audio level); (3) one bead per running background job on the middle ring, up to six; (5) a night side across the sphere from 7 pm to 6 am. Ring tilt (4) is not used. Preview switches: localStorage `zaenia.corePreview`.

## Hand gestures for actions
`core/gestureActions.ts` (29 node checks, `scripts/gestures.test.cjs`): open-hand swipes (previous/next tab, Home, minimise), 1–5 fingers held (Plan, Health, Know, Create, Build), rock sign (System), open palm while ZAE speaks (stop), fist held (Calm view), peace sign (mic), thumbs up/down (confirm/dismiss the newest card; forget-memory, app-launch and workspace cards stay voice/click only), pinch held (close tab). Camera frames stay in memory; only landmarks are used.

## Phone web app: sign in every time; Face ID
- Every open of the phone web app ends the earlier sign-in and shows the sign-in screen; two minutes in the background signs out (`App.tsx`).
- Face ID (`core/api/face_passkey.py`, `core/api/face_passkey_test.py` 7): a WebAuthn passkey on the iPhone. Adding one needs a signed-in phone and Grey's approval on the PC (desktop key; a prompt appears; unapproved keys expire after 10 minutes). Sign-in checks challenge (single use, bound to a cookie), rp id hash, origin, user-present and user-verified flags, and the P-256 signature; it gives the same phone session as voice sign-in. Keys are public-key only in `data/secure/phone_passkeys.json`; Settings › Phone Face ID lists and removes them. Verified on Grey's iPhone 2026-11-01 (audit: registered, signed_in).

## Voice trial records PC voice
The trial round is kept in `data/voice_trial.json`, so the PC voice service (separate process, which owns the mic while running) records its checks and lowest window score too. Grey's first run was not recorded because only the app mic was counted.

## Phase 3 (learning and self-correction): exit checks closed
Audit result: verified preferences, the proposal queue, pattern extraction, owner review, forget, conflict detection and most no-store rules already existed with tests. Added:
- **Rollback**: `UserMemory.restore` brings back an earlier (superseded/historical) value or keeps one side of a conflict, recorded as an owner correction (nothing deleted, provenance "Owner restored this value"). Routes `GET /api/assistant/profile/{id}/history`, `POST …/restore` (memory.read / memory.write). Profile review has History with Restore / Keep this.
- **Provenance in one place**: `core/personal_memory/overview.py` and `GET /api/assistant/memory/all` combine "You told me", the profile ledger (with evidence count and latest quote, status) and "Noticed" insights (with the words they came from). Assistant › Everything remembered.
- **No-store**: `core/personal_memory/no_store.py`: a sentence that starts or ends with "off the record", "don't remember/save this", "between us" is answered but not logged or learned from; "go off the record" starts a stretch that ends with "back on the record" or after 30 minutes. In memory only.
- **Permission non-escalation**: tests show permission/authorization/security keys can't be learned, a sentence claiming permission doesn't become an active preference, retrieval carries "never authority to execute", and the approval policy comes only from its own setting (forgetting memory always needs review).
- Tests: `core/personal_memory/phase3_test.py` 9; full suite 902 OK (14 skipped).
- Still partial: episodic memory is the conversation log plus topic threads, without its own reviewable "episode" records.

## Carbs, fat, sugars and cholesterol supported fully (2026-11-01)
Grey's day view showed "Not fully reported" for carbs, fat, sugars, sodium and cholesterol because two plain totals ("42 g protein", "750 calories") carried no other nutrients, and the sum gave up when any food lacked one.
- `chat_actions.fill_from_catalog`: a named food logged with only some numbers gets the rest from the closest USDA FoodData Central match, scaled so its calories (or protein, or carbs) equal Grey's; his own numbers never change; the source says so. Cholesterol can now be stated ("cholesterol 95mg").
- Generic names ("fitness & health", "food log", "nutrition"…) are not food names; the same entry twice within two minutes is logged once.
- `fitness_summary` adds `{nutrient}Known` and `coverage`; the Fitness day view shows the known sum with "from X of Y foods" instead of "Not fully reported".
- Tests: `chat_actions_test` +2; full suite 904 OK (14 skipped).

## Brain check (2026-11-01)
Live test of all four brains through the app's own calls (RTX 4070 Ti SUPER, 16 GB): Talk qwen3.5:4b 6.1 s cold / 0.1 s warm, Seek qwen3.5:9b 5.8 s / 0.1 s, Study qwen3:14b 12.8 s / 0.1 s, Keep qwen3:1.7b on CPU 2.7 s / 0.5 s; every answer correct, no thinking text leaked. Chat path: greeting 0.1 s (quick_self), normal question on Talk, web question on Seek with sources. Fixes:
- `core/brain/warmup.py`: the server loads Talk and the topic embedder at start (skipped while gaming), so the first reply after a restart isn't a cold start.
- `seek.evidence_context` tells Seek it just searched the web; it had answered "I can't search the live web myself" while citing the sources it was given.

## Build requests: ZAE as a coding helper (Grey's options 2 and 3, 2026-11-01)
Plan: `docs/architecture/ZAE_Coding_Helper_Plan.md`. Grey picked Claude Code (main) and Aider with the local Study model (small changes, offline).
- `core/assistant_platform/build_helper.py`: "ZAE, build ... on the X tab" / "change your code so ..." (chat and PC voice; plain "build muscle" isn't caught) or Code Doctor > Build requests. Talk writes a brief (title, size, likely files); nothing runs until Grey taps Start (desktop key or near pass). One request at a time, waits while gaming.
- The copy: a git worktree `C:\Projects\ZAENIA-Helper` on `zae/<id>` from live HEAD, sharing `desktop/node_modules` through a junction (removed before the copy is deleted). No data/, secrets or .env. Charter and the public scripture corpus are lent only while the security suites run, never while a tool runs.
- Tools: Claude Code headless (`-p`, acceptEdits, no Bash/web/MCP, project settings only); Aider 0.86 in `C:\Projects\ZAENIA-Tools\aider` (its own Python 3.12 venv; installed with Grey's OK) on `ollama_chat/qwen3:14b`, no shell suggestions, no auto-commits. Tool and test environments drop secret-like variables.
- Locked paths (`LOCKED` plus Code Doctor's and the file tools' lists): security, voice check, passkey, auth, permission routes, client gate, game mode, scripts/, .github, .claude, src-tauri, package.json, AGENTS/CLAUDE.md, data/, and the helper itself. Any hit throws the work away.
- Checks in the copy: full Python suite, the three security suites, and for app changes the UI checks and TypeScript. Failures go back to the tool twice. Ready requests show summary, files, results and diff; Grey gets an inbox notice.
- Approve and Undo (desktop key only): merge (ff or --no-ff) into the live checkout; undo is a git revert. The desktop app then restarts the server itself (restart_server) if Python changed and asks the server to run `zae.ps1 build` if the screens changed. (A one-off scheduled task for this was considered and dropped.)
- Nightly ideas (`build_ideas.py`): 1-5 a.m., once a day, not while gaming or building. Signals from the last day: repeated requests, "couldn't" replies, "done/logged" claims with no action, corrections, parts that went down. Study writes at most 3 evidence-backed "Fix" suggestions; no signals, no ideas. Suggestions has Build it, Add to plan, Not now and Never (never-list goes into the prompt).
- Verified: Claude Code and Aider each fixed real code in a temp repo; a full request ran end to end on the live code (tested and ready in about 2 minutes); live node_modules untouched. Tests: build_helper_test 11, build_ideas_test 4; full suite 919 OK (14 skipped).
- Note for Claude/Codex: approved ZAE builds are commits on the live branch, so merge the live branch into a dev branch before the next fast-forward.

## Development environment audit follow-up (2026-11-01)
Grey asked to fix `ZAENIA_DEVELOPMENT_ENVIRONMENT_AUDIT.md` and download the needed Python.
- Python 3.11.9 from python.org (Authenticode: Python Software Foundation, valid): the installer upgraded the existing per-user Python 3.11.0 in place to 3.11.9 (`%LOCALAPPDATA%\Programs\Python\Python311`; no PATH, launcher or file-association changes). `.venv311_backup` now reports 3.11.9. The live `.venv` (3.13.15) is unchanged. Installer kept in `C:\Projects\ZAENIA-Tools\downloads`.
- Verified what the audit couldn't: AMD Ryzen 9 7900X (12 cores / 24 threads), 31 GB RAM; RTX 4070 Ti SUPER 16 GB; Ollama 0.40.11 listening on 127.0.0.1:11434 only, Talk 100% on the GPU; all four brains answer correctly (see Brain check above).
- Gitleaks 8.30.1, redacted: all Git history (`--all`) 0 findings; tracked changes plus untracked, not-ignored files in the live checkout 0; ChatGPT worktree's 2 untracked files 0; Claude worktree has none. The earlier ~79 came from a full folder scan that includes ignored personal data and dependencies, which are not in Git.
- Left for Grey: moving the main `.venv` to 3.11.9, OpenCode, the separate Windows account for a development controller, GitHub secret-scanning/branch-protection settings.

## OpenCode with local Ollama (audit step 4, 2026-11-01)
- OpenCode 1.19.5 installed in `C:\Projects\ZAENIA-Tools\opencode` (npm, local folder; its postinstall script was not run and isn't needed). Start it with `C:\Projects\ZAENIA-Tools\opencode\zae-opencode.cmd` from the folder to work in.
- `opencode.json` there: only the `ollama` provider is enabled (OpenAI-compatible endpoint `http://127.0.0.1:11434/v1`), sharing and auto-update off. Models: `zae-code:14b` (an Ollama alias of qwen3:14b with a 16k context, from `Modelfile.zae-code`; no download) and `qwen3.5:9b` as the small model.
- Verified: `opencode models` lists only the two local models; `opencode run` fixed a bug in a throwaway repo in about a minute using its read and edit tools. Code goes only to Ollama on this PC (OpenCode fetches its provider package from npm the first time).
- Not wired into Build requests (Claude Code and Aider are). The 14B model at 16k needs about 12 GB of graphics memory, so Talk unloads while it runs.
