# Focused Sunday review packet for Claude
+
+Review `git diff main...release/2026-11-15`. Main is the reconstructed installed system 0.31.1 / UI 0.26.0; the release branch adds the approved Sunday scope. No production install or service restart was done during preparation.
+
+Prioritize: desktop/src-tauri/src/lib.rs and update_paths.rs (trusted runtime root and installer invocation); scripts/update_helpers.ps1, install_update.ps1, stage_update.ps1 (target/path validation, process ownership, rollback, hashes, CheckOnly); core/api/update_routes.py (installed receipts vs source metadata); core/assistant_platform/build_helper.py (no silent cloud selection, private failed-job handoff); core/brain/brain_service.py and local_llm.py plus learning_lab.py (permission-scoped data, actual model isolation); core/maps/commute.py and map_routes.py (explicitly saved endpoints, no GPS/work guesses); core/api/learning_lab_routes.py and research_workshop_routes.py (read/write scopes).
+
+Do not spend allowance rebuilding or rediscovering old branches. Read the source-provenance receipt, test results and detailed notes; report exact findings with affected paths and consequence. Review is independent and remains required before Sunday installation.
+
+Owner trials still needed: actual PDF attachment View, exact-recipient/text approved reply send (no real send has been attempted), physical phone, owner voice and post-Core-restart authentication. Synthetic tests do not replace them. The 20-task historical catalog is seeded/validated, not a measured coding-success baseline. Larger local-coder retrieval, per-step planning and overnight models remain roadmap work.
+