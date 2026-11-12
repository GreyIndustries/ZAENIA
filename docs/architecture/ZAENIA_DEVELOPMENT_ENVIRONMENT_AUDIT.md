# ZAENIA Development Environment Audit

**Audit date:** 2026-11-01
**Target:** Windows development workstation
**Mode:** Read-only inspection. No software, configuration, branch, or production changes were made.
**Confidence note:** Facts below come from commands available in this session. Where access was blocked, the result is marked unknown rather than inferred.

## 1. Hardware inventory

| Item | Finding | Verification |
|---|---|---|
| Windows | Windows reports version `10.0.26300.9711`; the supplied project brief identifies the target OS as Windows 11. | `cmd /c ver`; machine inventory APIs were blocked. |
| CPU | Not verified. Windows CIM inventory access was denied. | `Get-CimInstance Win32_Processor` unavailable. |
| System RAM | Not verified. Windows CIM inventory access was denied; no reliable physical-memory value was returned by the available counter query. | `Get-CimInstance Win32_ComputerSystem` / `Get-ComputerInfo` unavailable. |
| GPU | NVIDIA GeForce RTX 4070 Ti SUPER, 16,376 MiB reported. | `nvidia-smi`. |
| NVIDIA driver | 617.14. | `nvidia-smi`. |

## 2. GPU and driver

The GPU model, memory, and driver were directly reported by `nvidia-smi`. CUDA runtime compatibility and actual model acceleration were not verified. No inference benchmark was run.

## 3. Python installations

| Location / command | Reported version | Assessment |
|---|---:|---|
| `python` on PATH | 3.13.15 | Current default does not match the requested 3.11.9. |
| `C:\Users\zacka\AppData\Local\Programs\Python\Python311\python.exe` | 3.11.0 | Python 3.11 exists, but the requested patch version 3.11.9 was not found. |
| `C:\Users\zacka\AppData\Local\Programs\Python\Python312\python.exe` | 3.12.0 | Also installed. |
| `C:\Projects\ZAENIA\.venv\Scripts\python.exe` | 3.13.15 | Existing project environment; preserve it pending owner approval. |
| `C:\Projects\ZAENIA\.venv311_backup\Scripts\python.exe` | 3.11.0 | Backup environment, not the requested 3.11.9. |
| `.venv_broken_20260829` | Interpreter did not start at the expected Scripts path. | Not investigated or modified. |
| `py -0p` | “No installed Pythons found.” | Launcher inventory disagrees with directly verified interpreter paths. |

**Conclusion:** Python 3.11.9 is not verified as installed. Do not rebuild or replace an environment until the owner approves the next phase.

## 4. Git installation and repository relationships

- Git version: `2.51.2.windows.1`.
- `C:\Projects\ZAENIA` remote `origin` is `https://github.com/GreyIndustries/ZAENIA.git` for fetch and push.
- The accessible `C:\Projects\ZAENIA` checkout is on `codex/zaenia-identity-charter` at `571e68904b1e3f3f4bdd8e51504a996b32168f9c`, not on `main` as the 2026-10-30 handoff described.
- That checkout already has uncommitted changes in `AGENTS.md`, `docs/architecture/HANDOFF_2026-10-30.md`, and `docs/architecture/ZAENIA_Master_Build_Plan.md`, plus untracked `docs/architecture/ZAENIA_Identity_and_Product_Charter.md` and `docs/previews/`. These were left untouched.
- `git worktree list` identifies four linked checkouts: `C:\Projects\ZAENIA`, `C:\Projects\ZAENIA-Claude`, `C:\Projects\ZAENIA-ChatGPT`, and `C:\Users\zacka\.codex\worktrees\conductor-weekend\ZAENIA`.
- The Claude worktree is listed on `claude/brain-validation` at the same commit as the accessible project checkout. Direct filesystem inspection of `C:\Projects\ZAENIA-Claude` was denied by this session's access boundary.
- The ChatGPT worktree is listed on `feature/chatgpt-development` at `82d79b12001fe8f9d5281c3268c86132e3ce7acb`.
- The Conductor worktree is listed on `codex/conductor-weekend-2` at `caff135583941bc744d798fc0f15d93bec058664`.
- The local tag `zaenia-pristine-2026-10-30` exists. No reset, branch switch, merge, or push was performed.

## 5. Ollama installation and runtime

- Ollama CLI is installed; client version reported: `0.40.11`.
- Calls to `ollama list` and `ollama ps` could not connect to `127.0.0.1:11434` because this session's network policy denied local socket access. This does **not** prove whether the host Ollama service is running, which models are installed, or whether inference is GPU-accelerated.
- The configured `OLLAMA_HOST` value was not present in the environment variables inspected. Other non-secret Ollama tuning variable names were present; their values are omitted.

