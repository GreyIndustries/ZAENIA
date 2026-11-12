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
import hashlib
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = PROJECT_ROOT / "data" / "secure" / "vapid.key.dpapi"
SUBS_FILE = PROJECT_ROOT / "data" / "secure" / "push_subscriptions.json"
_LOCK = threading.Lock()
CATEGORIES = ("reminder", "calendar", "task", "training", "email", "research", "other")
PUSH_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com")


def device_id(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()[:32]


def validate_subscription(subscription: dict[str, Any]) -> dict[str, Any]:
    """Only browser-vendor HTTPS endpoints, with actual P-256/auth keys.

    Client data must never turn this sender into an arbitrary URL fetcher.
    Redirects are also refused at the HTTP transport boundary.
    """
    from cryptography.hazmat.primitives.asymmetric import ec
    if not isinstance(subscription, dict):
        raise ValueError("That isn't a valid push subscription.")
    endpoint = subscription.get("endpoint")
    try:
        parsed = urlsplit(endpoint if isinstance(endpoint, str) else "")
        host = parsed.hostname or ""
        allowed = host in PUSH_HOSTS or host.endswith((".push.apple.com", ".notify.windows.com", ".push.services.mozilla.com"))
        if (not allowed or parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.fragment or not parsed.path
                or len(endpoint) > 4096 or any(ord(c) < 33 for c in endpoint)):
            raise ValueError()
        keys = subscription.get("keys")
        decoded = {}
        for name, size in (("p256dh", 65), ("auth", 16)):
            value = keys[name]
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value) or len(value) > 90:
                raise ValueError()
            raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
            if len(raw) != size:
                raise ValueError()
            decoded[name] = value
        public = decoded["p256dh"]
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), base64.urlsafe_b64decode(public + "=" * (-len(public) % 4)))
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ValueError("Use a valid subscription from a supported browser's push service.") from error
    return {"endpoint": endpoint, "keys": decoded}


def preferences(value: dict[str, Any] | None = None) -> dict[str, Any]:
    value = value or {}
    if not isinstance(value, dict) or set(value) - {"categories", "preview"}:
        raise ValueError("Choose valid notification preferences.")
    categories = value.get("categories", list(CATEGORIES))
    preview = value.get("preview", False)
    if not isinstance(categories, list) or any(c not in CATEGORIES for c in categories) or type(preview) is not bool:
        raise ValueError("Choose valid notification categories and preview setting.")
    return {"categories": list(dict.fromkeys(categories)), "preview": preview}


def app_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or "." not in parsed.hostname
                or parsed.hostname in ("localhost", "127.0.0.1") or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise ValueError()
    except (TypeError, ValueError) as error:
        raise ValueError("Open ZAE at her HTTPS phone address before enabling notifications.") from error
    return f"https://{parsed.hostname}"


def contact(item: dict[str, Any]) -> str:
    configured = os.environ.get("ZAENIA_PUSH_CONTACT", "")
    if configured.startswith("mailto:") and re.fullmatch(r"mailto:[^\s@]+@[^\s@]+\.[^\s@]+", configured):
        return configured
    return app_origin(configured or item.get("appOrigin", ""))


def _protect(data: bytes, decrypt: bool = False) -> bytes:
    from core.voice_security.windows_protection import protect
    return protect(data, decrypt=decrypt)


def _private_pem(protect: Callable[..., bytes] = _protect, path: Path = KEY_FILE) -> bytes:
    from core.foundation.security.io import file_lock, reject_link
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, file_lock(path.with_suffix(".lock")):
        reject_link(path)
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
        from core.foundation.security.io import reject_link
        reject_link(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items: list[dict[str, Any]], path: Path = SUBS_FILE) -> None:
    from core.foundation.security.io import atomic_write
    atomic_write(path, json.dumps(items, indent=1).encode("utf-8"))


def subscribe(subscription: dict[str, Any], label: str = "phone", path: Path = SUBS_FILE,
              *, options: dict[str, Any] | None = None, origin: str = "") -> int:
    clean = validate_subscription(subscription)
    if origin:
        origin = app_origin(origin)
    from core.foundation.security.io import file_lock
    with _LOCK, file_lock(path.with_suffix(".lock")):
        items = subscriptions(path)
        previous = next((s for s in items if s["endpoint"] == clean["endpoint"]), {})
        items = [s for s in items if s["endpoint"] != clean["endpoint"]]
        if len(items) >= 10:
            raise ValueError("Ten browsers are already connected. Remove one before adding another.")
        items.append({**clean, "label": " ".join(str(label).split())[:40] or "phone",
                      "appOrigin": origin or previous.get("appOrigin", ""),
                      "preferences": preferences(options if options is not None else previous.get("preferences")),
                      "added": previous.get("added") or time.strftime("%Y-%m-%dT%H:%M:%S")})
        _save(items, path)
        return len(items)


def unsubscribe(endpoint: str, path: Path = SUBS_FILE) -> None:
    from core.foundation.security.io import file_lock
    with _LOCK, file_lock(path.with_suffix(".lock")):
        _save([s for s in subscriptions(path) if s["endpoint"] != endpoint], path)


def send_one(item: dict[str, Any], title: str, body: str, *, notice_id: str = "", url: str = "/app/",
             push: Callable[..., Any] | None = None, pem: bytes | None = None, ttl: int = 3600) -> str:
    """Provider acceptance only; never claims the phone displayed or read it."""
    import requests
    try:
        clean = validate_subscription(item)
        subject = contact(item)
    except ValueError:
        return "invalid_subscription"
    if push is None:
        from pywebpush import webpush as push
    from py_vapid import Vapid
    try:
        vapid = Vapid.from_pem(pem or _private_pem())
    except Exception:
        return "key_unavailable"
    # A hostile click destination cannot leave ZAE's own app.
    if not url.startswith("/app/") or url.startswith("//") or "\\" in url:
        url = "/app/"
    payload = json.dumps({"title": str(title)[:80], "body": str(body)[:240], "url": url,
                          "tag": notice_id[:100]}, ensure_ascii=False)

    class DirectSession(requests.Session):
        def post(self, url, **kwargs):
            kwargs["allow_redirects"] = False
            return super().post(url, **kwargs)

    try:
        with DirectSession() as session:
            response = push(subscription_info=clean, data=payload, vapid_private_key=vapid,
                            vapid_claims={"sub": subject}, ttl=max(0, min(ttl, 86400)), timeout=8,
                            requests_session=session)
        code = getattr(response, "status_code", 201)
        return "accepted" if code in (200, 201, 202) else f"http_{code}"
    except Exception as error:
        code = getattr(getattr(error, "response", None), "status_code", None)
        return f"http_{code}" if isinstance(code, int) else "network"


def send(title: str, body: str, url: str = "/app/", *, push: Callable[..., Any] | None = None, path: Path = SUBS_FILE,
         pem: bytes | None = None) -> int:
    """Legacy synchronous sender; returns provider acceptances, not phone receipts."""
    items = subscriptions(path)
    if not items:
        return 0
    if push is None:
        from pywebpush import webpush as push
    sent, gone = 0, []
    for item in items:
        result = send_one(item, title, body, url=url, push=push, pem=pem)
        if result == "accepted":
            sent += 1
        elif result in ("http_404", "http_410"):
            gone.append(item["endpoint"])
    if gone:
        for endpoint in gone:
            unsubscribe(endpoint, path)
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

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)


def _plus(clock: str, minutes: int) -> str:
    hours, mins = map(int, clock.split(":"))
    total = min(23 * 60 + 59, hours * 60 + mins + minutes)
    return f"{total // 60:02d}:{total % 60:02d}"
