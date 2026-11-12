"""ZAE puts what she just made into a tab herself: "add it to my fitness tab as a training plan".

Takes her last reply in the conversation (and the link Grey shared with it, if
any) and saves it as a real record:
- Fitness & Health > Training plans (a plan with its steps parsed out),
- Workbench > Projects,
- Notes.
The reply says exactly what was saved and where, and the tab opens. If there's
nothing to save, she says so; she never claims a save that didn't happen.
"""
from __future__ import annotations

import re
from typing import Any, Callable

_ADD = re.compile(
    r"^\s*(?:zae[,\s]+)?(?:please\s+|can you\s+|could you\s+)?(?:add|save|put|store|log|move|send|copy)\s+"
    r"(?:it|that|this|the\s+(?:plan|program|programme|workout|routine|answer|list|idea|summary)|that\s+(?:plan|program|workout|routine|answer|list))\s+"
    r"(?:to|in|into|on|under)\s+(?:my\s+|the\s+)?(?P<where>fitness(?:\s*(?:&|and)\s*health)?|training(?:\s+plans?)?|workbench|projects?|notes?)"
    r"(?:\s+(?:tab|page|section))?(?:\s+as\s+(?:a\s+|an\s+)?(?P<as>training\s+plan|plan|project|note))?\s*[.!?]*\s*$", re.I)
_SAVE_AS = re.compile(r"^\s*(?:zae[,\s]+)?(?:please\s+)?(?:save|add|make)\s+(?:it|that|this)\s+(?:as|into)\s+(?:a\s+|an\s+|my\s+)?"
                      r"(?P<as>training\s+plan|workout\s+plan|fitness\s+plan|project|note)\s*[.!?]*\s*$", re.I)
_URL = re.compile(r"https?://[^\s<>\"')\]]+")
TABS = {"plans": ("fitness", "Fitness & Health › Training plans"), "workbench": ("workbench", "Workbench › Projects"), "notes": ("notes", "Notes")}


def parse(message: str) -> str | None:
    """'plans' | 'workbench' | 'notes' when he asks to put her last answer in a tab."""
    found = _ADD.match(str(message)) or _SAVE_AS.match(str(message))
    if not found:
        return None
    target = " ".join(filter(None, (found.groupdict().get("as"), found.groupdict().get("where")))).lower()
    if "note" in target and "plan" not in target:
        return "notes"
    if "plan" in target or "fitness" in target or "training" in target:
        return "plans"
    if "project" in target or "workbench" in target:
        return "workbench"
    return None


_NOTE_NEW = re.compile(r"^\s*(?:zae[,\s]+)?(?:please\s+)?(?:add|save|put|write|jot)\s+(?:this|that|it)(?:\s+down)?\s+(?:to|in|into)\s+(?:my\s+|the\s+)?notes?"
                       r"(?:\s+tab)?\s*(?:[:,\-–]\s*(?P<text>.+))?\s*$", re.I | re.S)
_NOTE_UPDATE = re.compile(
    r"^\s*(?:zae[,\s]+)?(?:please\s+)?(?:update|add\s+to|append\s+to)\s+(?:my\s+|the\s+)?(?P<name>.+?)\s+note\s+with\s+(?:this|that|it)\s*(?:[:,\-–]\s*(?P<text>.+))?\s*$"
    r"|^\s*(?:zae[,\s]+)?(?:please\s+)?(?:add|put|append|write)\s+(?:this|that|it)\s+(?:to|in|into)\s+(?:my\s+|the\s+)?(?P<name2>.+?)\s+note\s*(?:[:,\-–]\s*(?P<text2>.+))?\s*$",
    re.I | re.S)


# "Make a note that the mixer needs a cable", "take a note: …", "note to self …", "write down …" (Grey, 2026-10-31).
_NOTE_SAID = re.compile(r"^\s*(?:(?:hey\s+)?zae[,\s]+)?(?:please\s+)?(?:can\s+you\s+)?"
                        r"(?:(?:make|take|add|create|start|write)\s+(?:me\s+)?(?:a\s+)?(?:new\s+|quick\s+)?note|note\s+to\s+self|note|"
                        r"write\s+(?:this\s+|that\s+)?down|jot\s+(?:this\s+|that\s+)?down)\b"
                        r"\s*(?:that|to|about|saying|of)?\s*[:,\-–]?\s*(?P<text>\S.{2,})$", re.I | re.S)


def parse_note(message: str) -> dict[str, str] | None:
    """'add this to notes[: text]' → a new note; 'update <name> note with this[: text]' → add to that note."""
    text = str(message).strip()
    found = _NOTE_UPDATE.match(text)
    if found:
        name = (found.group("name") or found.group("name2") or "").strip(" \"'")
        if name and name.lower() not in ("my", "the", "a"):
            return {"action": "update", "name": name, "text": (found.group("text") or found.group("text2") or "").strip()}
    found = _NOTE_NEW.match(text)
    if found:
        return {"action": "new", "name": "", "text": (found.group("text") or "").strip()}
    found = _NOTE_SAID.match(text)
    if found and not re.match(r"^\s*(?:this|that|it)(?:\s+(?:to|in|into)\b|\s*$)", found.group("text"), re.I):
        return {"action": "new", "name": "", "text": found.group("text").strip().rstrip(".")}
    return None


