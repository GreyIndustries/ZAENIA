# ZAENIA cleanup review — nothing deleted

Scanned `C:\Projects\ZAENIA` at 2026-10-18T04:37:57+00:00 in 0.7 seconds.

**63,339 files, 7,224 directories, 14.74 GiB (15,822,953,399 logical bytes).** Skipped links/junctions: 0; scan errors: 0.

Sizes are logical file lengths, not allocated disk space. Copies/hard links, compression, running writes and rebuilds can change the space actually recovered. This is a point-in-time inventory, not a frozen filesystem.

The complete tree was visited for metadata, including dependencies and build output. Security files, memories, databases, audio, archives and logs were not opened. The separate reference check reads application code and the public Piper model paths only; it records reference locations, never configuration or source contents.

## Review candidates

The groups below cover 8.84 GiB without double-counting. **This is review volume, not approved or guaranteed recoverable space.** Every group is pending your selection. No cleanup operation, shell deletion command or automatic-delete schedule has been added.

| ID | Item | Verified size / files | Assessment |
| --- | --- | ---: | --- |
| C01 | Rust build intermediates | 8.13 GiB / 9,895 | Review first; close the desktop app/build tools before selected cache cleanup. |
| C02 | Alternative Piper voices | 338.41 MiB / 8 | Review whether you want to keep the alternative voices; preserve the configured model/config pair. |
| C03 | Voice audition audio | 1.54 MiB / 6 | Review the test recordings for removal. |
| C04 | Archived broken Python environment | 165.93 MiB / 5,082 | Review after confirming all launchers use .venv. |
| C05 | Root npm installation and its manifests | 146.30 MiB / 6,890 | Likely redundant for the current desktop build; approve a controlled build check before removal. |
| C06 | Security restore copy | 7.10 KiB / 6 | Owner review required; do not keep stale credential material in routine source backups. |
| C07 | Blender autosaves | 1.15 MiB / 5 | Review autosaves separately from scenes and generator scripts. |
| C08 | Older UI snapshot folders | 3.42 MiB / 12 | Review after the current UI behavior is accepted. |
| C09 | Older UI history (keep newest three) | 7.87 MiB / 126 | Review the older snapshots; preserve the three newest plus any known good milestone. |
| C10 | Source rollback/export-preparation copies | 42.85 MiB / 804 | Review rollback needs after accepting and testing the upgrades. |
| C11 | One-time source exports and review tools | 555.65 KiB / 6 | Review whether the export/debug workflow is still useful. |
| C12 | Legacy placeholders and configuration candidates | 2.76 KiB / 10 | Review source/configuration together; external scripts and dynamic readers still need consideration. |
| C13 | CarPlay generated briefing audio | 19.16 MiB / 44 | Retain current sessions; design reference-aware retention before selecting old audio. |
| C14 | Application Python bytecode caches | 2.30 MiB / 208 | Optional cache cleanup after selected processes are closed; little benefit. |

## Keep protected

| Item | Verified size | Why |
| --- | ---: | --- |
| `.venv` | 4.61 GiB | Active Python environment selected by both startup scripts; includes ML/speech dependencies. |
| `desktop/node_modules` | 164.70 MiB | Desktop build dependencies; preserve while upgrading and testing. |
| `desktop/src-tauri/target/release/desktop.exe` | 25.44 MiB | Current runnable desktop build. Removing all of target removes this executable. |
| `desktop/dist` | 52.90 MiB | Built desktop frontend; rebuildable but currently used by packaging/build workflows. |
| `desktop/dist-web` | 52.90 MiB | Live phone/web frontend served by core/api/phone_app.py. |
| `data/secure` | 6.81 MiB | Owner authentication, policy and recovery material; metadata only, never classified as expendable. |
| `data/models` | 237.46 MiB | Speech/ML model data. |
| `data/personal_memory` | 17.71 KiB | Lasting personal memory, not cache. |
| `data/assistant_followthrough` | 32.00 KiB | Reminder inbox, delivery claims and preferences, not cache. |
| `data/voices/piper/en_US-hfc_female-medium.onnx` | 60.27 MiB | Configured active Piper voice; keep both model and JSON configuration. |
| `data/voices/piper/en_US-hfc_female-medium.onnx.json` | 4.92 KiB | Configured active Piper voice; keep both model and JSON configuration. |

