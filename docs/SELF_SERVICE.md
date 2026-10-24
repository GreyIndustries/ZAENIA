# Running and upgrading ZAE yourself

This guide is for Grey. It covers everything needed to keep ZAE running, bring in new features, test them, and undo them, without waiting on Claude or Codex. Every step is a command you can copy.

Contents:
1. [The maintenance tool](#1-the-maintenance-tool)
2. [Everyday checks](#2-everyday-checks)
3. [Getting new features](#3-getting-new-features)
4. [Updating ZAE](#4-updating-zae)
5. [Undoing an update](#5-undoing-an-update)
6. [Testing by yourself](#6-testing-by-yourself)
7. [GitHub on your own](#7-github-on-your-own)
8. [Python and add-ons](#8-python-and-add-ons)
9. [Fixing common problems](#9-fixing-common-problems)
10. [Safety rules](#10-safety-rules)

---

## 1. The maintenance tool

Everything in this guide goes through one tool, `scripts\zae.ps1`.

**Open it:** press Start, type **ZAE Maintenance**, and press Enter. A blue PowerShell window opens with this menu:

```
  1  Status       what's running and which version
  2  Test         run every test and the security suites
  3  Update       bring in new work from GitHub (tested, undone automatically if it fails)
  4  Build        rebuild and install the apps
  5  Restart      restart her server
  6  Rollback     undo the last update
  Q  Quit
```

Type a number and press Enter.

**From any PowerShell window instead:**

```powershell
cd "C:\Projects\ZAENIA"
.\scripts\zae.ps1 status
.\scripts\zae.ps1 test
.\scripts\zae.ps1 update
.\scripts\zae.ps1 build
.\scripts\zae.ps1 restart
.\scripts\zae.ps1 rollback
```

If the Start menu shortcut ever goes missing, run `.\scripts\zae.ps1 shortcut` to put it back.

**What the tool never touches:** your `data\` folder. That folder holds her memory, your profile, settings, game styles, voice profile and secrets. Git ignores it, so updates and rollbacks only change code.

---

## 2. Everyday checks

Run **1 Status**. Each line tells you something:

| Line | Meaning | If it's wrong |
|---|---|---|
| `Code: branch main, <commit>` | The version she's running. | She should always be on `main`. If not: `git -C C:\Projects\ZAENIA switch main` |
| `NOTE n file(s) changed locally` | Someone edited code in the live folder without committing it. | Updates refuse to run until this is clean. See [section 9](#9-fixing-common-problems). |
| `Python: Python 3.13.x` | Her Python version. | — |
| `Server: running, mode ...` | Her brain and API are up. | `5 Restart`. |
| `PC voice: listening` | The PC microphone service is on. | Start it: `.\scripts\start_zaenia_voice.ps1` (asks for your passkey). |
| `Last security check` | When she last checked herself. | Open the Security tab to run one. |
| `Latest restore point` | Where **Rollback** would take you. | — |

**Server modes:**
- **Token mode** (normal): `restart` works without your passkey.
- **Passkey mode** (full owner features): start it with `.\scripts\start_zaenia_server_passkey.ps1`. Nobody can restart it without your passkey, not even Claude.

---

## 3. Getting new features

New features come from Claude or Codex. Each works in its own copy of the code and pushes a branch to GitHub:

| Assistant | Its folder | Its branch |
|---|---|---|
| Claude | `C:\Projects\ZAENIA-Claude` | `feature/claude-development` |
| Codex (ChatGPT) | `C:\Projects\ZAENIA-ChatGPT` | `feature/chatgpt-development` |

**How to ask for a feature**, so the result is easy to install yourself:

> Build &lt;the feature&gt; in your worktree. Run all tests, update the master build plan, commit, and push your branch. Don't touch the live install. Tell me when it's ready for `zae.ps1 update`.

When it says it's pushed, run **3 Update** (section 4). Press Enter for Claude's branch, or type `C` for Codex's.

**Asking for a fix:** paste the exact error lines (the red `FAIL` lines, or a screenshot) and say what you were doing.

---

## 4. Updating ZAE

**3 Update** does all of this:

1. Checks that she's on `main` with no uncommitted changes.
2. Downloads the branch from GitHub and **lists what's new**, then asks `Bring these in, test them and install? (y/n)`.
3. Saves a **restore point**, a git tag named `zae-rollback-<date>-<time>`.
4. Merges the new work. If it clashes with what's installed, it changes nothing and tells you to ask the assistant to rebase.
5. Installs new Python or app add-ons, but only if the update changed them.
6. Runs **every test plus the three security suites**. **If anything fails, it undoes the update automatically** and shows the failing lines; send those to the assistant.
7. Rebuilds the desktop and phone apps, installs the desktop app (it closes and reopens ZAE), and restarts her server.

It takes about 3–5 minutes. **Close any game first**, because the build uses your CPU.

To update from a different branch:

```powershell
.\scripts\zae.ps1 update -Branch feature/chatgpt-development
```

**If it says "Close the running Zae window":** close ZAE and run **4 Build**.

**After updating:**
- If the update changed the PC voice service, restart that too: close its console, then run `.\scripts\start_zaenia_voice.ps1`.
- If her server was in passkey mode, restart it the same way.

---

## 5. Undoing an update

Run **6 Rollback**. It lists the last five restore points (newest first), asks before doing anything, puts the code back exactly as it was, rebuilds, and restarts.

To go back further than the latest restore point:

```powershell
.\scripts\zae.ps1 rollback -To zae-rollback-20261024-201500
```

To see every restore point:

```powershell
git -C C:\Projects\ZAENIA tag --list "zae-rollback-*"
```

Rollback never touches `data\`, so her memory and settings stay as they are.

---

## 6. Testing by yourself

Run **2 Test** any time, for example after Windows updates or if she acts strangely. It runs:
- about 640 Python tests;
- the security suites: **self-test** (passkey, sessions, rules, moral code, audit, encryption, tokens), **closure check** (entry points and the rule that your message reaches her brain unchanged) and **integration check** (console launches go through the rules);
- the app's UI checks and its TypeScript check.

Green `OK` lines mean healthy. A red `FAIL` line names the test. Send it to Claude or Codex.

To see the full output of one security suite:

```powershell
cd "C:\Projects\ZAENIA"; .\.venv\Scripts\python.exe -m core.foundation.closure_check
```

**Reasoning benchmark** (how well her brain reasons; needs your passkey):

```powershell
cd "C:\Projects\ZAENIA"; .\.venv\Scripts\python.exe -m core.reasoning benchmark --provider local --limit 14
```

---

## 7. GitHub on your own

The repository is `github.com/ZMGrey/ZAENIA` (private). **A free account is enough:** opening and merging pull requests on your own private repo doesn't need a paid plan. Paid plans only add extras such as required reviews and branch protection on private repos.

**Sign in once on this PC** (opens your browser):

```powershell
gh auth login
```

Choose GitHub.com, then HTTPS, then "Login with a web browser", and enter the code it shows.

**See the assistants' branches and pull requests:**

```powershell
cd "C:\Projects\ZAENIA"
gh pr list
gh pr view <number> --web
```

**Turn a pushed branch into a pull request and merge it** (keeps GitHub's `main` matching yours):

```powershell
gh pr create --base main --head feature/claude-development --title "Claude: <what it adds>" --body "Tested with zae.ps1 update."
gh pr checks <number> --watch
gh pr merge <number> --merge
```

`gh pr checks --watch` waits for the GitHub test run (Python syntax, desktop build, secret detection). Merge only when it's green.

**Push your live `main` to GitHub** (for example, after updating locally):

```powershell
git -C C:\Projects\ZAENIA push origin main
```

GitHub's checks run on every push. You can see them under the repo's **Actions** tab.

---

## 8. Python and add-ons

- She runs on **Python 3.13** in `C:\Projects\ZAENIA\.venv`.
- The previous 3.11 setup is kept in `.venv311_backup`.

**Install or upgrade one add-on:**

```powershell
cd "C:\Projects\ZAENIA"
.\.venv\Scripts\python.exe -m pip install --upgrade <name>
.\scripts\zae.ps1 test
```

If the tests fail afterwards, put the old version back:

```powershell
.\.venv\Scripts\python.exe -m pip install <name>==<old version>
```

`pip list` shows the current versions.

**Switch back to the old Python environment completely:**
1. Run `.\scripts\zae.ps1 restart` once, so you know the script works.
2. Close ZAE and the PC voice console.
3. Stop the server:
   ```powershell
   Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? CommandLine -like '*core.api.server*' | % { Stop-Process -Id $_.ProcessId -Force }
   ```
4. Swap the folders:
   ```powershell
   Rename-Item C:\Projects\ZAENIA\.venv .venv313_backup; Rename-Item C:\Projects\ZAENIA\.venv311_backup .venv
   ```
5. Run `.\scripts\zae.ps1 restart`.

**App add-ons (desktop):** `cd desktop; npm ci`. **Update** runs this for you when needed.

---

## 9. Fixing common problems

| Problem | Fix |
|---|---|
| Server not answering | `5 Restart`. If it still fails, it runs in the window so you can read why. |
| "Close ZAE first" / "Close the running Zae window" | Close ZAE completely (check the tray), then `4 Build`. |
| Update says "uncommitted local changes" | See which files with `git -C C:\Projects\ZAENIA status`. If you didn't mean to change them, undo with `git -C C:\Projects\ZAENIA restore <file>`. If an assistant made them in the live folder, ask it to move them to its worktree. |
| Update says "conflicts with this install" | Nothing changed. Ask the assistant: "Rebase your branch on main and push again." |
| A test fails after Windows or driver updates | Run `2 Test` again. If it still fails, send the FAIL lines. |
| She doesn't recognise your voice | Say "train my voice", or run `.\scripts\voice_training.ps1` (passkey). |
| Forgot the spoken phrase | `.\.venv\Scripts\python.exe -m core.foundation.foundation_main reset-voice-phrase`, then `... setup-voice-phrase` (passkey for each). |
| She answers twice | Make sure only one PC voice console is open, then restart it. |
| Game mode turned on for a normal app | Tell Claude or Codex the app's name; it goes on the not-a-game list (`core/assistant_platform/game_mode.py`). |
| Security check failed | Open the Security tab. Each failed line has a **Fix** with the exact command. |
| Something broke after an update | `6 Rollback`. |

---

## 10. Safety rules

- Never put your passkey, spoken phrase, API tokens or anything from `data\secure\` in a message, a file in the repo, or GitHub.
- Never commit the `data\` folder. Git ignores it, so don't force it with `git add -f`.
- Don't edit code in `C:\Projects\ZAENIA` directly. Ask an assistant to work in its own folder, then **Update**. That way every change is tested and can be undone.
- Read the "New on ..." list before saying `y` to an update. If you don't recognise something, say `n` and ask.