# "Open the song Midnight Drive", "open my research project on GPUs", "pull up the Arc Reactor project", "show my gym note".
_OPEN = re.compile(r"^\s*(?:(?:hey\s+)?zae[,\s]+)?(?:please\s+)?(?:can\s+you\s+)?(?:open|pull\s+up|show(?:\s+me)?|bring\s+up|go\s+to)\s+"
                   r"(?:up\s+)?(?:my\s+|the\s+)?(?P<kind>song|track|music\s+project|research\s+(?:project|topic)|topic|workbench\s+project|"
                   r"project|note)\s+(?:called\s+|named\s+|on\s+|about\s+|for\s+)?[\"']?(?P<name>.+?)[\"']?[.!?]?\s*$"
                   r"|^\s*(?:(?:hey\s+)?zae[,\s]+)?(?:please\s+)?(?:open|pull\s+up|show(?:\s+me)?|bring\s+up)\s+(?:my\s+|the\s+)?[\"']?"
                   r"(?P<name2>.+?)[\"']?\s+(?P<kind2>song|track|research\s+(?:project|topic)|topic|project|note)[.!?]?\s*$", re.I)


def parse_open(message: str) -> dict[str, str] | None:
    found = _OPEN.match(str(message).strip())
    if not found:
        return None
    kind = (found.group("kind") or found.group("kind2") or "").lower()
    name = (found.group("name") or found.group("name2") or "").strip(" \"'")
    if not name or name.lower() in ("it", "that", "this", "tab", "app"):
        return None
    kind = "music" if kind in ("song", "track", "music project") else "research" if ("research" in kind or kind == "topic") \
        else "notes" if kind == "note" else "workbench" if "workbench" in kind else "project"
    return {"kind": kind, "name": name}


