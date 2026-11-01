"""Nightly improvement ideas (Grey's option 3, 2026-11-01): ZAE looks at how the last day went and suggests fixes.

Once a night (1-5 a.m., skipped while a game or a build request is running) she gathers what went wrong:
requests Grey repeated, replies where she couldn't do something, replies that said "done" or "logged" when no action
ran, sentences where he corrected her, and parts of her system that went down. Study turns that into at most three
ideas, each with the evidence. They go to Suggestions as "Fix" ideas, where Grey taps Build it (a build request,
still checked and approved by him), Dismiss (not now) or Never (she stops suggesting that kind of change).
No signals means no ideas: she doesn't invent problems.
"""
from __future__ import annotations

import json
import re
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONVERSATION = PROJECT_ROOT / "data" / "conversation_memory.jsonl"
UPTIME = PROJECT_ROOT / "data" / "ui" / "uptime.json"
STATE = PROJECT_ROOT / "data" / "ui" / "build_ideas.json"
STUDY_MODEL = "qwen3:14b"

_CANT = re.compile(r"\b(?:I\s+(?:couldn't|can't|cannot|wasn't\s+able|am\s+not\s+able|don't\s+have\s+(?:access|a\s+way))|isn't\s+available|"
                   r"didn't\s+work|something\s+went\s+wrong|not\s+sure\s+what\s+you\s+mean)\b", re.I)
_CLAIM = re.compile(r"^\s*(?:done|logged|saved|added|set|all\s+set|got\s+it[,.]?\s+(?:logged|saved|added))\b|\b(?:I've|I\s+have)\s+(?:logged|saved|added|set|created|updated)\b", re.I)
_CORRECTION = re.compile(r"^\s*(?:no[,.!]|(?:nope|that's\s+(?:not|wrong)|not\s+what\s+I|you\s+(?:didn't|got\s+it\s+wrong)|wrong)\b)", re.I)
_TALK_ONLY = {"normal", "quick_self", "grounded_system", "live_data", "conductor_seek_web", None}


def _read_turns(since: datetime, path: Path = CONVERSATION) -> list[dict[str, Any]]:
    turns = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    when = datetime.fromisoformat(str(row.get("timestamp")))
                except (ValueError, TypeError):
                    continue
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                if when >= since:
                    turns.append({**row, "when": when})
    except OSError:
        pass
    return turns


def gather_signals(now: datetime | None = None, *, conversation: Path = CONVERSATION, uptime: Path = UPTIME) -> list[str]:
    """Plain lines describing what went wrong in the last day (no secrets; his words are quoted briefly)."""
    now = now or datetime.now(timezone.utc)
    turns = _read_turns(now - timedelta(hours=24), conversation)
    lines: list[str] = []
    asked = [t for t in turns if t.get("role") == "user"]
    norm = lambda text: re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()
    repeats = Counter()
    for first, second in zip(asked, asked[1:]):
        if norm(first.get("content")) and norm(first.get("content")) == norm(second.get("content")) \
                and (second["when"] - first["when"]).total_seconds() < 600:
            repeats[str(first.get("content"))[:120]] += 1
    lines += [f"Grey repeated a request ({count + 1} times in a row): \"{text}\"" for text, count in repeats.most_common(5)]
    for question, answer in zip(turns, turns[1:]):
        if question.get("role") != "user" or answer.get("role") != "assistant":
            continue
        reply = str(answer.get("content") or "")
        if _CANT.search(reply):
            lines.append(f"She couldn't do it. Grey: \"{str(question.get('content'))[:120]}\" ZAE: \"{reply[:140]}\"")
        elif _CLAIM.search(reply) and answer.get("route") in _TALK_ONLY:
            lines.append(f"She said it was done but no action ran (route {answer.get('route') or 'chat'}). "
                         f"Grey: \"{str(question.get('content'))[:120]}\" ZAE: \"{reply[:140]}\"")
    for turn in asked:
        if _CORRECTION.search(str(turn.get("content") or "")):
            lines.append(f"Grey corrected her: \"{str(turn.get('content'))[:140]}\"")
    try:
        events = json.loads(uptime.read_text(encoding="utf-8")).get("events") or []
        since = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
        down = Counter(e.get("part") for e in events if e.get("kind") == "down" and str(e.get("at")) >= since and e.get("part") != "desktop")
        lines += [f"Her {part} part went down {count} time(s) today." for part, count in down.items()]
    except (OSError, ValueError, AttributeError):
        pass
    return lines[:40]