The **whole** Rust target tree is 8.16 GiB, which differs from the older pasted estimate. C01 selects the large compiler/intermediate folders for review and excludes the top-level release executable/support artifacts.

## Corrections to the earlier list

- `core/conversation_runtime/fluid_runtime_test.py` is a **live runtime dependency**, imported by `core/voice_security/runtime.py`. Do not delete `*_test.py` files based on the suffix. Keep the microphone/voice diagnostics unless separately reviewed.
- `core/conversation/reply_engine.py` is listed in `core/brain/component_registry.yaml`. No direct Python import was found in the checked application sources, but removing it also requires correcting that component evidence. It remains outside cleanup candidates.
- `main.py`, `start.py` and `foundation_main.py` are byte-identical. They are documented compatibility entry points; keeping all three costs less than 1 KiB. External shortcuts were outside this audit.
- Root npm dependencies look redundant for the current app, but parent-module resolution exists. Preserve the root manifests until a controlled desktop build check confirms removal is harmless. The desktop has its own separate dependency installation.
- CarPlay WAV files belong to an active session/replay system. Preserve `data/carplay_sessions/sessions.sqlite3`. An age-only deletion job could break replay; reference-aware retention needs its own reviewed change.
- Blender scenes, scripts and UI/source backups are authored work or recovery points. A newer timestamp does not prove an older scene is unnecessary.
- The requirements files are installation instructions, not disposable space savings. Keep both Python manifests until a complete dependency inventory is validated; no Python manifest is selected for deletion.
- Corrected the malformed `sounddevicetzdata` entry into separate `sounddevice` and `tzdata` requirements. No exact duplicate package lines remain.
- Retained `requirements-module1.txt`, the pinned security dependency manifest. This audit installed no packages and changed no dependency manifest.

## Candidate details

### C01 — Rust build intermediates

Rebuilt by Cargo. Keep target/release/desktop.exe, its support artifacts and any installer bundles. The next native build will take longer.

Risk category: `regenerable`. Approval: **pending owner selection**. Files: 9,895; bytes: 8,731,089,333.

Exact paths:

- `desktop/src-tauri/target/debug`
- `desktop/src-tauri/target/release/.fingerprint`
- `desktop/src-tauri/target/release/build`
- `desktop/src-tauri/target/release/deps`
- `desktop/src-tauri/target/release/examples`
- `desktop/src-tauri/target/release/incremental`

Evidence locations: `desktop/src-tauri/target/release/desktop.exe`.

### C02 — Alternative Piper voices

These model paths are not selected by the current Piper configuration. They are optional voice choices, not proof of useless data.

Risk category: `optional_models`. Approval: **pending owner selection**. Files: 8; bytes: 354,846,588.

Exact paths:

- `data/voices/piper/en_US-amy-medium.onnx`
- `data/voices/piper/en_US-amy-medium.onnx.json`
- `data/voices/piper/en_US-kristin-medium.onnx`
- `data/voices/piper/en_US-kristin-medium.onnx.json`
- `data/voices/piper/en_US-lessac-high.onnx`
- `data/voices/piper/en_US-lessac-high.onnx.json`
- `data/voices/piper/en_US-ljspeech-high.onnx`
- `data/voices/piper/en_US-ljspeech-high.onnx.json`

Evidence locations: `core/voice_output/voice_config.yaml`.

### C03 — Voice audition audio

Generated voice auditions, including a test for the active voice; these are separate from the active ONNX model.

Risk category: `review_audio`. Approval: **pending owner selection**. Files: 6; bytes: 1,619,720.

Exact paths:

- `data/voices/piper/en_US-amy-medium-test.wav`
- `data/voices/piper/en_US-hfc_female-medium-test.wav`
- `data/voices/piper/en_US-kristin-medium-test.wav`
- `data/voices/piper/en_US-lessac-high-test.wav`
- `data/voices/piper/en_US-ljspeech-high-test.wav`
- `data/voices/piper/zaenia_test.wav`

