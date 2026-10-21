import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PERSONALITY_PATH = PROJECT_ROOT / "core" / "personality" / "personality.yaml"
FEEDBACK_LOG_PATH = PROJECT_ROOT / "core" / "personality" / "feedback_log.jsonl"
CARPLAY_MESSAGES_PATH = PROJECT_ROOT / "core" / "carplay" / "messages.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML file: {path}")

    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    from core.foundation.local_entry import owner_execute
    from core.foundation.security.io import atomic_write, reject_link
    def validate(p):
        if set(p) != {"path", "data"} or not isinstance(p["data"], dict):
            raise ValueError("Invalid personality update.")
        target = Path(p["path"]).absolute()
        reject_link(target)
        if target not in {PERSONALITY_PATH.absolute(),CARPLAY_MESSAGES_PATH.absolute()}:
            raise PermissionError("Personality writer cannot modify other files.")
        if target == PERSONALITY_PATH.absolute():
            current = load_yaml(target)
            if p["data"].get("core_identity") != current.get("core_identity"):
                raise PermissionError("Personality learning cannot change core identity.")
        return {"path":str(target),"data":p["data"]}
    def commit(p):
        validate(p)
        atomic_write(Path(p["path"]),yaml.safe_dump(p["data"],sort_keys=False,allow_unicode=True).encode("utf-8"))
    owner_execute("personality.write",{"path":str(Path(path).absolute()),"data":data},commit,validate)


def clean_text(text: str) -> str:
    return " ".join(text.strip().split())


def add_unique(items: list[str], text: str) -> bool:
    cleaned = clean_text(text)

    if not cleaned:
        raise ValueError("Text cannot be empty.")

    existing = {item.lower() for item in items}

    if cleaned.lower() in existing:
        return False

    items.append(cleaned)
    return True


def log_feedback(note: str, category: str = "general") -> None:
    FEEDBACK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "note": note,
    }

    with FEEDBACK_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def add_preference(text: str) -> bool:
    data = load_yaml(PERSONALITY_PATH)
    preferences = data.setdefault("custom", {}).setdefault("preferences", [])

    added = add_unique(preferences, text)
    save_yaml(PERSONALITY_PATH, data)

    if added:
        log_feedback(f"Preference added: {text}", "preference")

    return added


def add_avoid(text: str) -> bool:
    data = load_yaml(PERSONALITY_PATH)
    avoid = data.setdefault("custom", {}).setdefault("avoid", [])

    added = add_unique(avoid, text)
    save_yaml(PERSONALITY_PATH, data)

    if added:
        log_feedback(f"Avoid added: {text}", "avoid")

    return added


def get_summary() -> dict[str, list[str]]:
    data = load_yaml(PERSONALITY_PATH)

    preferred = []
    avoided = []

    preferred += data.get("tone", {}).get("preferred", [])
    preferred += data.get("decision_making", {}).get("priorities", [])
    preferred += data.get("carplay", {}).get("preferred", [])
    preferred += data.get("custom", {}).get("preferences", [])

    avoided += data.get("tone", {}).get("avoid", [])
    avoided += data.get("decision_making", {}).get("avoid", [])
    avoided += data.get("carplay", {}).get("avoid", [])
    avoided += data.get("custom", {}).get("avoid", [])

    return {
        "preferred": preferred,
        "avoided": avoided,
    }


def apply_to_carplay() -> dict[str, int]:
    personality = load_yaml(PERSONALITY_PATH)
    carplay = load_yaml(CARPLAY_MESSAGES_PATH)

    profile = carplay.setdefault("profile", {})
    style = profile.setdefault("style", [])
    avoid_phrases = profile.setdefault("avoid_phrases", [])

    before_style = len(style)
    before_avoid = len(avoid_phrases)

    for item in personality.get("tone", {}).get("preferred", []):
        add_unique(style, item)

    for item in personality.get("carplay", {}).get("preferred", []):
        add_unique(style, item)

    for item in personality.get("custom", {}).get("preferences", []):
        add_unique(style, item)

    for item in personality.get("tone", {}).get("avoid", []):
        add_unique(avoid_phrases, item)

    for item in personality.get("carplay", {}).get("avoid", []):
        add_unique(avoid_phrases, item)

    for item in personality.get("custom", {}).get("avoid", []):
        add_unique(avoid_phrases, item)

    save_yaml(CARPLAY_MESSAGES_PATH, carplay)
    log_feedback("Applied personality profile to CarPlay config.", "carplay")

    return {
        "style_added": len(style) - before_style,
        "avoid_added": len(avoid_phrases) - before_avoid,
    }


def read_feedback_log(limit: int = 20) -> list[dict[str, Any]]:
    if not FEEDBACK_LOG_PATH.exists():
        return []

    lines = FEEDBACK_LOG_PATH.read_text(encoding="utf-8").splitlines()
    entries = []

    for line in lines[-limit:]:
        if line.strip():
            entries.append(json.loads(line))

    return entries