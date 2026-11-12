# Sunday integration and repository untangle handoff — 2026-11-12
+
+Owner authorized implementation, publication, and corrected dependency order. Deployment stays held for Sunday November 15, America/Los_Angeles. Codex is release owner; Claude reviews the focused security/updater/execution diff on Saturday/Sunday.
+
+## Correct order
+1. Preserve sanitized shared WIP locally; reconcile the installed source onto fetched origin/main, preserving LICENSE.
+2. Validate updater runtime root, stale-version receipts, install lifecycle, copy retries, rollback, reconnect and What's new.
+3. Make local Aider the automatic coding path; retain only explicit per-request Claude opt-in with allowance labeling.
+4. Add guarded Mail/Map conversation support and verify desktop/phone navigation.
+5. Combine the accepted C1 core correction, nodes, learning, War Room and Research expansion; run final checks and both builds.
+6. Publish the installed baseline on main and Sunday work on release/2026-11-15; keep installation/restart held. Claude reviews main...release before final Sunday staging/owner installation.
+
+## Source provenance and preservation
+Local safety branch: wip/shared-root-2026-11-12, commit fbf8062. It excludes private runtime data, tool histories/caches and old private charter copies, and is not pushed. A narrowly annotated localStorage identifier was the only scanner false positive. No live source files were discarded.
+
+Installed baseline: codex/installed-baseline-20261112 reconstructs system 0.31.1 / UI 0.26.0 from sanitized shared source plus the pre-C1 backup recorded at core-c1-before-20261111-222137. It preserves fetched origin/main 642a36c and its LICENSE. Baseline Python: 1115 tests, no failures/errors, 14 existing skips; native/web builds passed. Original feature branches remain, because source reconciliation does not safely merge all their histories; no dirty or unique worktree was pruned.
+
+Sunday source: release/2026-11-15 includes the owner-approved 36-file node/learning delta, C1, installed feature source and the new packet changes. Detailed notes: docs/releases/SUNDAY_2026-11-15_RELEASE_NOTES.json (18 categorized entries). Versions: system 0.32.0 / UI 0.27.0. Stream Studio runtime experiments, native CarPlay drafts and login-gate phase1 practice remain out; their existing planning documents may remain as plans.
+
+## Implemented changes
+- Runtime-native root selection from trusted environment or root.json, validated real-deployment fallback; no temporary build roots. Existing auth and passkey prompts remain.
+- Installer CheckOnly, explicit -Root, ZAE-specific process selection, graceful/forced close, copy retries, .NET SHA-256 independent of PowerShell module availability, website+executable recovery.
+- Pending updates compare completed-install receipts, not ahead-of-install source metadata. Same/older receipts cannot offer Install. Visible updates poll after reconnect; latest installed notes show What's new.
+- Local coding at every automatic task size, with no online probe or silent paid fallback; model/attempt metadata and explicit Claude allowance label.
+- Private failed-local-build packets excluded from Git; 20 real historical tasks seeded and provenance-validated. No model success-rate baseline is claimed. Larger retrieval, per-step planning, weakened-test detection and overnight models stay on the phased local-coder roadmap.
+- Mail reference retrieval is guarded by memory.read. Save work commute stores chosen endpoints explicitly; chat invokes existing GODSPEED routing with guarded personal/status reads and no GPS/work guesses or invented ETA. F&H and existing routing/traffic/weather behavior is preserved.
+- Critical isolated CI job uses separately pinned test-only dependencies; production requirements unchanged. Its exact 45-test subset passes locally. GitHub's Linux/Python 3.11 run remains a separate result, not assumed passed from local Windows tests.
+
+## Verification
+Local Python runtime: 3.13.15. Complete Sunday backend/security run: 1147 tests, 0 failures, 0 errors, 14 existing skips. New critical cases are not skipped. Eight standalone Rust root-resolution tests pass. All 38 non-browser frontend suites pass. Six new-screen rendered checks pass. The navigation suite's 32 unaffected cases passed; the renamed node-manager case passed on its corrected rerun (all 33 behaviors verified). Native and web builds pass. Existing Vite chunk/import warnings and Starlette TestClient deprecation remain documented, without a dependency upgrade.
+
+Two existing test contracts were corrected rather than assertions removed: self-map checks now match the actual LIFE/Settings and new node destinations; the synthetic IMAP fixture uses a fixed November 8 clock. Inventory tests retain exhaustive unique-route checks and update the exact destination count to 112. No test was disabled to make the release pass.
+
+## Still requires real owner/device evidence
+Claude's independent security review; actual PDF attachment View; an exact-recipient/text approved real reply send (none sent); actual microphone and physical phone; post-install hashes, served website and restart/passkey recovery. Core source and frontend must deploy together. Current updater deploys exe/site, not Git source itself. Do not call built/held artifacts installed or live-verified.
+
+See docs/handoffs/2026-11-15-claude-review-packet.md. Final installation uses the established Settings > Updates confirmation flow. No automatic deployment, real mail sending, cloud coding run or live Core restart was performed.
+