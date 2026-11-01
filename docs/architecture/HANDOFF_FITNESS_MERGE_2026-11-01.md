# Handoff: merge the Fitness & Health sub-tabs (2026-11-01)

Grey asked (2026-11-01): merge Training program + Plans & targets + Food & exercise; merge Progress + Today + Day log; merge Recipes + Scan food + Weekly meal planner. Five layout previews were made for him to pick from:
https://claude.ai/artifact/DqDeXbPpXFjiSsDGXq98Za (source: the Claude session scratchpad; the boards are A to E).

**Status: done (2026-11-01).** Grey picked Today = A, Training = C, Food = E, plus recipe shelves (Made for this week / Cookbook) and logging exercises that aren't in the plan. Built and installed; see CLAUDE_NOTES_2026-11-01.md. The rest of this file is kept for reference.

## The merge
| New tab | Was | Components today (`desktop/src/components/personal/`) |
|---|---|---|
| **Today** | Progress, Today, Day log | `FitnessStudio.tsx`: `Progress`, `Today`, `DayLog` |
| **Training** | Training program, Plans & targets, Food & exercise | `TrainingProgram.tsx`; `FitnessPanel` from `PersonalPanels.tsx` with page "Plans & targets" and "Log" |
| **Food** | Recipes, Scan food, Weekly meal planner | `FitnessPanel` pages "Recipes" and "Scan food"; `MealPlanner.tsx` |

Current tab list: `FitnessStudio.tsx` line ~72 (`tabs: [Tab, string][]`), the `Tab` type (line ~24), `PANEL_PAGE` (line ~26) and the saved tab key `zaenia.fitness.tab`.

## The five options (from the preview)
- **A Stacked sections:** each merged tab is one scrolling page; the old tabs become labelled sections.
- **B Dashboard grid:** tiles, everything in a tab visible at once (Progress chart + Today rings on top, Day log below; Program week + Targets, Food & exercise below; Meal week + Scan/nutrients, Recipes below).
- **C Summary + switch:** a summary strip (weight, kcal, protein, today's workout) on top of every tab, then a segmented switch between the old pages.
- **D Timeline first:** Today has the day log as the centre column with rings and progress beside it; Training and Food lead with the week, then the day's detail.
- **E Side rail:** each tab has a short left list of its old pages and the page on the right (Grey prefers sidebar navigation).

## How to build it
1. Keep every existing component; only regroup them. New `Tab = "today" | "training" | "food"`, with a sub-view state where the option needs one (C and E).
2. Migrate the saved tab: map old values (`progress`, `today`, `log` → `today`; `program`, `plans`, `food` → `training`; `recipes`, `scan`, `meal-planner` → `food`).
3. Fix the internal jumps: `choose("program")` / `choose("food")` (setup, "Log food", "Open the workout"), `scanFood` (`choose("scan")` + `zae:food-scan`), and the chat/voice openers that target fitness sub-tabs (`ALIAS_SUBTAB`, `zae:page-tab` with page `fitness`, the `food-meal` and `training-setup` forms in `App.tsx`).
4. Use the look-styles tokens (`--zx-panel`, `--zx-line`, `--zx-radius`, `--zx-gap`), so per-tab colour, window style and spacing still apply (Grey's rule for every new page).
5. Phone width must still work (the phone web app shows Fitness).
6. Check: `node scripts/*.test.cjs` and `npx tsc --noEmit -p .` in `desktop`, the full Python suite (list `*_test.py` modules explicitly), then `npm run build && npm run build:web && npm run tauri build -- --no-bundle`, `scripts\restart_zaenia_server.ps1` only if Python changed, and `scripts\update_desktop_app.ps1`.

## Repo notes
- Claude works in `C:\Projects\ZAENIA-Claude` on `claude/brain-validation` and fast-forwards the live checkout (`C:\Projects\ZAENIA`, branch `codex/zaenia-identity-charter`). Approved ZAE Build requests also commit on the live branch, so merge the live branch first.
- Running notes for the build plan: `docs/architecture/CLAUDE_NOTES_2026-11-01.md`.
