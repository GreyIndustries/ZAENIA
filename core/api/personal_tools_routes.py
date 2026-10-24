"""Token-authenticated personal workspace API; no filesystem or app grants."""
import base64
import binascii

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from core.assistant_platform.personal_tools import COLLECTIONS, PersonalTools, draft_training_plan, public_url


class SaveBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    record: dict
    revision: int | None = Field(default=None, ge=1)


class SourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(default="", max_length=30000)
    url: str = Field(default="", max_length=2000)
    name: str = Field(default="", max_length=200)
    data: str = Field(default="", max_length=1400000)


class CompletionBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    completed: bool
    revision: int = Field(ge=1)


def create_personal_tools_router(get, call):
    router = APIRouter(prefix="/api/platform/personal", tags=["personal workspaces"])

    @router.get('/fitness-summary')
    def summary(day: str = Query(min_length=10, max_length=10)):
        return call(lambda: PersonalTools(get().store).fitness_summary(day))

    @router.post("/training-source")
    def source(body: SourceBody):
        def extract():
            if sum(bool(value) for value in (body.text, body.url, body.data)) != 1:
                raise ValueError("Choose pasted text, a public webpage, or one document.")
            name, url, content = body.name, body.url, body.text
            if body.url:
                public_url(body.url)
                from urllib.parse import urlsplit
                host = (urlsplit(body.url).hostname or "").lower()
                if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "vimeo.com", "www.vimeo.com"}:
                    return {"sourceUrl": body.url, "sourceName": "Video link", "sourceText": "", "steps": [], "note": "Video saved as a reference. Paste its transcript or captions to extract a routine; ZAE has not watched this video."}
                from core.assistant_operator.web import read_page
                page = read_page(body.url)
                content, name, url = page["text"][:30000], page.get("title", "Webpage")[:200], page.get("url", body.url)
            elif body.data:
                if not body.name.lower().endswith((".txt", ".md", ".pdf", ".docx", ".srt", ".vtt")):
                    raise ValueError("Choose TXT, Markdown, PDF, DOCX, SRT or VTT.")
                try:
                    raw = base64.b64decode(body.data, validate=True)
                except (ValueError, binascii.Error) as error:
                    raise ValueError("The file could not be decoded.") from error
                if len(raw) > 1000000:
                    raise ValueError("Use a source document under 1 MB.")
                if body.name.lower().endswith('.docx'):
                    import io
                    import zipfile
                    try:
                        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                            items = archive.infolist()
                            if len(items)>500 or sum(item.file_size for item in items)>20_000_000:
                                raise ValueError('This document expands beyond the import limit.')
                    except zipfile.BadZipFile as error:
                        raise ValueError('Choose a readable Word document.') from error
                from core.api.chat_files import extract_text
                _, content = extract_text(body.name, raw)
                content = content[:30000]
            result = draft_training_plan(content)
            return {**result, "sourceText": content, "sourceName": name or "Pasted text", "sourceUrl": url}
        return call(extract)

    @router.get("/{collection}")
    def listing(collection: str, day: str = Query(default="", max_length=10), archived: bool = False, offset: int = Query(default=0, ge=0, le=2000)):
        return call(lambda: PersonalTools(get().store).listing(collection, day=day, archived=archived, offset=offset))

    @router.get("/{collection}/{identifier}")
    def read(collection: str, identifier: str):
        if collection not in COLLECTIONS:
            raise HTTPException(404, "Unknown collection.")
        row = get().store.get(COLLECTIONS[collection], identifier)
        if row is None:
            raise HTTPException(404, "That item is unavailable.")
        return row

    @router.post("/{collection}")
    def create(collection: str, body: SaveBody):
        return call(lambda: PersonalTools(get().store).save(collection, body.record, revision=body.revision))

    @router.put("/{collection}/{identifier}")
    def save(collection: str, identifier: str, body: SaveBody):
        return call(lambda: PersonalTools(get().store).save(collection, body.record, identifier, body.revision))

    return router


def create_completion_router(get, call):
    router=APIRouter(prefix='/api/platform/calendar-completions',tags=['calendar completion'])

    @router.get('')
    def listing(day: str=Query(min_length=10,max_length=10)):
        def read():
            from datetime import date
            date.fromisoformat(day)
            return {'items':[item for item in get().store.list('calendar_completion') if item.get('date')==day]}
        return call(read)

    @router.put('/{identifier}')
    def update(identifier:str,body:CompletionBody):
        def save():
            import re
            if not re.fullmatch('[a-f0-9]{64}',identifier):raise ValueError('Invalid calendar occurrence.')
            old=get().store.get('calendar_completion',identifier)
            if old is None:raise HTTPException(404,'That completion record is unavailable.')
            from core.assistant_platform.store import now_text
            return get().store.put('calendar_completion',{**old,'completed':body.completed,'answeredAt':now_text(),'askedAt':'' if not body.completed else old.get('askedAt','')},identifier,revision=body.revision)
        return call(save)

    return router
