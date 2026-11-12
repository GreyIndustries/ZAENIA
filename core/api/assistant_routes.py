"""Permission-scoped personal memory and local follow-through controls."""
from __future__ import annotations

import re
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.foundation.security.audit import audit


def operation_for(method: str, path: str) -> str | None:
    if path == "/api/assistant/memory":
        return {"GET": "memory.read", "POST": "memory.write"}.get(method)
    if path == "/api/assistant/memory/forget" and method == "POST":
        return "memory.write"
    if re.fullmatch(r"/api/assistant/memory/[A-Za-z0-9_-]{1,100}", path) and method == "DELETE":
        return "memory.write"
    if path == "/api/assistant/insights":
        return {"GET": "memory.read", "DELETE": "memory.write"}.get(method)
    if re.fullmatch(r"/api/assistant/insights/[A-Za-z0-9_-]{1,100}", path) and method in {"DELETE", "PATCH"}:
        return "memory.write"
    # Grey's long-term profile (memory ledger): review, explain, confirm, forget.
    if path == "/api/assistant/profile" and method == "GET":
        return "memory.read"
    if re.fullmatch(r"/api/assistant/profile/[A-Za-z0-9_-]{1,100}", path):
        return {"GET": "memory.read", "DELETE": "memory.write"}.get(method)
    if re.fullmatch(r"/api/assistant/profile/[A-Za-z0-9_-]{1,100}/confirm", path) and method == "POST":
        return "memory.write"
    if re.fullmatch(r"/api/assistant/profile/[A-Za-z0-9_-]{1,100}/history", path) and method == "GET":
        return "memory.read"
    if re.fullmatch(r"/api/assistant/profile/[A-Za-z0-9_-]{1,100}/restore", path) and method == "POST":
        return "memory.write"
    if path == "/api/assistant/memory/all" and method == "GET":
        return "memory.read"
    if path == "/api/assistant/notifications" and method == "GET":
        return "notifications.read"
    if re.fullmatch(r"/api/assistant/notifications/[A-Za-z0-9_-]{1,100}/(?:ack|snooze|claim)", path) and method == "POST":
        return "notifications.write"
    if path == "/api/assistant/settings":
        return {"GET": "notifications.read", "PATCH": "assistant.settings.write"}.get(method)
    return None


class MemoryBody(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=800)
    category: str = Field(default="fact", max_length=20)


class ProfileConfirmBody(BaseModel):
    kind: str | None = Field(default=None, pattern=r"^(?:fact|preference|constraint|goal)$")


class ForgetBody(BaseModel):
    key: str = Field(min_length=1, max_length=120)


class InsightReviewBody(BaseModel):
    text: str | None = Field(default=None, min_length=8, max_length=240)
    kind: str | None = Field(default=None, max_length=30)
    revision: int = Field(ge=1)


class SnoozeBody(BaseModel):
    minutes: int = Field(default=15, ge=1, le=1440)


class ClaimBody(BaseModel):
    channel: str = Field(default="speech", max_length=20)


def memory_store():
    from core.personal_memory import MemoryStore
    return MemoryStore()


