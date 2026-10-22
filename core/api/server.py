from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.request import (
    Request,
    urlopen,
)

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    status,
    Request as FastAPIRequest,
)

from core.api.auth import (
    API_TOKEN_HEADER,
    build_memory_token_verifier,
    generate_api_token,
    verify_api_token,
)
from core.api.chat_routes import (
    create_chat_router,
)
from core.api.config import (
    ApiSettings,
    load_api_settings,
)


API_NAME = "ZÆNIA Local API"
API_VERSION = "0.9.1"
from core.foundation.client_gate import ScopedClientGate, CLIENT_CAPABILITIES
from core.foundation.auth.passkey import require_passkey
from core.api.brief_gate import OWNER_UNLOCK_MESSAGE, UnattendedBriefGate, refuse_interactive_passkey
from core.api.ui_routes import create_ui_router, operation_for as ui_operation_for
from core.api.assistant_routes import create_assistant_router, operation_for as assistant_operation_for
from core.api.desktop_key import KEY_HEADER as DESKTOP_KEY_HEADER, verify as verify_desktop_key
from core.api.platform_routes import create_platform_router, operation_for as platform_operation_for


TokenVerifier = Callable[
    [str],
    bool,
]


def utc_now_text() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def create_app(
    token_verifier: TokenVerifier | None = None,
    chat_handler: Callable[..., dict[str, object]] | None = None,
    client_gate: ScopedClientGate | UnattendedBriefGate | None = None,
    include_carplay: bool = True,
    include_phone_app: bool = True,
    start_followthrough: bool = False,
    platform_provider: Callable[[], object] | None = None,
    mobile_auth_service=None,
) -> FastAPI:
    """
    Create the complete ZÆNIA API application.

    Production uses the stored API-token hash.

    Self-tests can inject an isolated temporary token verifier
    without touching Zack's real credential.
    """

    active_token_verifier = (
        token_verifier
        if token_verifier is not None
        else verify_api_token
    )

    application = FastAPI(
        title=API_NAME,
        version=API_VERSION,
        description=(
            "Private API interface for Zack's "
            "local ZÆNIA assistant."
        ),
    )

    from core.api.mobile_auth import COOKIE, MobileAuth
    from core.api.mobile_auth_routes import browser_request_allowed, create_mobile_auth_router
    mobile_auth = mobile_auth_service if mobile_auth_service is not None else MobileAuth()
    application.state.mobile_auth = mobile_auth
    application.include_router(create_mobile_auth_router(mobile_auth))

    def authorize_operation(operation: str | None) -> None:
        if client_gate is None:
            raise HTTPException(503, "Authenticate the local API service before serving protected operations.")
        try:
            allowed = client_gate.authorize(operation)
        except PermissionError as error:
            raise HTTPException(503, str(error)) from error
        if not allowed:
            if isinstance(client_gate, UnattendedBriefGate):
                raise HTTPException(503, OWNER_UNLOCK_MESSAGE)
            raise HTTPException(403, "The client scope or active policy denies this operation.")

    followthrough_instance = None
    followthrough_lock = threading.Lock()

    def followthrough():
        nonlocal followthrough_instance
        with followthrough_lock:
            if followthrough_instance is None:
                from core.assistant_followthrough.service import FollowThroughService, local_calendar_snapshot, local_task_snapshot
                def events():
                    authorize_operation("notifications.write")
                    authorize_operation("calendar.read")
                    return local_calendar_snapshot()
                def tasks():
                    authorize_operation("tasks.read")
                    return local_task_snapshot()
                followthrough_instance = FollowThroughService(calendar_loader=events, task_loader=tasks)
        return followthrough_instance

    if start_followthrough:
        from core.assistant_platform.game_mode import GameModeMonitor
        game_mode = GameModeMonitor()

        @application.on_event("startup")
        def start_assistant_worker():
            followthrough().start()
            game_mode.start()  # frees the brain while a full-screen game is in front
            from core.tech_news.service import tech_news
            tech_news().start()  # tech headlines every 30 minutes (optional, online)
            from core.email_watch.service import email_watch
            email_watch().start()  # important-email summaries every 5 minutes, once Gmail is connected

        @application.on_event("shutdown")
        def stop_assistant_worker():
            game_mode.stop()
            from core.tech_news.service import tech_news
            tech_news().stop()
            from core.email_watch.service import email_watch
            email_watch().stop()
            if followthrough_instance is not None:
                followthrough_instance.stop()

    def require_api_authentication(
        request: FastAPIRequest,
        x_zaenia_api_token: str | None = Header(
            default=None,
            alias=API_TOKEN_HEADER,
        ),
        x_zaenia_desktop_key: str | None = Header(
            default=None,
            alias=DESKTOP_KEY_HEADER,
        ),
    ) -> None:
        """
        Validate the private client credential.

        Protected operations depend on this function. Clients send the API
        token; the paired desktop app on this PC may send its desktop key
        instead (created with the owner passkey, see desktop_key.py). The
        browser can also use a temporary, verified-speaker cookie session.
        The client gate below still decides each operation.
        """

        supplied_token = (
            x_zaenia_api_token
            or ""
        )

        if not active_token_verifier(
            supplied_token
        ) and not (
            x_zaenia_desktop_key
            and verify_desktop_key(x_zaenia_desktop_key)
        ) and not (
            browser_request_allowed(request)
            and mobile_auth.authenticated(request.cookies.get(COOKIE, ""))
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "ZÆNIA API authentication failed."
                ),
            )
        if request.url.path == "/api/auth/check":
            return
        operation = {
            ("POST","/api/chat"):"chat.reply",
            ("POST","/api/carplay/briefing"):"briefing.generate",
            ("POST","/api/carplay/answer"):"carplay.session.update",
            ("POST","/api/carplay/played"):"carplay.session.update",
            ("GET","/api/carplay/audio"):"carplay.audio.read",
            ("POST","/api/briefing"):"briefing.generate",
            ("POST","/api/briefing/answer"):"carplay.session.update",
            ("POST","/api/briefing/played"):"carplay.session.update",
            ("GET","/api/briefing/audio"):"carplay.audio.read",
            ("GET","/api/status"):"status.read",
        }.get((request.method,request.url.path)) or ui_operation_for(request.method, request.url.path) or assistant_operation_for(request.method, request.url.path) or platform_operation_for(request.method,request.url.path)
        authorize_operation(operation)

    @application.get(
        "/health",
        tags=[
            "system",
        ],
    )
    def health(
    ) -> dict[str, object]:
        """
        Lightweight health endpoint.

        It performs no action and exposes no sensitive state.
        """

        return {
            "success": True,
            "service": (
                "zaenia_api"
            ),
            "status": (getattr(client_gate,"mode","ready")) if client_gate is not None else "owner_activation_required",
            "version": API_VERSION,
            "local_only": True,
            "authentication": (
                "required_for_protected_routes"
            ),
            "assistant_followthrough_running": bool(followthrough_instance is not None and followthrough_instance.is_running),
            "timestamp": (
                utc_now_text()
            ),
        }

    @application.get(
        "/api/auth/check",
        tags=[
            "authentication",
        ],
        dependencies=[
            Depends(
                require_api_authentication
            ),
        ],
    )
    def authentication_check(
    ) -> dict[str, object]:
        """
        Verify that an API client authenticated successfully.

        No external action is performed.
        """

        return {
            "success": True,
            "authenticated": True,
            "service": (
                "zaenia_api"
            ),
            "timestamp": (
                utc_now_text()
            ),
        }

    @application.get(
        "/api/status",
        tags=[
            "system",
        ],
        dependencies=[
            Depends(
                require_api_authentication
            ),
        ],
    )
    def live_status(
    ) -> dict[str, object]:
        """
        Read-only live status for the desktop and phone UI.

        Module readiness, PC load and the last CarPlay brief.
        No secrets and no actions.
        """
        from core.api.status_feed import build_status

        return build_status(
            getattr(client_gate,"mode","full")
        )

    if include_carplay:
        from core.api.carplay_routes import create_carplay_router
        def car_handoff():
            try:
                authorize_operation('assistant.platform.read')
                authorize_operation('memory.read')
                from core.assistant_platform.service import existing_platform
                platform_service=platform_provider() if platform_provider else existing_platform()
                return platform_service.store.get('handoff','active') if platform_service else None
            except (PermissionError,HTTPException): return None
        application.include_router(create_carplay_router(require_api_authentication,handoff_loader=car_handoff))

    application.include_router(
        create_chat_router(
            require_api_authentication,
            chat_handler=chat_handler,
            memory_authorizer=authorize_operation,
        )
    )

    # Tasks, calendar, chat history, speech, system brief and file tools for
    # the desktop and phone UI. Same token check and client gate as above.
    application.include_router(
        create_ui_router(
            require_api_authentication,
            lambda: getattr(client_gate,"mode","full"),
            authorize_operation=authorize_operation,
        )
    )

    application.include_router(create_assistant_router(require_api_authentication, followthrough, authorize_sources=authorize_operation))
    application.include_router(create_platform_router(require_api_authentication,authorize_operation,provider=platform_provider))

    if include_phone_app:
        # The phone web app's files are public UI code with no secrets; its
        # status and chat calls still go through the token-protected routes.
        from core.api.phone_app import mount_phone_app
        mount_phone_app(application)

    return application


