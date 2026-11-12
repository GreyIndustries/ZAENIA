# ZÆNIA Constellation Fusion — model and integration handoff

Date: 2026-11-04. Feature branch: `codex/se-fusion-model` in the shared `C:\Projects\ZAENIA` checkout. Read current Git status before staging: this checkout contains substantial earlier Claude/Codex work. This task does not merge or publish that work.

## Delivered model

The owner's combined design is implemented as real, rotatable mesh geometry: inclined gimbal orbits, amber smoky-quartz folds, curved organic metal branches, four neural cell clusters and a central Conductor crystal. A separate mechanical execution gate sits below the SE. This is an optimized runtime interpretation of the concept, not a photorealistic image or a new inference system.

| Part | Shape and color | Role represented |
|---|---|---|
| Talk | Amber waveform capsule, upper right | Conversation and spoken answers |
| Seek | Cyan faceted prism, lower right | Reading and evidence gathering |
| Study | Violet layered cube, upper left | Detailed reasoning, research and code |
| Keep | Copper beads and mint traces, lower left | Small background summaries and memory |
| Conductor | Ivory crystal and orbital rings, center | Coordinates the four roles |
| Execution gate | Separate metal housing below | Core's independent authorization boundary |

Default asset labels are `qwen3.5:4b`, `qwen3.5:9b`, `qwen3:14b` and `qwen3:1.7b`. The integrated app takes displayed model names and statuses from its existing roster. The picture does not load, install or switch an inference model, and it cannot grant permissions or perform an action.

## Files Claude should use

All paths below are relative to the repository root.

| File | Purpose |
|---|---|
| `desktop/src/components/tools/se3d/fusionModel.ts` | Canonical portable geometry builder and activity animation |
| `desktop/src/components/tools/se3d/SEFusionCanvas.tsx` and `.css` | WebGL viewer, pointer/keyboard controls, picking, lighting and lifecycle |
| `desktop/src/components/tools/SEBrainMap.tsx` and `.css` | Existing roster integration and selectable Fusion/lightweight views |
| `desktop/public/models/zaenia-se-fusion.glb` | Portable glTF 2.0 binary, 3,765,276 bytes |
| `desktop/scripts/export-se-fusion.mjs` | Regenerates the GLB and reloads it to check semantic parts |
| `desktop/scripts/fusion-model.test.cjs` | Seven CPU geometry/resource regression checks |
| `desktop/se-fusion-preview.html` | Standalone Vite development preview entry |
| `desktop/src/previews/SEFusionPreview.tsx` and `.css` | Synthetic activity controls, with no API or personal-data access |
| `docs/previews/zaenia-se-fusion-desktop.jpg` | Actual WebGL preview capture using synthetic activity |

The GLB contains ordinary meshes and standard materials, with no external textures, custom shaders, instancing extension or additional dependencies. It is a static snapshot; the application uses the TypeScript builder for activity-driven motion. A GLB import into Blender or another renderer will need that renderer's own lighting and camera.

Semantic names include `ZAENIA_Constellation_Fusion`, `Talk_Constellation`, `Seek_Constellation`, `Study_Constellation`, `Keep_Constellation`, `Central_Conductor`, `Execution_Security_Gate`, `Smoky_Quartz_Folds`, `Porous_Organic_Metal_Ribs` and `Inclined_Gimbal_Orbits`. Group metadata and pick IDs identify the four brains, Conductor and gate.

## Existing app integration

Fusion is the default appearance in the existing SE view under Arena's **SE & tools** and Status **Readiness**. The **Lightweight constellation** button retains Claude's original view; preference is saved in `zaenia.se.visual`. SecurityModel and the shared projected-canvas engine remain separate and unchanged by this model task.

`SEFusionCanvas` consumes the existing `ConstellationFeed`: `signals()`, `text(id)`, `tip(id)` and `hubTip()`. Signal order is Talk, Seek, Study, Keep. The viewer accepts an optional selection callback for a brain or Conductor and a fallback callback. To reuse just the geometry:

```ts
const model = createFusionModel();
scene.add(model.root);
model.update(elapsedSeconds, { talk: 0.4, seek: 1, study: 0, keep: 0.2 }, motionAllowed);
// On unmount, remove the root and release its shared GPU resources once.
scene.remove(model.root);
model.dispose();
```

Levels range from zero to one. The builder does not change the root transform, allowing the host to own rotation and placement. `dispose()` is idempotent. The existing activity feed infers recent use from Ollama keep-alive changes, with a 12-second window; it is not token-level telemetry, an exact speaking detector or a representation of internal thoughts. Do not present synthetic preview activity as runtime evidence.

## Interaction and resource limits

- Drag to turn; arrow keys turn the focused canvas. Plus/minus zoom and Home resets. Visible zoom/reset buttons and brain selection buttons are also available.
- Narrow containers place model labels below the stage so they do not obscure the geometry. The model was inspected at a 390-pixel viewport with no horizontal overflow.
- There are 56 mesh objects and 51,852 triangles. The renderer caps motion at 30 FPS, DPR at 1.5, and drawing-buffer width at 1,400 pixels. These are implementation limits, not measured GPU utilization claims.
- Continuous motion stops when hidden, outside the viewport, reduced motion is requested, or the app marks itself in the background. Visible static activity refreshes once per second. Resize and manual interactions can still draw a frame.
- Geometry, materials, environment render target, renderer, observers, event handlers, timers and animation callbacks are released on unmount. Reflection-environment failure falls back to direct lights. WebGL failure offers the lightweight view in the app.
- The Three.js viewer is lazy-loaded. Its production JS chunk is approximately 600 KB uncompressed / 155 KB gzip; the GLB is copied as an optional asset and is not downloaded by this procedural viewer.

## Rebuild and inspect

From `C:\Projects\ZAENIA\desktop`, using the existing installed dependencies:

```powershell
node scripts/fusion-model.test.cjs
node scripts/export-se-fusion.mjs
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:1420/se-fusion-preview.html`. This is a development entry, not an additional production page. Its activity modes and reduced-motion switch are synthetic and do not contact Core. The GLB is also copied into both production output directories under `models/`.

For an app release, follow `AGENTS.md`: build `desktop/dist-web` and the Tauri release, then use the existing native updater when applying the update. No Core restart, auth change, new provider, cloud call or owner-data migration is required for this frontend model.

## Verification and release record

- TypeScript: passed.
- All 22 desktop Node test scripts: passed, including geometry, activity, security grouping and existing interaction regressions.
- GLB binary header and loader round-trip: passed; all four clusters, Conductor and separate gate retained.
- Actual Chrome/WebGL preview: rotation with keyboard and pointer, zoom/reset, selection, activity modes and reduced-motion controls inspected. Narrow-screen layout inspected at 390 × 844; viewport restored afterward.
- Desktop/browser Vite and native Tauri release builds passed. The existing updater backed up the prior binary, installed and reopened the app; installed/build SHA-256 hashes match. The existing Core serves the website, viewer bundle and 3,765,276-byte GLB with HTTP 200. Core and voice were not restarted. Exact release evidence is recorded in handoff section 20. This preview is not a live owner-voice trial or a benchmark of inference/model performance.

No GitHub merge is authorized by this model request. Preserve the earlier isolated publication branches and all existing uncommitted work.