def create_assistant_router(require_auth: Callable[..., Any], followthrough: Callable[[], Any], *, authorize_sources: Callable[[str], Any] | None = None) -> APIRouter:
    router = APIRouter(tags=["assistant"], dependencies=[Depends(require_auth)])

    def memory_call(callback):
        try:
            return callback(memory_store())
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/api/assistant/memory")
    def memories(query: str = Query(default="", max_length=200)):
        records = memory_call(lambda store: store.search(query, limit=100) if query.strip() else store.list(limit=100))
        return {"memories": records}

    @router.post("/api/assistant/memory")
    def remember(body: MemoryBody):
        saved = memory_call(lambda store: store.upsert(body.key, body.value, body.category))
        audit("assistant.memory_changed", operation="memory.write", reason_code="saved")
        # Values live in the explicit memory store, not a second chat log copy.
        return {"memory": saved}

    @router.post("/api/assistant/memory/forget")
    def forget(body: ForgetBody):
        removed = memory_call(lambda store: store.delete(key=body.key))
        audit("assistant.memory_changed", operation="memory.write", reason_code="forgotten" if removed else "not_found")
        return {"forgotten": removed, "key": body.key}

    @router.delete("/api/assistant/memory/{memory_id}")
    def delete_memory(memory_id: str):
        removed = memory_call(lambda store: store.delete(memory_id))
        if not removed:
            raise HTTPException(404, "That saved memory no longer exists.")
        audit("assistant.memory_changed", operation="memory.write", reason_code="forgotten")
        return {"deleted": memory_id}

    # What ZAE inferred about Zack from conversation: review and delete.
    @router.get("/api/assistant/insights")
    def insights():
        from core.personal_memory.insights import InsightStore, learning_settings
        return {"insights": InsightStore().list(limit=200), "enabled": learning_settings()["enabled"]}

    @router.delete("/api/assistant/insights/{insight_id}")
    def delete_insight(insight_id: str):
        from core.personal_memory.insights import InsightStore
        if not InsightStore().delete(insight_id):
            raise HTTPException(404, "That learned point no longer exists.")
        audit("assistant.memory_changed", operation="memory.write", reason_code="insight_forgotten")
        return {"deleted": insight_id}

    @router.patch("/api/assistant/insights/{insight_id}")
    def review_insight(insight_id: str, body: InsightReviewBody):
        from core.personal_memory.insights import InsightStore
        from core.assistant_platform.store import Conflict
        try:
            item = InsightStore().review(insight_id, text=body.text, kind=body.kind, revision=body.revision)
        except Conflict as error: raise HTTPException(409,str(error)) from error
        except KeyError as error: raise HTTPException(404,"That learned point no longer exists.") from error
        except ValueError as error: raise HTTPException(422,str(error)) from error
        audit("assistant.memory_changed", operation="memory.write", reason_code="insight_reviewed")
        return {"insight":item}

    @router.delete("/api/assistant/insights")
    def clear_insights():
        from core.personal_memory.insights import InsightStore
        removed = InsightStore().clear()
        audit("assistant.memory_changed", operation="memory.write", reason_code="insights_cleared")
        return {"cleared": removed}

    # What ZAE knows about Grey long-term: inspect, see why, confirm, forget.
    @router.get("/api/assistant/profile")
    def profile_records(q: str = Query(default="", max_length=200), status: str = Query(default="active", pattern=r"^(?:active|candidate|all)$"),
                        limit: int = Query(default=100, ge=1, le=500)):
        from core.personal_memory.owner_profile import owner_profile
        profile = owner_profile()
        return {"available": profile.available(), "records": profile.records(query=q, status=status, limit=limit)}

    @router.get("/api/assistant/profile/{memory_id}")
    def profile_explain(memory_id: str):
        from core.personal_memory.owner_profile import owner_profile
        try:
            return owner_profile().explain(memory_id)
        except KeyError as error:
            raise HTTPException(404, "That memory no longer exists.") from error

    @router.post("/api/assistant/profile/{memory_id}/confirm")
    def profile_confirm(memory_id: str, body: ProfileConfirmBody):
        from core.personal_memory.owner_profile import owner_profile
        try:
            result = owner_profile().confirm(memory_id, kind=body.kind)
        except (ValueError, PermissionError) as error:
            raise HTTPException(422, str(error)) from error
        audit("assistant.memory_changed", operation="memory.write", reason_code="profile_confirmed")
        return result

    @router.get("/api/assistant/profile/{memory_id}/history")
    def profile_history(memory_id: str):
        from core.personal_memory.owner_profile import owner_profile
        try:
            return {"history": owner_profile().history(memory_id)}
        except KeyError as error:
            raise HTTPException(404, "That memory no longer exists.") from error

    @router.post("/api/assistant/profile/{memory_id}/restore")
    def profile_restore(memory_id: str):
        from core.personal_memory.owner_profile import owner_profile
        try:
            result = owner_profile().restore(memory_id)
        except (ValueError, PermissionError) as error:
            raise HTTPException(422, str(error)) from error
        audit("assistant.memory_changed", operation="memory.write", reason_code="profile_restored")
        return result

    @router.get("/api/assistant/memory/all")
    def memory_all():
        """Everything ZAE remembers about Grey, from all three stores, each with where it came from."""
        from core.personal_memory.overview import everything
        return everything()

    @router.delete("/api/assistant/profile/{memory_id}")
    def profile_forget(memory_id: str):
        from core.personal_memory.owner_profile import owner_profile
        try:
            removed = owner_profile().forget(memory_id)
        except KeyError as error:
            raise HTTPException(404, "That memory no longer exists.") from error
        audit("assistant.memory_changed", operation="memory.write", reason_code="profile_forgotten")
        return {"forgotten": removed}

    @router.get("/api/assistant/notifications")
    def notifications(includeRead: bool = False):
        if authorize_sources is not None:
            authorize_sources("calendar.read")
            authorize_sources("tasks.read")
        return followthrough().list_notifications(include_read=includeRead)

    def notification_call(callback):
        from core.assistant_followthrough.service import NotificationNotFound
        try:
            return callback(followthrough())
        except NotificationNotFound as error:
            raise HTTPException(404, "That notification is no longer available.") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.post("/api/assistant/notifications/{notification_id}/ack")
    def acknowledge(notification_id: str):
        return notification_call(lambda service: service.acknowledge(notification_id))

    @router.post("/api/assistant/notifications/{notification_id}/snooze")
    def snooze(notification_id: str, body: SnoozeBody):
        return notification_call(lambda service: service.snooze(notification_id, body.minutes))

    @router.post("/api/assistant/notifications/{notification_id}/claim")
    def claim(notification_id: str, body: ClaimBody):
        return notification_call(lambda service: service.claim_delivery(notification_id, body.channel))

    @router.get("/api/assistant/settings")
    def settings():
        return {"settings": followthrough().get_settings()}

    @router.patch("/api/assistant/settings")
    def update_settings(body: dict[str, Any]):
        result = notification_call(lambda service: service.update_settings(body))
        audit("assistant.settings_changed", operation="assistant.settings.write", reason_code="updated")
        return {"settings": result}

    return router