# Importing this module does not request credentials or initialize audio devices.
# A direct ASGI launch fails closed for protected operations until a trusted host
# supplies an owner-approved client_gate. The CLI below handles activation.
app = create_app(include_carplay=False)


def run_server(
    settings: ApiSettings | None = None,
    brief_only: bool = False,
) -> None:
    """
    Run ZÆNIA's permanent API process.

    Network exposure is still localhost-only until the
    Tailscale stage.
    """

    active_settings = (
        settings
        if settings is not None
        else load_api_settings()
    )
    if not active_settings.local_only or active_settings.host not in {"127.0.0.1","localhost","::1"}:
        raise RuntimeError("Module 1 API service must bind to localhost.")
    from core.voice_security.voice_only import enabled as voice_only_enabled, VoiceOnlyClientGate
    voice_only_mode = voice_only_enabled()
    if voice_only_mode:
        service_app = create_app(client_gate=VoiceOnlyClientGate(), start_followthrough=True)
    elif brief_only:
        # Unattended start (Windows logon task): CarPlay brief, chat and the
        # status feed, all still behind the API token. Any accidental passkey
        # request fails at once instead of waiting in a hidden window.
        from core.foundation.auth import passkey as owner_passkey
        owner_passkey._private_input = refuse_interactive_passkey
        service_app = create_app(client_gate=UnattendedBriefGate(), start_followthrough=True)
    else:
        proof = require_passkey(operation="api.service.open",payload={"capabilities":sorted(CLIENT_CAPABILITIES)})
        service_app = create_app(client_gate=ScopedClientGate(proof), start_followthrough=True)

    print()
    print(
        "ZÆNIA Local API"
    )
    print(
        "==============="
    )
    print()

    print(
        "Host:",
        active_settings.host,
    )

    print(
        "Port:",
        active_settings.port,
    )

    print(
        "Network exposure:",
        (
            "LOCALHOST ONLY"
            if active_settings.local_only
            else "NETWORK ENABLED"
        ),
    )

    print(
        "Protected routes:",
        "API TOKEN REQUIRED",
    )

    print(
        "Mode:",
        "VOICE-ONLY STARTUP (Windows protected; API token required)" if voice_only_mode else
        "TOKEN MODE (brief, chat and status; owner features need the passkey)" if brief_only else "FULL (unlocked with the passkey)",
    )

    print()

    print(
        "Available endpoints:"
    )

    print(
        "GET  /health"
    )

    print(
        "GET  /api/auth/check"
    )

    print(
        "POST /api/carplay/briefing"
    )

    print(
        "GET  /api/carplay/audio"
    )

    print(
        "GET  /api/status"
    )

    print(
        "POST /api/chat"
    )

    print()

    print(
        "Press Ctrl+C to stop."
    )

    uvicorn.run(
        service_app,
        host=(
            active_settings.host
        ),
        port=(
            active_settings.port
        ),
        log_level="info",
        access_log=False,
    )


