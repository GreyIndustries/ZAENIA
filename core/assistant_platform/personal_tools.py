"""Local project, music and fitness records. Sources never confer permissions.

All edits are explicit, revision checked and covered by the portable profile.
No health targets, calorie expenditure or platform statistics are invented.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator

from core.assistant_platform.store import Conflict, now_text

CATEGORIES = ("Science", "Biology", "Tech", "Bio tech", "Bio chem", "Nuclear physics", "Nano technology", "AI")
COLLECTIONS = {"workbench": "workbench", "experiments": "workbench_experiment", "music": "music", "food": "fitness_food", "recipes": "fitness_recipe", "exercise": "fitness_exercise", "plans": "fitness_plan", "fitness-settings": "fitness_settings", "inventory": "fitness_inventory", "meal-plans": "fitness_meal_plan"}


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=160)
    archived: bool = False

    @field_validator("title")
    @classmethod
    def title_text(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Use a readable title.")
        return value.strip()


def public_url(value):
    if not value:
        return value
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTPS link without credentials.")
    return value


class Stroke(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    color: Literal["#f2b95f", "#75cfff", "#a5eeaa", "#f49cb8", "#eeeeee"] = "#f2b95f"
    width: FiniteFloat = Field(default=2.0, ge=1, le=12)
    points: list[list[FiniteFloat]] = Field(min_length=1, max_length=5000)

    @field_validator("points")
    @classmethod
    def coordinates(cls, points):
        if any(len(point) != 2 or not 0 <= point[0] <= 1000 or not 0 <= point[1] <= 600 for point in points):
            raise ValueError("Sketch points must fit the drawing surface.")
        return points


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    day: int = Field(ge=0, le=3650)
    values: list[FiniteFloat | None] = Field(min_length=1, max_length=4)
    note: str = Field(default="", max_length=300)


class Experiment(Record):
    """Workbench "Experiment log" (Grey's pick C): a hypothesis, what changes, what's held the same, and readings."""
    projectId: str = Field(default="", max_length=32)
    hypothesis: str = Field(default="", max_length=1000)
    variable: str = Field(default="", max_length=160)
    constants: str = Field(default="", max_length=300)
    measured: str = Field(default="", max_length=160)
    unit: str = Field(default="", max_length=20)
    groups: list[str] = Field(default_factory=lambda: ["A", "B"], min_length=1, max_length=4)
    plannedDays: int = Field(default=14, ge=1, le=3650)
    readings: list[Reading] = Field(default_factory=list, max_length=500)
    result: str = Field(default="", max_length=3000)

    @field_validator("groups")
    @classmethod
    def group_names(cls, value):
        if any(not item.strip() or len(item) > 40 for item in value):
            raise ValueError("Name each group in a few words.")
        return [item.strip() for item in value]


Subject = Literal["Science", "Biology", "Tech", "Bio tech", "Bio chem", "Nuclear physics", "Nano technology", "AI"]


class Project(Record):
    category: Subject = "Tech"
    # Cross-tags: other subjects the project also belongs to (it shows under each of them).
    tags: list[Subject] = Field(default_factory=list, max_length=8)
    # Notes for this project: ids of notes in the shared Notes store.
    noteIds: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("noteIds")
    @classmethod
    def note_ids(cls, value):
        if any(not re.fullmatch(r"[a-f0-9]{32}", item) for item in value):
            raise ValueError("Linked notes must be note ids.")
        return list(dict.fromkeys(value))
    color: Literal["amber", "blue", "green", "rose", "violet"] = "amber"
    size: Literal["small", "medium", "large"] = "medium"
    status: Literal["Idea", "Research", "Prototype", "Testing", "Complete"] = "Idea"
    body: str = Field(default="", max_length=30000)
    blueprint: str = Field(default="", max_length=2000)
    scenarios: str = Field(default="", max_length=10000)
    unit: Literal["mm", "cm", "m", "in", "ft"] = "mm"
    boardWidth: FiniteFloat = Field(default=100.0, gt=0, le=1000000)
    strokes: list[Stroke] = Field(default_factory=list, max_length=300)
    referenceImage: str = Field(default='', max_length=800100)

    @field_validator('referenceImage')
    @classmethod
    def raster_reference(cls, value):
        if not value:
            return value
        import base64
        import io
        from PIL import Image
        match=re.fullmatch(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)',value)
        if not match:
            raise ValueError('Import a PNG or JPEG reference image.')
        try:
            raw=base64.b64decode(match[2],validate=True)
            if len(raw)>600000:raise ValueError('Use a reference image under 600 KB.')
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!=('PNG' if match[1]=='png' else 'JPEG') or image.width*image.height>16000000:
                    raise ValueError('Use a PNG/JPEG reference below 16 megapixels.')
                image.verify()
        except Exception as error:
            raise ValueError('Reference image could not be read; use a PNG or JPEG under 600 KB and 16 megapixels.') from error
        return value

    @field_validator("strokes")
    @classmethod
    def sketch_limit(cls, strokes):
        if sum(len(stroke.points) for stroke in strokes) > 20000:
            raise ValueError("Sketch is full; start a separate project for another drawing.")
        return strokes


PLATFORMS = ("YouTube", "SoundCloud", "Spotify", "Apple Music")


class Release(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    platform: Literal["YouTube", "SoundCloud", "Spotify", "Apple Music"]
    url: str = Field(max_length=2000)
    _url = field_validator("url")(public_url)


class Statistics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    platform: Literal["YouTube", "SoundCloud", "Spotify", "Apple Music"]
    date: str
    metric: Literal["Plays", "Views", "Listeners", "Likes", "Saves"]
    value: int = Field(ge=0, le=10**12)
    source: str = Field(min_length=1, max_length=500)
    # Manual observations remain manual even if a restored file claims otherwise.
    method: Literal["manual"] = "manual"

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        return date.fromisoformat(value).isoformat()


MUSIC_CHECKLIST = ("Lyrics final", "Vocals recorded", "Mix approved", "Master exported", "Artwork ready", "Distribution submitted")


class StudioSession(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    date: str
    minutes: int = Field(default=0, ge=0, le=1440)
    note: str = Field(default="", max_length=300)

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        return date.fromisoformat(value).isoformat()


class Music(Record):
    stage: Literal["Idea", "Writing", "Recording", "Mixing", "Mastering", "Released"] = "Idea"
    projectFile: str = Field(default="", max_length=2000)
    bpm: FiniteFloat | None = Field(default=None, gt=0, le=1000)
    key: str = Field(default="", max_length=40)
    body: str = Field(default="", max_length=30000)
    releases: list[Release] = Field(default_factory=list, max_length=12)
    stats: list[Statistics] = Field(default_factory=list, max_length=300)
    # Song workspace (2026-10-28): lyrics, planned release date, release checklist, studio sessions, card colour.
    lyrics: str = Field(default="", max_length=30000)
    releaseDate: str = Field(default="", max_length=10)
    checklist: dict[str, bool] = Field(default_factory=dict, max_length=len(MUSIC_CHECKLIST))
    sessions: list[StudioSession] = Field(default_factory=list, max_length=300)
    art: Literal["amber", "blue", "green", "rose", "violet", "teal"] = "amber"

    @field_validator("releaseDate")
    @classmethod
    def release_date(cls, value):
        return date.fromisoformat(value).isoformat() if value else ""

    @field_validator("checklist")
    @classmethod
    def checklist_items(cls, value):
        if any(key not in MUSIC_CHECKLIST for key in value):
            raise ValueError("Unknown checklist item.")
        return value


# Live analytics: what each platform offers, so the Music tab can show what a connection needs.
# Nothing here connects; manual statistics stay the source until a connector is built and Grey adds its keys.
MUSIC_CONNECTIONS = [
    {"platform": "YouTube", "metric": "Views", "status": "not_connected",
     "needs": "A YouTube Data API key (Google Cloud, free quota). Gives public view, like and comment counts per video."},
    {"platform": "Spotify", "metric": "Plays", "status": "not_connected",
     "needs": "Spotify's public Web API has no stream counts; Spotify for Artists has no public API. Live data would come from its CSV export."},
    {"platform": "SoundCloud", "metric": "Plays", "status": "not_connected",
     "needs": "A SoundCloud API app (client id and secret; new apps need SoundCloud's approval). Gives play, like and repost counts."},
    {"platform": "Apple Music", "metric": "Plays", "status": "not_connected",
     "needs": "Apple Music for Artists has no public API. Live data would come from its CSV export."},
]


def music_overview(store) -> dict:
    """Every active song in full, for the Music dashboard, studio board and song workspace."""
    songs = [row for row in store.list(COLLECTIONS["music"]) if not row.get("archived")]
    songs.sort(key=lambda row: row.get("updatedAt", ""), reverse=True)
    return {"songs": songs[:300], "checklist": list(MUSIC_CHECKLIST), "connections": MUSIC_CONNECTIONS}


class Dated(Record):
    date: str

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        return date.fromisoformat(value).isoformat()


class Food(Dated):
    calories: FiniteFloat = Field(ge=0, le=20000)
    protein: FiniteFloat = Field(ge=0, le=2000)
    fiber: FiniteFloat = Field(ge=0, le=1000)
    source: str = Field(default="Food label / manual entry", max_length=300)
    carbs: FiniteFloat | None = Field(default=None, ge=0, le=5000)
    fat: FiniteFloat | None = Field(default=None, ge=0, le=2000)
    saturatedFat: FiniteFloat | None = Field(default=None, ge=0, le=1000)
    sugars: FiniteFloat | None = Field(default=None, ge=0, le=2000)
    sodiumMg: FiniteFloat | None = Field(default=None, ge=0, le=100000)
    cholesterolMg: FiniteFloat | None = Field(default=None, ge=0, le=100000)
    items: list[dict] = Field(default_factory=list, max_length=50)
    sourceDetails: list[dict] = Field(default_factory=list, max_length=50)


class Recipe(Record):
    category: str = Field(default="Meal", max_length=60)
    mealTypes: list[Literal["Breakfast", "Lunch", "Dinner"]] = Field(default_factory=list, max_length=3)
    servings: FiniteFloat = Field(default=1, gt=0, le=100)
    ingredients: list[dict] = Field(default_factory=list, max_length=100)
    instructions: str = Field(default="", max_length=10000)
    source: str = Field(default="Owner recipe", max_length=300)


class Inventory(Record):
    """A package/food with owner-confirmed portion facts and tracked servings."""
    barcode: str = Field(default="", max_length=32)
    source: str = Field(default="Owner-verified label", max_length=300)
    sourceUrl: str = Field(default="", max_length=2000)
    sourceName: str = Field(default="", max_length=160)
    servingLabel: str = Field(default="1 serving", max_length=100)
    servingGrams: FiniteFloat = Field(default=0, ge=0, le=100000)
    servingsTotal: FiniteFloat = Field(gt=0, le=10000)
    servingsUsed: FiniteFloat = Field(default=0, ge=0, le=10000)
    nutrients: dict[str, FiniteFloat | None] = Field(default_factory=dict)
    checkedAt: str = Field(default="", max_length=40)
    _url = field_validator("sourceUrl")(public_url)

    @field_validator("nutrients")
    @classmethod
    def nutrient_fields(cls, value):
        allowed = {"calories", "protein", "fiber", "carbs", "fat", "saturatedFat", "sugars", "sodiumMg", "cholesterolMg"}
        if set(value) - allowed or any(number is not None and number < 0 for number in value.values()):
            raise ValueError("Use non-negative nutrition facts with recognized nutrient names.")
        return value

    @field_validator("servingsUsed")
    @classmethod
    def used_within_total(cls, value, info):
        total = info.data.get("servingsTotal")
        if total is not None and value > total:
            raise ValueError("Used servings cannot exceed the amount available.")
        return value


class MealSlot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=64)
    date: str
    mealType: Literal["Breakfast", "Lunch", "Dinner"]
    itemType: Literal["inventory", "recipe"]
    itemId: str = Field(min_length=1, max_length=32)
    servings: FiniteFloat = Field(gt=0, le=1000)
    checkInAt: str = Field(default="12:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    status: Literal["scheduled", "eaten", "skipped"] = "scheduled"
    loggedFoodId: str = Field(default="", max_length=32)
    reminderId: str = Field(default="", max_length=32)

    @field_validator("date")
    @classmethod
    def slot_date(cls, value):
        return date.fromisoformat(value).isoformat()


class MealPlan(Record):
    weekStart: str
    slots: list[MealSlot] = Field(default_factory=list, max_length=300)

    @field_validator("weekStart")
    @classmethod
    def monday_start(cls, value):
        parsed = date.fromisoformat(value)
        if parsed.weekday() != 0:
            raise ValueError("Meal plan weeks start on Monday.")
        return parsed.isoformat()

    @field_validator("slots")
    @classmethod
    def slots_in_week(cls, value, info):
        start = date.fromisoformat(info.data["weekStart"]) if info.data.get("weekStart") else None
        if start and any((slot_day := date.fromisoformat(slot.date)).isocalendar()[:2] != start.isocalendar()[:2] for slot in value):
            raise ValueError("Every meal must be inside the selected Monday–Sunday week.")
        if len({slot.id for slot in value}) != len(value):
            raise ValueError("Meal slot ids must be unique.")
        return value


class Exercise(Dated):
    minutes: FiniteFloat = Field(gt=0, le=1440)
    calories: FiniteFloat = Field(ge=0, le=20000)
    source: Literal["Manual estimate", "Device estimate"] = "Manual estimate"
    notes: str = Field(default="", max_length=2000)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    exercise: str = Field(min_length=1, max_length=300)
    prescription: str = Field(default="", max_length=500)
    done: bool = False
    sets: int | None = Field(default=None, ge=1, le=100)
    reps: str = Field(default="", max_length=80)
    duration: str = Field(default="", max_length=80)
    restSeconds: int | None = Field(default=None, ge=0, le=3600)
    equipment: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=1000)


class TrainingSession(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    date: str
    steps: list[Step] = Field(max_length=100)

    @field_validator('date')
    @classmethod
    def valid_date(cls, value):
        return date.fromisoformat(value).isoformat()


class Plan(Record):
    sourceUrl: str = Field(default="", max_length=2000)
    sourceText: str = Field(default="", max_length=30000)
    sourceName: str = Field(default="", max_length=200)
    schedule: str = Field(default="", max_length=500)
    steps: list[Step] = Field(default_factory=list, max_length=100)
    sessions: list[TrainingSession] = Field(default_factory=list, max_length=200)
    _url = field_validator("sourceUrl")(public_url)


class FitnessSettings(Record):
    proteinTarget: FiniteFloat | None = Field(default=None, ge=0, le=2000)
    fiberTarget: FiniteFloat | None = Field(default=None, ge=0, le=1000)
    # Baseline excludes exercise logged here, to avoid counting it twice.
    baselineCalories: FiniteFloat | None = Field(default=None, ge=0, le=20000)


SCHEMAS = {"workbench": Project, "experiments": Experiment, "music": Music, "food": Food, "recipes": Recipe, "exercise": Exercise, "plans": Plan, "fitness-settings": FitnessSettings, "inventory": Inventory, "meal-plans": MealPlan}


def validate_record(collection, body):
    if collection not in SCHEMAS:
        raise ValueError("Unknown personal collection.")
    return SCHEMAS[collection].model_validate(body).model_dump()


class PersonalTools:
    def __init__(self, store):
        self.store = store

    def save(self, collection, body, identifier=None, revision=None):
        payload = validate_record(collection, body)
        if identifier:
            if not re.fullmatch(r"[a-f0-9]{32}", identifier) or type(revision) is not int or revision < 1:
                raise ValueError("Refresh the item before saving an edit.")
            old = self.store.get(COLLECTIONS[collection], identifier)
            if old is None:
                raise Conflict("That item is no longer available.")
        else:
            if revision is not None:
                raise ValueError("New items cannot have an existing revision.")
            old = None
        return self.store.put(COLLECTIONS[collection], {**payload, "createdAt": old["createdAt"] if old else now_text()}, identifier, revision=revision if identifier else 0)

    def listing(self, collection, *, day="", archived=False, offset=0):
        if collection not in COLLECTIONS:
            raise ValueError("Unknown personal collection.")
        if day:
            date.fromisoformat(day)
        rows = [row for row in self.store.list(COLLECTIONS[collection]) if row.get("archived", False) == archived and (not day or row.get("date") == day)]
        # Lists don't download every drawing, source document and history.
        fields = {"id", "revision", "updatedAt", "createdAt", "title", "archived", "category", "mealTypes", "tags", "color", "size", "status", "stage", "date", "weekStart", "slots", "barcode", "servingLabel", "servingGrams", "servingsTotal", "servingsUsed", "nutrients", "checkedAt", "sourceUrl", "sourceName", "calories", "protein", "fiber", "minutes", "source", "proteinTarget", "fiberTarget", "baselineCalories", "servings", "ingredients", "carbs", "fat", "saturatedFat", "sugars", "sodiumMg", "cholesterolMg", "items", "sourceDetails"}
        items = [{key: value for key, value in row.items() if key in fields} for row in rows[offset:offset+100]]
        return {"items": items, "total": len(rows), "nextOffset": offset+100 if offset+100 < len(rows) else None}

    def fitness_summary(self, day):
        date.fromisoformat(day)
        food = [item for item in self.store.list('fitness_food') if item.get('date') == day and not item.get('archived')]
        exercise = [item for item in self.store.list('fitness_exercise') if item.get('date') == day and not item.get('archived')]
        settings = next((item for item in self.store.list('fitness_settings') if not item.get('archived')), {})
        known = lambda key: [item[key] for item in food if item.get(key) is not None]
        coverage = {key: {'known': len(known(key)), 'of': len(food)} for key in ('carbs', 'fat', 'saturatedFat', 'sugars', 'sodiumMg', 'cholesterolMg')}
        return {'coverage': coverage,
                **{f'{key}Known': (round(sum(known(key)), 1) if known(key) else None) for key in coverage},
                'calories':sum(item['calories'] for item in food),'protein':sum(item['protein'] for item in food),
                'fiber':sum(item['fiber'] for item in food),'carbs':sum(item['carbs'] for item in food) if all(item.get('carbs') is not None for item in food) else None,
                'fat':sum(item['fat'] for item in food) if all(item.get('fat') is not None for item in food) else None,
                'saturatedFat':sum(item['saturatedFat'] for item in food) if all(item.get('saturatedFat') is not None for item in food) else None,
                'sugars':sum(item['sugars'] for item in food) if all(item.get('sugars') is not None for item in food) else None,
                'sodiumMg':sum(item['sodiumMg'] for item in food) if all(item.get('sodiumMg') is not None for item in food) else None,
                'cholesterolMg':sum(item['cholesterolMg'] for item in food) if all(item.get('cholesterolMg') is not None for item in food) else None,'burned':sum(item['calories'] for item in exercise),
                'baseline':settings.get('baselineCalories'),'proteinTarget':settings.get('proteinTarget'),'fiberTarget':settings.get('fiberTarget')}


def personal_answer(message, authorize):
    query = ' '.join(message.split()).strip(' .!?')
    search = re.fullmatch(r'(?:please )?(?:search|find)(?: in)? my workbench(?: for| about|:) +(.+)', query, re.I)
    projects = re.fullmatch(r'(?:show|list|what(?:\'s| is)|how(?:\'s| is)) (?:in )?my (workbench(?: projects)?|music(?: projects| progress)?|songs?)', query, re.I)
    nutrition = bool(re.fullmatch(r'(?:show|read|check|summarize) my (?:nutrition|fitness|food intake|calories|protein|fiber)(?: today)?',query,re.I) or re.fullmatch(r'how much (?:protein|fiber|calories) (?:have i|did i) (?:log|logged|eat|eaten|consume|consumed)(?: today)?',query,re.I))
    if not (search or projects or nutrition):
        return None
    if authorize is None or authorize('memory.read') is False:
        return 'Personal workspace records are unavailable with the current permissions.'
    from core.assistant_platform.service import platform
    tools = PersonalTools(platform().store)
    if nutrition:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        day = datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
        totals = tools.fitness_summary(day)
        answer = f"Logged today: {totals['calories']:g} kcal, {totals['protein']:g} g protein and {totals['fiber']:g} g fiber. Logged exercise burn: {totals['burned']:g} kcal (estimated). Intake minus exercise: {totals['calories']-totals['burned']:g} kcal; this excludes resting energy and other activity."
        if totals['baseline'] is not None:
            answer += f" With your non-exercise baseline, estimated energy balance is {totals['calories']-totals['burned']-totals['baseline']:g} kcal."
        return answer + f' Source: Fitness & Health logs · {day}. Missing meals or activities are not estimated.'
    collection = 'workbench' if search or projects[1].lower().startswith('workbench') else 'music'
    rows = [item for item in tools.store.list(COLLECTIONS[collection]) if not item.get('archived')]
    if search:
        words = search[1].casefold()
        rows = [item for item in rows if words in (item['title']+' '+item.get('body','')+' '+item.get('scenarios','')).casefold()]
    lines = []
    for item in rows[:5]:
        line = f"{item['title']}: {item.get('status') or item.get('stage')}"
        if collection == 'workbench' and search:
            line += '\n' + item['body'][:1000]
        if collection == 'music':
            for stat in sorted(item.get('stats',[]), key=lambda row: row['date'], reverse=True)[:3]:
                line += f"\n{stat['platform']}: {stat['value']:,} {stat['metric'].lower()} on {stat['date']} (manual; {stat['source']})."
        lines.append(line+f"\nSource: {collection.title()} · saved {item['updatedAt']}")
    return '\n\n'.join(lines) or f'No matching active {collection} records are saved yet.'


def draft_training_plan(content):
    """Extract actual exercise prescriptions; never invent a routine from a URL."""
    if not isinstance(content, str) or not 1 <= len(content) <= 30000:
        raise ValueError("Paste readable training text or a video transcript (up to 30,000 characters).")
    steps = []
    for line in content.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if len(line) > 800:
            continue
        match = re.search(r"\b(?:\d+\s*[x×]\s*\d+|\d+(?:\.\d+)?\s*(?:sets?|reps?|minutes?|mins?|seconds?|secs?|km|miles?)\b)", line, re.I)
        if match:
            name = line[:match.start()].strip(" :–-|")
            if name:
                steps.append({"exercise": name[:300], "prescription": line[match.start():][:500], "done": False})
        if len(steps) == 100:
            break
    return {"steps": steps, "note": "Review the extracted steps and schedule before saving. Only explicit prescriptions were copied." if steps else "No explicit exercise prescriptions found. Add steps manually, or paste the relevant text / video transcript."}
