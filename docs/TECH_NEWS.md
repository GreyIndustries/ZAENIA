# Tech news module

Status: IMPLEMENTED, UNIT TEST (8 pass), live feed check (10 of 10 sources reachable, 2026-10-21), live model check (llama3.1:8b answered "latest tech news" and "news about GPUs" from the cached headlines). Not yet merged into main.

## What it does

ZAE follows tech news from ten credible sources, listed in `core/tech_news/sources.yaml`:

| Source | Focus | Why it's on the list |
|---|---|---|
| Ars Technica | general, science, policy, hardware, security | In-depth specialist reporting; publishes corrections |
| MIT Technology Review | AI, science, research | Research-grounded explanations |
| IEEE Spectrum | engineering, hardware, AI | The engineering society's magazine; technically reviewed |
| BBC News Technology | general, policy | Public broadcaster with strict editorial guidelines |
| NPR Technology | general, policy, society | Non-profit newsroom with a public ethics code |
| The Verge | consumer, gadgets, AI, gaming | Large newsroom; transparent ethics and corrections |
| Wired | general, security, AI, science | Long-running investigative and explanatory reporting |
| The Register | enterprise, security, software | Fast, sceptical enterprise and security coverage |
| Tom's Hardware | hardware, GPUs, CPUs, PC | Hands-on testing and benchmarks |
| BleepingComputer | security, software, Windows | Rapid, detailed cybersecurity reporting |

The Guardian Technology and Krebs on Security are in the file as alternates, switched off. "Credible" here is an editorial judgment, based on named reporters, public corrections, original reporting or expert review, and keeping news separate from advertising. Edit the file to change the list.

- The API server checks every feed every 30 minutes (and on "Check now"). It reads only public headlines, links, dates and short summaries. Nothing about Grey is sent.
- When several sources report the same story, it's grouped and marked "N sources", and those stories are listed first.
- Headlines are cached in `data/news/tech_news.json` (not in git), so ZAE can still answer offline and says how old the news is. If a source fails, its earlier stories are kept.
- Ask "what's the latest tech news?" or "any news about Nvidia?" and ZAE answers from the cache, naming her sources. She doesn't invent news when the cache is empty.
- The app has a **Tech News** window: topic filters (AI, Hardware, Security, Gaming, Science), search, links to every source, and source status. You can also say "open tech news".

## Safety

- Feed text is untrusted. It reaches the model labeled as reference, never as instructions, and it never teaches Grey's profile or grants permissions (principle C).
- XML feeds that declare a DTD or entities are refused, and feeds over 3 MB are rejected.
- Only `https://` sources are accepted.
- This is an optional online extension (principle A). Without internet, everything else works normally.

## Files

- `core/tech_news/service.py`: fetching, parsing, grouping, cache, `news_context()` for the brain.
- `core/tech_news/sources.yaml`: the source list.
- `core/tech_news/service_test.py`: unit tests.
- Hooks: `core/api/server.py` (background refresh), `core/api/ui_routes.py` (`GET /api/news/tech`, `POST /api/news/tech/refresh`, both `status.read`), `core/brain/brain_service.py` (news context only for news questions).
- UI: `desktop/src/components/news/NewsPanel.tsx`, plus the News section in `App.tsx`, `layoutCommands.ts` and `WindowShell.tsx`.

## Right-side panel (2026-10-21, branch feature/claude-development)

Grey asked for a right-side panel for tech news. On the desktop (not on the phone), a slim **TECH NEWS** rail now sits down the right side under the top bar. It shows the top 8 stories, most-covered and newest first, with the sources, a "N sources" badge and the story's age. Clicking a story opens it in the default browser (via the Tauri opener plugin in the desktop app). "All tech news" opens the full window. The › button hides the rail to a small tab on the right edge, and the choice is remembered on that device.

While the rail is open, the stage (core, reply cards, chat bar) narrows to the space on its left, so nothing sits underneath it. Windows opened from the dock still float above everything. The rail refreshes from the local cache every 10 minutes while visible, and makes no requests while hidden.

Status: IMPLEMENTED; desktop tsc, UI script tests and build pass; visually checked at 1600×900 open and hidden (preview data). Not merged.
Files: desktop/src/components/news/NewsRail.tsx and .css, desktop/src/core/openLink.ts (shared link opener; NewsPanel links now use it too), desktop/src/App.tsx.
