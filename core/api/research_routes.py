"""Research and News reader routes (Library, Historical connections, Notebook, world news, article reader).

Same token check and client gate as the other UI routes; the operation for
each path is in ui_routes.ROUTES (reads: status.read, the notebook:
memory.read / memory.write, her analysis: chat.reply).
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

HEX = r"^[0-9a-f]{32}$"


class ReadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=8, max_length=1000)


class AnalyzeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=2, max_length=20)
    text: str = Field(default="", max_length=400_000)
    url: str = Field(default="", max_length=1000)
    kind: str = Field(default="article", pattern=r"^(article|book)$")
    question: str = Field(default="", max_length=500)
    term: str = Field(default="", max_length=60)
    period: str = Field(default="", max_length=10)
    title: str = Field(default="", max_length=300)
    topicId: str = Field(default="", max_length=32)


class MarkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=1000)
    source: str = Field(default="bible", pattern=r"^(bible|jewish|quran)$")


class TranslateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=200_000)
    url: str = Field(default="", max_length=1000)
    target: str = Field(default="English", max_length=30)
    source: str = Field(default="auto", max_length=30)
    style: str = Field(default="natural", max_length=10)


class AgentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=500)


class WatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=2, max_length=120)


class TopicBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)


class NotesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: str = Field(default="", max_length=50_000)


class SourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    kind: str = Field(default="web", max_length=10)
    url: str = Field(default="", max_length=1000)
    text: str = Field(default="", max_length=20_000)
    meta: str = Field(default="", max_length=300)
    fetch: bool = False


def _fail(error: Exception) -> HTTPException:
    if isinstance(error, (ValueError, KeyError)):
        return HTTPException(422, str(error).strip("'\""))
    return HTTPException(502, f"The source didn't answer ({type(error).__name__}). Try again in a moment.")


def create_research_router(require_api_authentication: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/api/research", dependencies=[Depends(require_api_authentication)], tags=["research"])

    def notebook():
        from core.research.notebook import Notebook
        return Notebook()

    def article(url: str) -> dict[str, str]:
        from core.research import web
        return web.readable(web.get_text(url))

    @router.get("/library")
    def library(q: str = Query(min_length=1, max_length=200)) -> dict[str, Any]:
        from core.research import library as books
        try:
            found = books.search(q)
        except Exception as error:
            raise _fail(error) from error
        try:
            found["overview"] = books.overview(q)
        except Exception:
            found["overview"] = None
        return found

    @router.post("/library/read")
    def read_book(body: ReadBody) -> dict[str, Any]:
        from core.research import library as books
        try:
            text = books.read_text(body.url)
        except Exception as error:
            raise _fail(error) from error
        return {"chars": len(text), "excerpt": text[:20_000]}

    @router.get("/article")
    def read_article(url: str = Query(min_length=8, max_length=1000)) -> dict[str, str]:
        try:
            return article(url)
        except Exception as error:
            raise _fail(error) from error

    @router.post("/analyze")
    def analyze(body: AnalyzeBody) -> dict[str, Any]:
        from core.research import analyze as brain
        try:
            if body.topicId:
                material = brain.notebook_material(notebook().material(body.topicId))
            elif body.text:
                material = body.text
            elif body.url and body.kind == "book":
                from core.research import library as books
                material = books.read_text(body.url)
            elif body.url:
                found = article(body.url)
                material = found["text"]
            else:
                material = ""
            return brain.analyze(body.task, material, question=body.question, term=body.term, period=body.period, title=body.title)
        except Exception as error:
            raise _fail(error) from error

    @router.get("/history")
    def history(terms: str = Query(min_length=1, max_length=200), source: str = Query(default="newspapers", max_length=12),
                language: str = Query(default="", max_length=12)) -> dict[str, Any]:
        from core.research import history as timeline
        try:
            return timeline.track(terms, source, language=language)
        except Exception as error:
            raise _fail(error) from error

    @router.get("/history/samples")
    def history_samples(term: str = Query(min_length=1, max_length=60), source: str = Query(max_length=12),
                        period: str = Query(pattern=r"^\d{4}s?$"), language: str = Query(default="", max_length=12)) -> dict[str, Any]:
        from core.research import history as timeline
        try:
            return {"rows": timeline.samples(term, source, period, language=language)}
        except Exception as error:
            raise _fail(error) from error

    @router.get("/worldnews")
    def world_news(q: str = Query(min_length=1, max_length=80), days: int = Query(default=7, ge=1, le=90)) -> dict[str, Any]:
        from core.research import history as timeline
        try:
            return {"stories": timeline.world_news(q, days)}
        except Exception as error:
            raise _fail(error) from error

    @router.get("/agent")
    def agent_jobs() -> dict[str, Any]:
        from core.research.agent import agent, watch
        return {"jobs": agent().list(), "watch": watch().list()}

    @router.post("/agent")
    def agent_start(body: AgentBody) -> dict[str, Any]:
        from core.research.agent import agent
        try:
            return agent().start(body.question)
        except Exception as error:
            raise _fail(error) from error

    @router.delete("/agent/{job_id}")
    def agent_delete(job_id: str = Path(pattern=HEX)) -> dict[str, Any]:
        from core.research.agent import agent
        agent().delete(job_id)
        return {"ok": True}

    @router.post("/watch")
    def watch_add(body: WatchBody) -> dict[str, Any]:
        from core.research.agent import watch
        try:
            return watch().add(body.topic)
        except Exception as error:
            raise _fail(error) from error

    @router.post("/watch/{topic_id}/check")
    def watch_check(topic_id: str = Path(pattern=HEX)) -> dict[str, Any]:
        from core.research.agent import watch
        try:
            return {"finding": watch().check(topic_id)}
        except Exception as error:
            raise _fail(error) from error

    @router.delete("/watch/{topic_id}")
    def watch_remove(topic_id: str = Path(pattern=HEX)) -> dict[str, Any]:
        from core.research.agent import watch
        watch().remove(topic_id)
        return {"ok": True}

    @router.get("/translate/languages")
    def languages() -> dict[str, Any]:
        from core.research.analyze import LANGUAGES, STYLES
        return {"languages": list(LANGUAGES), "styles": list(STYLES)}

    @router.post("/translate")
    def translate(body: TranslateBody) -> dict[str, Any]:
        from core.research import analyze as brain
        try:
            title = ""
            text = body.text
            if not text and body.url:
                found = article(body.url)
                text, title = found["text"], found.get("title", "")
            result = brain.translate(text, body.target, body.source, body.style)
            result["title"] = title
            result["original"] = text[:200_000] if body.url else ""
            return result
        except Exception as error:
            raise _fail(error) from error

    @router.get("/scripture")
    def scripture_passage(ref: str = Query(min_length=1, max_length=80), translations: str = Query(default="WEB,KJV", max_length=80),
                          interlinear: bool = True, source: str = Query(default="bible", pattern=r"^(bible|jewish|quran)$")) -> dict[str, Any]:
        from core.research import scripture
        wanted = [t.strip().upper() for t in translations.split(",") if t.strip()]
        try:
            if source == "jewish":
                found = scripture.jewish(ref)
            elif source == "quran":
                found = scripture.quran(ref, wanted)
            else:
                found = scripture.passage(ref, wanted, interlinear=interlinear)
        except Exception as error:
            raise _fail(error) from error
        found["text"] = scripture.passage_text(found)
        return found

    @router.get("/scripture/search")
    def scripture_search(q: str = Query(min_length=2, max_length=200),
                         source: str = Query(default="bible", pattern=r"^(bible|jewish|quran)$")) -> dict[str, Any]:
        from core.research import scripture
        try:
            return {"results": scripture.search(q, source=source)}
        except Exception as error:
            raise _fail(error) from error

    @router.get("/scripture/marks")
    def scripture_marks() -> dict[str, Any]:
        from core.research.scripture import ANCIENT, MORE_SITES, Marks
        return {"marks": Marks().list()[::-1], "ancient": ANCIENT, "sites": [{"name": n, "url": u} for n, u in MORE_SITES]}

    @router.post("/scripture/marks")
    def scripture_mark(body: MarkBody) -> dict[str, Any]:
        from core.research.scripture import Marks
        try:
            return Marks().add(body.reference, body.note, body.source)
        except Exception as error:
            raise _fail(error) from error

    @router.delete("/scripture/marks/{mark_id}")
    def scripture_unmark(mark_id: str) -> dict[str, Any]:
        from core.research.scripture import Marks
        Marks().delete(mark_id)
        return {"ok": True}

    @router.get("/notebook")
    def topics() -> dict[str, Any]:
        return {"topics": notebook().topics()}

    @router.post("/notebook")
    def new_topic(body: TopicBody) -> dict[str, Any]:
        try:
            return notebook().create(body.name)
        except Exception as error:
            raise _fail(error) from error

    @router.get("/notebook/{topic_id}")
    def topic(topic_id: str) -> dict[str, Any]:
        try:
            return notebook().get(topic_id)
        except Exception as error:
            raise _fail(error) from error

    @router.post("/notebook/link/{note_id}")
    def link_note(note_id: str) -> dict[str, Any]:
        try:
            return notebook().link_note(note_id)
        except Exception as error:
            raise _fail(error) from error

    @router.delete("/notebook/{topic_id}")
    def delete_topic(topic_id: str) -> dict[str, Any]:
        notebook().delete(topic_id)
        return {"ok": True}

    @router.put("/notebook/{topic_id}/notes")
    def save_notes(topic_id: str, body: NotesBody) -> dict[str, Any]:
        try:
            return notebook().set_notes(topic_id, body.notes)
        except Exception as error:
            raise _fail(error) from error

    @router.post("/notebook/{topic_id}/sources")
    def add_source(topic_id: str, body: SourceBody) -> dict[str, Any]:
        text = body.text
        try:
            if body.fetch and body.url and not text:
                if body.kind == "book":
                    from core.research import library as books
                    text = books.read_text(body.url)[:20_000]
                else:
                    text = article(body.url)["text"][:20_000]
        except Exception:
            text = ""  # keep the source by title and link if its text can't be fetched
        try:
            return notebook().add_source(topic_id, title=body.title, kind=body.kind, url=body.url, text=text, meta=body.meta)
        except Exception as error:
            raise _fail(error) from error

    @router.delete("/notebook/{topic_id}/sources/{source_id}")
    def remove_source(topic_id: str, source_id: str) -> dict[str, Any]:
        try:
            return notebook().remove_source(topic_id, source_id)
        except Exception as error:
            raise _fail(error) from error

    return router
