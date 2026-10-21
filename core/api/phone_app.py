"""
Phone web app hosting for the ZÆNIA API service.

The built phone UI (desktop/dist-web, made by `npm run build:web`) is served
at /app/ by the same localhost-only service. These files hold no secrets and
grant nothing: protected /api routes require an API token or a temporary
browser session issued after a fresh voice challenge and speaker match.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles


PHONE_APP_PREFIX = "/app"
PHONE_APP_DIR = Path(__file__).resolve().parents[2] / "desktop" / "dist-web"

# Windows can map .js to text/plain in the registry, which stops module
# scripts from loading in Safari. Pin the types the phone app uses.
for _type, _extension in (
    ("text/javascript", ".js"),
    ("text/css", ".css"),
    ("text/html", ".html"),
    ("application/manifest+json", ".webmanifest"),
    ("image/png", ".png"),
    ("image/jpeg", ".jpg"),
    ("image/svg+xml", ".svg"),
    ("font/woff2", ".woff2"),
    ("application/wasm", ".wasm"),
    ("application/octet-stream", ".task"),
):
    mimetypes.add_type(_type, _extension)

PHONE_APP_HEADERS = {
    # Scripts only from this server; the page may call only this server.
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' blob: data:; font-src 'self' data:; connect-src 'self'; "
        "manifest-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # The microphone is allowed for this page only (tap-to-talk and listening).
    "Permissions-Policy": "camera=(self), microphone=(self), geolocation=(), payment=(), usb=()",
}


class _PhoneAppFiles:
    """Static files plus security and cache headers on every response."""

    def __init__(self, directory: Path) -> None:
        self.files = StaticFiles(directory=str(directory), html=True)

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        path = str(scope.get("path", ""))

        async def send_with_headers(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in PHONE_APP_HEADERS.items():
                    headers[name] = value
                if "/handtracking/" in path and path.endswith(".js"):
                    # The pinned Emscripten worker creates binding functions.
                    # Limit JS evaluation permission to these local worker scripts,
                    # keeping the application page's stricter policy unchanged.
                    headers["Content-Security-Policy"] = (
                        "default-src 'self'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; "
                        "connect-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'"
                    )
                if "/assets/" in path:
                    # Build output names carry a content hash.
                    headers["Cache-Control"] = "public, max-age=31536000, immutable"
                else:
                    # The page, manifest and icons are checked on every launch
                    # so a rebuilt app shows up right away.
                    headers["Cache-Control"] = "no-cache"
            await send(message)

        await self.files(scope, receive, send_with_headers)


def mount_phone_app(application: Any, directory: Path | None = None) -> bool:
    """
    Serve the phone web app at /app/ and send / there.

    Returns True when a built app was found. Without a build, /app/ explains
    how to make one instead of failing.
    """

    app_dir = directory if directory is not None else PHONE_APP_DIR
    routes = application.router.routes

    async def to_phone_app(request: Request) -> RedirectResponse:
        # A relative Location keeps https when a proxy such as Tailscale
        # Serve sits in front of this localhost service.
        return RedirectResponse(f"{PHONE_APP_PREFIX}/", status_code=307)

    routes.append(Route("/", to_phone_app, methods=["GET"], include_in_schema=False))
    routes.append(Route(PHONE_APP_PREFIX, to_phone_app, methods=["GET"], include_in_schema=False))

    if (app_dir / "index.html").is_file():
        routes.append(Mount(PHONE_APP_PREFIX, app=_PhoneAppFiles(app_dir), name="phone-app"))
        return True

    async def not_built(request: Request) -> PlainTextResponse:
        separator = "; " if os.name == "nt" else " && "
        return PlainTextResponse(
            "The ZÆNIA phone app isn't built yet. On the PC run: "
            f"cd {app_dir.parent}{separator}npm run build:web",
            status_code=404,
            headers={"Cache-Control": "no-store"},
        )

    routes.append(Route(f"{PHONE_APP_PREFIX}/", not_built, methods=["GET"], include_in_schema=False))
    return False
