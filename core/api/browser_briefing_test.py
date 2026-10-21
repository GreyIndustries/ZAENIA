"""Browser briefing aliases and explicit full-brief requests with isolated data."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


class BrowserBriefingTests(unittest.TestCase):
    def test_browser_routes_request_full_and_keep_legacy_routes(self):
        from core.api.carplay_routes import create_carplay_router
        calls = []
        class Sessions:
            def __init__(self, **kwargs):
                pass

            def start(self, *args, **kwargs):
                calls.append((args, kwargs))
                return {"success": True, "generated_at": "2026-10-18T12:00:00-07:00", "duration_seconds": 0,
                        "calendar_sync": {"success": True, "reason": "Test."}, "briefing_text": "Nothing on schedule.",
                        "audio_ready": True, "audio_endpoint": "/api/carplay/audio?session_id=test", "traffic_included": True,
                        "session_id": "test", "briefing_type": "full"}
        app = FastAPI()
        app.include_router(create_carplay_router(lambda: None))
        with patch("core.api.carplay_routes.BriefingSessions", Sessions), TestClient(app) as client:
            result = client.post("/api/briefing", json={"request_id": "browser-1"})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["audio_endpoint"], "/api/briefing/audio?session_id=test")
            self.assertEqual(calls[-1], (("browser-1",), {"force_full": True}))
            self.assertEqual(client.post("/api/carplay/briefing", json={"request_id": "car-1"}).status_code, 200)
            self.assertEqual(calls[-1], (("car-1",), {}))

    def test_authentication_runs_before_session_initialization(self):
        from core.api.carplay_routes import create_carplay_router
        def denied():
            raise HTTPException(401, "Authentication required.")
        app = FastAPI()
        app.include_router(create_carplay_router(denied))
        with patch("core.api.carplay_routes.BriefingSessions") as service, TestClient(app) as client:
            for method, path in [("POST", "/api/briefing"), ("POST", "/api/briefing/played"), ("GET", "/api/briefing/audio")]:
                self.assertEqual(client.request(method, path, json={"session_id": "test"}).status_code, 401)
            service.assert_not_called()

    def test_browser_always_gets_full_calendar_weather_traffic_without_departure_prompt(self):
        from core.carplay_trigger.briefing_session import BriefingSessions
        now = datetime(2026, 10, 19, 16, 30, tzinfo=ZoneInfo("America/Los_Angeles"))
        raw = {"calendar_context": {"events": [], "status": "work"},
               "weather_summary": "Outside, it's 61 and cloudy, warming to around 66.",
               "weather_result": {"forecast": {"current": {"temperature_2m": 61, "weather_code": 3},
                                                 "current_units": {"temperature_2m": "°F"}}},
               "traffic_result": {"success": True}, "traffic_summary": "Traffic is moving normally, with no notable delays."}
        with TemporaryDirectory() as temp, patch("core.carplay_trigger.briefing_session.build_fresh_briefing", return_value=({"success": True}, raw)), patch(
            "core.carplay_trigger.briefing_session.generate_piper_audio", side_effect=lambda text, path: path.write_bytes(b"isolated-audio")):
            service = BriefingSessions(Path(temp), clock=lambda: now)
            first = service.start("browser-1", force_full=True)
            self.assertEqual(first["briefing_type"], "full")
            self.assertFalse(first["needs_answer"])
            self.assertEqual(first["briefing_text"], "Nothing on schedule. " + raw["weather_summary"] + " " + raw["traffic_summary"])
            service.played(first["session_id"])
            repeated = service.start("browser-2", force_full=True)
            self.assertEqual(repeated["briefing_type"], "full")
            self.assertEqual(repeated["briefing_text"], first["briefing_text"])


if __name__ == "__main__":
    unittest.main()
