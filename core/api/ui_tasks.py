"""Shared task list for the ZÆNIA UI (desktop app and phone).

Tasks live on the PC in data/ui/tasks.json, so every device sees the same
list. The owner allowed token clients to add, change, complete and delete
tasks (operations ui.tasks.write and ui.tasks.delete). Nothing here runs
commands or touches other files.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.foundation.security.io import atomic_write, file_lock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DATA_DIR = PROJECT_ROOT / "data" / "ui"

PRIORITIES = ("Critical", "High", "Normal", "Low")
STATUSES = ("Pending", "In Progress", "Completed")
MAX_TASKS = 2000
MAX_HISTORY = 60
TITLE_LIMIT = 180


class TaskError(ValueError):
    """A request the task list can't accept; the message is safe to show."""


class TaskNotFound(LookupError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _paths() -> tuple[Path, Path]:
    return UI_DATA_DIR / "tasks.json", UI_DATA_DIR / "tasks.lock"


def _valid_time(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 40:
        return False
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return moment.tzinfo is not None


def _clean_title(value: Any) -> str:
    if not isinstance(value, str):
        raise TaskError("Give the task a title.")
    title = " ".join(value.split())
    if not title:
        raise TaskError("Give the task a title.")
    if len(title) > TITLE_LIMIT:
        raise TaskError(f"Keep the title under {TITLE_LIMIT} characters.")
    return title


def _clean_deadline(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not _valid_time(value):
        raise TaskError("Use a full date and time for the deadline.")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="seconds")


def _validate_record(task: Any) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise TaskError("Invalid task.")
    if not isinstance(task.get("id"), str) or not 1 <= len(task["id"]) <= 80:
        raise TaskError("Invalid task id.")
    history = task.get("history")
    if not isinstance(history, list) or not all(
        isinstance(item, dict) and _valid_time(item.get("at")) and item.get("status") in STATUSES
        and isinstance(item.get("note"), str) and len(item["note"]) <= 200 for item in history
    ):
        raise TaskError("Invalid task history.")
    if task.get("priority") not in PRIORITIES or task.get("status") not in STATUSES:
        raise TaskError("Invalid task priority or status.")
    if not (task.get("deadline") is None or _valid_time(task.get("deadline"))):
        raise TaskError("Invalid task deadline.")
    if not _valid_time(task.get("createdAt")) or not _valid_time(task.get("updatedAt")):
        raise TaskError("Invalid task timestamps.")
    if type(task.get("archived")) is not bool:
        raise TaskError("Invalid archive flag.")
    return {
        "id": task["id"], "title": _clean_title(task.get("title")), "priority": task["priority"],
        "status": task["status"], "deadline": task.get("deadline"), "createdAt": task["createdAt"],
        "updatedAt": task["updatedAt"], "archived": task["archived"],
        "history": [{"at": h["at"], "status": h["status"], "note": h["note"]} for h in history][-MAX_HISTORY:],
    }


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list):
        raise RuntimeError("The task file on the PC is damaged; it was left unchanged.")
    return tasks


def _write(path: Path, tasks: list[dict[str, Any]]) -> None:
    body = json.dumps({"version": 1, "tasks": tasks}, ensure_ascii=False, indent=1)
    atomic_write(path, body.encode("utf-8"))


def list_tasks() -> list[dict[str, Any]]:
    path, lock = _paths()
    with file_lock(lock):
        return _read(path)


def _mutate(change) -> tuple[list[dict[str, Any]], Any]:
    path, lock = _paths()
    with file_lock(lock):
        tasks = _read(path)
        result = change(tasks)
        _write(path, tasks)
        return tasks, result


def create_task(title: Any, priority: Any = "Normal", deadline: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    clean_title = _clean_title(title)
    if priority not in PRIORITIES:
        raise TaskError("Choose a priority: Critical, High, Normal or Low.")
    clean_deadline = _clean_deadline(deadline)

    def change(tasks: list[dict[str, Any]]) -> dict[str, Any]:
        if len(tasks) >= MAX_TASKS:
            raise TaskError("The task list is full. Delete or archive old tasks first.")
        at = _now()
        task = {
            "id": str(uuid.uuid4()), "title": clean_title, "priority": priority, "status": "Pending",
            "deadline": clean_deadline, "createdAt": at, "updatedAt": at, "archived": False,
            "history": [{"at": at, "status": "Pending", "note": "Task created"}],
        }
        tasks.append(task)
        return task

    result = _mutate(change)
    from core.assistant_platform.receipts import record
    record("task.create",f"Created task: {result[1]['title']}",source_path=_paths()[0],target=result[1]['id'],after=result[1])
    return result


def update_task(task_id: str, patch: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from copy import deepcopy
    previous = []
    allowed = {"title", "priority", "status", "deadline", "archived"}
    if not isinstance(patch, dict) or not patch or set(patch) - allowed:
        raise TaskError("Nothing to change.")
    updates: dict[str, Any] = {}
    if "title" in patch:
        updates["title"] = _clean_title(patch["title"])
    if "priority" in patch:
        if patch["priority"] not in PRIORITIES:
            raise TaskError("Choose a priority: Critical, High, Normal or Low.")
        updates["priority"] = patch["priority"]
    if "status" in patch:
        if patch["status"] not in STATUSES:
            raise TaskError("Choose a status: Pending, In Progress or Completed.")
        updates["status"] = patch["status"]
    if "deadline" in patch:
        updates["deadline"] = _clean_deadline(patch["deadline"])
    if "archived" in patch:
        if type(patch["archived"]) is not bool:
            raise TaskError("Invalid archive flag.")
        updates["archived"] = patch["archived"]

    def change(tasks: list[dict[str, Any]]) -> dict[str, Any]:
        task = next((item for item in tasks if item.get("id") == task_id), None)
        if task is None:
            raise TaskNotFound(task_id)
        previous.append(deepcopy(task))
        at = _now()
        notes: list[str] = []
        if "title" in updates and updates["title"] != task["title"]:
            notes.append("Title changed")
        if "priority" in updates and updates["priority"] != task["priority"]:
            notes.append(f"Priority changed to {updates['priority']}")
        if "deadline" in updates and updates["deadline"] != task.get("deadline"):
            notes.append("Deadline updated" if updates["deadline"] else "Deadline cleared")
        if "archived" in updates and updates["archived"] != task["archived"]:
            notes.append("Task archived" if updates["archived"] else "Task restored")
        status_note = None
        if "status" in updates and updates["status"] != task["status"]:
            status_note = f"{task['status']} → {updates['status']}"
        task.update(updates)
        history = task.setdefault("history", [])
        for note in notes:
            history.append({"at": at, "status": task["status"], "note": note})
        if status_note:
            history.append({"at": at, "status": task["status"], "note": status_note})
        if notes or status_note:
            task["updatedAt"] = at
        task["history"] = history[-MAX_HISTORY:]
        return task

    result = _mutate(change)
    from core.assistant_platform.receipts import record
    record("task.update",f"Updated task: {result[1]['title']}",source_path=_paths()[0],target=task_id,after=result[1],before=previous[0])
    return result


def delete_task(task_id: str) -> list[dict[str, Any]]:
    def change(tasks: list[dict[str, Any]]) -> None:
        index = next((i for i, item in enumerate(tasks) if item.get("id") == task_id), None)
        if index is None:
            raise TaskNotFound(task_id)
        del tasks[index]

    tasks, _ = _mutate(change)
    return tasks


def import_tasks(records: Any) -> tuple[list[dict[str, Any]], int]:
    """Move a device's saved tasks onto the PC; tasks already there are kept."""
    if not isinstance(records, list) or len(records) > 500:
        raise TaskError("Send up to 500 tasks at a time.")
    clean = [_validate_record(record) for record in records]

    def change(tasks: list[dict[str, Any]]) -> int:
        known = {item.get("id") for item in tasks}
        added = 0
        for record in clean:
            if record["id"] in known:
                continue
            if len(tasks) >= MAX_TASKS:
                raise TaskError("The task list is full.")
            tasks.append(record)
            known.add(record["id"])
            added += 1
        return added

    return _mutate(change)
