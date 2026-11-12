"""Explicit conversational routes for jobs, documents, apps and workspaces."""
from __future__ import annotations

import re


def require(authorize, operation):
    if authorize is None or authorize(operation) is False:
        raise PermissionError("This source or action is unavailable with current permissions.")


def read_or_start(message, authorize):
    from core.assistant_platform.personal_tools import personal_answer
    personal = personal_answer(message, authorize)
    if personal is not None:
        return personal
    query = " ".join(message.split()).strip(" .!?")
    learn = re.fullmatch(r'(?:please )?(?:learn(?: from| this)?|download and learn(?: from)?|add to (?:your|my) (?:knowledge|library))[: ]+(https://\S+)', query, re.I)
    if learn:
        try:
            require(authorize,'memory.write')
            from core.assistant_platform.service import platform
            source=platform().knowledge.learn_url(learn[1])
            return f"Added {source['title']} to my learning library ({source['characters']:,} characters). I'll use relevant excerpts in future answers and cite the source." + (' This page was shortened; the library shows that limitation.' if source['truncated'] else '')
        except PermissionError: return 'Learning from a source is unavailable with the current permissions.'
        except Exception as error: return 'That source could not be learned: '+str(error).splitlines()[0][:250]
    note_search=re.fullmatch(r'(?:please )?(?:search|find|look)(?: in)? my notes(?: for| about|:) +(.+)',query,re.I)
    if note_search:
        try:
            require(authorize,'memory.read')
            from core.assistant_platform.service import platform
            from core.assistant_platform.notes import Notes
            notes=Notes(platform().store);matches=notes.list(note_search[1],limit=5)['notes']
            if not matches:return 'No matching active notes. Your saved notes are in the Notes tab.'
            return '\n\n'.join(f"{item['title']}\n{notes.get(item['id'])['body'][:1800]}\nSource: saved note · {item['updatedAt']}" for item in matches)
        except PermissionError:return 'Notes are unavailable with the current permissions.'
        except ValueError as error:return str(error)
    analysis = re.fullmatch(r"(?:start|run|do) (?:a |an )?(?:(priority|high priority) )?background analysis(?: (?:on|of|about))?[: ]+(.+)",query,re.I)
    document = re.fullmatch(r"(?:search|find|look)(?: in)? my (?:documents|notes|files)(?: for| about|:) +(.+)",query,re.I)
    progress = bool(re.fullmatch(r"(?:what(?:'s| is)|show|how is|how's|what is happening with) (?:the |my )?(?:background (?:work|analysis|jobs)|priority analysis|analysis progress)(?: doing| progressing)?",query,re.I))
    mission_progress=bool(re.fullmatch(r"(?:show|what(?:'s| is)|how is|how's) (?:the |my )?(?:mission(?: progress| status|s)?|active task|session handoff|current session)(?: doing| progressing)?",query,re.I))
    mission_draft=re.fullmatch(r'(?:please )?(?:draft|plan) (?:a )?mission(?: to| for|:) +(.+)',query,re.I)
    research_draft=re.fullmatch(r'(?:please )?(?:research|look up|search the web for) (.+)',query,re.I)
    if mission_progress or mission_draft or research_draft:
        try:
            require(authorize,'assistant.platform.read')
            from core.assistant_platform.service import platform
            operator=platform().operator
            if mission_progress:
                require(authorize,'memory.read')
                rows=operator.reconcile(compact=True)[:3]; handoff=operator.store.get('handoff','active')
                lines=[f"{r['title']}: {r['status'].replace('_',' ')}, {sum(s['status']=='completed' for s in r['steps'])} of {len(r['steps'])} steps finished." for r in rows]
                if handoff: lines.append('Active session: '+handoff['summary']+'. Next: '+handoff['nextStep'])
                return '\n'.join(lines) or 'No mission or session handoff is saved yet.'
            require(authorize,'assistant.platform.write')
            if research_draft:
                subject=research_draft[1]
                operator.create('Research: '+subject[:140],[{'tool':'web.research','args':{'query':subject}},{'tool':'evidence.summarize','args':{'sourceStep':0}}])
                return 'Research steps are ready in Assistant → Operate → Missions. Review the exact public query there, then run the mission.'
            require(authorize,'chat.reply')
            operator.draft(mission_draft[1][:140],mission_draft[1],authorize)
            return 'I’m drafting the mission locally. Its steps will appear in Assistant → Operate → Missions for review before execution.'
        except PermissionError:
            return 'That feature is unavailable with the current permissions.'
        except ValueError as error: return str(error)
    if not (analysis or document or progress): return None
    try:
        require(authorize,"assistant.platform.write" if analysis else "assistant.documents.read" if document else "assistant.platform.read")
        from core.assistant_platform.service import platform
        service = platform()
        if analysis:
            job = service.analyze(analysis[2],priority=bool(analysis[1]),authorize=authorize)
            return f"Started {'priority ' if job['priority'] else ''}background analysis: {job['title']}. " + ("It will continue alongside our conversation. " if job['priority'] else "It can yield model time to your current questions. ") + "Progress and results are in Assistant → Work."
        if document:
            require(authorize,"files.read")
            results = service.documents.search(document[1])
            if not results: return "I couldn't find a current matching excerpt in your indexed, approved document folders. Add or refresh a folder in Assistant → Documents."
            return "\n\n".join(item["excerpt"]+f"\nSource: {item['folder']}/{item['path']}"+(f", page {item['page']}" if item['page'] else ", text excerpt") for item in results[:4])[:5000]
        jobs = service.all_jobs()
        active = [row for row in jobs if row["status"] in {"queued","running"}]
        selected = active[:4] or jobs[:2]
        return "No background analysis has been started." if not selected else "\n".join(f"{row['title']}: {row['stage']}"+(f" — {row['detail']}" if row.get('detail') else "")+(" (priority; continues while we talk)" if row.get('priority') else "") for row in selected)
    except PermissionError:
        return "That feature is unavailable with the current permissions."
    except ValueError as error:
        return str(error)


def prepare(message, authorize):
    query = " ".join(message.split()).strip(" .!?")
    launch = re.fullmatch(r"(?:please )?(?:open|launch|start) (.+)",query,re.I)
    workspace = re.fullmatch(r"(?:please )?(?:start|resume|restore|switch to|open) (.+?)(?: workspace| session)",query,re.I)
    if not launch and not workspace: return None
    from core.assistant_platform.service import existing_platform
    try:
        require(authorize,"assistant.platform.read")
        service = existing_platform()
        if service is None: return None
        name = (workspace[1] if workspace else launch[1]).casefold()
        kind = "workspace" if workspace else "app"
        matches = [item for item in service.store.list(kind) if item["name"].casefold()==name]
        if not matches: return {"reply":"Register that app/file target in Assistant → Apps first."} if launch and not workspace else {"reply":"Save that named workspace in Assistant → Workspaces first."}
        if len(matches)>1: return {"reply":"More than one registered target has that name. Give each a distinct name in Assistant before opening it."}
        record = matches[0]
        return {"reply":f"Review opening {record['name']}.","proposal":{"kind":"workspace.restore" if workspace else "app.launch",
            "title":f"Open {record['name']}","parameters":{"id":record["id"],"name":record["name"],**({"revision":record["revision"]} if workspace else {})}}}
    except PermissionError:
        return {"reply":"Registered apps and workspaces are unavailable with the current permissions."}
