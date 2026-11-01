"""Doing things in ZAE's tabs from chat: everything the tabs can do, said in plain words.

Tasks, events, reminders, notes, plans, research and watch topics already have
their own chat handlers. This module covers the rest:
  - Fitness: open a sourced, review-before-save meal workflow; log food with explicitly supplied nutrition,
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
    "workout.actual": "Grey did a different workout than planned today, or describes everything done today (several exercises, a test, a class, a circuit): {}",
    "workout.plan": "go back to today's planned workout (undo the different workout logged instead): {}",
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
# Creating tasks, events, reminders and notes has its own handlers (they show a proposal first); never route it here.
_CREATE_OWN = re.compile(r"^\s*(?:please\s+|can you\s+|could you\s+)?(?:add|create|make|new|set up|schedule|put)\s+(?:me\s+)?(?:a\s+|an\s+)?(?:new\s+)?"
                         r"(?:task|todo|to-do|event|appointment|meeting|reminder|note)\b|^\s*remind me\b", re.I)
_QUESTION = re.compile(r"^\s*(what|how|why|when|where|who|which|is|are|do|does|can|could|should|would|will)\b", re.I)


_NUTRIENTS = {
    "calories": r"kcals?|cals?|calories|calorie",
    "protein": r"protein",
    "fiber": r"fib(?:er|re)",
    "carbs": r"carbs?|carbohydrates?",
    "saturatedFat": r"sat(?:urated)?\.?\s*fats?",
    "fat": r"fats?",
    "sugars": r"sugars?",
    "sodiumMg": r"sodium|salt",
    "cholesterolMg": r"cholesterol|chol",
}
# Every nutrient a food record can carry (Grey, 2026-11-01: carbs, fat, sugars and cholesterol supported fully).
_FULL = ("protein", "fiber", "carbs", "fat", "saturatedFat", "sugars", "sodiumMg", "cholesterolMg")
_GENERIC_FOOD = re.compile(r"^(?:food|foods|meal|meals|today|unknown|none|n/?a|snack|fitness|health|fitness\s*(?:&|and)\s*health|nutrition|"
                           r"food\s*log|log|logged\s+in\s+chat|my\s+food|calories|macros)$", re.I)


def fill_from_catalog(food: str, record: dict[str, Any], stated: dict[str, float], *, search=None) -> str | None:
    """A named food logged with only some numbers: the nutrients Grey didn't give come from the closest USDA FoodData
    Central match, scaled so its calories (or protein) equal his. Returns the match's name, or None when nothing fits.
    His own numbers are never changed."""
    if not food or _GENERIC_FOOD.match(food.strip()):
        return None
    missing = [k for k in _FULL if k not in stated]
    if not missing:
        return None
    try:
        if search is None:
            from core.assistant_platform.nutrition import search_food as search
        matches = (search(food) or {}).get("matches") or []
    except Exception:
        return None
    for match in matches:
        n = match.get("nutrients") or {}
        for ref in ("calories", "protein", "carbs"):
            mine, theirs = (record.get(ref) if ref == "calories" else stated.get(ref)), n.get(ref)
            if mine and theirs:
                factor = float(mine) / float(theirs)
                break
        else:
            continue
        if not 0.05 <= factor <= 20:          # a match this far off isn't the same food
            continue
        for key in missing:
            if n.get(key) is not None:
                record[key] = round(float(n[key]) * factor, 1)
        return str(match.get("title") or "USDA match")
    return None


def stated_nutrition(text: str) -> dict[str, float]:
    """Nutrition numbers Grey states ("150g protein", "2,100 cal", "carbs 220", "fiber: 30 grams"). Only what's said, never estimated."""
    found: dict[str, float] = {}
    text = str(text or "")
    number = r"(\d[\d,]*(?:\.\d+)?)\s*(?:g|grams?|mg|k?cals?|kcal|calories)?"
    for key, words in _NUTRIENTS.items():
        guard = r"(?<!saturated )(?<!sat )(?<!sat\. )" if key == "fat" else ""
        for pattern in (number + r"\s*(?:of\s+)?" + guard + r"(?:" + words + r")\b",
                        r"\b" + guard + r"(?:" + words + r")\s*(?:[:=-]|was|of|is|at)?\s*" + number):
            match = re.search(pattern, text, re.I)
            if match:
                found[key] = float(match.group(1).replace(",", ""))
                break
    return found


FITNESS_ACTIONS = ("food.log", "exercise.log", "body.log", "cardio.log", "workout.done", "set.log", "workout.actual", "workout.plan")


def fitness_quick_log(message: str, ask: Callable[[str], str]) -> dict[str, Any]:
    """The Fitness tab's "log anything" box: only fitness actions, and food only with numbers you state."""
    text = str(message or "").strip()
    if not text:
        raise ValueError("Type what to log, like \"weighed 195.4\" or \"ran 2 miles in 16:30\".")
    action = classify(text[:4000], ask)
    if action is None or action["action"] not in FITNESS_ACTIONS:
        raise ValueError("I couldn't tell what to log. Try \"weighed 195.4\", \"8,000 steps\", \"ran 2 miles in 16:30\" or \"150g protein, 2,100 cal\".")
    if action["action"] == "food.log" and not stated_nutrition(text):
        raise ValueError("For food without numbers, use the Log sub-tab so the portions and sources can be checked first.")
    action["args"]["text"] = text
    return run(action, ask=ask)


