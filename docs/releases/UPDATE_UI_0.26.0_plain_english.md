# ZAE update UI 0.26.0, in plain English: one core, and "Core in the mic" (C5)

Grey picked core concept C5, "Core in the mic", on 2026-11-11. This update builds exactly that and fixes how the core
behaved on other pages. It includes everything in the installed UI 0.25.0. System version stays 0.31.1. Server restart
needed: **no** (interface only).

## What was wrong
- **The core kept animating where nobody could see it.** Under app windows and category sheets it still drew about
  30 frames a second, costing roughly 40–80% of the browser's main thread in tests.
- **Calm view ran two cores at once.** The Home core kept running hidden behind Calm's own core.
- **It restarted when you changed pages.** Opening the first window or going back Home rebuilt it, so it jumped.
- **The corner core was pointless.** Since windows became solid in 0.24.0, the small core in the top-left corner was
  always hidden.
- **Orbit view drew a full-size core and then shrank it**, and its STANDING BY label overlapped "CORE".
- **Small bugs.** The Tabs strip covered the Today card on Home; the security readout split words on the letter "s".

## What it does now
- **Home:** unchanged. The big core in the centre card, with Standing by underneath. When ZAE listens, thinks or speaks,
  the label says so.
- **Every other page** (category sheet, apps, records, split panes, Settings, the tab manager): the same core glides
  into the chat bar's mic in about half a second and spins there at 46 px. Pages are otherwise clean.
- **When ZAE is busy off Home:** the core bursts out of the mic into a ring about 150 px across, with LISTENING,
  THINKING or SPEAKING to its left.
  - Listening: rings pulse outward.
  - Thinking: three dots orbit.
  - Speaking: one ring pulses gently.
  - When she is done it shrinks back into the mic.
  - The ring always stays fully on screen. Next to an edge (the phone's mic is near the right edge) it slides toward
    the middle, clear of any notch or rounded-corner safe area, and only shrinks on a screen narrower than the ring.
- **Colour:** off Home the core takes the app's colour (LIFE green, Notes violet, Research teal, Assistant pink, the
  app's own colour elsewhere, amber on the category sheet and tab manager).
- **Phone:** the same, using the 42 px mic of the "Say or type a page" bar. Phone Home is unchanged.
- **Calm view:** unchanged, using the same single core.
- **The mic still works as the mic.** The core never takes clicks and the button keeps its name for screen readers.
- **Reduced motion:** no glide or burst, just the state colour around the mic.

## What changed
| Area | Files | In plain English |
|---|---|---|
| One core | `core/CoreStage.tsx` (new), `App.tsx` | The core is created once and moved between Home, the mic, phone Home and Calm. A move between two visible places glides; it is never rebuilt. |
| Pause when hidden | `core/coreVisibility.ts` (new), `core/NeuralCore.tsx` | The core checks whether any of it can be seen whenever the layout changes (no polling) and pauses when it can't. |
| Core in the mic | `core/MicCore.tsx/.css` (new), `App.tsx`, `shell/TabStrip.tsx` | The mic layer, the burst ring, the state word, the page colour, and the tab manager telling the app when it is open. |
| Drawing | `core/neuralField.ts`, `core/NeuralCore.tsx` | Draws at the size shown, redraws at once after a resize, small mic layout, page-colour tint. |
| Fixes | `NeuralCore.css`, `App.css`, `CalmView.css` | Orbit label overlap, Tabs strip over the Today card, security readout, unused styles removed. |
| Tests | `scripts/core-visibility.test.cjs` (new) | When the core may pause, its drawing size, the mic layout, and keeping the burst ring on screen. |
| Release | `config/versions.json`, `docs/releases/CORE_UI_0.26.0.json`, master plan §48 | UI 0.26.0 with 8 detailed notes. |

Not changed on purpose: the core's look on Home and in Calm, the chat bar and mic behaviour, sign-in, Calm password,
approvals and every other page's layout.

## Checked
- TypeScript passes. All 37 unit test files pass, including the new core checks.
- The mobile browser test passes. The rendered page navigation and split-pane checks pass 33/33.
- Rendered C5 checks at 1440x900, 390x844 and 360x780:
  - Home to page and back keeps the same core (no restart), on desktop and phone.
  - The core sits in the mic on category, app, record, split, Settings and tab-manager screens.
  - Each voice state shows the burst and the right word.
  - Each app shows its colour.
  - The mic still receives clicks, and reduced motion shows no burst.
  - On both phone sizes every burst stays fully on screen, still covers the mic, and shrinks back centred on it.
- Screenshots and numbers are in `docs/previews/core-behavior/c5/`.

## Not checked
- A real microphone or real speech playback (a dev-only switch drove the voice states).
- Speaking follows a gentle pulse, because the app has no speech output level yet.
- The installed desktop app on its GPU, and a physical phone.

## To install (after Grey says OK)
1. Settings > Updates, install **ui-0.26.0**. No server restart needed. Refresh the phone page afterwards.
