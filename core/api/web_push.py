"""Phone notifications from ZAE through the browser (Web Push), so reminders reach Grey's iPhone.

The phone app (served at /app/ over Tailscale HTTPS) asks for permission and
subscribes with this server's public VAPID key; the subscription is saved
here. When a reminder, a follow-through notice, or a training reminder comes
due, ZAE sends a short push (title + one line) through the phone's push
service. On iPhone this needs iOS 16.4+ and the app added to the Home Screen.

The VAPID private key is kept DPAPI-protected (data/secure/vapid.key.dpapi);
subscriptions live in data/secure/push_subscriptions.json. Push text never
carries secrets: only the reminder's own words.
"""
from __future__ import annotations

import base64
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = PROJECT_ROOT / "data" / "secure" / "vapid.key.dpapi"
SUBS_FILE = PROJECT_ROOT / "data" / "secure" / "push_subscriptions.json"
CONTACT = "mailto:zaenia@localhost"
_LOCK = threading.Lock()


def _protect(data: bytes, decrypt: bool = False) -> bytes:
    from core.voice_security.windows_protection import protect
    return protect(data, decrypt=decrypt)


def _private_pem(protect: Callable[..., bytes] = _protect, path: Path = KEY_FILE) -> bytes:
    with _LOCK:
        if path.is_file():
            return protect(path.read_bytes(), decrypt=True)
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        path.parent.mkdir(parents=True, exist_ok=True)
        from core.foundation.security.io import atomic_write
        atomic_write(path, protect(pem))
        return pem


def public_key(pem: bytes | None = None) -> str:
    """The applicationServerKey the phone subscribes with (uncompressed point, base64url)."""
    from cryptography.hazmat.primitives import serialization
    key = serialization.load_pem_private_key(pem or _private_pem(), password=None)
    raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def subscriptions(path: Path = SUBS_FILE) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items: list[dict[str, Any]], path: Path = SUBS_FILE) -> None:
    from core.foundation.security.io import atomic_write
    atomic_write(path, json.dumps(items, indent=1).encode("utf-8"))


def subscribe(subscription: dict[str, Any], label: str = "phone", path: Path = SUBS_FILE) -> int:
    endpoint = str(subscription.get("endpoint") or "")
    keys = subscription.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("That isn't a valid push subscription.")
    with _LOCK:
        items = [s for s in subscriptions(path) if s["endpoint"] != endpoint]
        items.append({"endpoint": endpoint, "keys": {"p256dh": str(keys["p256dh"]), "auth": str(keys["auth"])},
                      "label": str(label)[:40], "added": time.strftime("%Y-%m-%dT%H:%M:%S")})
        _save(items[-10:], path)
        return len(items[-10:])


def unsubscribe(endpoint: str, path: Path = SUBS_FILE) -> None:
    with _LOCK:
        _save([s for s in subscriptions(path) if s["endpoint"] != endpoint], path)


def send(title: str, body: str, url: str = "/app/", *, push: Callable[..., Any] | None = None, path: Path = SUBS_FILE,
         pem: bytes | None = None) -> int:
    """Send to every subscribed phone; drops subscriptions the push service says are gone. Returns how many got it."""
    items = subscriptions(path)
    if not items:
        return 0
    if push is None:
        from pywebpush import webpush as push
    from py_vapid import Vapid
    vapid = Vapid.from_pem(pem or _private_pem())
    payload = json.dumps({"title": str(title)[:80], "body": str(body)[:240], "url": url})
    sent, gone = 0, []
    for item in items:
        try:
            push(subscription_info={"endpoint": item["endpoint"], "keys": item["keys"]}, data=payload, vapid_private_key=vapid,
                 vapid_claims={"sub": CONTACT}, ttl=3600)
            sent += 1
        except Exception as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status in (404, 410):
                gone.append(item["endpoint"])
    if gone:
        with _LOCK:
            _save([s for s in subscriptions(path) if s["endpoint"] not in gone], path)
    return sent


def notify(title: str, body: str, url: str = "/app/") -> None:
    """Fire-and-forget push (never blocks or breaks the caller)."""
    if not subscriptions():
        return

    def run():
        try:
            send(title, body, url)
        except Exception:
            pass
    threading.Thread(target=run, name="zaenia-web-push", daemon=True).start()


class TrainingReminders:
    """Daily phone reminders at the times set in Training program: workout, weigh-in, food log."""

    def __init__(self, clock: Callable[[], Any] | None = None, sender: Callable[[str, str], None] = notify):
        self.clock = clock
        self.sender = sender
        self.sent: set[str] = set()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def tick(self) -> list[str]:
        from datetime import datetime
        from core.assistant_platform.training import WEEKDAYS, overview, training
        now = self.clock() if self.clock else datetime.now()
        data = training().load()
        times = data["profile"].get("reminders") or {}
        fired = []
        for kind, at in times.items():
            key = f"{now.date().isoformat()}:{kind}"
            if not at or key in self.sent or now.strftime("%H:%M") < at or now.strftime("%H:%M") > _plus(at, 30):
                continue
            self.sent.add(key)
            entry = data["days"].get(now.date().isoformat(), {})
            if kind == "workout":
                try:
                    from core.assistant_platform.service import platform
                    label = overview(platform().store)["weekdays"].get(WEEKDAYS[now.weekday()], "")
                except Exception:
                    label = ""
                if not label:
                    continue
                self.sender("Time to train", f"Today: {label}. Open Training program to check it off.")
            elif kind == "weighIn" and not entry.get("weightLb"):
                self.sender("Weigh-in", "Step on the scale and log your weight in Training program.")
            elif kind == "food":
                self.sender("Log your food", "Add today's meals so I can check your calories against your target.")
            else:
                continue
            fired.append(kind)
        return fired

    def start(self) -> None:
        if self.thread is not None:
            return

        def run():
            while not self.stop_event.wait(60):
                try:
                    self.tick()
                except Exception:
                    pass
        self.thread = threading.Thread(target=run, name="zaenia-training-reminders", daemon=True)
        self.thread.start()


def _plus(clock: str, minutes: int) -> str:
    hours, mins = map(int, clock.split(":"))
    total = min(23 * 60 + 59, hours * 60 + mins + minutes)
    return f"{total // 60:02d}:{total % 60:02d}"
