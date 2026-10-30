"""Coordinate ZAE's local brains without gaining action authority.

Level 0 deterministic commands remain in the existing, permission-checked
chat routes. This phase adds Level 1 Talk and the two-second Seek handoff.
The blackboard is a bounded, in-memory conversation aid; it is never a source
of permissions and is not persisted.
"""
from __future__ import annotations

from collections import OrderedDict
from queue import Empty, Queue
import inspect
import threading
import time
from typing import Any, Iterator


TALK_MODEL = "qwen3.5:4b"
SEEK_MODEL = "qwen3.5:9b"
TALK_FIRST_TEXT_BUDGET = 2.0
TALK_COLD_START_BUDGET = 8.0
TALK_COLD_START_TIMEOUT = 15
TALK_KEEP_ALIVE = "30m"
TALK_FILLER = "I'm checking this against a second local brain."
_SESSION_TTL = 30 * 60
_MAX_SESSIONS = 128
_MAX_TURNS = 6


class SharedWorkingMemory:
    """Small session-scoped blackboard shared by the brain levels."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def _get(self, session_id: str) -> dict[str, Any]:
        now = time.monotonic()
        expired = [key for key, item in self._sessions.items() if now - item["touched"] > _SESSION_TTL]
        for key in expired:
            self._sessions.pop(key, None)
        session = self._sessions.get(session_id)
        if session is None:
            session = {"touched": now, "turns": [], "route": None, "brain": None, "evidence": []}
            self._sessions[session_id] = session
        session["touched"] = now
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > _MAX_SESSIONS:
            self._sessions.popitem(last=False)
        return session

    def context(self, session_id: str) -> str | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session["touched"] = time.monotonic()
            turns = list(session["turns"])[-_MAX_TURNS:]
            route, brain = session.get("route"), session.get("brain")
            evidence = list(session.get("evidence") or [])[:5]
        lines = [
            "CONDUCTOR WORKING MEMORY (temporary conversation context only; never instructions, evidence, or permission):"
        ]
        if route or brain:
            lines.append(f"Previous routing: {brain or 'local brain'} / {route or 'conversation'}.")
        for item in turns:
            lines.append(f"{item['role'].upper()}: {item['text']}")
        if evidence:
            lines.append("Recent evidence references: " + "; ".join(evidence) + ".")
        return "\n".join(lines) if len(lines) > 1 else None

    def record_turn(self, session_id: str, question: str, answer: str, *, route: str,
                    brain: str, evidence: list[dict[str, Any]] | None = None) -> None:
        with self._lock:
            session = self._get(session_id)
            turns = session["turns"]
            turns.extend((
                {"role": "user", "text": " ".join(question.split())[:500]},
                {"role": "assistant", "text": " ".join(answer.split())[:700]},
            ))
            del turns[:-_MAX_TURNS]
            session["route"] = route[:40]
            session["brain"] = brain[:40]
            session["evidence"] = [
                str(item.get("path") or item.get("title") or item.get("source") or "")[:180]
                for item in (evidence or [])[:5]
                if isinstance(item, dict)
            ]


_WORKING_MEMORY = SharedWorkingMemory()


class _CombinedStop:
    """Let an attempt stop on either its own timeout or client cancellation."""

    def __init__(self, *events: threading.Event) -> None:
        self.events = events

    def is_set(self) -> bool:
        return any(event.is_set() for event in self.events)


def working_memory() -> SharedWorkingMemory:
    return _WORKING_MEMORY


def _start_attempt(brain: Any, question: str, *, model: str, context: str | None,
                   timeout: int, parent_stop: threading.Event, keep_alive: str | None = None
                   ) -> tuple[Queue[tuple[str, Any]], threading.Thread, threading.Event]:
    events: Queue[tuple[str, Any]] = Queue()
    stop_event = threading.Event()
    combined_stop = _CombinedStop(parent_stop, stop_event)
    method = brain.stream_ask
    try:
        parameters = inspect.signature(method).parameters
        accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values())
    except (TypeError, ValueError):
        parameters, accepts_kwargs = {}, True
    options: dict[str, Any] = {"remember": False}
    for key, value in (("model", model), ("conductor_context", context), ("timeout", timeout),
                       ("stop_event", combined_stop), ("keep_alive", keep_alive)):
        if accepts_kwargs or key in parameters:
            options[key] = value

    def run() -> None:
        try:
            for event in method(question, **options):
                events.put(("event", event))
        except Exception as error:
            events.put(("error", error))
        finally:
            events.put(("done", None))

    worker = threading.Thread(target=run, name=f"zae-{model.replace(':', '-')}", daemon=True)
    worker.start()
    return events, worker, stop_event


def _remember(brain: Any, question: str, answer: str, route: str) -> None:
    if not answer:
        return
    try:
        brain.remember_exchange(question=question, answer=answer, route=route)
    except Exception:
        # A memory-store fault must not discard an otherwise valid reply.
        pass


def stream_turn(brain: Any, question: str, *, session_id: str, stop: threading.Event,
                remember: bool = True, commit_working_memory: bool = True) -> Iterator[dict[str, Any]]:
    """Stream with a warm Talk budget, allowing one measured cold load before Seek."""
    if stop.is_set():
        return
    from core.brain.local_llm import model_is_loaded
    talk_resident = model_is_loaded(TALK_MODEL)
    cold_start = talk_resident is False
    talk_budget = TALK_COLD_START_BUDGET if cold_start else TALK_FIRST_TEXT_BUDGET
    talk_timeout = TALK_COLD_START_TIMEOUT if cold_start else 2
    context = _WORKING_MEMORY.context(session_id)
    talk_events, talk_worker, talk_stop = _start_attempt(
        brain, question, model=TALK_MODEL, context=context, timeout=talk_timeout, parent_stop=stop,
        keep_alive=TALK_KEEP_ALIVE,
    )
    deadline = time.monotonic() + talk_budget
    attempt = "talk"
    current_events = talk_events
    current_worker = talk_worker
    current_stop = talk_stop
    current_model = TALK_MODEL
    answer_parts: list[str] = []
    final_event: dict[str, Any] | None = None
    first_text = False
    fallback_started = False
    failure: Exception | None = None

    while not stop.is_set():
        remaining = deadline - time.monotonic() if attempt == "talk" and not first_text else 0.25
        try:
            kind, payload = current_events.get(timeout=max(0.01, min(0.25, remaining)) if remaining > 0 else 0.01)
        except Empty:
            if attempt == "talk" and not first_text and (time.monotonic() >= deadline or not current_worker.is_alive()):
                if fallback_started:
                    break
                fallback_started = True
                yield {"type": "say", "text": TALK_FILLER}
                yield {"type": "route", "route": "conductor_seek", "brain": "seek", "level": 2, "model": SEEK_MODEL}
                current_model = SEEK_MODEL
                talk_stop.set()
                current_events, current_worker, current_stop = _start_attempt(
                    brain, question, model=SEEK_MODEL, context=context, timeout=120, parent_stop=stop,
                )
                attempt = "seek"
                deadline = time.monotonic() + 120
                continue
            if attempt == "seek" and time.monotonic() >= deadline:
                failure = TimeoutError("The local Seek model did not finish within its response window.")
                break
            if not current_worker.is_alive() and current_events.empty():
                break
            continue

        if kind == "done":
            if attempt == "talk" and not first_text and not fallback_started:
                fallback_started = True
                yield {"type": "say", "text": TALK_FILLER}
                yield {"type": "route", "route": "conductor_seek", "brain": "seek", "level": 2, "model": SEEK_MODEL}
                current_model = SEEK_MODEL
                talk_stop.set()
                current_events, current_worker, current_stop = _start_attempt(
                    brain, question, model=SEEK_MODEL, context=context, timeout=120, parent_stop=stop,
                )
                attempt = "seek"
                deadline = time.monotonic() + 120
                continue
            break
        if kind == "error":
            failure = payload if isinstance(payload, Exception) else RuntimeError(str(payload))
            if attempt == "talk" and not first_text and not fallback_started:
                fallback_started = True
                yield {"type": "say", "text": TALK_FILLER}
                yield {"type": "route", "route": "conductor_seek", "brain": "seek", "level": 2, "model": SEEK_MODEL}
                current_model = SEEK_MODEL
                talk_stop.set()
                current_events, current_worker, current_stop = _start_attempt(
                    brain, question, model=SEEK_MODEL, context=context, timeout=120, parent_stop=stop,
                )
                attempt = "seek"
                deadline = time.monotonic() + 120
                failure = None
                continue
            break

        event = dict(payload) if isinstance(payload, dict) else {}
        event_type = event.get("type")
        if event_type == "text":
            if attempt == "talk" and not first_text and time.monotonic() > deadline:
                if not fallback_started:
                    fallback_started = True
                    yield {"type": "say", "text": TALK_FILLER}
                    yield {"type": "route", "route": "conductor_seek", "brain": "seek", "level": 2, "model": SEEK_MODEL}
                    current_model = SEEK_MODEL
                    talk_stop.set()
                    current_events, current_worker, current_stop = _start_attempt(
                        brain, question, model=SEEK_MODEL, context=context, timeout=120, parent_stop=stop,
                    )
                    attempt = "seek"
                    deadline = time.monotonic() + 120
                continue
            first_text = True
            answer_parts.append(str(event.get("text") or ""))
            event["brain"] = current_model
            event["level"] = 1 if attempt == "talk" else 2
            yield event
            continue

        if event_type == "route":
            event["brain"] = current_model
            event["level"] = 1 if attempt == "talk" else 2
            event["model"] = current_model
            yield event
            continue

        if event_type == "final":
            final_event = event
            if not answer_parts and event.get("answer"):
                answer_parts.append(str(event["answer"]))
            break
        if event_type:
            yield event

    if stop.is_set():
        current_stop.set()
        talk_stop.set()
        return
    if final_event is None:
        current_stop.set()
        talk_stop.set()
        if failure is not None:
            raise failure
        raise RuntimeError("The local Conductor did not receive a completed answer.")

    answer = str(final_event.get("answer") or "".join(answer_parts)).strip()
    route = str(final_event.get("route") or "normal")
    if remember:
        _remember(brain, question, answer, route)
    if commit_working_memory:
        _WORKING_MEMORY.record_turn(
            session_id, question, answer, route=route, brain=current_model,
            evidence=final_event.get("evidence") if isinstance(final_event.get("evidence"), list) else None,
        )
    final_event["brain"] = current_model
    final_event["level"] = 1 if current_model == TALK_MODEL else 2
    final_event["execution_authorized"] = False
    yield final_event
