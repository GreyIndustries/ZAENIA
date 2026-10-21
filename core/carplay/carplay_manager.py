from pathlib import Path
from typing import Any

import yaml


DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

TIME_BLOCKS = ["Morning", "Afternoon", "Night"]


def load_message_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Message config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError("messages.yaml is empty or invalid.")

    return data


def validate_messages(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    messages = data.get("messages", {})
    avoid_phrases = [
        phrase.lower()
        for phrase in data.get("profile", {}).get("avoid_phrases", [])
    ]

    for day in DAYS:
        if day not in messages:
            problems.append(f"Missing day: {day}")
            continue

        for block in TIME_BLOCKS:
            message = messages[day].get(block)

            if not message:
                problems.append(f"Missing message: {day} {block}")
                continue

            lower_message = message.lower()

            for phrase in avoid_phrases:
                if phrase in lower_message:
                    problems.append(
                        f"Avoided phrase found in {day} {block}: {phrase}"
                    )

            if "=" in message:
                problems.append(f"Message contains '=' which breaks shortcut: {day} {block}")

    return problems


def build_carstartup_text(data: dict[str, Any]) -> str:
    messages = data["messages"]
    lines: list[str] = []

    for day in DAYS:
        for block in TIME_BLOCKS:
            key = f"{day}{block}"
            message = messages[day][block].strip()
            lines.append(f"{key}={message}")

    return "\n".join(lines) + "\n"


def write_carstartup_file(output_path: Path, text: str) -> None:
    from core.foundation.local_entry import owner_execute
    from core.foundation.security.io import atomic_write, reject_link
    expected = get_default_onedrive_path().absolute()
    def validate(p):
        if set(p) != {"path", "text"} or not isinstance(p["text"], str):
            raise ValueError("Invalid CarStartup request.")
        candidate = Path(p["path"]).absolute()
        reject_link(candidate)
        if candidate != expected:
            raise PermissionError("Legacy CarStartup writer only writes its configured OneDrive CarStartup.txt.")
        return {"path":str(candidate),"text":p["text"]}
    def commit(p):
        candidate = Path(p["path"])
        validate(p)
        atomic_write(candidate,p["text"].encode("utf-8"))
    owner_execute("files.write", {"path":str(Path(output_path).absolute()),"text":text}, commit, validate)


def get_default_onedrive_path() -> Path:
    home = Path.home()

    candidates = [
        home / "OneDrive" / "CarStartup.txt",
        home / "OneDrive - Personal" / "CarStartup.txt",
        home / "OneDrive" / "Documents" / "CarStartup.txt",
    ]

    for path in candidates:
        if path.parent.exists():
            return path

    return home / "OneDrive" / "CarStartup.txt"