"""Code Doctor, Suggestions, Arena and source search routes. Operations are listed in ui_routes.ROUTES."""
from __future__ import annotations

import hashlib
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field


class ProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(default="", max_length=400)


class FileBody(ProjectBody):
    file: str = Field(min_length=1, max_length=400)
    findings: list[str] = Field(default_factory=list, max_length=40)


class ApplyBody(ProjectBody):
    file: str = Field(min_length=1, max_length=400)
    text: str = Field(max_length=400_000)
    oldHash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ThinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    focus: str = Field(default="all", pattern=r"^(all|day|system)$")


class RunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field(pattern=r"^(python|javascript|powershell)$")
    code: str = Field(max_length=200_000)
    tests: str = Field(default="", max_length=50_000)
    stdin: str = Field(default="", max_length=20_000)
    timeout: float = Field(default=10, ge=1, le=60)


class PlaygroundAskBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field(pattern=r"^(python|javascript|powershell)$")
    code: str = Field(max_length=200_000)
    tests: str = Field(default="", max_length=50_000)
    result: dict | None = None
    question: str = Field(default="", max_length=1000)


class SnippetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default="", max_length=32)
    title: str = Field(default="", max_length=120)
    language: str = Field(pattern=r"^(python|javascript|powershell)$")
    code: str = Field(default="", max_length=200_000)
    tests: str = Field(default="", max_length=50_000)


class ImplementBody(ProjectBody):
    file: str = Field(min_length=1, max_length=400)
    code: str = Field(max_length=200_000)
    oldHash: str = Field(default="", max_length=64)


class DecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool


class ArenaBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    models: list[str] = Field(min_length=2, max_length=3)


class VoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round: str = Field(pattern=r"^[0-9a-f]{32}$")
    model: str = Field(min_length=1, max_length=120)


class BrainBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = Field(default=None, max_length=120)