def maybe(message: str) -> bool:
    """Worth asking her brain? An instruction about something a tab does, not a question."""
    text = str(message or "").strip()
    if len(text) < 6 or len(text) > 4000 or (_QUESTION.match(text) and not re.match(r"^\s*(can|could|will) you\b", text, re.I)):
        return False
    if _CREATE_OWN.search(text):
        return False
    return bool(_VERBS.search(text) and _TOPIC.search(text))


def classify(message: str, ask: Callable[[str], str]) -> dict[str, Any] | None:
    catalogue = "\n".join(f"- {name}: {about}" for name, about in ACTIONS.items())
    reply = ask(
        "Task: turn Grey's message into ONE app action, as JSON. Pick only from this list; if the message isn't asking for "
        "one of these (for example it's a question, chat, or creating a task/event/reminder/note), reply {\"action\": \"none\"}.\n"
        f"{catalogue}\n\nToday is {date.today().isoformat()}. Never estimate missing nutrition values. "
        "Reply with JSON only: {\"action\": \"name\", \"args\": {...}}\n\n"
        f"MESSAGE: {message}")
    match = re.search(r"\{.*\}", reply, re.S)
    try:
        data = json.loads(match.group(0) if match else reply)
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict) or data.get("action") not in ACTIONS:
        return None
    args = data.get("args") if isinstance(data.get("args"), dict) else {}
    if data["action"] in ("workout.actual", "food.log"):
        args["text"] = message
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
        stated = stated_nutrition(str(args.get("text") or ""))
        if stated:
            # Numbers Grey gives are logged as said: no lookup, no estimate.
            if not food or re.search(r"\b(" + "|".join(_NUTRIENTS.values()) + r")\b", food, re.I) or _GENERIC_FOOD.match(food):
                food = "Logged in chat"
            calories = stated.get("calories")
            from_macros = calories is None and all(k in stated for k in ("protein", "carbs", "fat"))
            if from_macros:
                calories = round(4 * stated["protein"] + 4 * stated["carbs"] + 9 * stated["fat"])
            record = {"title": food, "date": today, "calories": calories or 0, "protein": stated.get("protein", 0), "fiber": stated.get("fiber", 0),
                      "source": "Told ZAE in chat" + (" (calories from protein, carbs and fat)" if from_macros else "")}
            record.update({k: v for k, v in stated.items() if k in ("carbs", "fat", "saturatedFat", "sugars", "sodiumMg", "cholesterolMg")})
            matched = fill_from_catalog(food, record, stated)
            if matched:
                record["source"] += f"; the rest from USDA FoodData Central ({matched[:80]}), scaled to your numbers"
            # The same entry twice within two minutes (two mics, a repeat) is logged once.
            from datetime import datetime, timezone
            for item in store.list("fitness_food"):
                try:
                    recent = (datetime.now(timezone.utc) - datetime.fromisoformat(str(item.get("createdAt")))).total_seconds() < 120
                except (TypeError, ValueError):
                    recent = False
                if recent and item.get("date") == today and item.get("title") == food and not item.get("archived") \
                        and all(item.get(k) == record.get(k) for k in ("calories", "protein", "carbs", "fat")):
                    return {"reply": f"That's already logged{'' if food == 'Logged in chat' else ' for ' + food}.", "tab": "fitness"}
            PersonalTools(store).save("food", record)
            labels = {"protein": "g protein", "fiber": "g fiber", "carbs": "g carbs", "fat": "g fat", "saturatedFat": "g saturated fat", "sugars": "g sugar", "sodiumMg": "mg sodium", "cholesterolMg": "mg cholesterol"}
            said = [f"{calories:g} kcal" + (" (worked out from your macros)" if from_macros else "")] if calories is not None else []
            said += [f"{stated[k]:g} {label}" for k, label in labels.items() if k in stated]
            note = "" if calories is not None else " You didn't give calories, so none are counted for this entry."
            if matched:
                note += f" I filled in the rest from USDA ({matched[:60]})."
            elif food == "Logged in chat":
                note += " Name the food next time and I'll fill in carbs, fat, sugar and cholesterol too."
            return {"reply": f"Logged {', '.join(said)}{'' if food == 'Logged in chat' else ' for ' + food}.{note}", "tab": "fitness"}
        if not food or calories is None:
            raise ValueError("I need sourced values before saving this meal. Use the Fitness & Health meal review and check the food matches and portions first.")
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

    if name in ("workout.actual", "workout.plan"):
        from core.assistant_platform.training import day_view, parse_actual, training
        tracker = training()
        if name == "workout.plan":
            tracker.log_day(today, {"actual": None})
            planned = day_view(today, store)["workout"]
            return {"reply": f"Back to today's plan{': ' + planned['label'] if planned.get('label') else ''}.", "tab": "fitness"}
        if ask is None:
            from core.research.analyze import run_local as ask
        items = parse_actual(str(args.get("text") or ""), ask, tracker.load()["profile"].get("weightLb"))
        tracker.log_day(today, {"actual": items})
        burn = day_view(today, store)["burned"]
        lines = "; ".join(f"{item['name']} ({stat['stats'] or ('~' + format(item['minutes'], 'g') + ' min')}, {stat['kcal']} kcal)"
                          for item, stat in zip(items, burn["actual"]))
        return {"reply": f"Updated today to what you did: {lines}. That's about {sum(a['kcal'] for a in burn['actual'])} kcal burned "
                         f"(estimates from your times, loads and bodyweight), {burn['total']} kcal for the day with steps and cardio. "
                         "Fix any time in the Training program, or say \"back to the plan\" to undo.", "tab": "fitness"}

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
