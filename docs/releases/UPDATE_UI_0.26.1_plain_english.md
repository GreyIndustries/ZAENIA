# ZAE update UI 0.26.1, in plain English: visual correction — the core docks beside the top row (C1)

This is a **visual correction update**. Grey chose the C1 "Docked companion" look instead of C5 "Core in the mic".
Only where and how the core is drawn off Home changed. Nothing works differently. It includes everything in 0.26.0.
System version stays 0.31.1. Server restart needed: **no** (interface only).

## What changed
- **On every page except Home**, the core glides into a small living orb at the left end of the page's top row, just
  before the Life / Health / Know / Create / Build / Settings switcher. The row keeps a small space for it, and the orb
  glows slightly past that space. It keeps turning slowly.
- **Split panes:** only the pane you're using holds the orb. Click the other pane and it moves there.
- **Phone:** the orb sits at the left of the header, before Back and the page name.
- **When ZAE listens, thinks or speaks** off Home, the space widens a little and the orb swells and glows brighter:
  - listening: rings pulse outward
  - thinking: small dots orbit it
  - speaking: a ring pulses
  - There is no status word next to it.
- **The mic buttons are normal again.** Nothing sits in the chat bar's mic or the phone's "Say or type a page" mic.
- **Colour:** the orb takes the app's colour, as in 0.26.0 (LIFE green, Notes violet, Research teal, Assistant pink,
  amber otherwise).
- **Reduced motion:** no swelling or pulsing, just the colour.

## What did not change
- Home: the big core in the centre card with Standing by / Listening / Thinking / Speaking.
- Calm view.
- One core that never restarts when you change pages, and that pauses when nothing of it can be seen.
- Every page's layout, the chat bar, sign-in, approvals and all features.

## Files
| Area | Files | In plain English |
|---|---|---|
| Docked orb | `core/DockCore.tsx/.css` (new), `App.tsx` | The orb, its slot, the voice-state swell and the page colour. |
| Top rows | `shell/PaneNav.tsx`, `shell/PageNavigator.tsx`, `navigation/NavigationHub.tsx` | Each top row (desktop pane, category sheet, phone header) reserves the orb's space at its left. |
| Removed (C5) | `core/MicCore.tsx/.css`, the tab manager's state event in `shell/TabStrip.tsx`, the ring-placement helper in `core/coreVisibility.ts` | The core-in-the-mic look is gone. |
| Small fixes | `core/NeuralCore.tsx`, `core/neuralField.ts`, `core/CoreStage.tsx` | The orb counts as visible over a window, so it keeps animating; comments updated. |
| Tests | `scripts/core-visibility.test.cjs` | The orb's small drawing layout. |
| Release | `config/versions.json`, `docs/releases/CORE_UI_0.26.1.json`, master plan §48.1 | UI 0.26.1 with 4 notes. |

## Checked
- TypeScript, all unit test files and the mobile browser test pass.
- The page navigation and split-pane browser checks pass 33/33.
- Rendered C1 checks at 1440x900, 390x844 and 360x780 all pass:
  - the orb is centred in the top-row space on the category sheet, app, record, Settings, tab manager and split pages
  - it sits before the switcher (phone: before Back) without overlapping it
  - only the focused pane holds it
  - the same core is kept going Home → page → Home
  - each voice state widens the space to 54 px and swells the orb, with no word
  - the page colours are right
  - the mic is normal
  - reduced motion shows colour only
- Screenshots: `docs/previews/core-behavior/c1/`.

## Not checked
- A real microphone or speech.
- The installed desktop app's GPU.
- A physical phone.

## To install
Settings > Updates, install **ui-0.26.1**. No server restart needed. Refresh the phone page afterwards.
