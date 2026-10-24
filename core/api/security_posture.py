"""Live security strength: how well ZAE's defenses hold up against an attack, measured now.

Each area is rated strong, fair or weak from live readings on this PC: which
addresses the API actually listens on, Tailscale Funnel and the Windows
firewall, sign-in lockout state, secret files at rest, credential age, voice
calibration margins, server mode, the latest security-check suites, git
privacy, the audit trail and the last 24 hours of attack signs. Anything ZAE
can't measure is marked "not measured" and left out of the score.

This is a self-assessment of ZAE's own defenses, not a penetration test. It
reads no secret's contents (only file presence, sizes, dates and the
non-secret calibration scores) and changes nothing.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from core.foundation.storage.paths import (AUDIT_FILE, AUTH_RATE_FILE, MORAL_VAULT_FILE, PASSKEY_FILE, SALT_FILE,
                                           SECURE_DIR, SPEAKER_PROFILE_FILE, VAULT_FILE)

LEVEL_POINTS = {"strong": 100, "fair": 60, "weak": 20}
TOKEN_MAX_DAYS = 180
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = threading.Lock()


def _cached(key: str, seconds: float, compute: Callable[[], Any]) -> Any:
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < seconds:
            return hit[1]
    value = compute()
    with _CACHE_LOCK:
        _CACHE[key] = (now, value)
    return value


def _run(argv: list[str], timeout: float = 6) -> str | None:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, **NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _area(area_id: str, title: str, level: str, evidence: list[str], risk: str = "", fix: str = "",
          attack: str = "") -> dict[str, Any]:
    return {"id": area_id, "title": title, "level": level, "evidence": evidence, "risk": risk, "fix": fix, "attack": attack}


def _days_old(path: Path) -> int | None:
    try:
        return int((time.time() - path.stat().st_mtime) // 86400)
    except OSError:
        return None


# ------------------------------------------------------------- live readings

def api_listeners(port: int) -> list[str] | None:
    try:
        import psutil
        return sorted({c.laddr.ip for c in psutil.net_connections(kind="inet")
                       if c.laddr and c.laddr.port == port and c.status == psutil.CONN_LISTEN})
    except Exception:
        return None


def tailscale_state() -> dict[str, Any]:
    def read() -> dict[str, Any]:
        exe = shutil.which("tailscale") or next((p for p in (r"C:\Program Files\Tailscale\tailscale.exe",) if Path(p).is_file()), None)
        if not exe:
            return {"installed": False}
        serve = _run([exe, "serve", "status"])
        funnel = _run([exe, "funnel", "status"])
        text = f"{serve or ''}\n{funnel or ''}"
        return {"installed": True, "readable": serve is not None or funnel is not None,
                "serving": "proxy" in text.lower() or "http" in (serve or "").lower(),
                "funnel": "funnel on" in text.lower()}
    return _cached("tailscale", 60, read)


def firewall_state() -> dict[str, bool] | None:
    def read() -> dict[str, bool] | None:
        if os.name != "nt":
            return None
        out = _run(["netsh", "advfirewall", "show", "allprofiles", "state"])
        if out is None:
            return None
        profiles, current = {}, None
        for line in out.splitlines():
            line = line.strip()
            if line.endswith("Profile Settings:"):
                current = line.split()[0].lower()
            elif line.lower().startswith("state") and current:
                profiles[current] = line.split()[-1].upper() == "ON"
        return profiles or None
    return _cached("firewall", 60, read)


def signin_counter() -> dict[str, Any] | None:
    if not AUTH_RATE_FILE.is_file():
        return {"failures": 0, "locked": False}
    try:
        with closing(sqlite3.connect(f"file:{AUTH_RATE_FILE.as_posix()}?mode=ro", uri=True, timeout=2)) as db:
            row = db.execute("SELECT failures,locked_until FROM attempts WHERE id=1").fetchone()
    except sqlite3.Error:
        return None
    failures, locked_until = row if row else (0, 0)
    return {"failures": int(failures), "locked": float(locked_until) > time.time()}


def calibration_margin() -> dict[str, Any] | None:
    path = SECURE_DIR / "speaker_auth_calibration.yaml"
    if not path.is_file() or path.is_symlink():
        return None
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        observed = data.get("observed", {})
        genuine, impostor, threshold = float(observed["genuine_min"]), float(observed["impostor_max"]), float(data["threshold"])
    except Exception:
        return {"valid": False}
    return {"valid": impostor < threshold < genuine, "genuine": genuine, "impostor": impostor, "threshold": threshold,
            "margin": round(genuine - impostor, 3), "days": _days_old(path)}


def day_signals(now: datetime | None = None) -> dict[str, int]:
    from core.api.security_activity import recent_activity
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    counts = {"failedSignins": 0, "denied": 0, "voiceRejected": 0, "unlockFailed": 0}
    try:
        events = recent_activity(limit=300)["events"]
    except OSError:
        return counts
    for event in events:
        try:
            moment = datetime.fromisoformat(str(event.get("at")))
        except ValueError:
            continue
        if (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)) < since:
            continue
        if event["event"] == "auth.failed":
            counts["failedSignins"] += 1
        elif event["reason"] in ("scoped_client_denied", "unattended_brief_denied"):
            counts["denied"] += 1
        elif event["reason"] in ("speaker_rejected", "verification_failed"):
            counts["voiceRejected"] += 1
        if event["event"] == "security.tab_unlock_failed":
            counts["unlockFailed"] += 1
    return counts


# ------------------------------------------------------------- areas

def _network() -> dict[str, Any]:
    from core.api.config import load_api_settings
    try:
        settings = load_api_settings()
    except (RuntimeError, ValueError) as error:
        return _area("network", "Network exposure", "weak", [str(error)[:160]], "The server settings allow a non-local address.",
                     "Remove the ZAENIA_API_HOST setting so the server binds to 127.0.0.1.", "Remote attacks over the network")
    listening = api_listeners(settings.port)
    tail = tailscale_state()
    walls = firewall_state()
    evidence = [f"Configured for {settings.host}:{settings.port}."]
    level, risk, fix = "strong", "", ""
    if listening is None:
        evidence.append("Couldn't read the live listening sockets.")
    elif not listening:
        evidence.append(f"Nothing is listening on port {settings.port} right now (server stopped?).")
    else:
        exposed = [ip for ip in listening if ip not in LOOPBACK]
        evidence.append(f"Listening now on {', '.join(listening)}.")
        if exposed:
            level, risk = "weak", f"The API is reachable from the network on {', '.join(exposed)}."
            fix = "Restart the server with the default 127.0.0.1 host."
    if tail.get("installed"):
        if tail.get("funnel"):
            level, risk = "weak", "Tailscale Funnel is on: ZAE can be reached from the public internet."
            fix = "Turn Funnel off (tailscale funnel reset) and keep phone access on your tailnet only."
        elif tail.get("serving"):
            evidence.append("Tailscale serves ZAE to your own tailnet devices only (Funnel off).")
        elif tail.get("readable"):
            evidence.append("Tailscale is installed; nothing is being served.")
    if walls:
        off = [name for name, on in walls.items() if not on]
        evidence.append("Windows Firewall: " + ", ".join(f"{name} {'on' if on else 'OFF'}" for name, on in walls.items()) + ".")
        if off and level == "strong":
            level, risk = "fair", f"The Windows Firewall is off for the {', '.join(off)} profile."
            fix = "Turn the Windows Firewall back on in Windows Security > Firewall & network protection."
    return _area("network", "Network exposure", level, evidence, risk, fix, "Remote attacks over the network")


def _signin(signals: dict[str, int]) -> dict[str, Any]:
    counter = signin_counter()
    evidence = ["Passkey stored as an Argon2id hash (64 MB, 3 passes), 30-second lockout after 5 wrong tries."]
    level, risk, fix = "strong", "", ""
    if counter is None:
        evidence.append("Couldn't read the sign-in counter.")
    else:
        evidence.append(f"{counter['failures']} wrong tries in a row right now{' · locked out' if counter['locked'] else ''}.")
    evidence.append(f"{signals['failedSignins']} failed sign-ins and {signals['unlockFailed']} failed Security-tab unlocks in 24 h.")
    failed = signals["failedSignins"] + signals["unlockFailed"]
    if failed >= 20:
        level, risk = "weak", "Many failed sign-ins in a day: someone may be guessing the passkey."
        fix = "If it wasn't you, change the passkey at the PC and rotate the API token."
    elif failed >= 5 or (counter and counter["locked"]):
        level, risk = "fair", "Several failed sign-ins recently."
        fix = "If these weren't you, rotate the API token from the Security tab."
    return _area("signin", "Passkey guessing", level, evidence, risk, fix, "Brute-force and password guessing")


def _secrets() -> dict[str, Any]:
    files = (PASSKEY_FILE, SALT_FILE, VAULT_FILE, MORAL_VAULT_FILE)
    linked = [p.name for p in files if p.is_symlink()]
    missing = [p.name for p in files if not p.is_file()]
    if SECURE_DIR.is_symlink():
        linked.insert(0, "data/secure")
    if linked:
        return _area("secrets", "Secrets at rest", "weak", [f"Links instead of files: {', '.join(linked)}."],
                     "A link could point ZAE's secrets somewhere an attacker controls.",
                     "Replace the links with the real files inside data/secure.", "Stealing or swapping stored secrets")
    if missing:
        return _area("secrets", "Secrets at rest", "weak", [f"Missing: {', '.join(missing)}."],
                     "Without these, owner-only protections can't work.", "Run ZAE's security setup at the PC.",
                     "Stealing or swapping stored secrets")
    return _area("secrets", "Secrets at rest", "strong",
                 ["Passkey hash, salt, rules vault and moral-code vault present as plain files (contents not read).",
                  "Rules and moral code are encrypted with a key derived from the passkey."],
                 attack="Stealing or swapping stored secrets")


def _clients(mobile_sessions: int | None) -> dict[str, Any]:
    from core.api.auth import API_TOKEN_HASH_FILE
    from core.api import desktop_key, mobile_voice_profile
    evidence, level, risk, fix = [], "strong", "", ""
    token_days = _days_old(API_TOKEN_HASH_FILE) if API_TOKEN_HASH_FILE.is_file() else None
    evidence.append("API token: " + ("not set up" if token_days is None else f"set {token_days} day(s) ago (stored as a hash)") + ".")
    key_days = _days_old(desktop_key.key_path()) if desktop_key.is_paired() else None
    evidence.append("Desktop approval key: " + ("not paired" if key_days is None else f"paired {key_days} day(s) ago") + ".")
    evidence.append("Phone voice sign-in: " + ("on" if mobile_voice_profile.configured() else "off") + ".")
    if mobile_sessions is not None:
        evidence.append(f"{mobile_sessions} phone browser session(s) signed in now.")
    if token_days is not None and token_days > TOKEN_MAX_DAYS:
        level, risk = "fair", f"The API token is {token_days} days old; an old token has had more chances to leak."
        fix = "Rotate the API token from the Security tab, then reconnect the phone."
    return _area("clients", "App and phone access", level, evidence, risk, fix, "Stolen tokens and paired devices")


def _voice(signals: dict[str, int]) -> dict[str, Any]:
    cal = calibration_margin()
    attack = "Someone else's voice or a recording"
    if not SPEAKER_PROFILE_FILE.is_file():
        return _area("voice", "Voice impersonation", "fair", ["No voice profile is enrolled."],
                     "Voice features can't tell you apart from someone else.", "Run voice training from the Security tab.", attack)
    if not cal or not cal.get("valid"):
        return _area("voice", "Voice impersonation", "weak", ["Voice calibration is missing or doesn't separate you from others."],
                     "Voice checks may accept other people.", "Run voice training from the Security tab.", attack)
    evidence = [f"Calibration ({cal['days']} day(s) old): you score at least {cal['genuine']:.2f}, others at most {cal['impostor']:.2f}, "
                f"pass mark {cal['threshold']:.2f} (gap {cal['margin']:.2f}).",
                f"{signals['voiceRejected']} voice turn(s) rejected in 24 h.",
                "Phone voice sign-in uses six random words each time, so a replayed recording fails."]
    level, risk, fix = "strong", "", ""
    if cal["margin"] < 0.15:
        level, risk = "fair", "Your voice and other voices score close together, so a similar voice could pass."
        fix = "Retrain your voice in a quiet room (Security tab > Voice training)."
    elif signals["voiceRejected"] >= 10:
        level, risk = "fair", "Many voice turns were rejected today: someone else may be talking to ZAE, or your profile is out of date."
        fix = "If it was you, retrain your voice; if not, check who's near the microphone."
    return _area("voice", "Voice impersonation", level, evidence, risk, fix, attack)


def _mode(mode: str) -> dict[str, Any]:
    attack = "Misuse of a stolen app token"
    if mode == "unattended":
        return _area("mode", "Server mode", "strong", ["Token mode: owner features stay locked until the passkey is entered."], attack=attack)
    if mode == "voice_only":
        return _area("mode", "Server mode", "strong", ["Voice mode: owner requests need your verified voice."], attack=attack)
    return _area("mode", "Server mode", "fair", ["Passkey mode: owner features are open to the paired apps while the server runs."],
                 "Anyone holding the API token can use owner features until the server restarts.",
                 "Use token mode when you don't need owner features (Restart server).", attack)


def _from_report(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    attack = "Hidden flaws in ZAE's own security code"
    if not report:
        return [_area("tests", "Security code tests", "fair", ["No security check has run yet."],
                      "Flaws in the security code wouldn't be noticed.", "Run a security check below.", attack)]
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(report["at"])
    except (KeyError, TypeError, ValueError):
        age = timedelta(days=99)
    hours = int(age.total_seconds() // 3600)
    checks = report.get("checks", [])
    suites = [c for c in checks if c.get("group") == "tests"]
    failed = [c for c in suites if c.get("status") != "pass"]
    evidence = [f"{len(suites) - len(failed)} of {len(suites)} test suites passed in the check {hours} h ago."]
    if failed:
        tests = _area("tests", "Security code tests", "weak", evidence + [f"Failing: {', '.join(c['title'] for c in failed)}."],
                      "Part of ZAE's security code isn't behaving as tested.", failed[0].get("fix") or "Open the latest report below.", attack)
    elif hours > 48:
        tests = _area("tests", "Security code tests", "fair", evidence, "The last check is over two days old.",
                      "Run a security check below.", attack)
    else:
        tests = _area("tests", "Security code tests", "strong", evidence, attack=attack)
    privacy = [c for c in checks if c.get("id") in ("gitignore", "tracked_secrets")]
    leak = "Secrets leaking through GitHub"
    if not privacy:
        git = _area("git", "Secrets kept out of GitHub", "fair", ["Not checked in the latest report."], fix="Run a security check below.", attack=leak)
    elif any(c["status"] == "fail" for c in privacy):
        bad = next(c for c in privacy if c["status"] == "fail")
        git = _area("git", "Secrets kept out of GitHub", "weak", [bad["detail"]], "Private files could be pushed to GitHub.", bad["fix"], leak)
    else:
        git = _area("git", "Secrets kept out of GitHub", "strong", [c["detail"] for c in privacy] + [f"From the check {hours} h ago."], attack=leak)
    return [tests, git]


def _audit() -> dict[str, Any]:
    attack = "Covering tracks after an attack"
    if not AUDIT_FILE.is_file():
        return _area("audit", "Audit trail", "weak", ["No audit log."], "Attacks wouldn't leave a record.",
                     "Start the server; it records every permission check.", attack)
    stat = AUDIT_FILE.stat()
    minutes = int((time.time() - stat.st_mtime) // 60)
    archive = SECURE_DIR / "audit_archive"
    archived = len(list(archive.glob("*"))) if archive.is_dir() else 0
    evidence = [f"Last entry {minutes} min ago · {stat.st_size / 1024 ** 2:.1f} MB · {archived} archived log(s) kept, none deleted."]
    if minutes > 24 * 60:
        return _area("audit", "Audit trail", "fair", evidence, "Nothing has been recorded for over a day.",
                     "Check that the server is running.", attack)
    return _area("audit", "Audit trail", "strong", evidence, attack=attack)


def _signals(signals: dict[str, int]) -> dict[str, Any]:
    total = sum(signals.values())
    evidence = [f"Last 24 h: {signals['failedSignins']} failed sign-ins, {signals['denied']} blocked requests, "
                f"{signals['voiceRejected']} rejected voice turns, {signals['unlockFailed']} failed unlocks."]
    attack = "Attacks happening right now"
    if signals["denied"] >= 50 or total >= 80:
        return _area("signals", "Signs of attack (24 h)", "weak", evidence, "Unusually many blocked or failed attempts today.",
                     "Look through the activity list below; rotate the API token if anything isn't yours.", attack)
    if signals["denied"] >= 20 or total >= 30:
        return _area("signals", "Signs of attack (24 h)", "fair", evidence, "More blocked or failed attempts than usual.",
                     "Check the activity list below for anything you didn't do.", attack)
    return _area("signals", "Signs of attack (24 h)", "strong", evidence, attack=attack)


def _packages() -> dict[str, Any]:
    import sys
    return _area("packages", "Software vulnerabilities", "unknown",
                 [f"Python {sys.version.split()[0]}. Known-vulnerability lists for installed packages need the internet, so ZAE doesn't check them."],
                 "Outdated packages could have published flaws.",
                 "Keep Windows updated; update Python packages when ZAE's updates ask.", "Known flaws in installed software")


# ------------------------------------------------------------- assessment

def assess(mode: str = "", *, mobile_sessions: int | None = None, report: dict[str, Any] | None = None) -> dict[str, Any]:
    if report is None:
        from core.api.security_check import list_reports, load_report
        latest = list_reports(1)
        report = load_report(latest[0]["id"]) if latest else None
    signals = day_signals()
    builders: list[Callable[[], Any]] = [_network, lambda: _signin(signals), _secrets, lambda: _clients(mobile_sessions),
                                         lambda: _voice(signals), lambda: _mode(mode), lambda: _from_report(report),
                                         _audit, lambda: _signals(signals), _packages]
    areas: list[dict[str, Any]] = []
    for build in builders:
        try:
            result = build()
        except Exception as error:  # one broken reading must not hide the rest
            result = _area("error", "A reading couldn't be taken", "unknown", [type(error).__name__])
        areas.extend(result if isinstance(result, list) else [result])
    measured = [a for a in areas if a["level"] in LEVEL_POINTS]
    score = round(sum(LEVEL_POINTS[a["level"]] for a in measured) / len(measured)) if measured else 0
    weak = sum(1 for a in measured if a["level"] == "weak")
    level = "weak" if weak or score < 60 else "strong" if score >= 85 else "fair"
    return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "score": score, "level": level,
            "counts": {name: sum(1 for a in areas if a["level"] == name) for name in ("strong", "fair", "weak", "unknown")},
            "areas": areas, "signals": signals}


def recommendations(posture: dict[str, Any], report: dict[str, Any] | None) -> list[dict[str, str]]:
    """What to fix, most urgent first: weak areas, failed checks, then fair areas and warnings."""
    items: list[tuple[int, dict[str, str]]] = []
    rank = {"weak": 0, "fail": 1, "fair": 2, "warn": 3, "unknown": 4}
    for area in posture["areas"]:
        if area["level"] != "strong" and area["fix"]:
            items.append((rank[area["level"]], {"priority": "high" if area["level"] == "weak" else "medium" if area["level"] == "fair" else "low",
                                                 "title": area["title"], "why": area["risk"], "fix": area["fix"]}))
    for check in (report or {}).get("checks", []):
        if check.get("status") in ("fail", "warn") and check.get("fix"):
            items.append((rank[check["status"]], {"priority": "high" if check["status"] == "fail" else "medium",
                                                   "title": check["title"], "why": check.get("detail", ""), "fix": check["fix"]}))
    seen, ordered = set(), []
    for _, item in sorted(items, key=lambda pair: pair[0]):
        if item["fix"] not in seen:
            seen.add(item["fix"])
            ordered.append(item)
    return ordered


def improvements(limit: int = 20) -> dict[str, Any]:
    """How security has changed across saved checks: a trend and what changed since the previous check."""
    from core.api.security_check import list_reports, load_report
    summaries = list_reports(limit)
    trend = []
    for summary in reversed(summaries):
        report = load_report(summary["id"]) or {}
        posture = report.get("posture") or {}
        trend.append({"id": summary["id"], "at": summary["at"], "status": summary["status"], "counts": summary["counts"],
                      "score": posture.get("score")})
    fixed, broke, stronger, weaker = [], [], [], []
    if len(summaries) >= 2:
        latest, previous = load_report(summaries[0]["id"]) or {}, load_report(summaries[1]["id"]) or {}
        before = {c["id"]: c for c in previous.get("checks", [])}
        for check in latest.get("checks", []):
            old = before.get(check["id"])
            if old and old["status"] != "pass" and check["status"] == "pass":
                fixed.append(check["title"])
            elif old and old["status"] == "pass" and check["status"] != "pass":
                broke.append(check["title"])
        order = {"weak": 0, "fair": 1, "strong": 2}
        earlier = {a["id"]: a["level"] for a in (previous.get("posture") or {}).get("areas", [])}
        for area in (latest.get("posture") or {}).get("areas", []):
            was = earlier.get(area["id"])
            if was in order and area["level"] in order and order[area["level"]] != order[was]:
                (stronger if order[area["level"]] > order[was] else weaker).append(area["title"])
    return {"trend": trend, "fixed": fixed, "broke": broke, "stronger": stronger, "weaker": weaker,
            "since": summaries[1]["at"] if len(summaries) >= 2 else None}


def compact(posture: dict[str, Any]) -> dict[str, Any]:
    """Saved with each security check so later checks can show what improved."""
    return {"score": posture["score"], "level": posture["level"],
            "areas": [{"id": a["id"], "title": a["title"], "level": a["level"]} for a in posture["areas"]]}


def summary(mode: str = "") -> dict[str, Any]:
    """For the Status tab: the overall level only, no details."""
    from core.api.security_check import list_reports
    posture = _cached(f"summary:{mode}", 30, lambda: assess(mode))
    latest = list_reports(1)
    return {"level": posture["level"], "score": posture["score"],
            "toImprove": posture["counts"]["weak"] + posture["counts"]["fair"],
            "lastCheck": {"at": latest[0]["at"], "status": latest[0]["status"]} if latest else None}


def full_view(mode: str = "", *, mobile_sessions: int | None = None) -> dict[str, Any]:
    from core.api.security_check import list_reports, load_report
    latest = list_reports(1)
    report = load_report(latest[0]["id"]) if latest else None
    posture = assess(mode, mobile_sessions=mobile_sessions, report=report)
    return {"posture": posture, "recommendations": recommendations(posture, report), "improvements": improvements()}


if __name__ == "__main__":
    print(json.dumps(assess(), indent=1))
