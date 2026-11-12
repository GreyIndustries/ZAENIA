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


class TrainingActualBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=4000)


class TrainingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: dict = Field(default_factory=dict)


class ProgramBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    planId: str = Field(default="", max_length=32)
    weekdays: dict[str, str] = Field(default_factory=dict)


class TrainingSourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=8, max_length=2000)
    remove: bool = False


class CompletionBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    completed: bool
    revision: int = Field(ge=1)


class MealBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    description: str = Field(min_length=3, max_length=2000)
    items: list[dict] = Field(default_factory=list, max_length=50)
    date: str = Field(default_factory=lambda: __import__('datetime').date.today().isoformat(), min_length=10, max_length=10)


class BarcodeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    barcode: str = Field(min_length=8, max_length=32)


class FoodSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=120)


class LabelBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    data: str = Field(min_length=16, max_length=12000000)


class RecipeMathBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ingredients: list[dict] = Field(max_length=100)
    servings: float = Field(gt=0, le=100)


def create_personal_tools_router(get, call):
    router = APIRouter(prefix="/api/platform/personal", tags=["personal workspaces"])

    @router.get('/fitness-summary')
    def summary(day: str = Query(min_length=10, max_length=10)):
        return call(lambda: PersonalTools(get().store).fitness_summary(day))

    @router.get("/music/overview")
    def music_overview_route():
        from core.assistant_platform.personal_tools import music_overview
        return call(lambda: music_overview(get().store))

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

    @router.post("/nutrition/meal-preview")
    def nutrition_meal_preview(body: MealBody):
        from core.assistant_platform.nutrition import preview_meal
        return call(lambda: preview_meal(body.description, store=get().store))

    @router.post("/nutrition/log")
    def nutrition_log(body: MealBody):
        from datetime import date
        from core.assistant_platform.nutrition import totals
        def save_meal():
            if not body.items or any(not isinstance(item.get("nutrients"), dict) or any(item["nutrients"].get(key) is None for key in ("calories", "protein", "fiber")) for item in body.items):
                raise ValueError("Complete and review every food and serving before logging the meal.")
            sums = totals(body.items)
            food = {"title": body.description[:160], "date": body.date, "archived": False,
                    "calories": sums["calories"], "protein": sums["protein"], "fiber": sums["fiber"], "carbs": sums["carbs"],
                    "fat": sums["fat"], "saturatedFat": sums["saturatedFat"], "sugars": sums["sugars"],
                    "sodiumMg": sums["sodiumMg"], "cholesterolMg": sums["cholesterolMg"],
                    "source": "Reviewed nutrition records", "items": body.items,
                    "sourceDetails": [{"name": x.get("sourceName", ""), "url": x.get("source", ""), "checkedAt": x.get("checkedAt"),
                                       "nutrientsNotReported": [key for key, value in (x.get("nutrients") or {}).items() if value is None]}
                                      for x in body.items if x.get("source")]}
            return PersonalTools(get().store).save("food", food)
        return call(save_meal)

    @router.post("/nutrition/barcode")
    def nutrition_barcode(body: BarcodeBody):
        from core.assistant_platform.nutrition import barcode_lookup
        return call(lambda: barcode_lookup(body.barcode))

    @router.post("/nutrition/search")
    def nutrition_search(body: FoodSearchBody):
        from core.assistant_platform.nutrition import search_food
        return call(lambda: search_food(body.query))

    @router.post("/nutrition/suggest")
    def nutrition_suggest(body: FoodSearchBody):
        from core.assistant_platform.nutrition import search_products
        return call(lambda: search_products(body.query, get().store))

    @router.post("/nutrition/web")
    def nutrition_web(body: FoodSearchBody):
        from core.assistant_platform.nutrition_web import web_lookup
        from core.research.analyze import run_local
        return call(lambda: web_lookup(body.query, ask=run_local))

    @router.post("/nutrition/label")
    def nutrition_label(body: LabelBody):
        import base64, binascii
        from core.assistant_platform.nutrition import read_label
        def scan():
            try:
                raw = base64.b64decode(body.data, validate=True)
            except (ValueError, binascii.Error) as error:
                raise ValueError("The label image could not be read.") from error
            return read_label(raw)
        return call(scan)

    @router.post("/nutrition/recipe-math")
    def nutrition_recipe_math(body: RecipeMathBody):
        from core.assistant_platform.nutrition import totals
        def calculate():
            values = totals(body.ingredients)
            return {"perRecipe": values, "perServing": {key: round(value / body.servings, 2) if value is not None else None for key, value in values.items()}}
        return call(calculate)

    # ---- Training program: live daily tracker (core/assistant_platform/training.py)
    @router.get("/training")
    def training_overview(month: str = Query(default="", max_length=7)):
        from core.assistant_platform.training import overview
        return call(lambda: overview(get().store, month=month))

    @router.get("/training/day")
    def training_day(day: str = Query(min_length=10, max_length=10)):
        from core.assistant_platform.training import day_view
        return call(lambda: day_view(day, get().store))

    @router.post("/training/profile")
    def training_profile(body: TrainingBody):
        from core.assistant_platform.training import training
        return call(lambda: training().set_profile(body.changes))

    @router.post("/training/program")
    def training_program(body: ProgramBody):
        from core.assistant_platform.training import training
        return call(lambda: training().set_program(body.planId, body.weekdays))

    @router.post("/training/day")
    def training_log(body: TrainingBody, day: str = Query(min_length=10, max_length=10)):
        from core.assistant_platform.training import training
        return call(lambda: training().log_day(day, body.changes))

    @router.post("/training/quick-log")
    def training_quick_log(body: TrainingActualBody):
        from core.assistant_platform.chat_actions import fitness_quick_log
        from core.research.analyze import run_local
        return call(lambda: fitness_quick_log(body.text, run_local))

    @router.post("/training/actual")
    def training_actual(body: TrainingActualBody, day: str = Query(min_length=10, max_length=10)):
        from core.assistant_platform.training import parse_actual, training
        from core.research.analyze import run_local
        tracker = training()
        return call(lambda: tracker.log_day(day, {"actual": parse_actual(body.text, run_local, tracker.load()["profile"].get("weightLb")) if body.text.strip() else None}))

    @router.post("/training/source")
    def training_source(body: TrainingSourceBody):
        from core.assistant_platform.training import training
        if body.remove:
            return call(lambda: (training().remove_source(body.url), {"ok": True})[1])
        from core.research.analyze import run_local
        return call(lambda: training().add_source(body.url, ask=run_local))

    @router.post("/training/improve")
    def training_improve():
        from core.assistant_platform.training import improve_program
        from core.research.analyze import run_local
        return call(lambda: improve_program(get().store, run_local))

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
