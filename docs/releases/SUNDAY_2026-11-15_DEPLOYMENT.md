# Sunday release preparation receipt

Prepared 2026-11-12T00:00:57.592117-08:00 for Sunday November 15, 2026 (America/Los_Angeles).

Held package: `C:\Projects\ZAENIA\updates\held\sunday-2026-11-15-nodes-learning`.

Recovery copy: `C:\Projects\ZAENIA\backups\sunday-prep-20261111-235813`.

Status: held, not integrated, installable, installed or live-verified. Native and website artifacts exist; the full combined source must still be reviewed, integrated, tested and rebuilt before staging. The running app and website were not changed. No GitHub push or automatic deployment occurred.

Combined patch notes contain 11 categorized entries, including Claude's held C1 visual correction. Final versions and notes must be reconciled at feature freeze. The package contains `check_sunday_release.py`, source before/after hashes, recovery verification, and `SUNDAY_DEPLOYMENT.md` for the full release procedure.

Verification: 114 backend tests, 15 node/voice checks, six rendered checks, native/web builds, local-model practice and feature secret scan. Package and recovery hashes match, with no source drift at preparation. Re-run the checker at integration time; a clean integrity report is not deployment approval.

# Sunday, November 15, 2026 — held release preparation

This package is held for the Sunday whole-system update, America/Los_Angeles. It does not schedule an automatic installation or authorize a Core restart. Candidate versions are system 0.32.0 / UI 0.27.0; reconcile with Friday's accepted integrated source before assigning final release numbers.

## Included and verified

- Native executable and 74 browser artifact files, with SHA-256 manifest.
- A 36-file feature overlay, primary-before and candidate hashes, and review.patch.
- Detailed release notes and the shared node/research/learning handoff.
- 114 passing backend tests, 15 node/voice-routing checks, six rendered desktop/phone checks, existing navigation/catalogue checks and patch-note checks.
- Native and browser builds; real synthetic local-model practice; clean feature-source secret scan.
- Recovery copies of the currently installed executable, served website and affected source baselines. Recovery copies are not a claim that their application behavior was re-tested.

## Before integration

Run the package's `check_sunday_release.py` using the project Python environment and `--project-root C:\Projects\ZAENIA`. It checks package/source/recovery integrity and reports newer primary-file changes. It never applies source, merges, stages, restarts or installs. A successful check means the held package is intact, **not** deployment-ready.

Review any source drift against the primary checkout; preserve newer Claude/Codex work. Do not merge the isolated workspace wholesale: it was overlaid with earlier uncommitted primary source. Integrate only the reviewed feature changes on the agreed release branch. New Core routes, teaching-context assembly and frontend nodes must enter the same accepted source. The current updater does not deploy Core source by itself.

## Friday freeze and Saturday validation

1. Combine the accepted C1 core-placement correction and other approved weekly changes. Preserve F&H and GODSPEED functionality.
2. Reconcile system/UI/node versions and all detailed notes. Document real additions, changes, fixes, removals, performance/security effects and limits; do not lose earlier notes.
3. Re-run required backend and frontend checks, including denied-memory teaching, model isolation, research/citation behavior, voice destinations, records/revisions and remote layouts. Run Gitleaks against the final integrated source/diff before publication.
4. Build native desktop and `desktop/dist-web` from the accepted deployment checkout or a supported build copy beneath that checkout. These review binaries are evidence, not a replacement for the final integrated build. Validate deployment-root discovery, artifact hashes and the owner's existing install/recovery path.
5. Perform owner desktop/phone/voice trials, including enabled lesson context, correct LIFE/Mail and Schedule Board navigation, War Room drafts and research records. Keep unverified device behavior labeled unverified.

## Sunday release

After accepted-source integration and release gates pass, use the existing `scripts/stage_update.ps1` with `-Part system`, detailed release notes and `-RestartServer`. Confirm that the final package is under the primary checkout's `updates/pending`, that the native executable hash matches its manifest and that the served website is still unchanged until installation.

Grey installs through Settings > Updates using its existing confirmation flow. Verify Core health, final versions, desktop, phone website and critical actions afterward. Record installed and live-verified states separately. GitHub publication remains governed by the owner's existing explicit approval; this preparation does not push anything.

## Recovery

The exact recovery folder is in `sunday-release.json`. Verify it using the checker before release. If post-install checks fail, use the existing update backup/rollback workflow to restore the previous executable and website. Restore affected Core source from the reviewed source baseline as needed; preserve owner data and new lesson/planning records. Do not blindly copy or delete databases. A database snapshot, if needed at freeze, must use the application's supported consistent-backup procedure.

## Feature limits to retain in notes

Teaching uses model-specific reference retrieval, not weight fine-tuning. Practice outputs need owner review. Camera registration provides viewer links, not RTSP/ONVIF streaming or monitoring. Imported Quantum reference entries are unverified; citation overlap is not independent factual verification. The imported app's entire Tkinter UI and all its algorithms have not been ported as equivalent features.
