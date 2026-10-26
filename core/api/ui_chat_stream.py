"""Streaming chat for the ZÆNIA UI.

Words appear as ZÆNIA writes them, so the app can start speaking after the
first sentence instead of waiting for the whole reply. Uses BrainService
(the same path as the PC voice runtime): normal questions stream live,
questions about ZÆNIA's own system are grounded and verified first, and the
exchange is saved to conversation memory with only your words.

Stopping: the app calls cancel(request_id). The stream ends at the next
token, the connection to Ollama is closed so it stops generating, and the
part ZÆNIA already said is kept in memory.

Explicit task/calendar creation requests produce reviewable proposals. The
UI applies them through the existing separately authorized task/calendar
routes. This stream never executes an action or grants permission for one.
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable, Iterator

_ACTIVE: dict[str, threading.Event] = {}
_ACTIVE_LOCK = threading.Lock()
_BRAIN_LOCK = threading.Lock()
_BRAIN: Any = None
REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_DIALOGUES: dict[str, tuple[Any, float, threading.Lock]] = {}
_DIALOGUE_LOCK = threading.Lock()


def _prepare(message: str, conversation_id: str | None):
    from core.assistant_dialogue import ActionDialogue
    if conversation_id is None:
        return ActionDialogue().prepare(message)
    now = time.monotonic()
    with _DIALOGUE_LOCK:
        expired = [key for key, (_, at, _) in _DIALOGUES.items() if now - at >= 300]
        for key in expired:
            del _DIALOGUES[key]
        if conversation_id not in _DIALOGUES:
            if len(_DIALOGUES) >= 128:
                del _DIALOGUES[min(_DIALOGUES, key=lambda key: _DIALOGUES[key][1])]
            _DIALOGUES[conversation_id] = (ActionDialogue(), now, threading.Lock())
        dialogue, _, lock = _DIALOGUES[conversation_id]
        _DIALOGUES[conversation_id] = (dialogue, now, lock)
    with lock:
        return dialogue.prepare(message)


def _brain(authorize: Callable[[str], Any] | None = None) -> Any:
    if authorize is not None:
        from core.brain.brain_service import BrainService
        # The authorizer belongs to this request; never cache it across clients.
        return BrainService(memory_authorizer=authorize)
    global _BRAIN
    with _BRAIN_LOCK:
        if _BRAIN is None:
            from core.brain.brain_service import BrainService
            _BRAIN = BrainService()
        return _BRAIN


def cancel(request_id: str) -> bool:
    with _ACTIVE_LOCK:
        stop = _ACTIVE.get(request_id)
    if stop is None:
        return False
    stop.set()
    return True


def _line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


class _ThinkFilter:
    """Drops <think>…</think> text if an older Ollama ignores think=false."""

    def __init__(self) -> None:
        self.inside = False
        self.pending = ""

    def feed(self, text: str) -> str:
        data, out = self.pending + text, []
        self.pending = ""
        while data:
            tag = "</think>" if self.inside else "<think>"
            index = data.find(tag)
            if index < 0:
                # Hold back a partial tag at the end.
                keep = next((k for k in range(len(tag) - 1, 0, -1) if data.endswith(tag[:k])), 0)
                if not self.inside:
                    out.append(data[: len(data) - keep])
                self.pending = data[len(data) - keep:] if keep else ""
                break
            if not self.inside:
                out.append(data[:index])
            data = data[index + len(tag):]
            self.inside = not self.inside
        return "".join(out)


def _conversation_hooks(name: str) -> None:
    try:
        from core.conversation import conversation_state
        getattr(conversation_state, name)()
    except Exception:
        pass


def _protocol_or_reminder(message: str, authorize: Callable[[str], Any] | None) -> tuple[str, str, list[str]] | None:
    """A protocol phrase ("goodnight") or "remind me ..." is handled here, before the brain."""
    if authorize is None:
        return None
    from core.assistant_platform.training import setup_command, setup_missing
    if setup_command(message):
        # "Set up my training": her questions pop up in the Training program tab; the answers go straight in.
        missing = setup_missing()
        return ("Here are my questions. Fill them in and I'll set your calories, calendar and reminders."
                if missing else "Your program's set up. I've opened the questions so you can change anything."), "training_setup", ["fitness"]
    from core.assistant_platform import tab_actions
    target = tab_actions.parse(message)
    if target is not None:
        # "Add it to my fitness tab": her last answer becomes a real record in that tab.
        try:
            authorize("memory.write")
            from core.research.analyze import run_local
            result = tab_actions.save(target, _brain(authorize).load_recent_messages(), ask=run_local)
            if target == "plans":
                from core.assistant_platform.training import setup_missing
                if setup_missing():
                    return result["reply"] + " I've a few quick questions so I can set your calories and calendar.", "training_setup", [result["tab"]]
            return result["reply"], "tab_action", [result["tab"]]
        except PermissionError:
            return "Saving to your tabs isn't available with the current permissions.", "tab_action", []
        except ValueError as error:
            return str(error), "tab_action", []
    from core.research.agent import chat_command
    web = chat_command(message)
    if web is not None:
        kind, text = web
        try:
            if kind == "research":
                authorize("chat.reply")
                from core.research.agent import agent
                agent().start(text)
                return (f"On it. I'm researching {text} on the web; I'll let you know when it's ready. "
                        "It's in Research, under Web agent."), "web_agent", ["research"]
            authorize("memory.write")
            from core.research.agent import watch
            if kind == "watch":
                watch().add(text)
                return f"I'll keep an eye on {text} and tell you when there's news.", "web_agent", []
            watch().remove(next((t["id"] for t in watch().list() if t["topic"].casefold() == text.casefold()), text))
            return f"I've stopped watching {text}.", "web_agent", []
        except PermissionError:
            return "Web research isn't available with the current permissions.", "web_agent", []
        except ValueError as error:
            return str(error), "web_agent", []
    from core.assistant_platform import reminders as nudges
    request = nudges.parse_request(message)
    if request is not None:
        try:
            authorize("ui.tasks.write")
            when, what = request
            nudges.reminders().add(what, when)
            return f"I'll remind you at {nudges.spoken_time(when)}: {what}.", "reminder", []
        except PermissionError:
            return "Reminders aren't available with the current permissions.", "reminder", []
        except ValueError as error:
            return str(error), "reminder", []
    from core.assistant_platform.protocols import protocols, run
    found = protocols().match(message)
    if found is None:
        return None

    def ask(question: str) -> str:
        authorize("chat.reply")
        return str(_brain(authorize).ask(question, remember=False).get("answer") or "")

    def set_reminder(when: str, text: str) -> str:
        authorize("ui.tasks.write")
        parsed = nudges.parse_request(f"remind me in {when} minutes to {text}" if when.isdigit() else f"remind me at {when} to {text}")
        if parsed is None:
            raise ValueError(f"I couldn't read the time {when!r}")
        nudges.reminders().add(parsed[1], parsed[0])
        return f"Reminder set for {nudges.spoken_time(parsed[0])}."

    def headlines() -> list[str]:
        from core.tech_news.service import tech_news
        return [story["title"] for story in tech_news().headlines(limit=3)["stories"]]

    def coach(on: bool) -> None:
        authorize("assistant.desktop.manage")
        from core.assistant_platform.game_coach import game_coach
        game_coach().set_enabled(on)

    def stop_watch() -> None:
        authorize("assistant.desktop.manage")
        from core.assistant_platform.screen_watch import watcher
        watcher().stop()

    result = run(found, ask=ask, set_reminder=set_reminder, headlines=headlines, coach=coach, stop_watch=stop_watch)
    return result["reply"], "protocol", result["open"]


def stream(message: str, request_id: str, *, authorize: Callable[[str], Any] | None = None, conversation_id: str | None = None, images: list[str] | None = None, photo_history: list[dict] | None = None, files: list[tuple[str, bytes]] | None = None) -> Iterator[bytes]:
    stop = threading.Event()
    with _ACTIVE_LOCK:
        _ACTIVE[request_id] = stop
    parts: list[str] = []
    route = "normal"
    finished = False
    failure: str | None = None
    final_answer = ""
    think = _ThinkFilter()
    generator = None
    try:
        yield _line({"type": "start", "id": request_id})
        _conversation_hooks("activate_conversation")
        _conversation_hooks("record_user_speech")
        from core.assistant_platform.jobs import JOBS
        JOBS.foreground()
        from core.assistant_platform.screen_watch import screen_command, watcher, SCREEN_QUESTION
        command = screen_command(message)
        if command is not None and authorize is not None:
            # "Watch my second monitor" / "stop watching my screen".
            try:
                authorize("assistant.desktop.manage")
                state = watcher().start(command) if command else watcher().stop()
                answer = (f"Watching monitor {state['monitor']['number']}. Ask me about it anytime."
                          if state["watching"] else "Stopped watching your screen.")
            except PermissionError:
                answer = "Screen watching isn't available with the current permissions."
            except ValueError as error:
                answer = str(error)
            route = "screen_watch"
            yield _line({"type": "route", "route": route})
            yield _line({"type": "delta", "text": answer})
            yield _line({"type": "done", "reply": answer, "interrupted": False, "route": route})
            return
        quick = _protocol_or_reminder(message, authorize)
        if quick is not None:
            answer, route, tabs = quick
            yield _line({"type": "route", "route": route})
            if tabs:
                yield _line({"type": "protocol", "open": tabs})
            if route == "training_setup":
                yield _line({"type": "form", "form": "training-setup"})
            yield _line({"type": "delta", "text": answer})
            yield _line({"type": "done", "reply": answer, "interrupted": False, "route": route})
            return
        from core.assistant_platform.game_coach import coach_command, game_coach
        coaching = coach_command(message)
        if coaching is not None and authorize is not None:
            # "Watch me play" / "stop watching me play".
            try:
                authorize("assistant.desktop.manage")
                game_coach().set_enabled(coaching)
                answer = ("On it. I'll watch when a game is full screen and review how you played afterwards."
                          if coaching else "Done. I won't watch your games.")
            except PermissionError:
                answer = "The game coach isn't available with the current permissions."
            route = "game_coach"
            yield _line({"type": "route", "route": route})
            yield _line({"type": "delta", "text": answer})
            yield _line({"type": "done", "reply": answer, "interrupted": False, "route": route})
            return
        if not images and not files and authorize is not None:
            from core.research import links as link_reader
            if link_reader.find_links(message):
                # Links he sends are read (page text, TikTok captions and spoken words, YouTube details)
                # and answered from like shared files: data only, never instructions.
                authorize("chat.reply")
                yield _line({"type": "say", "text": "One sec, I'm reading that."})
                files = link_reader.links_as_files(message)
                route = "link"
                yield _line({"type": "route", "route": route})
            if link_reader.wants_clarify(message):
                material = "\n\n".join(raw.decode("utf-8", "replace") for _, raw in (files or []))
                try:
                    from core.research.analyze import run_local
                    questions = link_reader.clarify_questions(message, material, run_local)
                except Exception:
                    questions = []
                if questions:
                    # A few quick questions first, shown as a pop-up; his answers come back with the request.
                    answer = "A few quick questions so I get this right."
                    route = "clarify"
                    yield _line({"type": "route", "route": route})
                    yield _line({"type": "clarify", "questions": questions, "original": message})
                    yield _line({"type": "delta", "text": answer})
                    yield _line({"type": "done", "reply": answer, "interrupted": False, "route": route})
                    return
        if not images and SCREEN_QUESTION.search(message) and watcher().latest_frame_b64():
            # A question about the watched monitor: show her the latest capture.
            images = [watcher().latest_frame_b64()]
        if images:
            # Photo questions never enter command/proposal or durable memory paths.
            from core.api.photo_chat import stream_photo
            route = "photo"
            yield _line({"type": "route", "route": route})
            photo_message = message
            if files:
                from core.api.chat_files import files_block
                photo_message = message + "\n\n" + files_block(files)[0][:6000]
            generator = stream_photo(photo_message, images, photo_history or [], stop)
            for event in generator:
                if stop.is_set():
                    break
                if event["type"] == "text":
                    text = think.feed(event["text"])
                    if text:
                        parts.append(text)
                        yield _line({"type": "delta", "text": text})
                elif event["type"] == "final":
                    finished = True
            final_answer = "".join(parts).strip()
            if not final_answer and not stop.is_set():
                raise ValueError("The local photo model returned no answer. Please try again.")
            yield _line({"type": "done", "reply": final_answer, "interrupted": not finished, "route": route})
            return
        if files:
            # Shared files: answer from their contents; never an action or command path.
            from core.api.chat_files import stream_with_files
            route = "files"
            yield _line({"type": "route", "route": route})
            generator = stream_with_files(_brain(authorize), message, files, stop)
            for event in generator:
                if stop.is_set():
                    break
                if event["type"] == "text":
                    text = think.feed(event["text"])
                    if text:
                        parts.append(text)
                        yield _line({"type": "delta", "text": text})
                elif event["type"] == "final":
                    finished = True
                    final_answer = "".join(parts).strip()
            if finished:
                _conversation_hooks("record_reply")
                yield _line({"type": "done", "reply": final_answer, "interrupted": False, "route": route})
                return
            final_answer = "".join(parts).strip()
            yield _line({"type": "done", "reply": final_answer, "interrupted": True, "route": route})
            return
        from core.assistant_platform.conversation import read_or_start, prepare as prepare_platform
        platform_reply = read_or_start(message,authorize)
        platform_action = None if platform_reply is not None else prepare_platform(message,authorize)
        from core.assistant_service import recall_memory
        from core.personal_memory import parse_memory_request
        memory_request = parse_memory_request(message)
        try:
            recalled = recall_memory(message, authorize)
        except PermissionError:
            recalled = "Personal memory is unavailable with the current permissions."
        if recalled is not None:
            _prepare(message, conversation_id)  # A different request clears any calendar draft.
        action = {"reply":platform_reply} if platform_reply is not None else {"reply": recalled} if recalled is not None else _prepare(message, conversation_id)
        if action is None: action=platform_action
        if action is not None:
            route = "personal_memory" if memory_request else "action_proposal"
            yield _line({"type": "route", "route": route})
            if stop.is_set():
                yield _line({"type": "done", "reply": "", "interrupted": True, "route": route})
                return
            answer = str(action["reply"])
            # Save only the proposal/clarification, never an invented execution
            # result. A memory failure must not prevent reviewing the request.
            if not memory_request:
                try:
                    _brain().remember_exchange(question=message, answer=answer, route=route)
                except Exception:
                    pass
            yield _line({"type": "delta", "text": answer})
            if not stop.is_set() and action.get("proposal") is not None:
                yield _line({"type": "proposal", "proposal": action["proposal"]})
            _conversation_hooks("record_reply")
            yield _line({"type": "done", "reply": answer, "interrupted": stop.is_set(), "route": route})
            return
        brain = _brain(authorize)
        generator = brain.stream_ask(message, remember=True)
        for event in generator:
            if stop.is_set():
                break
            kind = event.get("type")
            if kind == "route":
                route = str(event.get("route") or route)
                yield _line({"type": "route", "route": route})
            elif kind == "text":
                text = think.feed(str(event.get("text") or ""))
                if text:
                    parts.append(text)
                    yield _line({"type": "delta", "text": text})
            elif kind == "final":
                finished = True
                final_answer = "".join(parts).strip() or think.feed(str(event.get("answer") or "")).strip()
    except Exception as error:  # Ollama down, model missing, etc.
        failure = str(error).splitlines()[0][:300] if str(error) else type(error).__name__
    finally:
        if generator is not None:
            try:
                generator.close()  # closes the Ollama connection, so it stops generating
            except Exception:
                pass
        with _ACTIVE_LOCK:
            _ACTIVE.pop(request_id, None)

    partial = "".join(parts).strip()
    if not finished and partial and route != "photo":
        # Interrupted: keep what was said so the next turn has the context.
        try:
            _brain().remember_exchange(question=message, answer=partial + " …", route=route)
        except Exception:
            pass
    if partial or finished:
        _conversation_hooks("record_reply")
    if failure and not partial:
        yield _line({"type": "error", "detail": f"ZÆNIA's brain didn't answer: {failure}"})
        return
    yield _line({
        "type": "done",
        "reply": final_answer if finished else partial,
        "interrupted": not finished,
        "route": route,
    })
