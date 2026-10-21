"""Owner sessions and one-use grants bound to the exact proposed action."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import secrets
import threading
import time
from typing import Any
from core.foundation.auth.passkey import (
    AuthenticatedPassphrase, authenticate_passphrase, consume_fresh_auth,
    credential_generation, payload_digest, require_passkey,
)
from core.foundation.security.audit import audit

_SESSIONS: dict[str, dict] = {}
_GRANTS: dict[str, dict] = {}
_CONFIRMATIONS: dict[str, dict] = {}
_LOCK = threading.RLock()

@dataclass(frozen=True)
class ActionGrant:
    token: str

@dataclass(frozen=True)
class Confirmation:
    token: str

class AuthSession:
    def __init__(self, minutes_valid: int = 10):
        if type(minutes_valid) is not int or not 1 <= minutes_valid <= 60:
            raise ValueError("Session lifetime must be between 1 and 60 minutes.")
        self.minutes_valid = minutes_valid
        self.authenticated_at: datetime | None = None
        self._id = secrets.token_urlsafe(32)

    def mark_authenticated(self, passphrase: str | None = None) -> None:
        if passphrase is None:
            proof = require_passkey()
        elif isinstance(passphrase, AuthenticatedPassphrase):
            proof = passphrase
        else:
            proof = authenticate_passphrase(passphrase)
        consume_fresh_auth(proof, operation="session.open")
        with _LOCK:
            _SESSIONS[self._id] = {
                "instance": self, "expires": time.monotonic() + self.minutes_valid * 60,
                "generation": credential_generation(),
            }
        self.authenticated_at = datetime.now(timezone.utc)

    def is_valid(self) -> bool:
        with _LOCK:
            record = _SESSIONS.get(self._id)
            if not record or record["instance"] is not self:
                return False
            try:
                valid = record["expires"] > time.monotonic() and record["generation"] == credential_generation()
            except OSError:
                valid = False
            if not valid:
                self.logout()
            return valid

    def require_valid(self) -> None:
        if not self.is_valid():
            raise PermissionError("Owner session expired or revoked. Authenticate again.")

    def logout(self) -> None:
        with _LOCK:
            _SESSIONS.pop(self._id, None)
            for registry in (_GRANTS, _CONFIRMATIONS):
                for key in list(registry):
                    if registry[key]["session"] == self._id:
                        del registry[key]
        self.authenticated_at = None

    def reauthenticate(self, operation: str, params: Any, passphrase: str | None = None) -> ActionGrant:
        self.require_valid()
        binding = {"operation": operation, "params": params}
        proof = (
            require_passkey(operation="action.reauthenticate", payload=binding)
            if passphrase is None else
            authenticate_passphrase(passphrase, operation="action.reauthenticate", payload=binding)
        )
        consume_fresh_auth(proof, operation="action.reauthenticate", payload=binding)
        # Rehashing may revoke the session; reopen its same verified owner generation.
        with _LOCK:
            record = _SESSIONS.get(self._id)
            if not record:
                raise PermissionError("Session has been revoked.")
            record["generation"] = credential_generation()
            grant = ActionGrant(secrets.token_urlsafe(32))
            _GRANTS[grant.token] = {
                "object": grant, "session": self._id, "binding": payload_digest(binding),
                "expires": time.monotonic() + 60,
            }
        return grant

    def grant_valid(self, grant: ActionGrant | None, operation: str, params: Any, *, consume: bool = False) -> bool:
        if not self.is_valid() or not isinstance(grant, ActionGrant):
            return False
        with _LOCK:
            record = _GRANTS.get(grant.token)
            valid = bool(
                record and record["object"] is grant and record["session"] == self._id
                and record["expires"] > time.monotonic()
                and record["binding"] == payload_digest({"operation": operation, "params": params})
            )
            if valid and consume:
                del _GRANTS[grant.token]
            return valid

    def confirm_after_owner_choice(self, operation: str, params: Any, *, previous: Confirmation | None = None) -> Confirmation:
        """Trusted UI only: call after an actual owner confirmation, never from a planner."""
        self.require_valid()
        binding = payload_digest({"operation": operation, "params": params})
        with _LOCK:
            stage = 1
            if previous is not None:
                record = _CONFIRMATIONS.get(previous.token)
                if not record or record["object"] is not previous or record["session"] != self._id or record["binding"] != binding or record["stage"] != 1 or record["expires"] <= time.monotonic():
                    raise PermissionError("The first confirmation is missing or mismatched.")
                del _CONFIRMATIONS[previous.token]
                stage = 2
            proof = Confirmation(secrets.token_urlsafe(32))
            _CONFIRMATIONS[proof.token] = {
                "object": proof, "session": self._id, "binding": binding,
                "stage": stage, "expires": time.monotonic() + 120,
            }
            return proof

    def consume_double_confirmation(self, proof: Confirmation | None, operation: str, params: Any, *, consume: bool = True) -> bool:
        if not self.is_valid() or not isinstance(proof, Confirmation):
            return False
        with _LOCK:
            record = _CONFIRMATIONS.get(proof.token)
            valid = bool(
                record and record["object"] is proof and record["session"] == self._id
                and record["binding"] == payload_digest({"operation": operation, "params": params})
                and record["stage"] == 2 and record["expires"] > time.monotonic()
            )
            if valid and consume:
                del _CONFIRMATIONS[proof.token]
            return valid
