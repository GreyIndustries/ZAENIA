# MediaPipe hand-control upgrade

Date: 2026-11-04. Branch: `codex/mediapipe-hand-control`, shared checkout `C:\Projects\ZAENIA`.

## Owner-facing behavior

Enable **Assistant → Assistant tools → Hands → Enable local hand controls**. The camera HUD provides **Adjust**, camera selection, pointing-hand preference, sensitivity, comfortable-reach calibration, and an optional separate shortcut mode.

1. Point at a window title bar or the SE Fusion model. The target highlights.
2. Pause briefly, then pinch thumb and index finger to grab the highlighted target.
3. Move one pinched hand to move a window or turn the model.
4. Add a second pinch. Separating hands enlarges the target; bringing them together shrinks it. Moving the pair moves the target; turning the pair rotates the model in its screen plane.
5. Release the controlling pinch to let go. Losing that hand cancels the grab; another hand cannot inherit it.
6. Point and pinch the explicit hand menu for Previous, Next, Home, Minimize or Close. A pinch elsewhere never closes a tab.
7. A held open palm means Stop speech. It never opens Build. Older nonconflicting pose shortcuts remain available in the separately selected shortcut mode.

Window grabs use title bars, excluding controls and form fields. Model grabs affect the Fusion viewer; the original lightweight constellation keeps its existing pointer controls. No general DOM clicking, operating-system mouse control or gesture-based authentication was added.

## Implementation and boundaries

- Existing **`@mediapipe/tasks-vision` 1.1.1** and vendored model/WASM assets are retained. Its current API already supports multiple hands; no dependency update or new download was needed. `desktop/public/handtracking/worker.js` now requests two hands and returns both landmark arrays and their associated handedness labels/scores.
- Camera frames remain in RAM, transfer to the local CPU worker, and are closed after processing. Capture stays at a maximum of 30 FPS, with one frame in flight and roughly 25 polling attempts per second. Actual processing rate depends on the camera/CPU and was not benchmarked in a physical hand trial.
- `desktop/src/core/handGestures.ts` extends the existing gesture module with `HandMotionController`, preserving legacy exports used by the platform regressions. The active manipulation path uses the new controller. It requires approximately 180 ms of pointing at a stable target and 180 ms of deliberate pinching, uses palm-normalized pinch/release thresholds of .28/.42 and smooths the calibrated cursor with a 65 ms filter.
- Hand continuity uses proximity plus stable handedness, never result-array order. Low/ambiguous handedness classification cancels continuity. This score indicates left/right classification confidence, **not** detection quality or owner identity. Existing MediaPipe detection/presence/tracking thresholds remain .65.
- Two-hand transforms use the pair's center for translation, span ratio for scale and screen-plane angle for twist. One/two-hand transitions rebase without a position jump. All deltas and scales are bounded. These are inferred camera gestures, not measured physical depth or dimensions.
- `handTargets.ts` resolves only visible title bars, Fusion stages and explicitly allowlisted presentation-menu buttons. It holds one target until release and cancels when that target disappears. `windowLayout.ts::handWindowRect` maps viewport motion to bounded stage fractions and preserves the center during resizing.
- App's callback uses existing `shell.open()` once and `shell.update()` for motion. `SEFusionCanvas` listens for a narrowly scoped visual-transform event on its stage. The target event cannot grant execution permissions or change inference/model settings.
- `HandControls.tsx` owns camera selection, calibration, two-hand skeleton/cursor feedback, worker lifetime, stale-result checks and an in-flight watchdog. Tracking loss releases on its next processed result; a stalled in-flight frame releases the target after 500 ms, with the camera disabled after a 5-second worker stall. Late callbacks from an old camera cannot disable its replacement.
- Hidden/unfocused/Calm/background/auth-prompt states release targets and stop camera controls. The user must enable them again. No hand input dismisses Calm or bypasses the enrolled dashboard password. Existing action handlers and authorization remain authoritative; no new confirmation rights were added.
- Deliberate hand activity resets idle/resting presentation timers without unlocking Calm. Window scale animations are stabilized while hand mode is enabled so title bars do not move away during targeting.
- Saved preferences contain only hand choice, sensitivity and two-dimensional reach bounds. Camera images, landmarks, identity/biometric records and credentials are not stored by this feature.

## Affected files

`desktop/public/handtracking/worker.js`; `desktop/src/core/handGestures.ts`, `handTargets.ts`, `gestureActions.ts`, `windowLayout.ts`; `desktop/src/components/shell/HandControls.tsx` and `.css`, `WindowShell.css`; `desktop/src/App.tsx`; `desktop/src/components/tools/se3d/SEFusionCanvas.tsx`; `desktop/src/components/overview/OverviewFrame.tsx`; `desktop/src/components/assistant/PlatformPanel.tsx`.

Regression coverage is in `desktop/scripts/hand-motion.test.cjs`, `hand-worker.test.cjs`, `hand-layout.test.cjs` and updated `gestures.test.cjs`.

## Verification

- TypeScript passed. All **25 desktop Node test scripts** passed, including 15 motion checks, 8 worker checks, 7 layout checks and 29 shortcut checks.
- Synthetic checks exercise target activation, changing targets, order reversal, hand loss/no transfer, pinch hysteresis, stale/malformed data, dominant hand, bounded deltas, centered scaling and one/two-hand rebasing.
- Worker tests execute the actual worker with a mocked local MediaPipe runtime, checking two-hand configuration, labels, monotonic timestamps, frame closing, errors and teardown.
- A real Chrome worker loaded the bundled MediaPipe/WASM/model and processed a blank image successfully without camera access or a cloud service.
- The synthetic browser practice page replayed window and Fusion-model gestures through the shared controller and target session. Each completed with one grab, 53 movement frames, 25 two-hand frames and release. Window geometry visibly changed; the model visibly turned/enlarged. View was reset after inspection. Screenshot: `docs/previews/zaenia-hand-controls.jpg`.
- This is **not** a live camera/owner-hand accuracy, calibration or performance trial. Physical lighting, camera focus, occlusion and comfortable reach still need checking on the owner's actual camera. No actual camera permission was requested during verification.

The development practice page is `http://127.0.0.1:1420/hand-controls-preview.html` with the existing local Vite server. Its demonstrations use synthetic landmarks; **Check local tracker** uses a blank image. Camera practice is a separate explicit button. This page is a development entry, not an additional production website page, and does not access Core or personal data.

## Release and collaboration

Desktop/browser Vite and native Tauri release builds passed; the existing updater backed up the prior executable, installed and reopened ZÆNIA. Installed/build SHA-256 hashes match. The existing Core serves the new main bundle and two-hand worker with HTTP 200. Exact release evidence is in handoff section 21. Existing large-chunk/dynamic-import warnings remain separate from gesture accuracy. Core/voice were not restarted and camera controls remain opt-in.

The owner subsequently requested GitHub publication. The clean `codex/mediapipe-fusion` branch is based on already-published `1097322`, retaining the earlier password/narration history and adding Fusion as this feature's model-view dependency. TypeScript and all 23 Node scripts in this exact publish tree pass; the broader shared checkout's 25-script result also included unrelated Brief/security grouping tests. Existing hand-camera accuracy limitations still apply. This publication does not replace the running app/site/Core or merge `main`. Inspect the root checkout's uncommitted work before later integration.

Official API reference: [MediaPipe Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker?tab=Web).