### C04 — Archived broken Python environment

Startup scripts select .venv/Scripts/python.exe. Keep the active .venv and its installed speech/ML dependencies.

Risk category: `old_environment`. Approval: **pending owner selection**. Files: 5,082; bytes: 173,985,700.

Exact paths:

- `.venv_broken_20260829`

Evidence locations: `scripts/start_zaenia_server.ps1`, `scripts/start_zaenia_voice.ps1`.

### C05 — Root npm installation and its manifests

The root manifest has no run/build scripts. The desktop owns its own manifest and node_modules. The root-only drei package has no current application-source import. Node can resolve parent modules, so static scanning alone is insufficient.

Risk category: `dependency_review`. Approval: **pending owner selection**. Files: 6,890; bytes: 153,403,368.

Exact paths:

- `node_modules`
- `package-lock.json`
- `package.json`

Evidence locations: `package.json`, `desktop/package.json`.

### C06 — Security restore copy

This is a restore-copy location, not data/secure. Contents were deliberately not read. Verify recovery needs before selecting the copy for removal.

Risk category: `sensitive_copy`. Approval: **pending owner selection**. Files: 6; bytes: 7,269.

Exact paths:

- `restore_check/secure`

### C07 — Blender autosaves

Autosaves can recover lost work. Scene revisions and scripts are authored assets and remain protected from automatic cleanup.

Risk category: `authored_asset_backup`. Approval: **pending owner selection**. Files: 5; bytes: 1,200,930.

Exact paths:

- `desktop/blender/ZAENIA_Warehouse_Stage06C_Rev3.blend1`
- `desktop/blender/ZAENIA_Warehouse_Stage06C_Rev5_OpenEnd.blend1`
- `desktop/blender/ZAENIA_Warehouse_Stage06C_Rev6_WallLights.blend1`
- `desktop/blender/ZAENIA_Warehouse_Stage06E_ReferenceMatch.blend1`
- `desktop/blender/ZAENIA_Warehouse_Stage06F_IntegratedLights.blend1`

### C08 — Older UI snapshot folders

Historical UI rollback copies; do not discard the only rollback for unverified changes.

Risk category: `rollback`. Approval: **pending owner selection**. Files: 12; bytes: 3,582,383.

Exact paths:

- `desktop/src backup`
- `desktop/ui-backup-20261012-203731`
- `desktop/ui-backup-identity-header-20261012-214739`
- `desktop/ui-backup-neural-core-20261013-200107`
- `desktop/ui-backup-system-core-20261012-211602`

### C09 — Older UI history (keep newest three)

Newest is based on folder modification metadata, not a guarantee of quality. Retention is a review suggestion only.

Risk category: `rollback`. Approval: **pending owner selection**. Files: 126; bytes: 8,249,028.

Exact paths:

- `desktop/ui-backups/_incoming`
- `desktop/ui-backups/blended-core-20261014-161311`
- `desktop/ui-backups/core-wake-20261014-161921`
- `desktop/ui-backups/dark-palette-20261014-164110`
- `desktop/ui-backups/desktop-auth-20261016-054126`
- `desktop/ui-backups/glass-20261014-202313`
- `desktop/ui-backups/hangar-particles-20261015-120315`
- `desktop/ui-backups/highlights-20261014-184503`
- `desktop/ui-backups/hybrid-ui-20261015-070923`
- `desktop/ui-backups/icon-glow-20261014-185733`
- `desktop/ui-backups/lighter-core-20261014-185554`
- `desktop/ui-backups/live-status-20261015-190107`
- `desktop/ui-backups/nerve-lines-only-20261014-212937`
- `desktop/ui-backups/nerve-ui-20261014-212027`
- `desktop/ui-backups/no-pedestal-20261015-114139`
- `desktop/ui-backups/organic-core-20261014-211158`
- `desktop/ui-backups/organic-core-20261014-211212`
- `desktop/ui-backups/phone-layout-20261015-180108`
- `desktop/ui-backups/phone-webapp-20261015-203942`
- `desktop/ui-backups/reference-core-20261015-115456`
- `desktop/ui-backups/status-feed-src-tauri`
- `desktop/ui-backups/status-orb-chatbox-20261015-123345`
- `desktop/ui-backups/stream-interrupt-20261015-231117`
- `desktop/ui-backups/ui-functions-20261015-213312`
- `desktop/ui-backups/voice-20261016-053248`

