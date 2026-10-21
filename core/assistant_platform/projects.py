"""Editable plans with dependency checks and progress from completed steps."""
from datetime import date
import uuid

from core.assistant_platform.store import Conflict, text


def validate_project(body):
    title = text(body.get("title"), "Project title", 200)
    steps = body.get("steps", [])
    if not isinstance(steps, list) or len(steps) > 150:
        raise ValueError("A project supports up to 150 steps.")
    normalized, known = [], set()
    for item in steps:
        if not isinstance(item, dict): raise ValueError("Each step must be an object.")
        identifier = item.get("id") or uuid.uuid4().hex
        if not isinstance(identifier, str) or len(identifier)>64 or identifier in known:
            raise ValueError("Each step needs a unique ID.")
        known.add(identifier)
        deadline = item.get("deadline") or None
        if deadline is not None: deadline = date.fromisoformat(deadline).isoformat()
        status = item.get("status", "pending")
        if status not in {"pending", "active", "completed"}: raise ValueError("Invalid step status.")
        dependencies = item.get("dependsOn", [])
        if not isinstance(dependencies, list) or any(not isinstance(value, str) for value in dependencies):
            raise ValueError("Dependencies must be step IDs.")
        normalized.append({"id": identifier, "title": text(item.get("title"), "Step title", 300),
            "milestone": text(item.get("milestone") or "Work", "Milestone", 120), "status": status,
            "deadline": deadline, "dependsOn": list(dict.fromkeys(dependencies))})
    graph = {item["id"]: item for item in normalized}
    visited = set()
    def visit(identifier, trail):
        if identifier in visited: return
        if identifier in trail: raise ValueError("Steps cannot depend on themselves or form a cycle.")
        for parent in graph[identifier]["dependsOn"]:
            if parent not in graph: raise ValueError("A dependency refers to a missing step.")
            visit(parent, trail | {identifier})
        visited.add(identifier)
    for item in normalized:
        visit(item["id"], set())
        if item["status"] in {"active", "completed"} and any(graph[parent]["status"] != "completed" for parent in item["dependsOn"]):
            raise ValueError("Complete prerequisite steps before starting or completing this step.")
    return {"title": title, "goal": str(body.get("goal") or "")[:2000], "steps": normalized}


def project_view(record):
    steps = record.get("steps", [])
    done = {item["id"] for item in steps if item["status"] == "completed"}
    ready = [item for item in steps if item["status"] != "completed" and all(parent in done for parent in item["dependsOn"])]
    return {**record, "completedSteps": len(done), "totalSteps": len(steps),
        "progress": round(100*len(done)/len(steps)) if steps else 0,
        "nextStep": ready[0] if ready else None}


def plan_from_lines(title, lines):
    """An editable initial plan; proposed steps never claim completed work."""
    return validate_project({"title": title, "steps": [{"title": line.strip(), "status": "pending"} for line in lines if line.strip()]})
