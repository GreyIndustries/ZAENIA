from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
import os
from typing import Any

import requests


GOOGLE_ROUTES_URL = (
    "https://routes.googleapis.com/"
    "directions/v2:computeRoutes"
)

GOOGLE_API_KEY_ENV = (
    "GOOGLE_MAPS_API_KEY"
)

DEFAULT_TIMEOUT_SECONDS = 15


def get_google_api_key() -> str:
    """
    Read the Google Maps Routes API credential from the
    Windows environment.

    The key is never stored in ZÆNIA source code.
    """

    api_key = str(
        os.environ.get(
            GOOGLE_API_KEY_ENV,
            "",
        )
    ).strip()

    if not api_key:
        raise RuntimeError(
            "Missing GOOGLE_MAPS_API_KEY."
        )

    return api_key


def parse_google_duration(
    value: str | None,
) -> float:
    """
    Convert Google's protobuf duration format:

        123.45s

    into seconds.
    """

    if not value:
        return 0.0

    text = str(
        value
    ).strip()

    if not text.endswith(
        "s"
    ):
        raise ValueError(
            "Unexpected Google duration format: "
            f"{text}"
        )

    return float(
        text[:-1]
    )


def round_minutes(
    seconds: float,
) -> int:
    """
    Convert seconds to a spoken whole-minute value.
    """

    return max(
        0,
        round(
            seconds / 60.0
        ),
    )


def meters_to_miles(
    meters: int | float,
) -> float:
    return round(
        float(
            meters
        )
        / 1609.344,
        1,
    )


def build_traffic_summary(
    *,
    traffic_minutes: int,
    baseline_minutes: int,
    delay_minutes: int,
    distance_miles: float,
) -> str:
    """
    Build a concise CarPlay traffic sentence.

    No motivational or personality filler belongs here.
    """

    if delay_minutes <= 2:
        return (
            "Google Maps shows traffic moving normally. "
            f"The drive is about {traffic_minutes} minutes "
            f"over {distance_miles:g} miles."
        )

    if delay_minutes <= 7:
        return (
            "Google Maps shows some traffic. "
            f"The drive is about {traffic_minutes} minutes, "
            f"with roughly {delay_minutes} minutes of delay."
        )

    if delay_minutes <= 15:
        return (
            "Google Maps shows heavier traffic. "
            f"The drive is about {traffic_minutes} minutes, "
            f"around {delay_minutes} minutes slower "
            "than normal."
        )

    return (
        "Google Maps shows significant traffic. "
        f"The drive is about {traffic_minutes} minutes, "
        f"around {delay_minutes} minutes slower "
        "than normal."
    )


