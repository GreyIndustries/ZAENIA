"""Authenticated, explicitly mapped teaching/planning routes; no execution tools."""
from typing import Any, Callable
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from core.assistant_platform import learning_lab as lab
from core.assistant_platform.store import Conflict


class RecordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: dict[str, Any]
    revision: int | None = Field(default=None, ge=1)


class EvaluationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: list[str] = Field(min_length=1, max_length=3)


def create_learning_lab_router(auth: Callable[..., None], authorize: Callable[..., None], store_provider=None):
    store_provider = store_provider or lab.records
    router = APIRouter(prefix="/api/learning-lab", dependencies=[Depends(auth)])

    @router.get("/models")
    def models():
        from core.assistant_platform.arena import local_models
        try:
            return {"models": local_models(), "error": None}
        except Exception:
            return {"models": [], "error": "Local model runtime unavailable."}

    @router.get("/sections")
    def sections():
        return {"sections": lab.PLAN_SECTIONS}

    @router.get("/records/{kind}")
    def listing(kind: str):
        try:
            return {"items": store_provider().list(lab.collection(kind), limit=500)}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.post("/records/{kind}")
    def create(kind: str, body: RecordBody):
        try:
            return store_provider().put(lab.collection(kind), lab.clean_record(kind, body.record))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.put("/records/{kind}/{identifier}")
    def update(kind: str, identifier: str, body: RecordBody):
        if body.revision is None:
            raise HTTPException(422, "Revision is required.")
        try:
            if not store_provider().get(lab.collection(kind), identifier):
                raise HTTPException(404, "Record not found.")
            return store_provider().put(lab.collection(kind), lab.clean_record(kind, body.record), identifier, revision=body.revision)
        except Conflict as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.delete("/records/{kind}/{identifier}")
    def remove(kind: str, identifier: str, revision: int):
        try:
            return {"deleted": store_provider().delete(lab.collection(kind), identifier, revision=revision)}
        except Conflict as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.post("/evaluate/{identifier}")
    def evaluate(identifier: str, body: EvaluationBody):
        authorize("memory.read")
        row = store_provider().get(lab.collection("lessons"), identifier)
        if not row:
            raise HTTPException(404, "Lesson not found.")
        try:
            return lab.evaluate_lesson(row, body.models)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except Exception as error:
            raise HTTPException(503, "Local evaluation unavailable.") from error

    return router
