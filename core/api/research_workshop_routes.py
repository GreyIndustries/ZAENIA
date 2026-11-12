from typing import Callable
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Pasted source", max_length=200)
    text: str = Field(max_length=20000)


class WorkshopBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str = Field(max_length=30)
    question: str = Field(min_length=1, max_length=4000)
    sources: list[Source] = Field(default_factory=list, max_length=20)
    topicId: str = Field(default="", pattern=r"^([0-9a-f]{32})?$")


def create_research_workshop_router(auth: Callable[..., None], authorize: Callable[..., None]):
    router = APIRouter(prefix="/api/research/workshop", dependencies=[Depends(auth)])

    @router.get("/reference")
    def reference(q: str = Query(default="", max_length=200), category: str = Query(default="", max_length=80)):
        from core.research.workshop import reference_search
        return reference_search(q, category)

    @router.post("/analyze")
    def analyze(body: WorkshopBody):
        from core.research.workshop import analyze
        sources = [s.model_dump() for s in body.sources]
        if body.topicId:
            authorize("memory.read")
            from core.research.notebook import notebook
            topic = notebook().material(body.topicId)
            sources.extend({"title": s.get("title", "Saved source"), "text": s.get("text", "")[:20000]} for s in topic.get("sources", [])[:20-len(sources)])
        try:
            return analyze(body.mode, body.question, sources)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except Exception as error:
            raise HTTPException(503, "Local research analysis unavailable. Your sources were not saved or uploaded.") from error

    return router
