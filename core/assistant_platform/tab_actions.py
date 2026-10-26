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


def last_reply(messages: list[dict[str, str]]) -> tuple[str, str]:
    """Her last real answer and the user message before it (where a shared link would be)."""
    answer, asked = "", ""
    for index in range(len(messages) - 1, -1, -1):
        item = messages[index]
        if item.get("role") == "assistant" and len(str(item.get("content", "")).strip()) > 40:
            answer = str(item["content"]).strip()
            for earlier in range(index - 1, -1, -1):
                if messages[earlier].get("role") == "user":
                    asked = str(messages[earlier].get("content", ""))
                    break
            break
    return answer, asked


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
