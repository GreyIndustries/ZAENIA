"""ZAE's reply to Grey's wake-up calls and sleep phrases, built from the situation.

The app sends what it knows (time, how long Calm view was on, what's next, tasks, food, news, security, jobs).
Her local brain writes one short JARVIS-style line from only those facts, as a statement or a question; if it
is slow or unavailable, a written line built from the same facts is used. The reply also names which dashboard
card to bring forward ("focus"), so the dashboard matches what she said. She never claims human feelings.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

FOCI = ("tasks", "calendar", "fitness", "news", "system")
WAKE_CALLS = ("Wake up sleepy, we have work to do", "Sleeping on the job?", "The boss is here",
              "Zae, you're still there?", "The day is not yet over")
SLEEP_PHRASES = ("Take everything to the background", "I'm going to sleep",
                 "Let's put a pin in this and continue tomorrow", "Calm view")


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def focus_for(kind: str, s: dict[str, Any]) -> str:
    """The dashboard card that matches the moment."""
    if kind == "sleep":
        return "system"
    if (_num(s.get("overdue")) or 0) > 0:
        return "tasks"
    hours_to_next = _num((s.get("next") or {}).get("hoursAway"))
    if hours_to_next is not None and hours_to_next <= 12:
        return "calendar"
    if (_num(s.get("kcalLeft")) or 0) > 500 and (_num(s.get("hour")) or 12) < 21:
        return "fitness"
    if (_num(s.get("dueToday")) or 0) > 0:
        return "tasks"
    if (_num(s.get("news")) or 0) > 0:
        return "news"
    return "system"


def facts(kind: str, s: dict[str, Any]) -> list[str]:
    out = []
    hour = _num(s.get("hour"))
    if hour is not None:
        out.append(f"Local time: {int(hour):02d}:{int(_num(s.get('minute')) or 0):02d}.")
    calm = _num(s.get("calmMinutes"))
    if kind == "wake" and calm is not None:
        out.append(f"ZAE was in Calm view for {int(calm)} minutes.")
    nxt = s.get("next") or {}
    if nxt.get("title"):
        out.append(f"Next on the calendar: {str(nxt['title'])[:120]} {str(nxt.get('when', ''))[:40]}.".replace(" .", "."))
    for key, label in (("dueToday", "tasks due today"), ("overdue", "overdue tasks")):
        if _num(s.get(key)) is not None:
            out.append(f"{int(_num(s.get(key)))} {label}.")
    if _num(s.get("kcalLeft")) is not None:
        out.append(f"{int(_num(s.get('kcalLeft')))} calories left today.")
    if _num(s.get("news")) is not None:
        out.append(f"{int(_num(s.get('news')))} new tech stories.")
    if _num(s.get("security")) is not None:
        out.append(f"Security score {int(_num(s.get('security')))}.")
    for key, label in ((("finished", "Finished while calm"),) if kind == "wake" else ()) + (("running", "Still running"),):
        items = [str(x)[:80] for x in (s.get(key) or [])][:3]
        if items:
            out.append(f"{label}: {', '.join(items)}.")
    if kind == "sleep" and s.get("section"):
        out.append(f"Grey was in the {str(s['section'])[:30]} tab.")
    return out


def fallback_line(kind: str, phrase_id: int, s: dict[str, Any]) -> str:
    """A written reply from the same facts, for when the brain is slow or off."""
    hour = int(_num(s.get("hour")) or 12)
    part = "morning" if 4 <= hour < 12 else "afternoon" if hour < 18 else "evening"
    nxt = s.get("next") or {}
    overdue, due = int(_num(s.get("overdue")) or 0), int(_num(s.get("dueToday")) or 0)
    kcal = _num(s.get("kcalLeft"))
    finished = [str(x) for x in (s.get("finished") or [])][:2]
    if kind == "sleep":
        running = [str(x) for x in (s.get("running") or [])][:2]
        keep = f" I'll keep {', '.join(running)} going in the background." if running else ""
        return {1: f"Moving everything to the background.{keep}",
                2: f"Good night, Grey.{keep} I'll have the morning ready.",
                3: f"Pinned. Your place is saved and we'll pick it up tomorrow.{keep}",
                4: f"Going calm.{keep}"}.get(phrase_id, f"Going calm.{keep}")
    if overdue:
        news = f"{overdue} task{'s' if overdue > 1 else ''} overdue"
    elif nxt.get("title"):
        news = f"{nxt['title']} is next{(' ' + str(nxt.get('when'))) if nxt.get('when') else ''}"
    elif due:
        news = f"{due} task{'s' if due > 1 else ''} due today"
    elif kcal is not None and kcal > 500:
        news = f"{int(kcal)} calories still to plan"
    else:
        news = "nothing urgent waiting"
    done = f" While you were away I finished {', '.join(finished)}." if finished else ""
    return {1: f"Awake and ready. {news[0].upper() + news[1:]}.{done} Where do you want to start?",
            2: f"Never fully asleep.{done} {news[0].upper() + news[1:]}.",
            3: f"Good {part}, boss. {news[0].upper() + news[1:]}.{done}",
            4: f"Always. {news[0].upper() + news[1:]}.{done}",
            5: f"Agreed, there's still time. {news[0].upper() + news[1:]}.{done} What's the plan?"}.get(phrase_id, f"I'm here. {news}.")


def prompt(kind: str, phrase: str, s: dict[str, Any]) -> str:
    lines = "\n".join(f"- {fact}" for fact in facts(kind, s)) or "- (no details available)"
    task = ("Grey just woke you from Calm view with this wake-up call. Answer in one or two short sentences, in a dry, "
            "capable, JARVIS-like tone, as a statement or a question that fits his words and the moment. Mention the "
            "single most useful fact.") if kind == "wake" else (
            "Grey just said this sleep phrase; you're switching to Calm view and moving running work to the background. "
            "Answer in one short sentence that fits his words and the moment. Don't promise any action other than keeping "
            "the running work going in the background.")
    return (f"You are ZAE, Grey's local assistant. {task} Use only the facts below, never invent any. Never claim human "
            f"feelings or experiences. No emoji, no lists, under 35 words.\n\nGrey said: \"{phrase[:120]}\"\nFacts:\n{lines}")


def compose(kind: str, phrase_id: int, situation: dict[str, Any], *, run: Callable[[str], str] | None = None,
            timeout: float = 4.0) -> dict[str, Any]:
    if kind not in ("wake", "sleep"):
        raise ValueError("Unknown phrase kind.")
    phrases = WAKE_CALLS if kind == "wake" else SLEEP_PHRASES
    phrase = phrases[max(1, min(phrase_id, len(phrases))) - 1]
    line = fallback_line(kind, phrase_id, situation)
    source = "written"
    if run is not None:
        box: dict[str, str] = {}
        worker = threading.Thread(target=lambda: box.setdefault("text", run(prompt(kind, phrase, situation))), daemon=True)
        worker.start()
        worker.join(timeout)
        text = " ".join(str(box.get("text", "")).replace("*", "").split()).strip("\"'“” ")
        if 8 <= len(text) <= 280:
            line, source = text, "brain"
    return {"kind": kind, "phrase": phrase, "line": line, "focus": focus_in(line, kind, situation), "source": source}


def focus_in(line: str, kind: str, situation: dict[str, Any]) -> str:
    """The card that matches what she actually said (so the dashboard follows her words), else what matters most."""
    text = line.lower()
    title = str((situation.get("next") or {}).get("title") or "").lower()
    if kind == "wake":
        if "calorie" in text or "protein" in text or "kcal" in text:
            return "fitness"
        if "overdue" in text or "task" in text:
            return "tasks"
        if (title and title[:12] in text) or "calendar" in text:
            return "calendar"
        if "news" in text or "stor" in text:
            return "news"
    return focus_for(kind, situation)
