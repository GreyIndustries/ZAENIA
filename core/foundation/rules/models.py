"""Typed action names; prose and model output never add execution capabilities."""
from dataclasses import asdict, dataclass, field
import json
from types import MappingProxyType
from typing import Any, Literal
from uuid import uuid4

RuleType = Literal["hard", "soft"]
RuleAction = Literal["allow", "deny", "require_reauth", "log_only"]

@dataclass
class Rule:
    id: str
    name: str
    description: str
    rule_type: RuleType
    action: RuleAction
    enabled: bool = True
    operations: tuple[str, ...] = ("*",)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["operations"] = list(self.operations)
        return result

def create_rule(name: str, description: str, rule_type: RuleType, action: RuleAction,
                enabled: bool = True, operations: tuple[str, ...] = ("*",)) -> Rule:
    rule = Rule(str(uuid4()), name, description, rule_type, action, enabled, operations)
    validate_rule(rule.to_dict())
    return rule

def validate_rule(rule: dict) -> dict:
    if not isinstance(rule, dict) or set(rule) - {"id", "name", "description", "rule_type", "action", "enabled", "operations"}:
        raise ValueError("Malformed rule.")
    if rule.get("rule_type") not in ("hard", "soft") or rule.get("action") not in ("allow", "deny", "require_reauth", "log_only"):
        raise ValueError("Invalid rule type or action.")
    if type(rule.get("enabled", True)) is not bool:
        raise ValueError("Rule enabled must be a boolean.")
    for key, limit in (("id", 100), ("name", 200), ("description", 4000)):
        if not isinstance(rule.get(key), str) or not rule[key].strip() or len(rule[key]) > limit:
            raise ValueError("Invalid rule text.")
    scopes = rule.get("operations", ["*"])
    if not isinstance(scopes, (list, tuple)) or not scopes or len(scopes) > 100:
        raise ValueError("A rule needs explicit operation scopes or '*'.")
    if any(not isinstance(scope, str) or (scope != "*" and scope not in OPERATIONS) for scope in scopes):
        raise ValueError("A rule names an unknown operation.")
    return {**rule, "enabled": rule.get("enabled", True), "operations": list(scopes)}

@dataclass(frozen=True)
class Operation:
    sensitive: bool = False
    double_confirmation: bool = False
    moral_context_required: bool = False

OPERATIONS = MappingProxyType({
    "rules.read": Operation(),
    "rules.add": Operation(True),
    "rules.save": Operation(True),
    "rules.delete": Operation(True),
    "rules.disable": Operation(True),
    "moral.read": Operation(),
    "moral.notes.update": Operation(True),
    "scripture.read": Operation(),
    "scripture.import": Operation(True),
    "scripture.context.update": Operation(True),
    "relationship.advice": Operation(moral_context_required=True),
    "accountability.plan": Operation(moral_context_required=True),
    "life.protect": Operation(moral_context_required=True),
    "chat.reply": Operation(),
    "voice.service.open": Operation(True),
    "calendar.read": Operation(),
    "calendar.write": Operation(True),
    "calendar.delete": Operation(True),
    "tasks.read": Operation(),
    "tasks.write": Operation(True),
    "files.read": Operation(),
    "files.move": Operation(True),
    "files.rename": Operation(True),
    "files.delete": Operation(True, True),
    "behavior.read": Operation(),
    "behavior.write": Operation(True),
    "behavior.record": Operation(),
    "personality.read": Operation(),
    "personality.write": Operation(True),
    "files.write": Operation(True),
    "weather.read": Operation(),
    "traffic.read": Operation(),
    "briefing.generate": Operation(),
    "carplay.session.update": Operation(),
    "carplay.audio.read": Operation(),
    "status.read": Operation(),
    # UI functions the owner allowed for token clients (Oct 2026). Each is
    # narrow: the UI's own task list, ZÆNIA scheduling events, chat history,
    # spoken replies and file-change proposals. Applying a file change needs
    # the paired desktop approval key on top of the token.
    "ui.tasks.write": Operation(),
    "ui.tasks.delete": Operation(),
    "ui.calendar.write": Operation(),
    "ui.calendar.delete": Operation(),
    "chat.history.read": Operation(),
    "chat.speak": Operation(),
    "files.propose": Operation(),
    "files.desktop.apply": Operation(),
    # Speech-to-text for the UI microphone; audio is not stored.
    "voice.transcribe": Operation(),
    # Local personal memory and the assistant's local notification inbox.
    "memory.read": Operation(),
    "memory.write": Operation(),
    "notifications.read": Operation(),
    "notifications.write": Operation(),
    "assistant.settings.write": Operation(),
    "assistant.platform.read": Operation(),
    "assistant.platform.write": Operation(),
    "assistant.desktop.manage": Operation(),
    "assistant.apps.launch": Operation(),
    "assistant.documents.read": Operation(),
    "profile.export": Operation(True),
    "profile.restore": Operation(True, True),
    "auth.token.create": Operation(True),
    "auth.token.rotate": Operation(True),
    "auth.token.revoke": Operation(True),
    "auth.speaker.enroll": Operation(True),
    "auth.speaker.calibrate": Operation(True),
    "auth.mic.change": Operation(True),
    "auth.mic.reset": Operation(True),
    "auth.voice.enroll": Operation(True),
    "auth.voice.reset": Operation(True),
    "security.backup": Operation(True),
    "security.restore": Operation(True),
})
LEGACY_OPERATIONS = MappingProxyType({
    "list_rules": "rules.read", "show_rules": "rules.read",
    "calendar_delete": "calendar.delete", "file_delete": "files.delete",
})

@dataclass(frozen=True)
class ActionRequest:
    operation: str
    params: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> "ActionRequest":
        if not isinstance(self.operation, str) or self.operation not in OPERATIONS or not isinstance(self.params, dict):
            raise ValueError("Unknown operation or malformed parameters.")
        encoded = json.dumps(self.params, sort_keys=True, allow_nan=False, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 65536:
            raise ValueError("Action parameters exceed the size limit.")
        return ActionRequest(self.operation, json.loads(encoded))
