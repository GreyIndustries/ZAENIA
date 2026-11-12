"""Owner notes: durable saves, revision conflicts and recoverable archiving."""
from __future__ import annotations
import re
import unicodedata
from core.assistant_platform.store import Conflict,now_text,text

MAX_BODY=30000


def validate_note(value):
    if not isinstance(value,dict) or set(value)-{'id','revision','updatedAt','createdAt','title','body','pinned','archived','reference'}:
        raise ValueError('Unsupported note fields.')
    body=value.get('body','')
    if not isinstance(body,str) or len(body)>MAX_BODY or any(ord(c)<32 and c not in '\n\r\t' for c in body):
        raise ValueError('Notes support up to 30,000 characters, including line breaks.')
    flags={}
    for key in ('pinned','archived','reference'):
        flag=value.get(key,False)
        if type(flag) is not bool: raise ValueError('Note options must be true or false.')
        flags[key]=flag
    return {'title':text(value.get('title'),'Note title',160),'body':body,**flags}


class Notes:
    def __init__(self,store):self.store=store

    def save(self,value,identifier=None,revision=None):
        normalized=validate_note(value)
        old=self.store.get('note',identifier) if identifier else None
        if identifier and (old is None or revision is None):raise Conflict('Refresh the saved note before editing it.')
        return self.store.put('note',{**normalized,'createdAt':old['createdAt'] if old else now_text()},identifier,revision=revision)

    def list(self,query='',*,archived=False,offset=0,limit=100,reference_only=False):
        if not isinstance(query,str) or len(query)>300 or type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:
            raise ValueError('Invalid notes search or page size.')
        needle=unicodedata.normalize('NFKC',query.strip()).casefold()
        with self.store.connection() as db:
            db.create_function('note_fold',1,lambda value:unicodedata.normalize('NFKC',str(value or '')).casefold(),deterministic=True)
            where="kind='note' AND json_extract(payload,'$.archived')=?"
            params=[int(archived)]
            if reference_only:where+=" AND json_extract(payload,'$.reference')=1"
            if needle:
                where+=" AND instr(note_fold(json_extract(payload,'$.title') || char(10) || json_extract(payload,'$.body')),?)>0"
                params.append(needle)
            total=db.execute('SELECT COUNT(*) FROM records WHERE '+where,params).fetchone()[0]
            rows=db.execute("SELECT id,revision,updated,json_extract(payload,'$.title') AS title,substr(json_extract(payload,'$.body'),1,420) AS excerpt,length(json_extract(payload,'$.body')) AS chars,json_extract(payload,'$.pinned') AS pinned,json_extract(payload,'$.reference') AS reference FROM records WHERE "+where+" ORDER BY json_extract(payload,'$.pinned') DESC,updated DESC,id LIMIT ? OFFSET ?",(*params,limit,offset))
            items=[{'id':r['id'],'revision':r['revision'],'updatedAt':r['updated'],'title':r['title'],'excerpt':r['excerpt'],'chars':r['chars'] or 0,'pinned':bool(r['pinned']),'reference':bool(r['reference']),'archived':archived} for r in rows]
        return {'notes':items,'total':total,'offset':offset,'nextOffset':offset+limit if offset+limit<total else None}

    # ---- Shared notes: the same notes back the Notes tab, Research notebook topics and Workbench projects.
    def create(self,title,body=''):
        return self.save({'title':str(title)[:160] or 'Note','body':str(body)[:MAX_BODY]})

    def set_body(self,identifier,body):
        row=self.get(identifier)
        keep={k:row.get(k,False if k!='title' else 'Note') for k in ('title','pinned','archived','reference')}
        return self.save({**keep,'body':str(body)[-MAX_BODY:]},identifier,row['revision'])

    def append(self,identifier,addition,stamp=True):
        """Add text to the end of a note (oldest text is dropped first if it would pass the size limit)."""
        from datetime import datetime
        row=self.get(identifier)
        header=f"— {datetime.now().strftime('%b %d, %I:%M %p').replace(' 0',' ')}\n" if stamp else ''
        body=(row['body'].rstrip()+'\n\n'+header+str(addition).strip()).strip()
        return self.set_body(identifier,body)

    def find(self,name):
        """The note he means by name: exact title, then a title containing it, then the best text match."""
        wanted=unicodedata.normalize('NFKC',str(name)).strip().casefold()
        if not wanted:return None
        rows=self.list(wanted,limit=50)['notes']
        for test in (lambda t:t==wanted,lambda t:t.startswith(wanted),lambda t:wanted in t):
            for row in rows:
                if test(unicodedata.normalize('NFKC',row['title']).casefold()):return row
        return rows[0] if rows else None

    def get(self,identifier):
        row=self.store.get('note',identifier)
        if row is None:raise ValueError('That note is unavailable.')
        return row

    def context(self,question):
        # Only explicitly opted-in active notes enter ordinary conversations.
        from core.personal_memory.store import _tokens
        terms=sorted(_tokens(question),key=len,reverse=True)[:5]
        chosen={}
        for term in terms:
            for row in self.list(term,limit=3,reference_only=True)['notes']:
                chosen.setdefault(row['id'],row)
            if len(chosen)>=3:break
        result=[]
        for row in list(chosen.values())[:3]:
            current=self.store.get('note',row['id'])
            if current and current.get('reference') and not current.get('archived'):
                result.append({'id':current['id'],'title':current['title'],'excerpt':current['body'][:1800],'updatedAt':current['updatedAt']})
        return result
