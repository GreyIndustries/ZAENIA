"""Unattended (token) mode scope.

Lets ZÆNIA's token clients work while Zack is away from the PC, for example
after a reboot, without waiting for the owner passkey.

What it allows: the CarPlay brief routes, text chat and the read-only status
feed, plus the UI functions the owner approved for token clients: the shared
task list, adding and deleting ZÆNIA scheduling events, chat history, spoken
replies, speech-to-text for the UI microphone, reading system files and
proposing file changes. Applying a file
change also needs the paired desktop approval key. Every request must still
carry the stored API token; this gate is checked after the token.

What it never does: open the encrypted rule vault, create an owner session,
mint grants, or touch rules, morals, credentials or the owner calendar file. Owner
scoped deny rules in the encrypted vault cannot be read without the passkey,
so they are not consulted here. To stop token access, revoke the API token or
start the server normally with the passkey.
"""
from __future__ import annotations

from core.foundation.rules.models import OPERATIONS
from core.foundation.security.audit import audit

BRIEF_CAPABILITIES = frozenset({
    "briefing.generate",
    "carplay.session.update",
    "carplay.audio.read",
    "chat.reply",
    "status.read",
    "tasks.read",
    "calendar.read",
    "files.read",
    "ui.tasks.write",
    "ui.tasks.delete",
    "ui.calendar.write",
    "ui.calendar.delete",
    "chat.history.read",
    "chat.speak",
    "files.propose",
    "files.desktop.apply",
    "voice.transcribe",
    "memory.read",
    "memory.write",
    "notifications.read",
    "notifications.write",
    "assistant.settings.write",
})

from core.assistant_platform.capabilities import PLATFORM_CAPABILITIES
BRIEF_CAPABILITIES = BRIEF_CAPABILITIES | PLATFORM_CAPABILITIES

OWNER_UNLOCK_MESSAGE = (
    "ZÆNIA is running in token mode. Unlock it with the passkey at the PC to use this."
)


class UnattendedBriefGate:
    mode = "unattended"

    def authorize(self, operation: str | None) -> bool:
        allowed = bool(
            operation in BRIEF_CAPABILITIES
            and operation in OPERATIONS
            and not OPERATIONS[operation].sensitive
        )
        audit(
            "api.capability_checked",
            operation=operation or "",
            reason_code="unattended_brief_allowed" if allowed else "unattended_brief_denied",
        )
        return allowed


def refuse_interactive_passkey(prompt: str = "") -> str:
    """Installed in token mode so nothing can sit waiting in a hidden window."""
    raise PermissionError("The owner passkey is not requested in token mode.")