### C10 — Source rollback/export-preparation copies

These copies support recovery and are small beside build output. Archives or copied source may include private configuration; no archive contents were opened.

Risk category: `rollback`. Approval: **pending owner selection**. Files: 804; bytes: 44,929,622.

Exact paths:

- `backups`
- `core/api/_backup_before_brief_only`
- `core/api/_backup_before_phone_app`
- `core/api/_backup_before_status_feed`
- `core/api/_backup_before_ui_functions`
- `core/calendar_context/_backup_before_calendar_fix`
- `core/carplay_trigger/_backup_before_calendar_fix`
- `module1_backups`
- `module1_prep`
- `scripts/_backup_before_brief_only`

### C11 — One-time source exports and review tools

Not current application entry points. A test or export tool can still be useful when run manually; its name is not deletion authorization.

Risk category: `manual_tools`. Approval: **pending owner selection**. Files: 6; bytes: 568,986.

Exact paths:

- `ZAENIA_All_Core_Source_Review.zip`
- `ZAENIA_Module1_Source_Review.zip`
- `ZAENIA_Module2_Source_Review.zip`
- `carplay_review.txt`
- `collect_module2_source.py`
- `test_carplay_update.py`

### C12 — Legacy placeholders and configuration candidates

No direct application imports of the old db/path-helper modules were found. Empty folders/files take negligible space. Configuration contents, including placeholder credentials, were not copied into the report.

Risk category: `legacy_source`. Approval: **pending owner selection**. Files: 10; bytes: 2,826.

Exact paths:

- `config.yaml`
- `config/settings.yaml`
- `core/conversation/conversation_main.py`
- `core/db.py`
- `core/foundation/_init_.py`
- `core/init.py`
- `core/settings.yaml`
- `core/utils.py`
- `utils`
- `voice`

### C13 — CarPlay generated briefing audio

The running CarPlay service stores audio paths in sessions.sqlite3 and exposes delivery/replay. Age or a .wav extension alone is insufficient. The database was not read or changed.

Risk category: `runtime_references`. Approval: **pending owner selection**. Files: 44; bytes: 20,091,328.

Exact paths:

- `data/carplay_sessions/*.wav (exact session filenames kept in the private inventory)`

Evidence locations: `core/carplay_trigger/briefing_session.py`, `core/api/status_feed.py`.

### C14 — Application Python bytecode caches

Recreated by Python. No source modules or active virtual-environment packages are selected.

Risk category: `regenerable`. Approval: **pending owner selection**. Files: 208; bytes: 2,409,647.

Exact paths:

- `core/__pycache__`
- `core/api/__pycache__`
- `core/assistant_followthrough/__pycache__`
- `core/assistant_platform/__pycache__`
- `core/behavior/__pycache__`
- `core/brain/__pycache__`
- `core/briefing/__pycache__`
- `core/calendar_context/__pycache__`
- `core/carplay/__pycache__`
- `core/carplay_audio/__pycache__`
- `core/carplay_trigger/__pycache__`
- `core/console/__pycache__`
- `core/conversation/__pycache__`
- `core/conversation_runtime/__pycache__`
- `core/foundation/__pycache__`
- `core/foundation/auth/__pycache__`
- `core/foundation/moral_code/__pycache__`
- `core/foundation/rules/__pycache__`
- `core/foundation/security/__pycache__`
- `core/foundation/storage/__pycache__`
- `core/google_calendar_sync/__pycache__`
- `core/personal_memory/__pycache__`
- `core/personality/__pycache__`
- `core/reasoning/__pycache__`
- `core/reminders/__pycache__`
- `core/scheduling/__pycache__`
- `core/traffic/__pycache__`
- `core/voice_listener/__pycache__`
- `core/voice_output/__pycache__`
- `core/voice_security/__pycache__`
- `core/weather/__pycache__`
- `scripts/__pycache__`
- `utils/__pycache__`

