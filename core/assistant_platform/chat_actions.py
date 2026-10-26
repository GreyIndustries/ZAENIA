"""Doing things in ZAE's tabs from chat: everything the tabs can do, said in plain words.

Tasks, events, reminders, notes, plans, research and watch topics already have
their own chat handlers. This module covers the rest:
- Fitness: log food (her estimate when calories aren't given, labelled as one),
  exercise, weight / body fat / steps, cardio, sets, and checking off today's
  workout.
- Tasks: mark done, change priority or deadline.
- Reminders: cancel one.
- Workbench and Music: new project, change its stage.
- Research: translate text, find books in the Library.
- Training program: add a source link, improve the program from its sources.
- Suggestions: think of ideas; Code Doctor: check ZAE's code.

A cheap word check decides whether to ask her brain at all; the brain then
picks one action and its details as JSON from the catalogue below (it can only
pick from it). Every action is reversible from its tab (nothing is deleted
except a reminder he names), and the reply says exactly what was done.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Callable

ACTIONS = {
    "food.log": "log food he ate: {\"name\": str, \"calories\": number or null, \"protein\": number or null, \"fiber\": number or null}",
    "exercise.log": "log an exercise session (not running/walking distance): {\"name\": str, \"minutes\": number, \"calories\": number or null}",
    "body.log": "log body numbers for today: {\"weightLb\": number or null, \"bodyFat\": number or null, \"steps\": number or null}",
    "cardio.log": "log cardio: {\"type\": run|walk|hike|cycle|swim|row|elliptical|stairs|hiit|jump rope|sport|other, \"miles\": number or null, \"minutes\": number or null}",
    "workout.done": "check off exercises from today's workout: {\"exercises\": [str] or [\"all\"]}",
    "set.log": "log lifting sets: {\"exercise\": str, \"sets\": number, \"reps\": number, \"weightLb\": number or null}",
    "task.complete": "mark a task done: {\"task\": str}",
    "task.update": "change a task: {\"task\": str, \"priority\": Critical|High|Normal|Low or null, \"deadline\": \"YYYY-MM-DD\" or null}",
    "reminder.cancel": "cancel a reminder: {\"text\": str}",
    "project.create": "new Workbench project: {\"title\": str, \"subject\": Science|Biology|Tech|Bio tech|Bio chem|Nuclear physics|Nano technology|AI or null}",
    "project.stage": "move a Workbench project to a stage: {\"project\": str, \"stage\": Idea|Research|Prototype|Testing|Complete}",
    "music.create": "new Music project (a song or track): {\"title\": str}",
    "music.stage": "move a Music project to a stage: {\"project\": str, \"stage\": Idea|Writing|Recording|Mixing|Mastering|Released}",
    "translate": "translate text: {\"text\": str, \"to\": language}",
    "library.search": "find books in the Library: {\"query\": str}",
    "program.source": "add a link to the Training program's sources: {\"url\": str}",
    "program.improve": "improve the training program from its sources: {}",
    "suggestions.think": "think of suggestions: {\"focus\": all|day|system}",
    "codedoctor.scan": "check ZAE's own code for problems: {}",
}

_VERBS = re.compile(r"\b(log|logged|add|track|record|mark|check off|finished|did|done|ate|eaten|had|drank|weigh|weighed|walked|ran|run|"
                    r"biked|cycled|swam|rowed|hiked|complete|completed|change|move|set|make|start|create|new|cancel|delete|remove|"
                    r"translate|find|look for|improve|think of|suggest|scan|check)\b", re.I)
_TOPIC = re.compile(r"\b(calorie|kcal|protein|fiber|meal|breakfast|lunch|dinner|snack|food|ate|eat|weigh|weight|body ?fat|steps?|"
                    r"miles?|mi\b|km|minutes?|mins?|run|ran|walk|bike|cycle|swim|row|hike|cardio|workout|exercise|sets?|reps?|"
                    r"bench|squat|deadlift|curl|press|pull-?ups?|push-?ups?|dips|plank|task|todo|to-do|reminder|project|workbench|"
                    r"song|track|beat|music|stage|translate|book|library|program|source|suggestion|idea|code doctor|my code|your code|"
                    r"prototype|testing|mixing|mastering|recording|released|writing|lunge|row|raise|crunch|twist|burpee)(?:e?s)?\b", re.I)
_QUESTION = re.compile(r"^\s*(what|how|why|when|where|who|which|is|are|do|does|can|could|should|would|will)\b", re.I)


def maybe(message: str) -> bool:
    """Worth asking her brain? An instruction about something a tab does, not a question."""
    text = str(message or "").strip()
    if len(text) < 6 or len(text) > 600 or (_QUESTION.match(text) and not re.match(r"^\s*(can|could|will) you\b", text, re.I)):
        return False
    return bool(_VERBS.search(text) and _TOPIC.search(text))


def classify(message: str, ask: Callable[[str], str]) -> dict[str, Any] | None:
    catalogue = "\n".join(f"- {name}: {about}" for name, about in ACTIONS.items())
    reply = ask(
        "Task: turn Grey's message into ONE app action, as JSON. Pick only from this list; if the message isn't asking for "
        "one of these (for example it's a question, chat, or creating a task/event/reminder/note), reply {\"action\": \"none\"}.\n"
        f"{catalogue}\n\nToday is {date.today().isoformat()}. For food with no calories given, estimate calories and protein "
        "for a normal portion and add \"estimated\": true. Reply with JSON only: {\"action\": \"name\", \"args\": {...}}\n\n"
        f"MESSAGE: {message}")
    match = re.search(r"\{.*\}", reply, re.S)
    try:
        data = json.loads(match.group(0) if match else reply)
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict) or data.get("action") not in ACTIONS:
        return None
    args = data.get("args") if isinstance(data.get("args"), dict) else {}
    if data.get("estimated"):
        args["estimated"] = True
    return {"action": data["action"], "args": args}


def _num(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", ""))
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def _best(name: str, items: list[dict[str, Any]], key: str = "title") -> dict[str, Any] | None:
    wanted = str(name or "").strip().casefold()
    if not wanted:
        return None
    for test in (lambda t: t == wanted, lambda t: t.startswith(wanted), lambda t: wanted in t,
                 lambda t: all(word in t for word in wanted.split())):
        for item in items:
            if test(str(item.get(key, "")).casefold()):
                return item
    return None


def run(action: dict[str, Any], *, store: Any = None, ask: Callable[[str], str] | None = None) -> dict[str, Any]:
    """Do it. Returns {"reply": what was done, "tab": tab to open or ""}; ValueError with a plain reason otherwise."""
    name, args = action["action"], action.get("args") or {}
    today = date.today().isoformat()
    if store is None and name.split(".")[0] in ("food", "exercise", "project", "music", "body", "cardio", "workout", "set", "program"):
        from core.assistant_platform.service import platform
        store = platform().store

    if name == "food.log":
        from core.assistant_platform.personal_tools import PersonalTools
        food = str(args.get("name") or "").strip()[:160]
        calories = _num(args.get("calories"))
        if food and calories is None and ask is not None:
            # No calories given: her estimate for a normal portion, labelled as an estimate.
            guess = re.search(r"\{.*\}", ask("Task: estimate nutrition, as JSON. For one normal portion of: " + food +
                                             "\nReply with JSON only: {\"calories\": number, \"protein\": number, \"fiber\": number}") or "", re.S)
            try:
                numbers = json.loads(guess.group(0)) if guess else {}
            except ValueError:
                numbers = {}
            calories = _num(numbers.get("calories"))
            args = {**args, "protein": args.get("protein") or numbers.get("protein"), "fiber": args.get("fiber") or numbers.get("fiber"), "estimated": True}
        if not food or calories is None:
            raise ValueError("Tell me what you ate and roughly how much, like \"log chicken and rice, 600 calories\".")
        estimated = bool(args.get("estimated"))
        PersonalTools(store).save("food", {"title": food, "date": today, "calories": calories, "protein": _num(args.get("protein")) or 0,
                                           "fiber": _num(args.get("fiber")) or 0,
                                           "source": "ZAE's estimate (check the label)" if estimated else "Told ZAE in chat"})
        extra = f", {(_num(args.get('protein')) or 0):g} g protein" if _num(args.get("protein")) else ""
        return {"reply": f"Logged {food}: {calories:g} kcal{extra}{' (my estimate; fix it in Fitness if the label says otherwise)' if estimated else ''}.", "tab": "fitness"}

    if name == "exercise.log":
        from core.assistant_platform.personal_tools import PersonalTools
        title = str(args.get("name") or "").strip()[:160]
        minutes = _num(args.get("minutes"))
        if not title or not minutes:
            raise ValueError("Tell me the exercise and how long, like \"log 45 minutes of basketball\".")
        calories = _num(args.get("calories"))
        if calories is None:
            from core.assistant_platform.training import training
            weight = training().load()["profile"].get("weightLb") or 180
            calories = round(4.0 * weight * 0.4536 * minutes / 60)
        PersonalTools(store).save("exercise", {"title": title, "date": today, "minutes": minutes, "calories": calories,
                                               "source": "Manual estimate", "notes": "Logged from chat"})
        return {"reply": f"Logged {title}, {minutes:g} min, about {calories:g} kcal.", "tab": "fitness"}

    if name in ("body.log", "cardio.log", "workout.done", "set.log"):
        from core.assistant_platform.training import day_view, training
        tracker = training()
        entry = tracker.load()["days"].get(today, {})
        if name == "body.log":
            changes = {k: _num(args.get(k)) for k in ("weightLb", "bodyFat", "steps") if _num(args.get(k)) is not None}
            if not changes:
                raise ValueError("Tell me the number, like \"I weigh 194\" or \"log 8,000 steps\".")
            tracker.log_day(today, changes)
            said = ", ".join(f"{'weight' if k == 'weightLb' else 'body fat' if k == 'bodyFat' else 'steps'} {v:g}{' lb' if k == 'weightLb' else '%' if k == 'bodyFat' else ''}"
                             for k, v in changes.items())
            return {"reply": f"Logged {said} for today.", "tab": "fitness"}
        if name == "cardio.log":
            miles, minutes = _num(args.get("miles")), _num(args.get("minutes"))
            if not miles and not minutes:
                raise ValueError("Tell me how far or how long, like \"I ran 2 miles\".")
            session = {"type": str(args.get("type") or "other"), "miles": miles or 0, "minutes": minutes or 0}
            tracker.log_day(today, {"cardio": (entry.get("cardio") or []) + [session]})
            return {"reply": f"Logged {session['type']}{f' {miles:g} mi' if miles else ''}{f' in {minutes:g} min' if minutes else ''}.", "tab": "fitness"}
        planned = day_view(today, store)["workout"]["exercises"]
        if name == "workout.done":
            wanted = [str(w) for w in (args.get("exercises") or [])]
            if not planned:
                raise ValueError("There's no workout planned for today in your Training program.")
            chosen = planned if any(w.lower() == "all" for w in wanted) else [e for w in wanted if (e := _best(w, planned, "exercise"))]
            if not chosen:
                raise ValueError("I couldn't match that to today's workout: " + ", ".join(e["exercise"] for e in planned) + ".")
            done = {**(entry.get("done") or {}), **{e["exercise"]: True for e in chosen}}
            tracker.log_day(today, {"done": done})
            left = [e["exercise"] for e in planned if not done.get(e["exercise"])]
            return {"reply": f"Checked off {', '.join(e['exercise'] for e in chosen)}." + (f" Left today: {', '.join(left)}." if left else " That's today's workout done."), "tab": "fitness"}
        exercise = str(args.get("exercise") or "").strip()
        reps = _num(args.get("reps"))
        if not exercise or not reps:
            raise ValueError("Tell me the lift and reps, like \"bench 3 sets of 8 at 185\".")
        match = _best(exercise, planned, "exercise")
        exercise = match["exercise"] if match else exercise[:300].title()
        sets = int(_num(args.get("sets")) or 1)
        weight = _num(args.get("weightLb")) or 0
        rows = (entry.get("sets") or []) + [{"exercise": exercise, "reps": int(reps), "weightLb": weight}] * min(sets, 20)
        tracker.log_day(today, {"sets": rows, "done": {**(entry.get("done") or {}), exercise: True}})
        return {"reply": f"Logged {exercise}: {sets} × {int(reps)}{f' at {weight:g} lb' if weight else ''}.", "tab": "fitness"}

    if name in ("task.complete", "task.update"):
        from core.api import ui_tasks
        tasks = [t for t in ui_tasks.list_tasks() if not t.get("archived")]
        wanted = re.sub(r"\b(the|my|task|to-?do)\b", " ", str(args.get("task") or ""), flags=re.I).strip()
        task = _best(wanted, [t for t in tasks if t.get("status") != "Completed"] or tasks)
        if task is None:
            raise ValueError(f"I couldn't find a task called \"{args.get('task')}\".")
        if name == "task.complete":
            ui_tasks.update_task(task["id"], {"status": "Completed"})
            return {"reply": f"Marked \"{task['title']}\" done.", "tab": "tasks"}
        patch = {k: args[k] for k in ("priority", "deadline") if args.get(k)}
        if not patch:
            raise ValueError("Tell me what to change: the priority or the deadline.")
        ui_tasks.update_task(task["id"], patch)
        return {"reply": f"Updated \"{task['title']}\": " + ", ".join(f"{k} {v}" for k, v in patch.items()) + ".", "tab": "tasks"}

    if name == "reminder.cancel":
        from core.assistant_platform.reminders import reminders
        found = _best(args.get("text"), reminders().list(), "text")
        if found is None:
            raise ValueError(f"I couldn't find a reminder about \"{args.get('text')}\".")
        reminders().delete(found["id"])
        return {"reply": f"Cancelled the reminder: {found['text']}.", "tab": "tasks"}

    if name in ("project.create", "music.create"):
        from core.assistant_platform.personal_tools import CATEGORIES, PersonalTools
        title = str(args.get("title") or "").strip()[:160]
        if not title:
            raise ValueError("Give the project a name.")
        if name == "project.create":
            subject = args.get("subject") if args.get("subject") in CATEGORIES else "Tech"
            PersonalTools(store).save("workbench", {"title": title, "category": subject})
            return {"reply": f"Started a Workbench project, \"{title}\" ({subject}).", "tab": "workbench"}
        PersonalTools(store).save("music", {"title": title})
        return {"reply": f"Started a Music project, \"{title}\".", "tab": "music"}

    if name in ("project.stage", "music.stage"):
        from core.assistant_platform.personal_tools import PersonalTools
        collection, field, tab = ("workbench", "status", "workbench") if name == "project.stage" else ("music", "stage", "music")
        kind = "workbench" if collection == "workbench" else "music"
        rows = [r for r in store.list(kind) if not r.get("archived")]
        row = _best(args.get("project"), rows)
        if row is None:
            raise ValueError(f"I couldn't find a project called \"{args.get('project')}\".")
        record = {k: v for k, v in row.items() if k not in ("id", "revision", "updatedAt", "createdAt")}
        record[field] = str(args.get("stage") or "")
        PersonalTools(store).save(collection, record, row["id"], row["revision"])
        return {"reply": f"Moved \"{row['title']}\" to {record[field]}.", "tab": tab}

    if name == "translate":
        from core.research.analyze import LANGUAGES, translate
        target = next((l for l in LANGUAGES if l.lower() == str(args.get("to") or "English").lower()), None)
        if not target or not str(args.get("text") or "").strip():
            raise ValueError("Tell me the text and the language, like \"translate good morning to Spanish\".")
        return {"reply": translate(str(args["text"]), target, run=ask)["translation"] if ask else translate(str(args["text"]), target)["translation"], "tab": ""}

    if name == "library.search":
        from core.research import library
        found = library.search(str(args.get("query") or ""))
        books = found.get("results", [])[:5]
        if not books:
            return {"reply": "I didn't find free copies of that.", "tab": "research"}
        return {"reply": "Found in the Library: " + "; ".join(f"{b['title']} ({b.get('author') or 'unknown'}, {b.get('access') or b.get('source')})" for b in books)
                + ". They're in Research › The Library.", "tab": "research"}

    if name == "program.source":
        from core.assistant_platform.training import training
        url = str(args.get("url") or "").strip()
        if not url.startswith("http"):
            raise ValueError("Paste the link.")
        source = training().add_source(url, ask=ask)
        return {"reply": f"Added {source['title'] or url} to your Training program's sources.", "tab": "fitness"}

    if name == "program.improve":
        from core.assistant_platform.training import improve_program
        improve_program(store, ask)
        return {"reply": "I wrote an improved program from your sources and made it active. Your old plan is kept.", "tab": "fitness"}

    if name == "suggestions.think":
        from core.assistant_platform.suggestions import suggestions
        focus = args.get("focus") if args.get("focus") in ("all", "day", "system") else "all"
        fresh = suggestions().think(ask, focus=focus)
        return {"reply": (f"{len(fresh)} new idea{'s' if len(fresh) != 1 else ''}: " + "; ".join(s["title"] for s in fresh) + ". They're in Code Doctor › Suggestions.")
                if fresh else "Nothing new to suggest right now.", "tab": "codedoctor"}

    if name == "codedoctor.scan":
        from core.assistant_platform.code_doctor import scan
        result = scan("")
        findings = result.get("findings") or []
        return {"reply": f"Checked {result.get('totals', {}).get('files', 0)} files: {len(findings)} thing{'s' if len(findings) != 1 else ''} to look at."
                + (" They're in Code Doctor." if findings else ""), "tab": "codedoctor"}

    raise ValueError("I can't do that one from chat yet.")
