# Claude install note — 2026-11-08

Grey asked Claude to install the Code Doctor **Plain English** tab and ZAE's **self-map**. Both are committed on branch `claude/code-doctor-plain-english` (`150a2c6`, `84facb8`, based on `9af7887`); see Master Build Plan sections 33–34 and handoff sections 27–28 on that branch.

To install, the code changes (not the docs) from that branch were applied on top of the uncommitted work in this shared checkout (`codex/stream-studio-plan`). The patch applied cleanly. Nothing was committed here.

- **New files:** `core/assistant_platform/plain_english.py` and its test, `core/brain/self_map.py`, `core/brain/self_map_planned.yaml` and its test, `desktop/src/components/tools/PlainEnglish.tsx`.
- **Edited files:** `core/api/tools_routes.py`, `core/assistant_platform/code_doctor.py`, `core/brain/conversation_rules.py`, `core/brain/local_llm.py`, `desktop/src/components/tools/CodeStudio.tsx`, `CodeStudio.css` and `Playground.tsx`.
- **Pre-install copies** of the edited files: `backups/claude-plain-english-install-2026-11-08/`.

**Checks in this checkout:** 993 Python tests passed (1 skipped); `closure_check`, `self_test` and `integration_check` passed; all 28 desktop scripts and the desktop, web and native builds passed.

**Installed:** `scripts/update_desktop_app.ps1` installed and reopened the app, and its hash matches the build. The old `--unattended` server process was stopped and the `ZAENIA API Server` task was started again. `/health` reports unattended mode with authentication required, `/app/` returns 200 and serves the bundle containing the new tab, and `/api/code/explain` returns 401 without credentials.

When committing this checkout's work, either include these files or take them from the Claude branch. Don't drop them, or the installed app will lose the tab on the next rebuild.

## Update — research upgrades and the ENTHON name (later on 2026-11-08)

- The Plain English tab is now labelled **ENTHON** (Grey's choice, Claude commit `f2971ca`). It touched `CodeStudio.tsx`, `PlainEnglish.tsx`, `Playground.tsx` and `core/brain/self_map_test.py`.
- **Research upgrades** (Claude commit `e8f62df` on `claude/research-upgrades`; Master Build Plan section 35 on that branch) were applied here the same way, as a clean patch with no commits.
  - New files: `core/research/sources.py`, `core/research/evidence.py`, `core/research/research_upgrade_test.py`.
  - Edited files: `core/research/agent.py`, `core/research/agent_test.py`, `core/brain/seek.py`, `desktop/src/components/research/WebAgentPanel.tsx`, `Research.css`.
  - Pre-install copies: `backups/claude-research-install-2026-11-08/`.
- **Checks here:** 1,004 Python tests OK; the 3 foundation suites, 28 desktop scripts, TypeScript, and web and native builds pass. The app is reinstalled with a matching hash. The server was restarted in the same unattended mode: `/health` and `/app/` work, and research routes return 401 without credentials.
- Include these files when committing this checkout.