## Largest top-level items

| Path | Logical size |
| --- | ---: |
| `desktop` | 8.50 GiB |
| `.venv` | 4.61 GiB |
| `data` | 1.28 GiB |
| `.venv_broken_20260829` | 165.93 MiB |
| `node_modules` | 146.27 MiB |
| `backups` | 42.44 MiB |
| `core` | 3.91 MiB |
| `docs` | 319.51 KiB |
| `scripts` | 166.30 KiB |
| `module1_backups` | 112.69 KiB |
| `restore_check` | 78.12 KiB |
| `module1_prep` | 29.47 KiB |
| `utils` | 488 B |
| `config` | 243 B |
| `.claude` | 204 B |
| `voice` | 0 B |

## Source-reference evidence

Static references cannot prove a file is unused; external launchers, manually run tools and dynamic path construction may not appear.

- `legacy_database`: `core/db.py:1`.
- `legacy_path_helpers`: no match in the checked scope.
- `legacy_configs`: no match in the checked scope.
- `legacy_reply_engine`: `core/brain/component_registry.yaml:202`.
- `runtime_test_dependency`: `core/voice_security/actions_test.py:387`, `core/voice_security/actions_test.py:408`, `core/voice_security/actions_test.py:563`, `core/voice_security/runtime.py:61`, `core/voice_security/runtime.py:97`, `core/voice_security/runtime.py:137`, `core/voice_security/runtime.py:176`.
- `root_only_drei`: `package.json:3`.
- `old_environment`: `core/brain/system_index.py:112`, `core/brain/system_index.py:500`.
- `carplay_sessions`: `core/api/status_feed.py:132`, `core/carplay_audio/carplay_audio.py:445`, `core/carplay_audio/carplay_audio.py:447`, `core/carplay_trigger/briefing_session.py:203`.
- `web_bundle`: `core/api/phone_app.py:4`, `core/api/phone_app.py:25`, `core/api/ui_files.py:37`, `core/assistant_platform/health.py:72`, `desktop/package.json:9`.
- `launchers`: `core/assistant_platform/platform_test.py:199`, `core/assistant_platform/platform_test.py:201`, `core/foundation/closure_check.py:159`, `core/foundation/foundation_main.py:1`, `foundation_main.py:2`, `main.py:2`, `start.py:2`.

## Repeatable review process

1. Run the read-only audit again to refresh metadata and reference evidence.
2. Review the group IDs and exact paths. Select explicitly which items to remove; all current entries remain unapproved.
3. Compare a fresh scan with this snapshot. Investigate changed paths and active references before approving any selected deletion. A comparison is a metadata hint, not a cryptographic content or authorization check.
4. Before a separately authorized cleanup, preserve the runnable desktop build and useful rollback points, close affected processes and verify each resolved path stays inside this project. Never expand a selection to credentials, personal state, models, other projects or games.
5. A future deletion command must show the exact selected paths and current sizes for owner approval. This scanner has no deletion mode, and ZAE is not authorized to delete any candidate automatically.

Run from the project directory:

```powershell
.venv\Scripts\python.exe scripts\cleanup_audit.py
# Load the existing inventory first, then report metadata changes while refreshing it:
.venv\Scripts\python.exe scripts\cleanup_audit.py --baseline data/cleanup_review/inventory.json
```

Outputs: `docs/CLEANUP_REVIEW.md` and `data/cleanup_review/inventory.json`. Only these generated review artifacts are written. The detailed inventory is under private owner/SYSTEM permissions and excluded from the token file browser by the existing data-directory boundary. It records local file paths, sizes, timestamps, reference locations and candidate explanations; it contains no file contents. Protected-state filenames and detailed diff paths are kept out of this Markdown report.

## Changes since the previous snapshot

Baseline: 2026-10-18T04:37:53+00:00. Added: 0; missing: 0; changed size/timestamp: 2.

Size/mtime comparison only; identical-size content changes with preserved timestamps are not detected. Missing paths were not deleted by this tool.

Exact added/missing/changed paths are available only in the private JSON inventory.
