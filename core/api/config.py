from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8766

API_HOST_ENV = "ZAENIA_API_HOST"
API_PORT_ENV = "ZAENIA_API_PORT"


@dataclass(frozen=True)
class ApiSettings:
    """
    Runtime settings for ZÆNIA's API server.

    During the foundation stage the server is intentionally
    restricted to localhost.

    Network access will be enabled later only after API
    authentication is in place.
    """

    host: str
    port: int
    local_only: bool


def load_api_settings() -> ApiSettings:
    """
    Load API settings from environment variables.

    Current security rule:
        only localhost bindings are permitted.
    """

    host = str(
        os.environ.get(
            API_HOST_ENV,
            DEFAULT_API_HOST,
        )
    ).strip()

    raw_port = str(
        os.environ.get(
            API_PORT_ENV,
            DEFAULT_API_PORT,
        )
    ).strip()

    try:
        port = int(raw_port)

    except ValueError as error:
        raise ValueError(
            f"{API_PORT_ENV} must be a valid integer."
        ) from error

    if not 1 <= port <= 65535:
        raise ValueError(
            f"{API_PORT_ENV} must be between 1 and 65535."
        )

    approved_local_hosts = {
        "127.0.0.1",
        "localhost",
        "::1",
    }

    if host not in approved_local_hosts:
        raise RuntimeError(
            "ZÆNIA API network exposure is disabled during "
            "the foundation stage. "
            "Use 127.0.0.1 until API authentication is built."
        )

    return ApiSettings(
        host=host,
        port=port,
        local_only=True,
    )