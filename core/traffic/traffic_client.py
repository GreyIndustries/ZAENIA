import os
from typing import Any

import requests


TRAFFIC_FLOWS_URL = "https://wsdot.wa.gov/Traffic/api/TrafficFlow/TrafficFlowREST.svc/GetTrafficFlowsAsJson"


I5_AREA_KEYWORDS = [
    "i-5",
    "i 5",
    "interstate 5",
    "lacey",
    "jblm",
    "joint base lewis",
    "mcchord",
    "dupont",
    "lakewood",
    "tacoma",
    "nisqually",
    "steilacoom",
    "mounts road",
]


def get_wsdot_api_key() -> str:
    api_key = os.getenv("WSDOT_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Missing WSDOT_API_KEY. Save it to Windows before using traffic tools."
        )

    return api_key


def fetch_traffic_flows() -> list[dict[str, Any]]:
    api_key = get_wsdot_api_key()

    response = requests.get(
        TRAFFIC_FLOWS_URL,
        params={"AccessCode": api_key},
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("Unexpected WSDOT traffic flow response format.")

    return data


def item_to_search_text(item: dict[str, Any]) -> str:
    parts = []

    for key, value in item.items():
        if isinstance(value, (str, int, float)):
            parts.append(str(value))

        if isinstance(value, dict):
            for inner_value in value.values():
                if isinstance(inner_value, (str, int, float)):
                    parts.append(str(inner_value))

    return " ".join(parts).lower()


def filter_i5_area_flows(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []

    for item in flows:
        search_text = item_to_search_text(item)

        if any(keyword in search_text for keyword in I5_AREA_KEYWORDS):
            matches.append(item)

    return matches


def summarize_flow_conditions(flows: list[dict[str, Any]]) -> str:
    if not flows:
        return "No matching I-5 traffic flow sensors were found for the JBLM, Lacey, or Tacoma area."

    condition_counts: dict[str, int] = {}

    for item in flows:
        condition = (
            item.get("CurrentFlow")
            or item.get("Flow")
            or item.get("Status")
            or item.get("TrafficStatus")
            or "Unknown"
        )

        condition = str(condition)
        condition_counts[condition] = condition_counts.get(condition, 0) + 1

    worst_order = ["StopAndGo", "Heavy", "Moderate", "WideOpen", "Unknown"]

    worst_condition = "Unknown"

    for condition in worst_order:
        if condition in condition_counts:
            worst_condition = condition
            break

    readable = {
        "WideOpen": "clear",
        "Moderate": "moderate",
        "Heavy": "heavy",
        "StopAndGo": "stop-and-go",
        "Unknown": "unclear",
    }.get(worst_condition, worst_condition)

    return (
        f"I-5 traffic check: {readable} traffic reported across "
        f"{len(flows)} matching sensor points near the JBLM, Lacey, and Tacoma corridor."
    )


def get_i5_traffic_summary() -> dict[str, Any]:
    all_flows = fetch_traffic_flows()
    i5_flows = filter_i5_area_flows(all_flows)
    summary = summarize_flow_conditions(i5_flows)

    return {
        "total_flow_points": len(all_flows),
        "matched_i5_points": len(i5_flows),
        "summary": summary,
        "matched_flows": i5_flows,
    }