def get_google_maps_traffic(
    origin: str,
    destination: str,
    *,
    routing_preference: str = "TRAFFIC_AWARE_OPTIMAL",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    Request a traffic-aware driving route from Google Maps.

    Google accepts terminal waypoints as human-readable
    addresses, Place IDs, or coordinates. ZÆNIA uses an
    address/string here so this provider is easy to connect
    to later calendar/location intelligence.

    Returned structure is provider-neutral enough for a later
    Google → WSDOT fallback layer.
    """

    origin = origin.strip()
    destination = destination.strip()

    if not origin:
        raise ValueError(
            "Traffic origin cannot be empty."
        )

    if not destination:
        raise ValueError(
            "Traffic destination cannot be empty."
        )

    api_key = (
        get_google_api_key()
    )

    request_body = {
        "origin": {
            "address": origin,
        },
        "destination": {
            "address": destination,
        },
        "travelMode": "DRIVE",
        "routingPreference": (
            routing_preference
        ),
        "computeAlternativeRoutes": False,
        "languageCode": "en-US",
        "units": "IMPERIAL",
    }

    headers = {
        "Content-Type": (
            "application/json"
        ),
        "X-Goog-Api-Key": (
            api_key
        ),
        "X-Goog-FieldMask": (
            "routes.duration,"
            "routes.staticDuration,"
            "routes.distanceMeters"
        ),
    }

    response = requests.post(
        GOOGLE_ROUTES_URL,
        json=request_body,
        headers=headers,
        timeout=timeout_seconds,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "Google Routes request failed "
            f"with HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    payload = (
        response.json()
    )

    routes = (
        payload.get(
            "routes",
            [],
        )
        or []
    )

    if not routes:
        raise RuntimeError(
            "Google Maps returned no route."
        )

    route = (
        routes[0]
    )

    traffic_seconds = (
        parse_google_duration(
            route.get(
                "duration"
            )
        )
    )

    baseline_seconds = (
        parse_google_duration(
            route.get(
                "staticDuration"
            )
        )
    )

    distance_meters = int(
        route.get(
            "distanceMeters",
            0,
        )
        or 0
    )

    if traffic_seconds <= 0:
        raise RuntimeError(
            "Google Maps returned an invalid "
            "traffic duration."
        )

    if baseline_seconds <= 0:
        baseline_seconds = (
            traffic_seconds
        )

    delay_seconds = max(
        0.0,
        traffic_seconds
        - baseline_seconds,
    )

    traffic_minutes = (
        round_minutes(
            traffic_seconds
        )
    )

    baseline_minutes = (
        round_minutes(
            baseline_seconds
        )
    )

    delay_minutes = (
        round_minutes(
            delay_seconds
        )
    )

    distance_miles = (
        meters_to_miles(
            distance_meters
        )
    )

    summary = (
        build_traffic_summary(
            traffic_minutes=(
                traffic_minutes
            ),
            baseline_minutes=(
                baseline_minutes
            ),
            delay_minutes=(
                delay_minutes
            ),
            distance_miles=(
                distance_miles
            ),
        )
    )

    return {
        "success": True,
        "provider": (
            "google_maps_routes"
        ),
        "origin": origin,
        "destination": destination,
        "traffic_minutes": (
            traffic_minutes
        ),
        "baseline_minutes": (
            baseline_minutes
        ),
        "delay_minutes": (
            delay_minutes
        ),
        "distance_miles": (
            distance_miles
        ),
        "routing_preference": (
            routing_preference
        ),
        "summary": (
            summary
        ),
    }


def run_self_test(
    origin: str,
    destination: str,
) -> bool:
    """
    Run one live Google Maps traffic request.

    The API key itself is never printed.
    """

    print()

    print(
        "ZÆNIA Google Maps Traffic Self-Test"
    )

    print()

    print(
        "Provider:",
        "Google Maps Routes API",
    )

    print(
        "Origin:",
        origin,
    )

    print(
        "Destination:",
        destination,
    )

    print()

    try:
        result = (
            get_google_maps_traffic(
                origin,
                destination,
            )
        )

    except Exception as error:
        print(
            "Google Maps traffic: FAIL"
        )

        print(
            "Error:",
            error,
        )

        return False

    print(
        "Google Maps traffic: PASS"
    )

    print(
        "Traffic-aware ETA:",
        f"{result['traffic_minutes']} minutes",
    )

    print(
        "Baseline ETA:",
        f"{result['baseline_minutes']} minutes",
    )

    print(
        "Current delay:",
        f"{result['delay_minutes']} minutes",
    )

    print(
        "Distance:",
        f"{result['distance_miles']} miles",
    )

    print()

    print(
        "Spoken summary:"
    )

    print(
        result[
            "summary"
        ]
    )

    return True


@owner_command('traffic.read')
def main() -> None:
    parser = (
        argparse.ArgumentParser(
            description=(
                "ZÆNIA Google Maps live "
                "traffic provider."
            )
        )
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    test_parser = (
        subparsers.add_parser(
            "self-test"
        )
    )

    test_parser.add_argument(
        "--origin",
        required=True,
    )

    test_parser.add_argument(
        "--destination",
        required=True,
    )

    args = (
        parser.parse_args()
    )

    if args.command == "self-test":
        passed = (
            run_self_test(
                origin=(
                    args.origin
                ),
                destination=(
                    args.destination
                ),
            )
        )

        if not passed:
            raise SystemExit(
                1
            )


if __name__ == "__main__":
    main()