"""Reminders, Protocols and Self-Sustain routes. Operations are listed in ui_routes.ROUTES."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class ReminderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=300)
    due: str = Field(min_length=10, max_length=40)
    channels: list[str] = Field(default_factory=lambda: ["screen", "speak"], max_length=3)
    repeat: str = Field(default="none", max_length=10)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(max_length=12)
    value: str = Field(default="", max_length=300)


class ProtocolBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    phrases: list[str] = Field(min_length=1, max_length=8)
    steps: list[Step] = Field(min_length=1, max_length=12)
    enabled: bool = True


class WatchdogBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    on: bool


def _bad(error: Exception) -> HTTPException:
    return HTTPException(422, str(error).strip("'\""))


def create_selfcare_router(require_api_authentication: Callable[..., None]) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_api_authentication)])

    @router.get("/api/reminders")
    def list_reminders() -> dict[str, Any]:
        from core.assistant_platform.reminders import reminders
        return {"reminders": reminders().list()}

    @router.post("/api/reminders")
    def add_reminder(body: ReminderBody) -> dict[str, Any]:
        from core.assistant_platform.reminders import reminders
        try:
            return reminders().add(body.text, body.due, channels=body.channels, repeat=body.repeat)
        except (ValueError, KeyError) as error:
            raise _bad(error) from error

    @router.delete("/api/reminders/{reminder_id}")
    def delete_reminder(reminder_id: str) -> dict[str, Any]:
        from core.assistant_platform.reminders import reminders
        reminders().delete(reminder_id)
        return {"ok": True}

    @router.get("/api/protocols")
    def list_protocols() -> dict[str, Any]:
        from core.assistant_platform.protocols import EXAMPLES, KINDS, TABS, protocols
        return {"protocols": protocols().list(), "kinds": list(KINDS), "tabs": list(TABS), "examples": EXAMPLES}

    @router.post("/api/protocols")
    def add_protocol(body: ProtocolBody) -> dict[str, Any]:
        from core.assistant_platform.protocols import protocols
        try:
            return protocols().save(body.model_dump())
        except (ValueError, KeyError) as error:
            raise _bad(error) from error

    @router.put("/api/protocols/{protocol_id}")
    def edit_protocol(protocol_id: str, body: ProtocolBody) -> dict[str, Any]:
        from core.assistant_platform.protocols import protocols
        try:
            return protocols().save(body.model_dump(), protocol_id)
        except (ValueError, KeyError) as error:
            raise _bad(error) from error

    @router.delete("/api/protocols/{protocol_id}")
    def delete_protocol(protocol_id: str) -> dict[str, Any]:
        from core.assistant_platform.protocols import protocols
        protocols().delete(protocol_id)
        return {"ok": True}

    @router.get("/api/pc/specs")
    def pc_specs(refresh: bool = False) -> dict[str, Any]:
        from core.assistant_platform.pc_specs import specs, summary
        try:
            data = specs(refresh=refresh)
        except Exception as error:
            raise HTTPException(502, f"Couldn't read this PC's parts ({type(error).__name__}).") from error
        return {**data, "summary": summary(data)}

    @router.get("/api/selfcare")
    def selfcare_state() -> dict[str, Any]:
        from core.assistant_platform.selfcare import health
        return health()

    # ---- Phone notifications (web_push.py)
    @router.get("/api/push/key")
    def push_key() -> dict[str, Any]:
        from core.api import web_push
        try:
            return {"key": web_push.public_key(), "phones": len(web_push.subscriptions())}
        except Exception as error:
            raise HTTPException(502, f"Push keys unavailable ({type(error).__name__}).") from error

    @router.post("/api/push/subscribe")
    def push_subscribe(body: dict[str, Any]) -> dict[str, Any]:
        from core.api import web_push
        try:
            return {"phones": web_push.subscribe(body.get("subscription") or {}, str(body.get("label") or "phone"))}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.post("/api/push/unsubscribe")
    def push_unsubscribe(body: dict[str, Any]) -> dict[str, Any]:
        from core.api import web_push
        web_push.unsubscribe(str(body.get("endpoint") or ""))
        return {"ok": True}

    @router.post("/api/push/test")
    def push_test() -> dict[str, Any]:
        from core.api import web_push
        try:
            return {"sent": web_push.send("ZAE", "Notifications are working. I'll remind you here.")}
        except Exception as error:
            raise HTTPException(502, f"Couldn't send ({type(error).__name__}).") from error

    @router.post("/api/selfcare/backup")
    def backup() -> dict[str, Any]:
        from core.assistant_platform.selfcare import backup_now
        try:
            return backup_now()
        except OSError as error:
            raise HTTPException(500, f"The backup couldn't be written: {error}") from error

    @router.post("/api/selfcare/watchdog")
    def watchdog(body: WatchdogBody) -> dict[str, Any]:
        from core.assistant_platform import selfcare
        ok = selfcare.install_watchdog() if body.on else selfcare.remove_watchdog()
        if not ok:
            raise HTTPException(500, "Windows didn't accept the scheduled task.")
        return {"watchdog": selfcare.watchdog_installed()}

    return router
