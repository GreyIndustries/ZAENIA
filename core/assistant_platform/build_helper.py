"""Build requests: ZAE hands a code change to a coding tool, tests it in a copy, and waits for Grey (2026-11-01).

The flow (Grey picked option 2 with Claude Code and Aider, and option 3, nightly ideas):
1. Grey asks ("ZAE, build ...") or taps "Build it" on an idea. Talk writes a brief; nothing runs yet.
2. Grey checks the brief and taps Start. The request waits while a game is running.
3. A separate git worktree (ZAENIA-Helper, branch zae/<id>) is made from the live code. data/, secrets and the
   live app are never in it. The coding tool works only there: Claude Code (no shell, no web) for most work,
   Aider with the local Study model for small changes or when offline.
4. Every changed path is checked against the locked list (security, voice check, passkey, permissions, the
   scripts that build and restart her, and this helper). Any hit throws the work away.
5. The test suite, the security suites and (for app changes) the UI checks and TypeScript run in the copy. A
   failure goes back to the tool up to twice.
6. Ready: the diff and results wait in Code Doctor > Build requests. Approve (desktop app only) merges the branch
   into the live code and rebuilds or restarts what changed; Reject deletes it; Undo reverts an approved change.

ZAE never starts, approves or merges anything herself, never pushes, and can't change what's locked here.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HELPER_ROOT = PROJECT_ROOT.parent / "ZAENIA-Helper"
STATE_FILE = PROJECT_ROOT / "data" / "ui" / "build_requests.json"
APPLY_LOG = PROJECT_ROOT / "data" / "ui" / "build_apply.log"
AIDER_HOME = PROJECT_ROOT.parent / "ZAENIA-Tools" / "aider"  # its own Python environment, outside the repo
AIDER_MODEL = "qwen3:14b"
KEEP = 50
TOOLS = ("claude", "aider")
SIZES = ("small", "medium", "large")
TOOL_LIMIT = {"claude": 30 * 60, "aider": 20 * 60}
RETRIES = 2

# Paths a build request may never change (compared lower-case, as path prefixes). Code Doctor's and the file
# tools' own lists are added in locked().
LOCKED = (
    "core/assistant_platform/build_helper.py", "core/assistant_platform/build_ideas.py", "core/api/build_routes.py",
    "core/api/tools_routes.py", "core/api/near_pc.py", "core/api/client_gate", "core/api/face_passkey",
    "core/api/mobile_auth", "core/api/desktop_key", "core/api/security_", "core/api/vault", "core/api/auth",
    "core/assistant_platform/game_mode.py",
    "scripts/", ".github/", ".claude/", ".gitignore", ".gitattributes", "agents.md", "claude.md",
    "desktop/src-tauri/", "desktop/package.json", "desktop/package-lock.json", "desktop/vite.config",
    "requirements", "pyproject.toml", "data/",
)
RULES = """You are working in a separate copy of ZAE's code (ZAENIA), not the live app. Grey reviews your change before it goes live.
- Make the smallest change that does what the brief asks, in the style of the surrounding code. Add or update tests next to the code (files named *_test.py, or desktop/scripts/*.test.cjs).
- Never change these locked paths (the change is thrown away if you do): {locked}.
- Don't run commands, install packages or use the web. ZAE runs the tests herself and tells you what failed.
- Never add secrets, tokens or personal data.
- When you're done, reply with two or three plain sentences saying what you changed and how Grey will see it."""

_LOCK = threading.RLock()
_WAKE = threading.Event()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_env() -> dict[str, str]:
    """The environment for tools and tests, without anything that looks like a secret."""
    return {key: value for key, value in os.environ.items()
            if not re.search(r"TOKEN|SECRET|PASS|API_?KEY|CREDENTIAL|ZAENIA_.*KEY|TWILIO|OPENAI|GEMINI|GOOGLE_", key, re.I)}


def locked(path: str) -> bool:
    rel = path.replace("\\", "/").removeprefix("./").lower()
    if any(rel == item.rstrip("/") or rel.startswith(item) for item in LOCKED):
        return True
    from core.api.ui_files import PROTECTED as FILE_LOCKS
    from core.assistant_platform.code_doctor import PROTECTED as DOCTOR_LOCKS
    return any(rel == item.lower() or rel.startswith(item.lower().rstrip("/") + "/") for item in FILE_LOCKS) \
        or any(rel.startswith(item.lower()) for item in DOCTOR_LOCKS)


def git(*args: str, cwd: Path = PROJECT_ROOT, check: bool = True, timeout: float = 120) -> str:
    result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout)
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[:800] or f"git {args[0]} failed")
    return result.stdout.strip()


# ---------------------------------------------------------------- the coding tools
def claude_exe() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    pattern = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "Anthropic.ClaudeCode_*" / "claude.exe")
    hits = sorted(glob.glob(pattern))
    return hits[-1] if hits else None


def aider_exe() -> str | None:
    exe = AIDER_HOME / "Scripts" / "aider.exe"
    return str(exe) if exe.exists() else None


def online(host: str = "api.anthropic.com") -> bool:
    import socket
    try:
        socket.create_connection((host, 443), timeout=3).close()
        return True
    except OSError:
        return False


def tools_available() -> dict[str, bool]:
    return {"claude": bool(claude_exe()), "aider": bool(aider_exe())}


def choose_tool(size: str, wanted: str | None = None, *, available: dict[str, bool] | None = None,
                is_online: Callable[[], bool] = online) -> str:
    """Claude Code for real features; Aider (local, free) for small changes or when Claude Code can't be reached."""
    available = available or tools_available()
    if wanted in TOOLS and available.get(wanted):
        return wanted
    if available.get("claude") and (size != "small" or not available.get("aider")) and is_online():
        return "claude"
    if available.get("aider"):
        return "aider"
    if available.get("claude"):
        return "claude"
    raise RuntimeError("Neither coding tool is installed (Claude Code or Aider).")


def run_tool(tool: str, folder: Path, prompt: str, files: list[str]) -> tuple[bool, str]:
    """Run one coding pass in the copy. Returns (finished, what it said)."""
    rules = RULES.format(locked=", ".join(item.rstrip("/") for item in LOCKED[:20]) + ", and ZAE's security code")
    env = _clean_env()
    if tool == "claude":
        exe = claude_exe()
        if not exe:
            raise RuntimeError("Claude Code isn't installed.")
        command = [exe, "-p", "--output-format", "json", "--permission-mode", "acceptEdits", "--no-session-persistence",
                   "--strict-mcp-config", "--setting-sources", "project", "--append-system-prompt", rules,
                   "--disallowedTools", "Bash,WebFetch,WebSearch,NotebookEdit,Task"]
        stdin = prompt
    else:
        exe = aider_exe()
        if not exe:
            raise RuntimeError("Aider isn't installed.")
        env.update({"OLLAMA_API_BASE": "http://127.0.0.1:11434", "AIDER_ANALYTICS": "false", "PYTHONIOENCODING": "utf-8"})
        command = [exe, "--model", f"ollama_chat/{AIDER_MODEL}", "--yes-always", "--no-auto-commits", "--no-dirty-commits",
                   "--no-suggest-shell-commands", "--no-check-update", "--no-analytics", "--no-show-model-warnings",
                   "--no-detect-urls", "--no-pretty", "--no-stream", "--no-gitignore", "--map-tokens", "2048",
                   "--message", rules + "\n\n" + prompt,
                   *[name for name in files if (folder / name).is_file() and not locked(name)][:8]]
        stdin = ""
    try:
        result = subprocess.run(command, cwd=folder, input=stdin, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=TOOL_LIMIT[tool], env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return False, f"The coding tool ran out of time ({TOOL_LIMIT[tool] // 60} min)."
    out = result.stdout or ""
    if tool == "claude":
        try:
            data = json.loads(out)
            return (not data.get("is_error")), str(data.get("result") or "").strip()[:3000]
        except ValueError:
            return False, (out or result.stderr or "Claude Code gave no answer.").strip()[-1500:]
    tail = "\n".join(line for line in out.splitlines() if line.strip())[-2000:]
    return result.returncode == 0, tail or (result.stderr or "").strip()[-1500:]


# ---------------------------------------------------------------- the copy
def make_copy(request_id: str, *, root: Path = PROJECT_ROOT, helper: Path = HELPER_ROOT) -> tuple[str, str]:
    """A fresh worktree of the live code on its own branch. Returns (branch, base commit)."""
    remove_copy(root=root, helper=helper)
    base = git("rev-parse", "HEAD", cwd=root)
    branch = f"zae/{request_id[:8]}"
    git("worktree", "add", "-B", branch, str(helper), base, cwd=root)
    node_modules = root / "desktop" / "node_modules"
    if node_modules.is_dir() and (helper / "desktop").is_dir():
        # The copy shares the live app's packages through a junction (removed before the copy is deleted).
        subprocess.run(["cmd", "/c", "mklink", "/J", str(helper / "desktop" / "node_modules"), str(node_modules)],
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return branch, base


def remove_copy(*, root: Path = PROJECT_ROOT, helper: Path = HELPER_ROOT) -> None:
    junction = helper / "desktop" / "node_modules"
    if junction.exists() or os.path.islink(junction):
        try:
            os.rmdir(junction)  # removes the junction only, never the live packages behind it
        except OSError:
            pass
        if junction.exists():
            raise RuntimeError("Couldn't unlink the copy's packages folder safely; the copy was left in place.")
    if helper.exists():
        git("worktree", "remove", "--force", str(helper), cwd=root, check=False)
        if helper.exists():
            shutil.rmtree(helper, ignore_errors=True)
    git("worktree", "prune", cwd=root, check=False)


def changed_paths(folder: Path, base: str) -> list[str]:
    git("add", "-A", cwd=folder)
    names = git("diff", "--cached", "--name-only", "--no-renames", base, cwd=folder)
    return [line.strip() for line in names.splitlines() if line.strip()]


# ---------------------------------------------------------------- checks
def run_checks(folder: Path, changed: list[str], *, python: Path | None = None) -> tuple[bool, str]:
    """Her tests in the copy: the Python suite and security suites, and for app changes the UI checks and TypeScript."""
    python = python or PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    env, flags = _clean_env(), getattr(subprocess, "CREATE_NO_WINDOW", 0)
    lines: list[str] = []
    modules = sorted(str(path.relative_to(folder).with_suffix("")).replace(os.sep, ".")
                     for top in ("core", "scripts") for path in (folder / top).rglob("*_test.py")
                     if "__pycache__" not in path.parts and "_backup" not in str(path))
    result = subprocess.run([str(python), "-m", "unittest", *modules], cwd=folder, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=20 * 60, env=env, creationflags=flags)
    summary = [line for line in (result.stderr or "").splitlines() if re.match(r"^(Ran \d+|OK|FAILED)", line)]
    lines.append("Python tests: " + " ".join(summary))
    if result.returncode != 0:
        failures = [line for line in result.stderr.splitlines() if re.match(r"^(ERROR|FAIL):", line)][:12]
        detail = result.stderr[-3000:] if not failures else "\n".join(failures) + "\n" + result.stderr[-2000:]
        return False, "\n".join(lines) + "\n" + detail
    for suite in ("core.foundation.self_test", "core.foundation.closure_check", "core.foundation.integration_check"):
        if not (folder / Path(*suite.split("."))).with_suffix(".py").exists():
            continue
        check = subprocess.run([str(python), "-m", suite], cwd=folder, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=10 * 60, env=env, creationflags=flags)
        if check.returncode != 0:
            return False, "\n".join(lines) + f"\nSecurity suite {suite} failed:\n" + (check.stdout + check.stderr)[-2000:]
    lines.append("Security suites: passed")
    if any(name.startswith("desktop/") for name in changed):
        desktop = folder / "desktop"
        for script in sorted((desktop / "scripts").glob("*.test.cjs")):
            ui = subprocess.run(["node", str(script)], cwd=desktop, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=5 * 60, env=env, creationflags=flags)
            if ui.returncode != 0:
                return False, "\n".join(lines) + f"\nUI check {script.name} failed:\n" + (ui.stdout + ui.stderr)[-2000:]
        lines.append("UI checks: passed")
        tsc = desktop / "node_modules" / "typescript" / "bin" / "tsc"
        types = subprocess.run(["node", str(tsc), "--noEmit", "-p", "."], cwd=desktop, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=10 * 60, env=env, creationflags=flags)
        if types.returncode != 0:
            return False, "\n".join(lines) + "\nTypeScript errors:\n" + (types.stdout + types.stderr)[-2500:]
        lines.append("TypeScript: passed")
    return True, "\n".join(lines)


# ---------------------------------------------------------------- the brief
def brief_prompt(request: str, hints: list[str]) -> str:
    return ("You are ZAE. Grey asked you to change your own app. Turn his words into a clear task for a coding tool. "
            "Reply with JSON only: {\"title\": \"3-7 words\", \"brief\": \"what to change and how Grey will see it, "
            "in 2-5 plain sentences\", \"size\": \"small, medium or large\", \"check\": \"one sentence: how to tell it works\"}. "
            "small = a setting, colour, wording or one function; large = a new screen or feature across many files.\n\n"
            f"GREY'S WORDS: {request}\n\nFILES THAT MAY BE INVOLVED: {', '.join(hints) or 'unknown'}")


def file_hints(request: str, *, root: Path = PROJECT_ROOT, limit: int = 10) -> list[str]:
    """Files whose names match words in the request (her own code only)."""
    words = {w for w in re.findall(r"[a-z]{4,}", request.lower())} - {"make", "when", "with", "that", "this", "have", "your",
                                                                      "from", "into", "should", "would", "could", "build", "please"}
    if not words:
        return []
    scored: list[tuple[int, str]] = []
    for top in ("core", "desktop/src"):
        for path in (root / top).rglob("*"):
            if path.suffix not in (".py", ".ts", ".tsx", ".css") or "__pycache__" in path.parts or path.name.endswith("_test.py"):
                continue
            rel = path.relative_to(root).as_posix()
            score = sum(word in rel.lower() for word in words)
            if score and not locked(rel):
                scored.append((score, rel))
    return [rel for _, rel in sorted(scored, key=lambda item: (-item[0], len(item[1])))[:limit]]


def write_brief(request: str, ask: Callable[[str], str]) -> dict[str, Any]:
    hints = file_hints(request)
    raw = ask(brief_prompt(request, hints))
    match = re.search(r"\{.*\}", raw or "", re.S)
    try:
        data = json.loads(match.group(0) if match else "{}")
    except ValueError:
        data = {}
    size = str(data.get("size") or "").lower().strip()
    title = " ".join(str(data.get("title") or request).split())[:80]
    brief = " ".join(str(data.get("brief") or request).split())[:1500]
    check = " ".join(str(data.get("check") or "").split())[:300]
    return {"title": title, "brief": brief + (f" Done when: {check}" if check else ""),
            "size": size if size in SIZES else "medium", "files": hints}


# ---------------------------------------------------------------- requests
class BuildRequests:
    def __init__(self, path: Path = STATE_FILE, *, root: Path = PROJECT_ROOT, helper: Path = HELPER_ROOT,
                 tool_runner: Callable[..., tuple[bool, str]] = run_tool,
                 checks: Callable[..., tuple[bool, str]] = run_checks,
                 choose: Callable[..., str] = choose_tool,
                 gaming: Callable[[], bool] | None = None,
                 notify: Callable[[str, str, str], None] | None = None):
        self.path, self.root, self.helper = Path(path), Path(root), Path(helper)
        self.tool_runner, self.checks, self.choose = tool_runner, checks, choose
        self.gaming = gaming or _gaming
        self.notify = notify or _notify
        self.worker: threading.Thread | None = None

    # storage
    def list(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        from core.foundation.security.io import atomic_write
        atomic_write(self.path, json.dumps(items[-KEEP:], indent=1).encode("utf-8"))

    def get(self, request_id: str) -> dict[str, Any]:
        item = next((entry for entry in self.list() if entry["id"] == request_id), None)
        if item is None:
            raise KeyError("That build request no longer exists.")
        return item

    def _update(self, request_id: str, **changes: Any) -> dict[str, Any]:
        with _LOCK:
            items = self.list()
            item = next((entry for entry in items if entry["id"] == request_id), None)
            if item is None:
                raise KeyError("That build request no longer exists.")
            item.update(changes, updatedAt=_now())
            self._save(items)
            return item

    # steps Grey takes
    def create(self, request: str, ask: Callable[[str], str], *, source: str = "chat", idea: str | None = None) -> dict[str, Any]:
        request = " ".join(str(request).split())[:2000]
        if len(request) < 4:
            raise ValueError("Say what you'd like changed.")
        brief = write_brief(request, ask)
        item = {"id": uuid.uuid4().hex, "request": request, **brief, "tool": None, "status": "draft",
                "step": "Waiting for you to check the brief and tap Start.", "source": source, "idea": idea,
                "createdAt": _now(), "updatedAt": _now()}
        with _LOCK:
            self._save(self.list() + [item])
        return item

    def start(self, request_id: str, *, brief: str | None = None, tool: str | None = None) -> dict[str, Any]:
        item = self.get(request_id)
        if item["status"] not in ("draft", "failed"):
            raise ValueError("Only a draft or a failed request can be started.")
        changes: dict[str, Any] = {"status": "queued", "step": "Waiting for its turn.", "error": None,
                                   "wantedTool": tool if tool in TOOLS else None}
        if brief and brief.strip():
            changes["brief"] = " ".join(brief.split())[:3000]
        item = self._update(request_id, **changes)
        self.ensure_worker()
        return item

    def reject(self, request_id: str) -> dict[str, Any]:
        item = self.get(request_id)
        if item["status"] in ("working", "applying"):
            raise ValueError("Wait until this step finishes.")
        if item["status"] in ("approved", "undone"):
            raise ValueError("This change is already live; use Undo instead.")
        if item.get("branch"):
            git("branch", "-D", item["branch"], cwd=self.root, check=False)
        return self._update(request_id, status="rejected", step="Thrown away. Nothing changed.")

    def approve(self, request_id: str, *, apply: Callable[[list[str]], None] | None = None) -> dict[str, Any]:
        item = self.get(request_id)
        if item["status"] != "ready":
            raise ValueError("Only a ready, tested change can be approved.")
        pre = git("rev-parse", "HEAD", cwd=self.root)
        merged = subprocess.run(["git", "-C", str(self.root), "merge", "--ff-only", item["branch"]], capture_output=True, text=True)
        fast = merged.returncode == 0
        if not fast:
            merged = subprocess.run(["git", "-C", str(self.root), "merge", "--no-ff", "--no-edit", "-m",
                                     f"ZAE build: {item['title']} (approved by Grey)", item["branch"]], capture_output=True, text=True)
            if merged.returncode != 0:
                git("merge", "--abort", cwd=self.root, check=False)
                return self._update(request_id, step="Couldn't add it to the live code: " + (merged.stderr or merged.stdout).strip()[:400]
                                    + " Nothing changed.")
        post = git("rev-parse", "HEAD", cwd=self.root)
        item = self._update(request_id, status="approved", merged={"pre": pre, "post": post, "fast": fast, "at": _now()},
                            step="Approved and added to the live code. Rebuilding what changed.")
        (apply or apply_live)(item.get("changed") or [])
        return item

    def undo(self, request_id: str, *, apply: Callable[[list[str]], None] | None = None) -> dict[str, Any]:
        item = self.get(request_id)
        if item["status"] != "approved" or not item.get("merged"):
            raise ValueError("Only an approved change can be undone.")
        merged = item["merged"]
        if merged["fast"]:
            args = ["revert", "--no-edit", f"{merged['pre']}..{merged['post']}"]
        else:
            args = ["revert", "--no-edit", "-m", "1", merged["post"]]
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True)
        if result.returncode != 0:
            git("revert", "--abort", cwd=self.root, check=False)
            raise ValueError("Couldn't undo it automatically (later changes touch the same lines): "
                             + (result.stderr or result.stdout).strip()[:300])
        item = self._update(request_id, status="undone", step="Undone. The change was reverted and the app is rebuilding.")
        (apply or apply_live)(item.get("changed") or [])
        return item

    # the worker
    def ensure_worker(self) -> None:
        with _LOCK:
            if self.worker is None or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._loop, name="zaenia-build-requests", daemon=True)
                self.worker.start()
        _WAKE.set()

    def recover(self) -> None:
        """After a restart: a request cut off mid-work goes back in the queue."""
        for item in self.list():
            if item["status"] == "working":
                self._update(item["id"], status="queued", step="Restarting after ZAE's server restarted.")
        if any(item["status"] == "queued" for item in self.list()):
            self.ensure_worker()

    def _loop(self) -> None:
        while True:
            queued = [item for item in self.list() if item["status"] == "queued"]
            if not queued:
                _WAKE.clear()
                _WAKE.wait(600)
                continue
            if self.gaming():
                self._update(queued[0]["id"], step="Waiting until your game is over.")
                time.sleep(60)
                continue
            self.process(queued[0]["id"])

    def process(self, request_id: str) -> dict[str, Any]:
        item = self._update(request_id, status="working", step="Making a safe copy of the code.")
        try:
            tool = self.choose(item.get("size") or "medium", item.get("wantedTool"))
            branch, base = make_copy(request_id, root=self.root, helper=self.helper)
            self._update(request_id, tool=tool, branch=branch, base=base)
            prompt = f"TASK: {item['title']}\n{item['brief']}\n\nGrey's own words: {item['request']}"
            if item.get("files"):
                prompt += "\nFiles that may be involved: " + ", ".join(item["files"])
            said, report, changed = "", "", []
            for attempt in range(RETRIES + 1):
                label = "Claude Code" if tool == "claude" else "Aider (local)"
                self._update(request_id, step=f"{label} is writing the change." if not attempt else f"{label} is fixing what failed (try {attempt + 1}).")
                finished, said = self.tool_runner(tool, self.helper, prompt, item.get("files") or [])
                changed = changed_paths(self.helper, base)
                if not changed:
                    raise RuntimeError("The coding tool didn't change anything. " + (said[:400] if said else ""))
                bad = [name for name in changed if locked(name)]
                if bad:
                    raise PermissionError("It tried to change locked files (" + ", ".join(bad[:5]) + "), so the work was thrown away.")
                self._update(request_id, step="Testing the change in the copy.", changed=changed)
                passed, report = self.checks(self.helper, changed)
                if passed:
                    break
                prompt = (f"TASK: {item['title']}\n{item['brief']}\n\nYour change is in place, but ZAE's checks failed. "
                          f"Fix it without weakening any test:\n{report[-3000:]}")
            else:
                diff = git("diff", "--cached", base, cwd=self.helper)
                self._update(request_id, status="failed", step="The tests still failed after the retries. Nothing changed.",
                             summary=said, checks={"ok": False, "text": report[-4000:]}, diff=diff[:200_000])
                self.notify(request_id, f"Build request failed: {item['title']}", "The tests still failed; see Code Doctor > Build requests.")
                return self.get(request_id)
            git("-c", "user.name=ZAE", "-c", "user.email=zae@localhost", "commit", "-q", "-m", f"ZAE build: {item['title']}\n\n{item['request'][:500]}", cwd=self.helper)
            diff = git("diff", base, "HEAD", cwd=self.helper)
            self._update(request_id, status="ready", step="Tested and ready for you to approve at the PC.",
                         summary=said, checks={"ok": True, "text": report[-4000:]}, diff=diff[:200_000], changed=changed)
            self.notify(request_id, f"Ready to review: {item['title']}", "Tests passed. Approve or reject it in Code Doctor > Build requests on the PC.")
        except Exception as error:
            self._update(request_id, status="failed", step="Stopped: " + str(error)[:500], error=str(error)[:800])
            self.notify(request_id, f"Build request stopped: {item['title']}", str(error)[:300])
        finally:
            try:
                remove_copy(root=self.root, helper=self.helper)
            except Exception:
                pass
            final = self.get(request_id)
            if final["status"] == "failed" and final.get("branch"):
                git("branch", "-D", final["branch"], cwd=self.root, check=False)  # the diff is kept in the request
            if final.get("tool") == "aider":
                _bring_talk_back()
        return final


def _gaming() -> bool:
    try:
        from core.assistant_platform.game_mode import active
        return active()
    except Exception:
        return False


def _notify(request_id: str, title: str, message: str) -> None:
    try:
        from core.assistant_followthrough.service import FollowThroughService
        FollowThroughService().post("build", f"{request_id}:{title}", title, message)
    except Exception:
        pass


def _bring_talk_back() -> None:
    try:
        from core.research.agent import _study_done
        _study_done()  # Aider used the Study model; free it and reload Talk
    except Exception:
        pass


def apply_live(changed: list[str], *, root: Path = PROJECT_ROOT) -> None:
    """Rebuild the desktop app if app files changed, then restart the server if her code changed. Runs detached,
    because the server restart ends this process; the log is data/ui/build_apply.log."""
    app = any(name.startswith("desktop/") for name in changed)
    server = any(name.startswith(("core/", "config")) or name.endswith(".py") for name in changed)
    if not (app or server):
        return
    steps = []
    if app:
        steps.append(f"& '{root / 'scripts' / 'zae.ps1'}' build -Yes")
    if server:
        steps.append(f"& '{root / 'scripts' / 'restart_zaenia_server.ps1'}'")
    script = "; ".join(steps)
    APPLY_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(APPLY_LOG, "a", encoding="utf-8")
    log.write(f"\n== {_now()} applying: app={app} server={server}\n")
    log.flush()
    flags = 0x00000008 | 0x00000200 | 0x08000000  # detached, new process group, no window
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    try:
        subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, creationflags=flags | 0x01000000)  # break away from the server's job
    except OSError:
        subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)


def view(items: list[dict[str, Any]]) -> dict[str, Any]:
    available = tools_available()
    return {"requests": items[::-1], "tools": available, "running": any(i["status"] in ("queued", "working") for i in items)}


_REQUESTS: BuildRequests | None = None


def build_requests() -> BuildRequests:
    global _REQUESTS
    if _REQUESTS is None:
        _REQUESTS = BuildRequests()
    return _REQUESTS


_ASK_BUILD = re.compile(
    r"^\s*(?:(?:hey\s+)?zae[,!\s]+)?(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|i\s+want\s+you\s+to\s+)?"
    r"(?P<verb>build(?:\s+me)?|code(?:\s+up)?|change\s+your(?:\s+own)?\s+code\s+(?:so|to)|upgrade\s+yourself\s+(?:so|to)|add\s+(?:a\s+)?feature)\s+"
    r"(?P<what>.{6,})$", re.I | re.S)
# "Build" alone is everyday talk ("build muscle", "build me a workout plan"), so it must be about her app.
_ABOUT_APP = re.compile(r"\b(?:app|tab|screen|button|feature|panel|widget|page|settings?|core|rings?|dashboard|card|"
                        r"yourself|your\s+(?:own\s+)?code|top\s+bar|sidebar|menu|chat|voice|view)\b", re.I)


def parse_build(message: str) -> str | None:
    """'ZAE, build ... on the X tab' / 'change your code so ...' -> what to build; None for anything else."""
    match = _ASK_BUILD.match(message or "")
    if not match:
        return None
    what = match.group("what").strip().rstrip(".!")
    if re.match(r"^(?:the\s+)?(?:app|apps|desktop\s+app)$", what, re.I):
        return None
    if re.match(r"build|code", match.group("verb"), re.I) and not _ABOUT_APP.search(what):
        return None
    return what
