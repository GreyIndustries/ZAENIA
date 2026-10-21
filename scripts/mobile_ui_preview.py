"""Extends the existing isolated UI fixture with a simulated mobile briefing."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import wave


def main():
    from scripts.assistant_ui_preview import main as preview
    from core.api.server import create_app
    import uvicorn
    run = uvicorn.run
    with TemporaryDirectory(prefix="zae-mobile-preview-") as directory:
        audio = Path(directory) / "preview.wav"
        with wave.open(str(audio), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(b"\0\0" * 8000)

        class Sessions:
            def __init__(self, **kwargs):
                pass

            def start(self, request_id=None, **kwargs):
                return {"success": True, "generated_at": "2026-10-18T12:00:00-07:00", "duration_seconds": 0,
                        "calendar_sync": {"success": True, "reason": "Isolated sample."},
                        "briefing_text": "Nothing on schedule. Outside, it's 61 and cloudy, warming to around 66. Traffic is moving normally, with no notable delays.",
                        "audio_ready": True, "audio_endpoint": "/api/briefing/audio?session_id=preview",
                        "traffic_included": True, "session_id": "preview", "briefing_type": "full", "needs_answer": False}

            def get(self, session_id):
                return {"audio_path": str(audio)}

            def require_recent(self, session):
                pass

            def played(self, session_id):
                return {"success": True}

        def application(**kwargs):
            kwargs["include_carplay"] = True
            return create_app(**kwargs)

        def serve(app, **kwargs):
            kwargs["port"] = 8878
            return run(app, **kwargs)

        with patch("core.api.server.create_app", application), patch("core.api.carplay_routes.BriefingSessions", Sessions), patch("uvicorn.run", serve):
            preview()


if __name__ == "__main__":
    main()