def find_free_local_port(
) -> int:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as listener:
        listener.bind(
            (
                "127.0.0.1",
                0,
            )
        )

        return int(
            listener.getsockname()[1]
        )


def wait_for_server(
    server: uvicorn.Server,
    timeout_seconds: float = 10.0,
) -> bool:
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while (
        time.monotonic()
        < deadline
    ):
        if server.started:
            return True

        time.sleep(
            0.05
        )

    return False


def request_json(
    request: Request,
    *,
    timeout: float = 10.0,
) -> tuple[
    int,
    dict[str, object],
]:
    """
    Execute an HTTP request and decode a JSON response.

    HTTP error responses are intentionally returned rather
    than immediately raised so authentication rejection can
    be tested.
    """

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            status_code = int(
                response.status
            )

            raw_body = (
                response.read()
            )

    except HTTPError as error:
        status_code = int(
            error.code
        )

        raw_body = (
            error.read()
        )

    payload = json.loads(
        raw_body.decode(
            "utf-8"
        )
    )

    return (
        status_code,
        payload,
    )


def request_binary(
    request: Request,
    *,
    timeout: float = 10.0,
) -> tuple[
    int,
    bytes,
    str,
]:
    """
    Execute a request expected to return binary content.
    """

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            return (
                int(
                    response.status
                ),
                response.read(),
                str(
                    response.headers.get(
                        "Content-Type",
                        "",
                    )
                ),
            )

    except HTTPError as error:
        return (
            int(
                error.code
            ),
            error.read(),
            str(
                error.headers.get(
                    "Content-Type",
                    "",
                )
            ),
        )


