from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEATHER_CONFIG_PATH = PROJECT_ROOT / "core" / "weather" / "weather_config.yaml"


def load_weather_config() -> dict[str, Any]:
    if not WEATHER_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Weather config not found: {WEATHER_CONFIG_PATH}")

    with WEATHER_CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError("weather_config.yaml is empty or invalid.")

    return data


def parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def get_now_for_config(config: dict[str, Any]) -> datetime:
    timezone_name = config.get("weather_system", {}).get("timezone", "America/Los_Angeles")
    return datetime.now(ZoneInfo(timezone_name))


def is_weekday_duty_time(config: dict[str, Any], now: datetime) -> bool:
    rule = config.get("schedule_rules", {}).get("weekday_duty_hours", {})

    if not rule.get("enabled", False):
        return False

    current_day = now.strftime("%A")
    allowed_days = rule.get("days", [])

    if current_day not in allowed_days:
        return False

    start = parse_time(rule["start_time"])
    end = parse_time(rule["end_time"])

    current_time = now.time()

    return start <= current_time <= end


def select_weather_location() -> dict[str, Any]:
    config = load_weather_config()

    manual = config.get("manual_override", {})
    locations = config.get("locations", {})

    if manual.get("enabled"):
        location_key = manual.get("location_key")

        if location_key and location_key in locations:
            selected = locations[location_key].copy()
            selected["source"] = "manual_override"
            selected["location_key"] = location_key
            return selected

        custom_lookup = manual.get("custom_lookup_name")
        custom_name = manual.get("custom_location_name")

        if custom_lookup:
            return {
                "name": custom_name or custom_lookup,
                "display_label": custom_name or custom_lookup,
                "lookup_name": custom_lookup,
                "latitude": None,
                "longitude": None,
                "source": "manual_override_custom",
                "location_key": "custom",
            }

    now = get_now_for_config(config)

    if is_weekday_duty_time(config, now):
        location_key = config["schedule_rules"]["weekday_duty_hours"]["location_key"]
    else:
        location_key = config.get("default_location_key", "off_duty")

    selected = locations[location_key].copy()
    selected["source"] = "schedule"
    selected["location_key"] = location_key
    selected["selected_at"] = now.isoformat()

    return selected


def build_location_response(location: dict[str, Any]) -> str:
    name = location.get("name", "unknown location")
    label = location.get("display_label", name)

    return f"ZÆNIA weather context is set to {label}."