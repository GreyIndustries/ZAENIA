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
- Tests: `core/personal_memory/phase3_test.py` 9; full suite 903 OK (14 skipped).
- Still partial: episodic memory is the conversation log plus topic threads, without its own reviewable "episode" records.
