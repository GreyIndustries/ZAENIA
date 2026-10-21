from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.carplay_audio.carplay_audio import get_onedrive_folder
from core.carplay_trigger.carplay_refresh_server import (
    refresh_carplay_briefing,
)


# [comment omitted from source review]
# [comment omitted from source review]
# [comment omitted from source review]
BRIDGE_FOLDER_NAME = "ZÆNIA"
CARPLAY_FOLDER_NAME = "CarPlay"

REQUEST_FILE_NAME = "request.json"
RESPONSE_FILE_NAME = "response.json"

DEFAULT_POLL_SECONDS = 1.0


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_bridge_folder() -> Path:
    """
    Shared OneDrive folder:

        OneDrive
        └── ZÆNIA
            └── CarPlay
    """

    return (
        get_onedrive_folder()
        / BRIDGE_FOLDER_NAME
        / CARPLAY_FOLDER_NAME
    )


def get_request_file() -> Path:
    return get_bridge_folder() / REQUEST_FILE_NAME


def get_response_file() -> Path:
    return get_bridge_folder() / RESPONSE_FILE_NAME


def ensure_bridge_folder() -> None:
    get_bridge_folder().mkdir(
        parents=True,
        exist_ok=True,
    )


def read_json_file(
    path: Path,
) -> dict[str, Any] | None:
    """
    Read a JSON file without crashing if OneDrive is still
    syncing or the file is temporarily incomplete.
    """

    if not path.exists():
        return None

    try:
        text = path.read_text(
            encoding="utf-8-sig",
        )

        data = json.loads(text)

    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None

    if not isinstance(data, dict):
        return None

    return data


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    """
    Write the complete JSON file before replacing the public
    OneDrive version.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        path.name + ".tmp"
    )

    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )

    try:
        temporary_path.write_text(
            text,
            encoding="utf-8",
        )

        temporary_path.replace(path)

    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def validate_request(
    request: dict[str, Any],
) -> tuple[bool, str]:
    """
    This bridge accepts only CarPlay refresh requests.

    It is not a general ZÆNIA command interface.
    """

    request_id = str(
        request.get(
            "request_id",
            "",
        )
    ).strip()

    if not request_id:
        return False, "Missing request_id."

    action = str(
        request.get(
            "action",
            "",
        )
    ).strip().lower()

    if action != "refresh_carplay":
        return False, "Unsupported bridge action."

    return True, ""


def response_matches_request(
    request_id: str,
) -> bool:
    """
    Prevent the same OneDrive request from being processed
    repeatedly.
    """

    response = read_json_file(
        get_response_file()
    )

    if not response:
        return False

    return (
        str(
            response.get(
                "request_id",
                "",
            )
        ).strip()
        == request_id
    )


def build_failure_response(
    *,
    request_id: str,
    error: str,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "success": False,
        "completed_at": utc_now_text(),
        "error": error,
    }


def process_once() -> bool:
    """
    Process one new CarPlay request if one exists.
    """

    ensure_bridge_folder()

    request = read_json_file(
        get_request_file()
    )

    if not request:
        return False

    request_id = str(
        request.get(
            "request_id",
            "",
        )
    ).strip()

    if (
        request_id
        and response_matches_request(
            request_id
        )
    ):
        return False

    valid, reason = validate_request(
        request
    )

    if not valid:
        atomic_write_json(
            get_response_file(),
            build_failure_response(
                request_id=request_id or "unknown",
                error=reason,
            ),
        )

        print(
            "Rejected invalid CarPlay request:",
            reason,
        )

        return True

    print()
    print(
        "New CarPlay connection request detected."
    )
    print(
        "Request ID:",
        request_id,
    )
    print(
        "Refreshing ZÆNIA briefing..."
    )

    try:
        result = refresh_carplay_briefing()

        briefing = (
            result.get(
                "briefing",
                {},
            )
            or {}
        )

        response = {
            "request_id": request_id,
            "success": True,
            "completed_at": utc_now_text(),
            "generated_at": result.get(
                "generated_at"
            ),
            "duration_seconds": result.get(
                "duration_seconds"
            ),
            "calendar_sync": result.get(
                "calendar_sync",
                {},
            ),
            "audio_path": briefing.get(
                "audio_path",
                "",
            ),
            "text_path": briefing.get(
                "text_path",
                "",
            ),
            "traffic_included": briefing.get(
                "traffic_included",
                False,
            ),
            "weather_location": briefing.get(
                "weather_location"
            ),
        }

        atomic_write_json(
            get_response_file(),
            response,
        )

        print(
            "Fresh CarPlay briefing created."
        )
        print(
            "Response written to OneDrive."
        )

        return True

    except Exception as error:
        atomic_write_json(
            get_response_file(),
            build_failure_response(
                request_id=request_id,
                error=str(error),
            ),
        )

        print(
            "CarPlay refresh failed:",
            error,
        )

        return True


def run_watch_loop(
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> None:
    ensure_bridge_folder()

    print()
    print(
        "ZÆNIA OneDrive CarPlay Bridge"
    )
    print()
    print(
        "Bridge folder:"
    )
    print(
        get_bridge_folder()
    )
    print()
    print(
        "Watching for CarPlay requests..."
    )
    print(
        "Polling interval:",
        f"{poll_seconds:.1f} seconds",
    )
    print()
    print(
        "Press Ctrl+C to stop."
    )

    try:
        while True:
            process_once()

            time.sleep(
                poll_seconds
            )

    except KeyboardInterrupt:
        print()
        print(
            "CarPlay bridge stopped."
        )


def create_test_request() -> str:
    """
    Simulate the same request the iPhone creates.
    """

    request_id = str(
        uuid.uuid4()
    )

    request = {
        "request_id": request_id,
        "action": "refresh_carplay",
        "reason": "self_test",
        "requested_at": utc_now_text(),
    }

    atomic_write_json(
        get_request_file(),
        request,
    )

    return request_id


def run_self_test() -> bool:
    ensure_bridge_folder()

    print()
    print(
        "ZÆNIA OneDrive CarPlay Bridge Self-Test"
    )
    print()
    print(
        "Bridge folder:"
    )
    print(
        get_bridge_folder()
    )
    print()

    request_id = create_test_request()

    print(
        "Request ID:",
        request_id,
    )

    processed = process_once()

    response = read_json_file(
        get_response_file()
    )

    if not response:
        print(
            "Response file: FAIL"
        )
        return False

    matching_id = (
        str(
            response.get(
                "request_id",
                "",
            )
        )
        == request_id
    )

    success = (
        response.get(
            "success"
        )
        is True
    )

    audio_path_text = str(
        response.get(
            "audio_path",
            "",
        )
    )

    text_path_text = str(
        response.get(
            "text_path",
            "",
        )
    )

    audio_path = (
        Path(audio_path_text)
        if audio_path_text
        else None
    )

    text_path = (
        Path(text_path_text)
        if text_path_text
        else None
    )

    audio_exists = bool(
        audio_path
        and audio_path.exists()
    )

    text_exists = bool(
        text_path
        and text_path.exists()
    )

    passed = (
        processed
        and matching_id
        and success
        and audio_exists
        and text_exists
    )

    print()
    print(
        "Request detected:",
        "PASS" if processed else "FAIL",
    )
    print(
        "Matching response ID:",
        "PASS" if matching_id else "FAIL",
    )
    print(
        "Refresh result:",
        "PASS" if success else "FAIL",
    )
    print(
        "Piper audio:",
        "PASS" if audio_exists else "FAIL",
    )
    print(
        "Briefing text:",
        "PASS" if text_exists else "FAIL",
    )
    print()
    print(
        "OneDrive bridge:",
        "PASS" if passed else "FAIL",
    )

    return passed


@owner_command('briefing.generate')
def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ZÆNIA OneDrive CarPlay bridge."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    watch_parser = subparsers.add_parser(
        "watch"
    )

    watch_parser.add_argument(
        "--poll",
        type=float,
        default=DEFAULT_POLL_SECONDS,
    )

    subparsers.add_parser(
        "self-test"
    )

    args = parser.parse_args()

    if args.command == "watch":
        run_watch_loop(
            poll_seconds=max(
                0.5,
                float(args.poll),
            )
        )

        return

    if args.command == "self-test":
        if not run_self_test():
            raise SystemExit(1)


if __name__ == "__main__":
    main()