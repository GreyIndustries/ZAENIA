# ZAE as a portable OS shell: roadmap

Goal: ZÆNIA's desktop app becomes the layer you live in, the step before a
full operating system. It runs on any Windows PC (later Linux), with ZAE as
the one interface for your apps, files and day.

## Done (2026-10-17)

- **Window shell**: every workspace page (Status, Tasks, Calendar, Assistant,
  Files, System) opens as a movable, resizable window over the core. Windows
  minimise to a dock, keep their place between launches, and double-click on a
  title bar maximises.
- **Adaptive windows**: windows step back while ZAE listens, thinks or speaks,
  and fade when you've been idle; hovering or focusing one restores it.
- **Context-driven**: what you say brings the right window forward ("what's on
  my calendar" opens Calendar; a task proposal opens Tasks).
- **Talk from anywhere**: floating transcript and input on every screen; `/`
  focuses the input; no wake word; her brain decides when to speak.
- **Awareness**: what you say (memory only) and which app/window you're in.
- **Learning**: inferred key points about you, reviewable in Assistant.
- **Voice**: Kokoro neural voice, Piper fallback.

## Next, in order

1. **Hand gestures** — use the webcam (opt-in, on-device) to read hand
   motions only, never faces: point to pick a window, pinch-and-drag to move
   it, spread to enlarge, swipe to minimise or switch, open palm to stop ZAE
   talking. Needs a local hand-tracking model (MediaPipe Hand Landmarker) and
   a camera on/off switch; no frames are stored or sent anywhere.
2. **Launcher** — "open Blender", "show my downloads": ZAE starts apps and
   opens folders through an allowlisted, confirmed action (same review-and-
   confirm rule as tasks/calendar).
3. **Live app windows** — show a chosen app (browser tab, terminal, notes)
   as a ZAE window: start with an embedded browser view and a terminal panel.
4. **Workspaces** — named layouts ("coding", "planning", "evening") that ZAE
   switches to based on the time, the active app, and what you say.
5. **Notifications centre** — one inbox for follow-through, calendar alerts,
   build results and system warnings, with spoken summaries.
6. **Portable profile** — one encrypted bundle (settings, memory, learned
   points, layouts) you can carry to another PC; owner passkey required.
7. **Boot-to-ZAE (kiosk mode)** — run as the Windows shell for a dedicated
   machine, with an escape hatch back to Explorer.
8. **Phone as remote** — the phone app becomes a second screen and mic for
   the shell (already shares chat, tasks, calendar).

Each step keeps the existing rules: local-first, owner-verified voice,
spoken/clicked confirmation before anything changes data or runs a program.
