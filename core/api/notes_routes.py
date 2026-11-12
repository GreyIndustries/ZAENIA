"""Notes share the existing authenticated memory read/write permissions."""
from fastapi import APIRouter,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field

class NoteBody(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    title:str=Field(min_length=1,max_length=160)
    body:str=Field(default='',max_length=30000)
    pinned:bool=False
    archived:bool=False
    reference:bool=False
    revision:int|None=Field(default=None,ge=1)


def create_notes_router(get,call):
    from core.assistant_platform.notes import Notes
    router=APIRouter(prefix='/api/platform/notes',tags=['notes'])
    def notes():return Notes(get().store)

    def links():
        """Which notes belong to a research topic or a workbench project (shown as tags in Notes)."""
        tags={}
        try:
            from core.research.notebook import Notebook
            for topic in Notebook(store=get().store).topics():
                if topic.get('noteId'):tags.setdefault(topic['noteId'],[]).append('Research')
        except Exception:
            pass
        for project in get().store.list('workbench'):
            for note_id in project.get('noteIds') or []:
                tags.setdefault(note_id,[]).append('Workbench: '+project.get('title','')[:40])
        return tags

    @router.get('')
    def listing(q:str=Query(default='',max_length=300),archived:bool=False,offset:int=Query(default=0,ge=0)):
        def run():
            result=notes().list(q,archived=archived,offset=offset)
            tags=links()
            for item in result['notes']:item['tags']=tags.get(item['id'],[])
            return result
        return call(run)

    @router.post('/{identifier}/append')
    def append(identifier:str,body:dict):
        return call(lambda:notes().append(identifier,str(body.get('text',''))[:30000],stamp=bool(body.get('stamp',True))))

    @router.get('/{identifier}')
    def read(identifier:str):
        row=get().store.get('note',identifier)
        if row is None:raise HTTPException(404,'That note is unavailable.')
        return row

    @router.post('')
    def create(body:NoteBody):
        if body.revision is not None:raise HTTPException(422,'New notes do not have an existing revision.')
        return call(lambda:notes().save(body.model_dump(exclude={'revision'})))

    @router.put('/{identifier}')
    def save(identifier:str,body:NoteBody):
        return call(lambda:notes().save(body.model_dump(exclude={'revision'}),identifier,body.revision))

    return router