def _bad(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(403, str(error))
    if isinstance(error, (ValueError, KeyError)):
        return HTTPException(422, str(error).strip("'\""))
    return HTTPException(502, f"That didn't work ({type(error).__name__}).")


def _ask_brain(prompt: str) -> str:
    from core.research.analyze import run_local
    return run_local(prompt)


def require_desktop(x_zaenia_desktop_key: str | None = Header(default=None, alias="X-ZAENIA-DESKTOP-KEY")) -> None:
    """Changing files or her brain only from the paired desktop app on the PC."""
    from core.api.desktop_key import is_paired, verify
    if not is_paired() or not verify(x_zaenia_desktop_key):
        raise HTTPException(403, "Only the ZÆNIA desktop app on the PC can do that.")


def create_tools_router(require_api_authentication: Callable[..., None]) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_api_authentication)])

    # ---- Code Doctor
    @router.post("/api/code/scan")
    def code_scan(body: ProjectBody) -> dict[str, Any]:
        from core.assistant_platform.code_doctor import scan
        try:
            return scan(body.project)
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/code/explain")
    def code_explain(body: FileBody) -> dict[str, Any]:
        from core.assistant_platform import code_doctor as doctor
        try:
            target, text = doctor.read_file(body.project, body.file)
            return {"review": _ask_brain(doctor.review_prompt(body.file, text, body.findings, fix=False))}
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/code/fix")
    def code_fix(body: FileBody) -> dict[str, Any]:
        from core.assistant_platform import code_doctor as doctor
        try:
            target, text = doctor.read_file(body.project, body.file)
            fixed = doctor.extract_code(_ask_brain(doctor.review_prompt(body.file, text, body.findings, fix=True)))
            if not fixed or fixed.strip() == text.strip():
                return {"changed": False, "message": "ZAE didn't find a change worth making."}
            return {"changed": True, "diff": doctor.unified(text, fixed, body.file), "text": fixed,
                    "oldHash": hashlib.sha256(text.encode("utf-8")).hexdigest(), "protected": doctor.protected(target)}
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/code/apply")
    def code_apply(body: ApplyBody, x_zaenia_desktop_key: str | None = Header(default=None, alias="X-ZAENIA-DESKTOP-KEY"),
                   x_zaenia_near_pass: str | None = Header(default=None, alias="X-ZAENIA-NEAR-PASS")) -> dict[str, Any]:
        from core.api.near_pc import desktop_or_near
        from core.assistant_platform.code_doctor import apply_fix
        from core.foundation.security.audit import audit
        if desktop_or_near(x_zaenia_desktop_key, x_zaenia_near_pass) is None:
            require_desktop(x_zaenia_desktop_key)
        try:
            result = apply_fix(body.project, body.file, body.text, body.oldHash)
        except Exception as error:
            raise _bad(error) from error
        audit("code_doctor.fix_applied", operation="assistant.desktop.manage", reason_code="backup_kept")
        return result

    # ---- Playground: write, run and test code before putting it in a project (playground.py)
    @router.post("/api/code/run", dependencies=[Depends(require_desktop)])
    def code_run(body: RunBody) -> dict[str, Any]:
        from core.assistant_platform.playground import run
        try:
            return run(body.language, body.code, tests=body.tests, stdin=body.stdin, timeout=body.timeout)
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/code/playground/ask")
    def code_playground_ask(body: PlaygroundAskBody) -> dict[str, Any]:
        from core.assistant_platform import code_doctor as doctor
        from core.assistant_platform.playground import ask_prompt
        try:
            answer = _ask_brain(ask_prompt(body.language, body.code, body.tests, body.result, body.question))
            return {"answer": answer, "code": doctor.extract_code(answer)}
        except Exception as error:
            raise _bad(error) from error

    @router.get("/api/code/snippets")
    def code_snippets() -> dict[str, Any]:
        from core.assistant_platform.playground import snippets
        return {"snippets": snippets()[::-1]}

    @router.post("/api/code/snippets")
    def code_snippet_save(body: SnippetBody) -> dict[str, Any]:
        from core.assistant_platform.playground import save_snippet
        try:
            return save_snippet(body.model_dump())
        except Exception as error:
            raise _bad(error) from error

    @router.delete("/api/code/snippets/{snippet_id}")
    def code_snippet_delete(snippet_id: str) -> dict[str, Any]:
        from core.assistant_platform.playground import delete_snippet
        delete_snippet(snippet_id)
        return {"ok": True}

    @router.post("/api/code/load")
    def code_load(body: FileBody) -> dict[str, Any]:
        from core.assistant_platform.playground import load_file
        try:
            return load_file(body.project, body.file)
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/code/implement", dependencies=[Depends(require_desktop)])
    def code_implement(body: ImplementBody) -> dict[str, Any]:
        from core.assistant_platform.playground import save_to_project
        from core.foundation.security.audit import audit
        try:
            result = save_to_project(body.project, body.file, body.code, body.oldHash)
        except Exception as error:
            raise _bad(error) from error
        audit("code_playground.implemented", operation="assistant.desktop.manage", reason_code="backup_kept" if result["backup"] else "new_file")
        return result

    @router.get("/api/code/search")
    def code_search(q: str = Query(min_length=2, max_length=120)) -> dict[str, Any]:
        """Source search across ZAE's own code (the folders the Files tab shows)."""
        from core.api.ui_files import ALLOWED_DIRS, PROJECT_ROOT
        needle, hits = q.casefold(), []
        for folder in ALLOWED_DIRS:
            for path in sorted((PROJECT_ROOT / folder).rglob("*")):
                if len(hits) >= 200:
                    break
                if not path.is_file() or path.suffix not in (".py", ".ts", ".tsx", ".rs", ".css", ".ps1", ".yaml", ".md", ".json") \
                        or "__pycache__" in path.parts or "_backup" in str(path) or path.stat().st_size > 400_000:
                    continue
                try:
                    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                        if needle in line.casefold():
                            hits.append({"file": path.relative_to(PROJECT_ROOT).as_posix(), "line": number, "text": line.strip()[:200]})
                            if len(hits) >= 200:
                                break
                except (UnicodeDecodeError, OSError):
                    continue
        return {"query": q, "hits": hits}

    # ---- Suggestions
    @router.get("/api/suggestions")
    def suggestion_list() -> dict[str, Any]:
        from core.assistant_platform.suggestions import suggestions, upgrade_plan
        items = suggestions().list()
        return {"suggestions": items[::-1], "plan": upgrade_plan(items)}

    @router.post("/api/suggestions/think")
    def suggestion_think(body: ThinkBody | None = None) -> dict[str, Any]:
        from core.assistant_platform.suggestions import suggestions
        try:
            return {"new": suggestions().think(_ask_brain, focus=(body.focus if body else "all"))}
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/suggestions/{suggestion_id}")
    def suggestion_decide(suggestion_id: str, body: DecideBody) -> dict[str, Any]:
        from core.assistant_platform import reminders as nudges
        from core.assistant_platform.suggestions import suggestions

        def set_reminder(when: str, text: str) -> str:
            parsed = nudges.parse_request(f"remind me in {when} minutes to {text}" if when.isdigit() else f"remind me at {when} to {text}")
            if parsed is None:
                return f"Couldn't read the time {when!r}; no reminder set."
            nudges.reminders().add(parsed[1], parsed[0])
            return f"Reminder set for {nudges.spoken_time(parsed[0])}."
        try:
            return suggestions().decide(suggestion_id, body.approve, set_reminder)
        except Exception as error:
            raise _bad(error) from error

    # ---- Her brains and coding tools (Arena > Brains & tools), checked live
    @router.get("/api/brains")
    def brain_roster() -> dict[str, Any]:
        from core.brain.roster import roster
        return roster()

    # ---- Arena
    @router.get("/api/arena")
    def arena_state() -> dict[str, Any]:
        from core.assistant_platform.arena import arena, local_models
        try:
            models = local_models()
        except Exception:
            models = []
        return {**arena().board(), "models": models}

    @router.post("/api/arena/round")
    def arena_round(body: ArenaBody) -> dict[str, Any]:
        from core.assistant_platform.arena import arena
        try:
            return arena().run(body.question, body.models)
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/arena/vote")
    def arena_vote(body: VoteBody) -> dict[str, Any]:
        from core.assistant_platform.arena import arena
        try:
            return arena().vote(body.round, body.model)
        except Exception as error:
            raise _bad(error) from error

    @router.post("/api/arena/brain", dependencies=[Depends(require_desktop)])
    def arena_brain(body: BrainBody) -> dict[str, Any]:
        from core.assistant_platform.arena import arena
        from core.foundation.security.audit import audit
        try:
            result = arena().use_as_brain(body.model)
        except Exception as error:
            raise _bad(error) from error
        audit("arena.brain_changed", operation="assistant.desktop.manage", reason_code="owner_choice")
        return result

    return router