def _best(rows: list[dict[str, Any]], name: str, key: str = "title") -> dict[str, Any] | None:
    wanted = re.sub(r"\s+", " ", name).strip().casefold()
    for test in (lambda t: t == wanted, lambda t: t.startswith(wanted), lambda t: wanted in t,
                 lambda t: bool(set(wanted.split()) & set(t.split())) and len(set(wanted.split()) & set(t.split())) >= max(1, len(wanted.split()) // 2)):
        for row in rows:
            if test(str(row.get(key, "")).casefold()):
                return row
    return None


def open_record(request: dict[str, str], *, store: Any = None) -> dict[str, Any]:
    """Find the record he named and open its tab on it: {"reply", "tab", "focus"}; ValueError when nothing matches."""
    if store is None:
        from core.assistant_platform.service import platform
        store = platform().store
    kind, name = request["kind"], request["name"]
    tries = [kind] if kind != "project" else ["workbench", "research", "music"]
    for where in tries:
        if where == "music":
            from core.assistant_platform.personal_tools import music_overview
            row = _best(music_overview(store)["songs"], name)
            if row:
                return {"reply": f"Here's {row['title']}.", "tab": "music", "focus": row["title"]}
        elif where == "workbench":
            from core.assistant_platform.personal_tools import COLLECTIONS
            row = _best([r for r in store.list(COLLECTIONS["workbench"]) if not r.get("archived")], name)
            if row:
                return {"reply": f"Here's {row['title']}.", "tab": "workbench", "focus": row["title"]}
        elif where == "research":
            from core.research.notebook import Notebook
            row = _best(Notebook().topics(), name, "name")
            if row:
                return {"reply": f"Here's your research on {row['name']}.", "tab": "research", "focus": row["name"]}
        elif where == "notes":
            from core.assistant_platform.notes import Notes
            row = Notes(store).find(name)
            if row:
                return {"reply": f"Here's your {row['title']} note.", "tab": "notes", "focus": row["title"]}
    label = {"music": "song", "research": "research topic", "notes": "note", "workbench": "Workbench project"}.get(kind, "project")
    raise ValueError(f"I couldn't find a {label} called {name}.")


def save_note(request: dict[str, str], messages: list[dict[str, str]], *, store: Any = None, ask: Callable[[str], str] | None = None) -> dict[str, Any]:
    """Do a note request from chat: the text he gave, or her last answer when he says 'this'."""
    from core.assistant_platform.notes import Notes
    if store is None:
        from core.assistant_platform.service import platform
        store = platform().store
    content = request.get("text") or last_reply(messages)[0]
    if not content:
        raise ValueError("There's nothing to add yet. Say \"add this to notes: …\" with the text, or ask me something first.")
    notes = Notes(store)
    if request["action"] == "update":
        found = notes.find(request["name"])
        if found is None:
            note = notes.create(request["name"][:160].strip().title(), content)
            return {"reply": f"There was no \"{request['name']}\" note, so I started one with that in it.", "tab": "notes", "id": note["id"]}
        notes.append(found["id"], content)
        return {"reply": f"Added to your \"{found['title']}\" note.", "tab": "notes", "id": found["id"]}
    title = _title(content, "", ask, "Note from chat")
    note = notes.create(title, content)
    return {"reply": f"Saved to Notes as \"{title}\".", "tab": "notes", "id": note["id"], "focus": title}


def last_reply(messages: list[dict[str, str]]) -> tuple[str, str]:
    """Her last real answer and the user message before it (where a shared link would be)."""
    # The thing worth saving is her last substantial answer (a plan, a list), not a short "Done" or "I added it"
    # line after it; within her last four replies, the newest long one wins, else the newest at all.
    replies = [i for i in range(len(messages) - 1, -1, -1)
               if messages[i].get("role") == "assistant" and len(str(messages[i].get("content", "")).strip()) > 40][:4]
    if not replies:
        return "", ""
    index = next((i for i in replies if len(messages[i]["content"]) > 300 or re.search(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s", messages[i]["content"])), replies[0])
    asked = next((str(messages[e].get("content", "")) for e in range(index - 1, -1, -1) if messages[e].get("role") == "user"), "")
    return str(messages[index]["content"]).strip(), asked


_DAY = re.compile(r"^(?:\*\*)?(?P<day>(?:mon|tues|wednes|thurs|fri|satur|sun)day|day\s*\d+|week\s*\d+)\b[^:]*:?\s*(?:\*\*)?(?P<rest>.*)$", re.I)


def plan_steps(text: str) -> list[dict[str, Any]]:
    """Steps from a written plan: day headings and exercises with their sets and reps."""
    steps = []
    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s*", "", raw).replace("**", "").strip()
        if not line or len(line) > 280:
            continue
        day = _DAY.match(line)
        if day:
            steps.append({"exercise": line.rstrip(":"), "prescription": "", "done": False})
            continue
        if not raw.lstrip().startswith(("-", "*", "+", "•")) and not re.match(r"^\s*\d+[.)]", raw):
            continue
        match = re.match(r"^(?P<name>[^(:]{2,120}?)\s*(?:\((?P<p1>[^)]{1,200})\)|:\s*(?P<p2>.{1,200}))?$", line)
        if match:
            steps.append({"exercise": match.group("name").strip(" -–:"), "prescription": (match.group("p1") or match.group("p2") or "").strip(), "done": False})
        if len(steps) >= 100:
            break
    return steps


def _title(answer: str, asked: str, ask: Callable[[str], str] | None, fallback: str) -> str:
    if ask is not None:
        try:
            title = ask("Give a short title (3 to 6 words, no quotes, no punctuation at the end) for this:\n\n" + answer[:1500])
            title = " ".join(title.strip().strip('"\'').splitlines()[0].split())[:80] if title.strip() else ""
            if 2 < len(title) <= 80:
                return title
        except Exception:
            pass
    heading = next((l.strip("#* ") for l in answer.splitlines() if l.strip().startswith(("#", "**")) and 3 < len(l.strip("#* ")) < 80), "")
    return heading or fallback


def save(target: str, messages: list[dict[str, str]], *, store: Any = None, ask: Callable[[str], str] | None = None) -> dict[str, Any]:
    """Save her last answer into the tab. Returns {reply, tab, id} or raises ValueError with a plain reason."""
    answer, asked = last_reply(messages)
    if not answer:
        raise ValueError("There's nothing from me to save yet. Ask me for the plan first, then say \"add it to my fitness tab\".")
    if store is None:
        from core.assistant_platform.service import platform
        store = platform().store
    links = _URL.findall(asked)
    if target == "plans":
        from core.assistant_platform.personal_tools import PersonalTools
        title = _title(answer, asked, ask, "Training plan")
        steps = plan_steps(answer)
        record = PersonalTools(store).save("plans", {
            "title": title, "sourceUrl": links[0] if links else "", "sourceText": answer[:30000],
            "sourceName": "Made by ZAE in chat", "schedule": "", "steps": steps, "sessions": []})
        detail = f" with {len(steps)} steps" if steps else ""
    elif target == "workbench":
        from core.assistant_platform.personal_tools import PersonalTools
        title = _title(answer, asked, ask, "Idea from chat")
        record = PersonalTools(store).save("workbench", {"title": title, "body": answer[:30000], "blueprint": links[0] if links else ""})
        detail = ""
    elif target == "notes":
        from core.assistant_platform.notes import Notes
        title = _title(answer, asked, ask, "From ZAE")
        record = Notes(store).save({"title": title[:160], "body": (answer + (f"\n\nSource: {links[0]}" if links else ""))[:30000]})
        detail = ""
    else:
        raise ValueError("I can save to Training plans, Workbench projects or Notes.")
    tab, place = TABS[target]
    return {"reply": f"Saved to {place} as \"{title}\"{detail}. It's open now.", "tab": tab, "id": record.get("id")}