def ideas_prompt(signals: list[str], never: list[str], earlier: list[str]) -> str:
    return ("You are ZAE, Grey's personal assistant, looking at what went wrong with you in the last day. Suggest at most 3 "
            "specific changes to your own app that would fix the most important problems below. Every idea must point at "
            "something in the list (quote it as the evidence). If nothing below is worth fixing, reply with an empty list. "
            + ("Grey said NEVER to these kinds of change, so don't suggest anything like them: " + "; ".join(never[:20]) + ". " if never else "")
            + ("Don't repeat these earlier ideas: " + "; ".join(earlier[:20]) + ". " if earlier else "")
            + "Reply with JSON only: {\"ideas\": [{\"title\": \"short, 3-8 words\", \"why\": \"the evidence, one sentence\", "
            "\"how\": \"what to change, one or two sentences\", \"effort\": \"small, medium or large\"}]}\n\nWHAT WENT WRONG:\n- "
            + "\n- ".join(signals))


def _study(prompt: str) -> str:
    from core.research.analyze import run_local
    return run_local(prompt, model=STUDY_MODEL)


class NightlyIdeas:
    def __init__(self, *, state: Path = STATE, ask: Callable[[str], str] = _study,
                 signals: Callable[[], list[str]] = gather_signals, store: Any = None,
                 busy: Callable[[], bool] | None = None, notify: Callable[[int], None] | None = None,
                 done: Callable[[], None] | None = None):
        self.state, self.ask, self.signals = Path(state), ask, signals
        self._store, self.busy = store, busy or _busy
        self.notify, self.done = notify or _notify, done or _bring_talk_back
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    @property
    def store(self):
        if self._store is None:
            from core.assistant_platform.suggestions import suggestions
            self._store = suggestions()
        return self._store

    def last(self) -> dict[str, Any]:
        try:
            return json.loads(self.state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def due(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        last = self.last().get("at")
        try:
            age = (now.astimezone(timezone.utc) - datetime.fromisoformat(last)).total_seconds() if last else 1e9
        except ValueError:
            age = 1e9
        return 1 <= now.hour <= 5 and age > 20 * 3600

    def run(self, *, force: bool = False) -> list[dict[str, Any]]:
        if not force and (not self.due() or self.busy()):
            return []
        signals = self.signals()
        fresh: list[dict[str, Any]] = []
        if signals:
            items = self.store.list()
            never = [i["title"] for i in items if i.get("status") == "never"]
            earlier = [i["title"] for i in items[::-1] if i.get("for") == "fix" and i.get("status") != "never"]
            try:
                raw = self.ask(ideas_prompt(signals, never, earlier))
            finally:
                self.done()
            match = re.search(r"\{.*\}", raw or "", re.S)
            try:
                proposed = (json.loads(match.group(0)) if match else {}).get("ideas") or []
            except (ValueError, AttributeError):
                proposed = []
            fresh = self.store.add([idea for idea in proposed[:3] if isinstance(idea, dict)])
        from core.foundation.security.io import atomic_write
        atomic_write(self.state, json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                             "signals": len(signals), "ideas": len(fresh)}).encode("utf-8"))
        if fresh:
            self.notify(len(fresh))
        return fresh

    def start(self) -> None:
        if self.thread is not None:
            return

        def loop() -> None:
            while not self.stop_event.wait(600):
                try:
                    self.run()
                except Exception:
                    pass
        self.thread = threading.Thread(target=loop, name="zaenia-nightly-ideas", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()


def _busy() -> bool:
    try:
        from core.assistant_platform.game_mode import active
        from core.assistant_platform.build_helper import build_requests
        return active() or any(item["status"] in ("queued", "working") for item in build_requests().list())
    except Exception:
        return True


def _notify(count: int) -> None:
    try:
        from core.assistant_followthrough.service import FollowThroughService
        FollowThroughService().post("build_ideas", datetime.now().strftime("%Y-%m-%d"), f"{count} upgrade idea{'s' if count != 1 else ''} from ZAE",
                                    "From how yesterday went. See Code Doctor > Suggestions; tap Build it on any you want.")
    except Exception:
        pass


def _bring_talk_back() -> None:
    try:
        from core.research.agent import _study_done
        _study_done()
    except Exception:
        pass


_IDEAS: NightlyIdeas | None = None


def ideas() -> NightlyIdeas:
    global _IDEAS
    if _IDEAS is None:
        _IDEAS = NightlyIdeas()
    return _IDEAS