## 6. OpenCode and Claude Code

- OpenCode: no `opencode` executable was found on PATH.
- Claude Code: installed; `claude --version` reports `2.1.302`.
- Claude Code configuration was not changed or inspected for credentials.

## 7. Dependencies and test configuration

- Python dependency files present: `requirements.txt`, `requirements-module1.txt`, and `requirements-operator.txt`.
- `requirements.txt` mixes unpinned entries with exact pins; no `pyproject.toml`, `setup.cfg`, `pytest.ini`, or `tox.ini` was found at the project root.
- `desktop/package.json` defines the Vite/Tauri app, TypeScript build, web build, and two named Node test scripts. Node is `v24.19.0`; npm is `11.17.0`.
- The handoff documents Python `unittest` usage and additional desktop test scripts. Tests were not run in this read-only audit.
- No dependency installation or Python environment modification was performed.

## 8. Existing security controls and scan results

- `.gitignore` excludes `.env` files, key/certificate extensions, local `config/settings.yaml`, databases, private calendar and learning data, personal profile/assessment data, backups, and generated artifacts. Ignore rules reduce accidental adds but do not protect files already committed or copied outside the repository.
- `config/settings.yaml` is ignored and was not listed as a tracked file. Its contents were not read.
- `.github/workflows/zaenia-ci.yml` contains a Git-history Gitleaks job. It pins Gitleaks `8.24.3`, verifies the downloaded archive checksum, and scans Git history with redaction enabled.
- Local Gitleaks is installed; version `8.30.1`.
- Read-only Gitleaks checks on the accessible checkout reported **0 findings in local Git history** and **0 findings in the tracked working diff**. These checks do not cover every untracked file, other worktrees, or a current GitHub scan. A full directory scan was stopped because it traversed generated/dependency content for longer than appropriate; therefore the earlier reported ~79 unstaged findings are **not considered resolved or fully re-audited**.
- The GitHub repository's Free-plan secret-scanning or push-protection settings and branch protections were not inspected. The presence of a CI workflow does not establish those account-level settings.
- No credential values, secret material, or personal assessment data are included in this report.

## 9. Problems and verification gaps

1. Python 3.11.9 is not verified; the active project `.venv` uses Python 3.13.15 and the available Python 3.11 reports 3.11.0.
2. OpenCode is not installed or not discoverable on PATH.
3. Ollama is installed, but service status, model inventory, localhost binding, and GPU acceleration could not be verified from this restricted session.
4. CPU and physical RAM could not be inspected due Windows inventory access restrictions.
5. The accessible project checkout is on a feature branch with existing uncommitted changes, while the handoff describes a different `main` state. The handoff is therefore not a reliable description of every current checkout.
6. The earlier ~79 Gitleaks findings have not been conclusively rechecked across all current files and worktrees. The limited Git-history and tracked-diff scans returned zero; the full directory scan did not complete.
7. Claude's configuration, account-level GitHub security settings, and agent Windows-account boundaries were not verified.

## 10. Recommended next steps

1. Keep the existing checkout, branch, and virtual environments intact. Confirm which checkout is the intended integration workspace before any implementation work.
2. With owner approval, verify the host's CPU/RAM and Ollama runtime from a normal local session, then record models, bind address, GPU placement, and a small inference benchmark.
3. Confirm whether Python 3.11.9 is required exactly or whether another 3.11 patch is acceptable. If exact, install/configure only after approval; preserve `.venv` and use a separate environment for evaluation.
4. Evaluate OpenCode installation and configure a local-only Ollama endpoint. Verify provider selection before any private-code use.
5. Reconcile Gitleaks findings by scanning the intended branch's tracked files, untracked files, and Git history separately with redacted output; document false-positive handling without weakening the scanner policy.
6. Inspect the Claude/ChatGPT worktree arrangement and current Claude configuration without exposing credentials. Do not grant autonomous agents access to production secrets or personal data.
7. Before building the proposed Development Controller, define a separate standard Windows account, sanitized repository copy, explicit tool allowlist, audit-log location, and owner approval gates.
8. Run no installs, configuration changes, merges, or production actions until the owner approves moving beyond this audit.

## Audit boundary

This report is a snapshot of the accessible workstation and checkout on 2026-11-01. Restricted CIM and local-network access limited verification. It is not a claim that the whole machine, every checkout, or GitHub account settings have been audited.
