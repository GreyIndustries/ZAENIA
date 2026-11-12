"""Game mode: free ZAE's brain while a full-screen game (or any full-screen
app) is in front, and load it again only when Grey talks to her.

The API server checks the foreground window every few seconds. After a
full-screen app has been in front for about 20 seconds, game mode starts:

* the local models are unloaded from graphics memory right away;
* any reply during the game releases the brain again after 1 minute instead
  of 10;
* on PC Voice, overheard speech (voice chat, talking to the game) only reaches
  the brain when it mentions ZAE by name, so friends talking doesn't keep
  reloading her.

It ends about 10 seconds after the full-screen app leaves the front. The state
is a small file (data/ui/game_mode.json) so the server and PC Voice agree.
Nothing about the game is stored beyond the app's name.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = PROJECT_ROOT / "data" / "ui" / "game_mode.json"
CHECK_SECONDS = 5.0
ENTER_SECONDS = 20.0
LEAVE_SECONDS = 10.0
GAME_KEEP_ALIVE = "1m"
STALE_SECONDS = 30.0

# Full-screen windows that are not games: the desktop itself, ZAE, lock screen.
_NOT_GAMES = {"explorer.exe", "desktop.exe", "zaenia.exe", "lockapp.exe", "searchhost.exe",
              "startmenuexperiencehost.exe", "shellexperiencehost.exe", "textinputhost.exe", "claude.exe",
              # Hosts Windows Store apps (Settings, Photos, Calculator...): maximised, it looked like a game.
              "applicationframehost.exe"}


def fullscreen_app() -> str | None:
    """Executable name of the foreground window when it covers its whole monitor, else None."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        from core.voice_listener.activity import foreground_window
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd or user32.IsIconic(hwnd):
            return None
        found = foreground_window()
        exe = (found[0] if found else "").lower()
        if not exe or exe in _NOT_GAMES:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO(); info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        screen = info.rcMonitor
        covers = rect.left <= screen.left and rect.top <= screen.top and rect.right >= screen.right and rect.bottom >= screen.bottom
        return exe if covers else None
    except Exception:
        return None


def read_state() -> dict[str, Any]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def active() -> bool:
    """True while game mode is on (and the server is still updating it)."""
    data = read_state()
    if not data.get("active"):
        return False
    try:
        updated = datetime.fromisoformat(str(data.get("updatedAt")))
    except (TypeError, ValueError):
        return False
    return (datetime.now(timezone.utc) - updated).total_seconds() <= STALE_SECONDS


def keep_alive(default: str) -> str:
    return GAME_KEEP_ALIVE if active() else default


def unload_models(endpoint: str = "http://127.0.0.1:11434") -> list[str]:
    """Ask Ollama to drop every loaded model from memory now."""
    import requests
    freed = []
    try:
        loaded = requests.get(endpoint + "/api/ps", timeout=3).json().get("models", [])
    except Exception:
        return freed
    for model in loaded:
        name = model.get("name") or model.get("model")
        if not name:
            continue
        try:
            requests.post(endpoint + "/api/generate", json={"model": name, "keep_alive": 0}, timeout=10)
            freed.append(name)
        except Exception:
            pass
    return freed


class GameModeMonitor:
    def __init__(self, *, detect: Callable[[], str | None] = fullscreen_app,
                 unload: Callable[[], list[str]] = unload_models,
                 write: Callable[[dict[str, Any]], None] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.detect, self.unload, self.clock = detect, unload, clock
        self.write = write or self._write
        self.active = False
        self.app: str | None = None
        self.seen_since: float | None = None
        self.gone_since: float | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    @staticmethod
    def _write(record: dict[str, Any]) -> None:
        try:
            from core.foundation.security.io import atomic_write
            atomic_write(STATE_FILE, json.dumps(record).encode("utf-8"))
        except Exception:
            pass

    def step(self) -> None:
        now = self.clock()
        app = self.detect()
        if app:
            self.gone_since = None
            if self.seen_since is None or app != self.app:
                self.seen_since, self.app = now, app
            if not self.active and now - self.seen_since >= ENTER_SECONDS:
                self.active = True
                self.unload()
        else:
            self.seen_since = None
            if self.active:
                self.gone_since = self.gone_since if self.gone_since is not None else now
                if now - self.gone_since >= LEAVE_SECONDS:
                    self.active, self.gone_since = False, None
        self.write({"active": self.active, "app": self.app if self.active else None,
                    "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    def start(self) -> None:
        if self.thread is not None or os.name != "nt":
            return
        def run():
            while not self.stop_event.wait(CHECK_SECONDS):
                try:
                    self.step()
                except Exception:
                    pass
        self.thread = threading.Thread(target=run, name="zaenia-game-mode", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self._write({"active": False, "app": None, "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})