def run_self_test(
) -> bool:
    """
    Test the complete current API stack.

    The test uses a temporary credential stored only in memory.

    It verifies:

        public health
        invalid-token rejection
        valid-token acceptance
        protected CarPlay generation
        protected Piper WAV retrieval

    Zack's real API credential is not read, changed, printed,
    or replaced by this test.
    """

    host = "127.0.0.1"
    port = find_free_local_port()

    temporary_token = (
        generate_api_token()
    )

    test_verifier = (
        build_memory_token_verifier(
            temporary_token
        )
    )

    test_app = (
        create_app(
            token_verifier=(
                test_verifier
            )
            , client_gate=ScopedClientGate(require_passkey(operation="api.service.open",payload={"capabilities":sorted(CLIENT_CAPABILITIES)}))
        )
    )

    config = uvicorn.Config(
        test_app,
        host=host,
        port=port,
        log_level="error",
        access_log=False,
    )

    server = (
        uvicorn.Server(
            config
        )
    )

    thread = (
        threading.Thread(
            target=server.run,
            daemon=True,
        )
    )

    print()

    print(
        "ZÆNIA CarPlay API Self-Test"
    )

    print()

    print(
        "Starting temporary protected API..."
    )

    thread.start()

    started = (
        wait_for_server(
            server
        )
    )

    if not started:
        print(
            "Server startup: FAIL"
        )

        server.should_exit = True

        thread.join(
            timeout=5
        )

        return False

    print(
        "Server startup: PASS"
    )

    base_url = (
        f"http://{host}:{port}"
    )

    passed = False

    try:
        health_request = (
            Request(
                f"{base_url}/health",
                method="GET",
            )
        )

        (
            health_status,
            health_payload,
        ) = request_json(
            health_request
        )

        health_ok = (
            health_status == 200
            and health_payload.get(
                "success"
            )
            is True
        )

        bad_request = (
            Request(
                (
                    f"{base_url}"
                    "/api/carplay/briefing"
                ),
                method="POST",
                headers={
                    API_TOKEN_HEADER: (
                        "invalid-token"
                    ),
                },
            )
        )

        (
            bad_status,
            _bad_payload,
        ) = request_json(
            bad_request
        )

        bad_token_rejected = (
            bad_status == 401
        )

        auth_request = (
            Request(
                (
                    f"{base_url}"
                    "/api/auth/check"
                ),
                method="GET",
                headers={
                    API_TOKEN_HEADER: (
                        temporary_token
                    ),
                },
            )
        )

        (
            auth_status,
            auth_payload,
        ) = request_json(
            auth_request
        )

        auth_ok = (
            auth_status == 200
            and auth_payload.get(
                "authenticated"
            )
            is True
        )

        briefing_request = (
            Request(
                (
                    f"{base_url}"
                    "/api/carplay/briefing"
                ),
                method="POST",
                headers={
                    API_TOKEN_HEADER: (
                        temporary_token
                    ),
                },
            )
        )

        (
            briefing_status,
            briefing_payload,
        ) = request_json(
            briefing_request,
            timeout=180,
        )

        briefing_text = str(
            briefing_payload.get(
                "briefing_text",
                "",
            )
        ).strip()

        briefing_ok = (
            briefing_status == 200
            and briefing_payload.get(
                "success"
            )
            is True
            and bool(
                briefing_text
            )
        )

        audio_ready = (
            briefing_payload.get(
                "audio_ready"
            )
            is True
        )

        audio_request = (
            Request(
                (
                    f"{base_url}"
                    "/api/carplay/audio"
                ),
                method="GET",
                headers={
                    API_TOKEN_HEADER: (
                        temporary_token
                    ),
                },
            )
        )

        (
            audio_status,
            audio_body,
            audio_content_type,
        ) = request_binary(
            audio_request,
            timeout=30,
        )

        audio_ok = (
            audio_status == 200
            and len(
                audio_body
            ) > 1000
            and (
                "audio/wav"
                in audio_content_type.lower()
                or
                "audio/x-wav"
                in audio_content_type.lower()
            )
        )

        passed = (
            health_ok
            and bad_token_rejected
            and auth_ok
            and briefing_ok
            and audio_ready
            and audio_ok
        )

        print()

        print(
            "Public health endpoint:",
            (
                "PASS"
                if health_ok
                else "FAIL"
            ),
        )

        print(
            "Invalid token rejected:",
            (
                "PASS"
                if bad_token_rejected
                else "FAIL"
            ),
        )

        print(
            "Valid token accepted:",
            (
                "PASS"
                if auth_ok
                else "FAIL"
            ),
        )

        print(
            "Fresh briefing generated:",
            (
                "PASS"
                if briefing_ok
                else "FAIL"
            ),
        )

        print(
            "Piper audio reported ready:",
            (
                "PASS"
                if audio_ready
                else "FAIL"
            ),
        )

        print(
            "Protected WAV download:",
            (
                "PASS"
                if audio_ok
                else "FAIL"
            ),
        )

        if briefing_text:
            print()

            print(
                "Current briefing:"
            )

            print(
                briefing_text
            )

        if not briefing_ok:
            print()

            print(
                "Briefing HTTP status:",
                briefing_status,
            )

            print(
                "Briefing response:"
            )

            print(
                json.dumps(
                    briefing_payload,
                    indent=2,
                    ensure_ascii=False,
                )
            )

    except (
        URLError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print()

        print(
            "CarPlay API test failed:",
            error,
        )

        passed = False

    finally:
        server.should_exit = True

        thread.join(
            timeout=5
        )

    print()

    print(
        "ZÆNIA CarPlay API:",
        (
            "PASS"
            if passed
            else "FAIL"
        ),
    )

    return passed


def main(
) -> None:
    parser = (
        argparse.ArgumentParser(
            description=(
                "ZÆNIA local API server."
            )
        )
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    server_parser = subparsers.add_parser(
        "server",
        help=(
            "Run the local ZÆNIA API server."
        ),
    )

    server_parser.add_argument(
        "--unattended",
        "--brief-only",
        dest="brief_only",
        action="store_true",
        help=(
            "Start without the passkey in token mode: CarPlay brief, "
            "chat and status, all behind the API token."
        ),
    )

    subparsers.add_parser(
        "pair-desktop",
        help=(
            "Create the desktop approval key (needs the owner passkey). "
            "File changes from the phone apply only after approval in the desktop app."
        ),
    )

    subparsers.add_parser(
        "self-test",
        help=(
            "Run the protected CarPlay API test."
        ),
    )

    args = (
        parser.parse_args()
    )

    if args.command == "server":
        run_server(brief_only=args.brief_only)

        return

    if args.command == "pair-desktop":
        from core.api.desktop_key import pair_desktop
        path = pair_desktop()
        print("Desktop approval key saved for this Windows user:", path)
        print("Restart the ZÆNIA desktop app; it can now approve file changes.")
        return

    if args.command == "self-test":
        passed = (
            run_self_test()
        )

        if not passed:
            raise SystemExit(
                1
            )


if __name__ == "__main__":
    main()
