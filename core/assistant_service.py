"""Shared, local action preparation and authorized personal-memory lookup.

Preparation grants no execution authority. Voice and UI handlers must authorize
their own exact operation before applying a reviewed proposal.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from core.api.assistant_actions import propose_action


def prepare_action(message: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    from core.personal_memory import parse_memory_request
    request = parse_memory_request(message)
    if request is None:
        return propose_action(message, now=now)
    if request.get("reply"):
        return {"reply": request["reply"]}
    operation = request["operation"]
    if operation == "recall":
        return None  # handled only by the separately authorized lookup
    if operation == "remember":
        parameters = {key: request[key] for key in ("key", "value", "category")}
        return {
            "reply": "Review this personal memory before saving it. You can correct or remove it in Assistant.",
            "proposal": {"kind": "memory.remember", "title": "Remember personal information", "parameters": parameters},
        }
    if operation == "forget":
        return {
            "reply": "Review the exact memory key to remove from personal memory.",
            "proposal": {"kind": "memory.forget", "title": "Forget personal memory", "parameters": {"key": request["key"]}},
        }
    return None


def authorize_memory(authorize: Callable[[str], Any] | None, operation: str) -> None:
    if authorize is None:
        raise PermissionError("Personal memory is unavailable with the current permissions.")
    try:
        allowed = authorize(operation)
    except Exception:
        raise PermissionError("Personal memory is unavailable with the current permissions.") from None
    if allowed is False:
        raise PermissionError("Personal memory is unavailable with the current permissions.")


def recall_memory(message: str, authorize: Callable[[str], Any] | None, *, store: Any = None) -> str | None:
    from core.personal_memory import MemoryStore, parse_memory_request
    request = parse_memory_request(message)
    if request is None or request.get("operation") != "recall":
        return None
    authorize_memory(authorize, "memory.read")
    active = store if store is not None else MemoryStore()
    query = request.get("query", "").strip()
    records = active.search(query, limit=8) if query else active.list(limit=20)
    if not records:
        return "I don't have a saved personal memory matching that request."
    lines = [f"{item['key']}: {item['value']} ({item['category']})" for item in records[:8]]
    return ("You asked me to remember:\n" + "\n".join(lines))[:2000]
