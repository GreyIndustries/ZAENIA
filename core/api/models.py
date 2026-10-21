from __future__ import annotations

from pydantic import BaseModel, Field


class CalendarSyncResult(BaseModel):
    success: bool
    reason: str


class CarPlayBriefingResponse(BaseModel):
    success: bool
    generated_at: str
    duration_seconds: float
    calendar_sync: CalendarSyncResult
    briefing_text: str
    audio_ready: bool
    audio_endpoint: str
    traffic_included: bool
    traffic_window: str | None = None
    session_id: str = ""
    briefing_type: str = "full"
    needs_answer: bool = False


class CarPlayConnectionRequest(BaseModel):
    request_id: str | None = Field(default=None, max_length=100)


class CarPlayAnswerRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(default="", max_length=500)


class CarPlayPlayedRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
