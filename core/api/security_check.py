"""Security self-check: ZAE checks her own security and keeps a report of each run.

Two parts. The isolated security test suites in core/foundation run in their own
temporary folders (they never touch the live passkey, vaults or memory). Then a
few read-only checks on the live setup: secure files present, localhost-only
server, private data kept out of git, the audit log, recent sign-in failures.
Nothing here reads a secret's contents or changes a permission. Reports hold
check names and results only, saved under data/security_checks (gitignored).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from core.foundation.storage.paths import (AUDIT_FILE, DATA_DIR, MORAL_VAULT_FILE, PASSKEY_FILE, PROJECT_ROOT,
                                           SALT_FILE, SECURE_DIR, VAULT_FILE)

REPORT_DIR = DATA_DIR / "security_checks"
KEEP = 50
MIN_GAP_SECONDS = 10 * 60          # manual runs: at most one every 10 minutes
DAILY_SECONDS = 24 * 3600          # automatic run once a day
SUITE_TIMEOUT = 240
REPORT_ID = re.compile(r"^\d{8}T\d{6}Z$")
# No console window flashing up when the quiet (token-mode) server runs a check.
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

# module, title, what it covers
SUITES = (
    ("core.foundation.self_test", "Security self-test",
     "Passkey, sessions, rules, moral code, audit, encryption and API tokens"),
    ("core.foundation.closure_check", "Entry-point boundaries",
     "Local entry guards, scoped denials, exact sensitive changes and bounded writes"),
    ("core.foundation.integration_check", "Console integration",
     "Console launches pass through the real rules"),
)
# Paths that must stay out of GitHub, and tracked names that would mean a leak.
MUST_IGNORE = ("data/secure/passkey.hash", "data/secure/audit.log", ".env", "core/foundation/moral_code/charter.json")
LEAK = re.compile(r"(^|/)(data/|\.env$|[^/]*\.vault$|passkey\.hash$|master\.salt$|api_access\.sha256$|"
                  r"credentials\.json$|token\.json$|[^/]*\.pem$|[^/]*\.key$)", re.I)


def _command(module: str, *args: str) -> str:
    """A command that works as typed in PowerShell, from any folder."""
    return f'cd "{PROJECT_ROOT}"; .\.venv\Scripts\python.exe -m {" ".join((module,) + args)}'


def _check(group: str, check_id: str, title: str, status: str, detail: str = "", fix: str = "") -> dict[str, str]:
    return {"group": group, "id": check_id, "title": title, "status": status, "detail": detail, "fix": fix}


def _run_suite(module: str, title: str, covers: str,
               runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict[str, str]:
    check_id = module.rsplit(".", 1)[-1]
    started = time.monotonic()
    try:
        done = runner([sys.executable, "-m", module], cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=SUITE_TIMEOUT,
                      env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **NO_WINDOW)
    except subprocess.TimeoutExpired:
        return _check("tests", check_id, title, "fail", f"Did not finish within {SUITE_TIMEOUT} seconds.",
                      f"In PowerShell at the PC, run {_command(module)} to see where it stops.")
    except OSError as error:
        return _check("tests", check_id, title, "fail", f"Could not start ({type(error).__name__}).")
    seconds = time.monotonic() - started
    output = f"{done.stdout}\n{done.stderr}"
    if done.returncode == 0:
        # Each suite prints its own summary; keep only the count.
        count = re.search(r"Ran (\d+) isolated security checks|PASS: (\d+)", output)
        number = next((group for group in count.groups() if group), None) if count else None
        return _check("tests", check_id, title, "pass",
                      f"{number + ' checks passed' if number else 'Passed'} in {seconds:.0f}s. {covers}.")
    missing = re.search(r"No such file or directory: '[^']*?([\w.-]+)'", output)
    if missing:
        return _check("tests", check_id, title, "fail", f"A file the tests need is missing ({missing.group(1)}).",
                      "Restore the file from your backups, then run the check again.")
    failed = re.findall(r"FAILED CHECK: ([\w.]+)", output)
    detail = (f"{len(failed)} check(s) failed: {', '.join(failed[:6])}." if failed
              else "The suite reported a failure.")
    return _check("tests", check_id, title, "fail", detail, f"In PowerShell at the PC, run {_command(module)} for the full output.")


def _secure_files() -> list[dict[str, str]]:
    checks = []
    if SECURE_DIR.is_symlink() or (SECURE_DIR.exists() and not SECURE_DIR.is_dir()):
        checks.append(_check("setup", "secure_dir", "Secure folder", "fail", "data/secure is not a plain folder.",
                             "data/secure must be a real folder, not a link."))
        return checks
    checks.append(_check("setup", "secure_dir", "Secure folder", "pass" if SECURE_DIR.is_dir() else "fail",
                         "data/secure is a plain folder." if SECURE_DIR.is_dir() else "data/secure does not exist.",
                         "" if SECURE_DIR.is_dir() else "At the PC, run ZÆNIA's security setup."))
    from core.api.auth import API_TOKEN_HASH_FILE
    files = (
        ("passkey", "Owner passkey", (PASSKEY_FILE, SALT_FILE), "fail", "At the PC, run ZÆNIA's security setup to create the passkey."),
        ("rules_vault", "Security rules vault", (VAULT_FILE,), "fail", "Create the rules vault with the security setup."),
        ("moral_vault", "Moral-code vault", (MORAL_VAULT_FILE,), "fail", "Create the moral-code policy with the security setup."),
        ("api_token", "API token", (API_TOKEN_HASH_FILE,), "warn", "Create one in PowerShell at the PC: " + _command("core.api.auth", "create")),
    )
    for check_id, title, paths, missing_level, fix in files:
        linked = [path.name for path in paths if path.is_symlink()]
        absent = [path.name for path in paths if not path.is_file()]
        if linked:
            checks.append(_check("setup", check_id, title, "fail", f"{', '.join(linked)} is a link, not a file.",
                                 "Secure files must be plain files inside data/secure."))
        elif absent:
            checks.append(_check("setup", check_id, title, missing_level, "Not set up.", fix))
        else:
            checks.append(_check("setup", check_id, title, "pass", "Present (contents not read)."))
    return checks


def _localhost() -> dict[str, str]:
    from core.api.config import load_api_settings
    try:
        settings = load_api_settings()
    except (RuntimeError, ValueError) as error:
        return _check("setup", "localhost", "Server stays on this PC", "fail", str(error)[:200],
                      "Remove the ZAENIA API host setting so the server binds to 127.0.0.1.")
    return _check("setup", "localhost", "Server stays on this PC", "pass",
                  f"The API listens on {settings.host} only; nothing else on the network can reach it.")


def _git(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30, **NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_privacy() -> list[dict[str, str]]:
    ignored = _git("check-ignore", *MUST_IGNORE)
    tracked = _git("ls-files")
    if ignored is None or tracked is None or tracked.returncode != 0:
        return [_check("setup", "git_privacy", "Private data kept out of GitHub", "warn",
                       "Git isn't available here, so this couldn't be checked.")]
    covered = set(ignored.stdout.split())
    exposed = [path for path in MUST_IGNORE if path not in covered]
    leaked = [path for path in tracked.stdout.splitlines() if LEAK.search(path)]
    checks = [_check("setup", "gitignore", "Private data is gitignored", "fail" if exposed else "pass",
                     f"Not ignored: {', '.join(exposed)}." if exposed else "Secure files, the audit log, .env and the charter are ignored by git.",
                     "Add these paths to .gitignore before the next commit." if exposed else "")]
    checks.append(_check("setup", "tracked_secrets", "No secret files in git", "fail" if leaked else "pass",
                         f"Tracked: {', '.join(leaked[:5])}{' …' if len(leaked) > 5 else ''}." if leaked
                         else f"Checked {len(tracked.stdout.splitlines())} tracked files by name.",
                         "Remove them from git (git rm --cached) and rotate anything they contained." if leaked else ""))
    return checks


def _audit_log() -> dict[str, str]:
    from core.foundation.security.audit import ROTATE_BYTES
    if not AUDIT_FILE.is_file():
        return _check("setup", "audit_log", "Audit log", "warn", "No audit log yet.",
                      "It starts when the server first checks a permission.")
    size = AUDIT_FILE.stat().st_size
    if size > ROTATE_BYTES * 2:
        return _check("setup", "audit_log", "Audit log", "warn", f"{size / 1024 ** 2:.0f} MB: rotation isn't keeping it small.",
                      "Restart the server; older entries move to data/secure/audit_archive.")
    return _check("setup", "audit_log", "Audit log", "pass", f"Recording ({size / 1024 ** 2:.1f} MB).")


def _recent_activity(now: datetime) -> list[dict[str, str]]:
    from core.api.security_activity import recent_activity
    try:
        events = recent_activity(limit=300)["events"]
    except OSError:
        return [_check("activity", "activity", "Recent activity", "warn", "The audit log couldn't be read.")]
    since = now - timedelta(hours=24)

    def recent(event: dict[str, Any]) -> bool:
        try:
            moment = datetime.fromisoformat(str(event.get("at")))
        except ValueError:
            return False
        return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)) >= since

    day = [event for event in events if recent(event)]
    failed = sum(1 for event in day if event["event"] == "auth.failed")
    denied = sum(1 for event in day if event["reason"] in ("scoped_client_denied", "unattended_brief_denied"))
    voice = sum(1 for event in day if event["reason"] in ("speaker_rejected", "verification_failed"))
    return [
        _check("activity", "failed_signins", "Failed sign-ins (24 h)", "warn" if failed >= 5 else "pass",
               f"{failed} failed sign-in(s).", "If these weren't you, rotate the API token at the PC." if failed >= 5 else ""),
        _check("activity", "denials", "Requests denied (24 h)", "warn" if denied >= 20 else "pass",
               f"{denied} request(s) blocked by your security rules.",
               "Check Security activity below for what was blocked." if denied >= 20 else ""),
        _check("activity", "voice_rejections", "Voice rejections (24 h)", "warn" if voice >= 10 else "pass",
               f"{voice} voice turn(s) not recognised as you.",
               "If it was you, retrain your voice; if not, someone else is talking to ZAE." if voice >= 10 else ""),
    ]


def run_security_check(trigger: str = "manual", *, mode: str = "", now: datetime | None = None,
                       suite_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    started = time.monotonic()
    checks = [_run_suite(module, title, covers, suite_runner) for module, title, covers in SUITES]
    for part in (_secure_files, lambda: [_localhost()], _git_privacy, lambda: [_audit_log()], lambda: _recent_activity(now)):
        try:
            checks.extend(part())
        except Exception as error:  # one broken check must not hide the rest
            checks.append(_check("setup", "check_error", "A check couldn't run", "warn", type(error).__name__))
    if mode == "unattended":
        checks.append(_check("setup", "server_mode", "Server mode", "pass",
                             "Token mode: owner features stay locked until the passkey is entered."))
    counts = {status: sum(1 for check in checks if check["status"] == status) for status in ("pass", "warn", "fail")}
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    report = {
        "id": now.strftime("%Y%m%dT%H%M%SZ"), "at": now.isoformat(timespec="seconds"), "trigger": trigger,
        "status": status, "counts": counts, "seconds": round(time.monotonic() - started, 1), "checks": checks,
        "headline": ("All security checks passed." if status == "pass"
                     else f"{counts['fail']} check{'s' if counts['fail'] != 1 else ''} failed." if counts["fail"]
                     else f"Passed with {counts['warn']} warning{'s' if counts['warn'] != 1 else ''}."),
    }
    try:  # live strength at the time of this check, so later checks can show what improved
        from core.api.security_posture import assess, compact
        report["posture"] = compact(assess(mode, report=report))
    except Exception:
        pass
    _save(report)
    try:
        from core.foundation.security.audit import audit
        audit("security.self_check", operation="security.self_check", reason_code=f"self_check_{status}")
    except Exception:
        pass
    return report


def _save(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / f"{report['id']}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporary, target)
    for old in sorted(REPORT_DIR.glob("*.json"), reverse=True)[KEEP:]:
        old.unlink(missing_ok=True)


def load_report(report_id: str) -> dict[str, Any] | None:
    if not REPORT_ID.match(report_id):
        return None
    path = REPORT_DIR / f"{report_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_reports(limit: int = KEEP) -> list[dict[str, Any]]:
    summaries = []
    for path in sorted(REPORT_DIR.glob("*.json"), reverse=True)[:limit] if REPORT_DIR.is_dir() else []:
        report = load_report(path.stem)
        if report:
            summaries.append({key: report.get(key) for key in ("id", "at", "trigger", "status", "counts", "headline", "seconds")})
    return summaries


class SecurityCheckService:
    """Runs one check at a time, limits manual runs and runs one automatically each day."""

    def __init__(self, clock: Callable[[], float] = time.time, runner: Callable[..., dict[str, Any]] = run_security_check):
        self.clock, self.runner = clock, runner
        self.lock = threading.Lock()
        self.running = False
        self.last_error: str | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def _last_run(self) -> float | None:
        latest = list_reports(1)
        if not latest:
            return None
        try:
            return datetime.fromisoformat(latest[0]["at"]).timestamp()
        except (TypeError, ValueError):
            return None

    def wait_seconds(self) -> int:
        last = self._last_run()
        return 0 if last is None else max(0, int(last + MIN_GAP_SECONDS - self.clock()))

    def start_check(self, trigger: str = "manual", mode: str = "", *, wait: bool = False) -> dict[str, Any]:
        with self.lock:
            if self.running:
                return {"started": False, "running": True, "reason": "A security check is already running."}
            gap = self.wait_seconds() if trigger == "manual" else 0
            if gap:
                return {"started": False, "running": False, "retryAfter": gap,
                        "reason": f"The last check was under 10 minutes ago. Try again in {max(1, gap // 60)} minute(s)."}
            self.running = True

        def work():
            try:
                self.runner(trigger, mode=mode)
                self.last_error = None
            except Exception as error:
                self.last_error = type(error).__name__
            finally:
                self.running = False

        if wait:
            work()
        else:
            threading.Thread(target=work, name="zaenia-security-check", daemon=True).start()
        return {"started": True, "running": not wait}

    def state(self, limit: int = KEEP) -> dict[str, Any]:
        reports = list_reports(limit)
        return {"running": self.running, "reports": reports, "latest": load_report(reports[0]["id"]) if reports else None,
                "retryAfter": self.wait_seconds(), "error": self.last_error}

    def start(self, mode: Callable[[], str] = lambda: "") -> None:
        if self.thread is not None:
            return

        def loop():
            # A few minutes after startup, then hourly: run when the last check is a day old.
            delay = 180
            while not self.stop_event.wait(delay):
                delay = 3600
                last = self._last_run()
                if last is None or self.clock() - last >= DAILY_SECONDS:
                    self.start_check("daily", mode(), wait=True)

        self.thread = threading.Thread(target=loop, name="zaenia-security-daily", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()


_SERVICE: SecurityCheckService | None = None
_SERVICE_LOCK = threading.Lock()


def security_checks() -> SecurityCheckService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = SecurityCheckService()
        return _SERVICE


SECURITY_QUESTION = re.compile(r"\bsecurity (?:check|scan|report|self[- ]?check|test)s?\b|\bhow(?:'s| is) (?:your|my|the) security\b|\bare you secure\b", re.I)


def security_check_context(question: str) -> str | None:
    """The latest report for the brain when Grey asks about her security checks (reference data only)."""
    if not SECURITY_QUESTION.search(question or ""):
        return None
    reports = list_reports(1)
    if not reports:
        return "SECURITY SELF-CHECK: no check has run yet. Say so; it can be started from the Security tab."
    report = load_report(reports[0]["id"]) or {}
    problems = [f"- {check['title']}: {check['status'].upper()}. {check['detail']}"
                for check in report.get("checks", []) if check.get("status") != "pass"]
    counts = report.get("counts", {})
    return (f"SECURITY SELF-CHECK (latest, {report.get('at')}, {report.get('trigger')}): {report.get('headline')} "
            f"{counts.get('pass', 0)} passed, {counts.get('warn', 0)} warnings, {counts.get('fail', 0)} failed. "
            "Report only these results; don't invent checks." + ("\n" + "\n".join(problems[:8]) if problems else ""))
