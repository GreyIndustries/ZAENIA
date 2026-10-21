"""Provider-independent contracts and strict validation; Python 3.11+."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any
from zoneinfo import ZoneInfo


class ReasoningError(Exception):
    """A safe, user-facing error without credentials or remote response bodies."""


class InvalidDecision(ReasoningError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field.")
        result[key] = value
    return result


def strict_json(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError("Non-finite JSON number.")

    return json.loads(text, object_pairs_hook=_unique_object,
                      parse_constant=reject_constant)


def aware_datetime(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("A timestamp must be a string.")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamps require an explicit UTC offset.")
    return result


@dataclass(frozen=True)
class ReasoningRequest:
    question: str
    now: str
    timezone: str = "America/Los_Angeles"
    evidence: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> "ReasoningRequest":
        if not isinstance(self.question, str) or not self.question.strip():
            raise ValueError("A question is required.")
        if len(self.question) > 12000:
            raise ValueError("The question is too long.")
        aware_datetime(self.now)
        ZoneInfo(self.timezone)
        if not isinstance(self.evidence, dict):
            raise ValueError("Evidence must be a JSON object.")
        if any(not isinstance(key, str) or not key or len(key) > 100
               for key in self.evidence):
            raise ValueError("Invalid evidence identifier.")
        encoded = json.dumps(self.evidence, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 32000:
            raise ValueError("Evidence exceeds the 32 KB limit.")
        return ReasoningRequest(self.question.strip(), self.now, self.timezone,
                                strict_json(encoded))

    def to_dict(self) -> dict[str, Any]:
        return {"question": self.question, "current_time": self.now,
                "timezone": self.timezone, "reference_evidence": self.evidence}


OPERATIONS = ("calendar.write", "calendar.read", "weather.read", "files.rename")


def decision_schema() -> dict[str, Any]:
    action = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "operation": {"type": "string", "enum": list(OPERATIONS)},
            "parameters_json": {"type": "string"},
        },
        "required": ["operation", "parameters_json"],
    }
    fields = {
        "kind": {"type": "string", "enum": ["answer", "clarify", "proposal", "refuse"]},
        "message": {"type": "string"},
        "explanation": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "actions": {"type": "array", "items": action},
        "execution_status": {"type": "string", "enum": ["not_executed"]},
    }
    return {"type": "object", "additionalProperties": False,
            "properties": fields, "required": list(fields)}


@dataclass(frozen=True)
class ProposedAction:
    operation: str
    parameters_json: str

    @property
    def parameters(self) -> dict[str, Any]:
        return strict_json(self.parameters_json)

    def to_dict(self) -> dict[str, str]:
        return {"operation": self.operation, "parameters_json": self.parameters_json}


@dataclass(frozen=True)
class Decision:
    kind: str
    message: str
    explanation: str
    questions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    actions: tuple[ProposedAction, ...]
    execution_status: str = "not_executed"

    @classmethod
    def parse(cls, raw: str, request: ReasoningRequest) -> "Decision":
        try:
            if len(raw.encode("utf-8")) > 65536:
                raise ValueError("Decision exceeds the size limit.")
            value = strict_json(raw)
            fields = set(decision_schema()["required"])
            if not isinstance(value, dict) or set(value) != fields:
                raise ValueError("Decision has missing or unexpected fields.")
            if value["kind"] not in ("answer", "clarify", "proposal", "refuse"):
                raise ValueError("Unknown decision kind.")
            if value["execution_status"] != "not_executed":
                raise ValueError("A model cannot claim an executed action.")
            for key, limit in (("message", 4000), ("explanation", 1200)):
                if not isinstance(value[key], str) or len(value[key]) > limit:
                    raise ValueError("Invalid decision text.")
            if not value["message"].strip():
                raise ValueError("The decision message is empty.")
            for key, limit in (("questions", 4), ("evidence_ids", 20)):
                items = value[key]
                if (not isinstance(items, list) or len(items) > limit
                        or any(not isinstance(item, str) or not item.strip()
                               or len(item) > 1000 for item in items)):
                    raise ValueError("Invalid decision list.")
            if any(key not in request.evidence for key in value["evidence_ids"]):
                raise ValueError("Decision cites unavailable evidence.")
            if not isinstance(value["actions"], list) or len(value["actions"]) > 3:
                raise ValueError("Invalid action list.")
            actions: list[ProposedAction] = []
            for item in value["actions"]:
                if not isinstance(item, dict) or set(item) != {"operation", "parameters_json"}:
                    raise ValueError("Malformed action proposal.")
                if item["operation"] not in OPERATIONS:
                    raise ValueError("Unknown proposed operation.")
                if not isinstance(item["parameters_json"], str) or len(item["parameters_json"]) > 12000:
                    raise ValueError("Invalid action parameters.")
                action = ProposedAction(item["operation"], item["parameters_json"])
                _validate_action(action, request)
                actions.append(action)
            kind = value["kind"]
            if kind == "proposal" and (not actions or value["questions"]):
                raise ValueError("Proposals require actions and no unanswered questions.")
            if kind != "proposal" and actions:
                raise ValueError("Only proposals may contain actions.")
            if kind == "clarify" and not value["questions"]:
                raise ValueError("Clarification requires a question.")
            if kind != "clarify" and value["questions"]:
                raise ValueError("Only clarification may contain questions.")
            return cls(kind, value["message"], value["explanation"],
                       tuple(value["questions"]), tuple(value["evidence_ids"]), tuple(actions))
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            raise InvalidDecision("The provider returned an invalid decision; no action was executed.") from error

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "message": self.message, "explanation": self.explanation,
                "questions": list(self.questions), "evidence_ids": list(self.evidence_ids),
                "actions": [action.to_dict() for action in self.actions],
                "execution_status": self.execution_status}


def _valid_text(value: Any, limit: int = 300) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def _in_zone(value: str, name: str) -> datetime:
    parsed = aware_datetime(value)
    converted = parsed.astimezone(ZoneInfo(name))
    if parsed.utcoffset() != converted.utcoffset():
        raise ValueError("Timestamp offset does not match the specified timezone.")
    return parsed


def _validate_action(action: ProposedAction, request: ReasoningRequest) -> None:
    params = action.parameters
    if not isinstance(params, dict):
        raise ValueError("Action parameters must be a JSON object.")
    if action.operation == "calendar.write":
        expected = {"kind", "title", "trigger_at", "event_at", "lead_minutes", "timezone"}
        if set(params) != expected or params["kind"] != "reminder":
            raise ValueError("Stage 1 calendar proposals support reminders only.")
        if not _valid_text(params["title"], 200) or params["timezone"] != request.timezone:
            raise ValueError("Invalid reminder title or timezone.")
        lead = params["lead_minutes"]
        if type(lead) is not int or not 1 <= lead <= 1440:
            raise ValueError("Invalid reminder lead time.")
        trigger = _in_zone(params["trigger_at"], request.timezone)
        event = _in_zone(params["event_at"], request.timezone)
        seconds = (event.astimezone(timezone.utc) - trigger.astimezone(timezone.utc)).total_seconds()
        if seconds != lead * 60:
            raise ValueError("Reminder time does not match its lead time.")
        if trigger <= aware_datetime(request.now):
            raise ValueError("A reminder must be in the future.")
    elif action.operation == "calendar.read":
        if set(params) != {"start_at", "end_at", "timezone"} or params["timezone"] != request.timezone:
            raise ValueError("Invalid calendar range.")
        start = _in_zone(params["start_at"], request.timezone)
        end = _in_zone(params["end_at"], request.timezone)
        if end <= start:
            raise ValueError("A calendar range must end after it starts.")
    elif action.operation == "weather.read":
        if set(params) != {"location"} or not _valid_text(params["location"]):
            raise ValueError("Invalid weather location.")
    elif action.operation == "files.rename":
        if set(params) != {"source", "destination"}:
            raise ValueError("Invalid rename parameters.")
        if any(not _valid_text(params[key], 1000) or "\x00" in params[key] for key in params):
            raise ValueError("Invalid proposed path.")
        if params["source"] == params["destination"]:
            raise ValueError("A rename needs two different paths.")
