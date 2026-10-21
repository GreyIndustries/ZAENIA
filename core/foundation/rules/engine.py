"""Owner-authorized typed dispatcher. Treat model text as untrusted proposals."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import threading
from typing import Any, Callable
from core.foundation.auth.passkey import consume_fresh_auth
from core.foundation.auth.session import ActionGrant, AuthSession, Confirmation
from core.foundation.moral_code.engine import MoralCase, evaluate_moral_case
from core.foundation.moral_code.vault import load_policy, validate_policy
from core.foundation.rules.models import ActionRequest, OPERATIONS, LEGACY_OPERATIONS
from core.foundation.rules.vault import CANONICAL_HARD, load_vault, mutate_soft_rule, normalize_vault
from core.foundation.security.audit import audit
from core.foundation.security.io import reject_link
from core.foundation.storage.paths import VAULT_FILE, MORAL_VAULT_FILE

@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason_code: str
    reason: str
    requires_reauth: bool = False
    requires_confirmation: bool = False
    execution_authorized: bool = False

class RuleEngine:
    """Trusted host constructs/registers this object; never expose it to an LLM.

    Authorization exists only during execute(), never as a transferable ALLOW.
    Handlers and validators are trusted application code, not plugin/model text.
    """
    def __init__(self, session: AuthSession, vault: dict, policy: dict):
        session.require_valid()
        self._session = session
        self._vault = normalize_vault(vault)
        self._policy = validate_policy(policy)
        self._handlers: dict[str, tuple[Callable, Callable]] = {}
        self._sealed = False
        self._lock = threading.RLock()
        self._generation = self._policy_generation()

    @classmethod
    def open(cls, passphrase: str) -> "RuleEngine":
        session = AuthSession()
        session.mark_authenticated(passphrase)
        return cls(session, load_vault(passphrase), load_policy(passphrase))

    @staticmethod
    def _policy_generation() -> tuple[str, str]:
        for path in (VAULT_FILE, MORAL_VAULT_FILE):
            reject_link(path)
        return tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (VAULT_FILE, MORAL_VAULT_FILE))

    @property
    def session(self) -> AuthSession:
        return self._session

    def register(self, operation: str, handler: Callable, validator: Callable) -> None:
        """Startup only. Validator must check resource bounds and return a dict."""
        with self._lock:
            self._session.require_valid()
            if self._sealed or operation not in OPERATIONS or operation in self._handlers:
                raise PermissionError("Unknown, duplicate, or late handler registration.")
            if not callable(handler) or not callable(validator):
                raise TypeError("Both a trusted handler and parameter validator are required.")
            self._handlers[operation] = (handler, validator)

    def seal(self) -> None:
        with self._lock:
            self._sealed = True

    def prepare(self, request: ActionRequest) -> ActionRequest:
        request = request.snapshot()
        if request.operation not in self._handlers:
            raise ValueError("No trusted handler is registered for this operation.")
        canonical = self._handlers[request.operation][1](request.params)
        return ActionRequest(request.operation, canonical).snapshot()

    def _check(self, request: ActionRequest, *, grant: ActionGrant | None,
               confirmation: Confirmation | None, moral_case: MoralCase | None,
               moral_review: ActionGrant | None) -> GateDecision:
        op = request.operation
        if not self._session.is_valid():
            return GateDecision(False, "owner_session_required", "Authenticate the owner before execution.")
        try:
            if self._generation != self._policy_generation():
                return GateDecision(False, "policy_changed", "Policy changed; reopen the authenticated engine.")
            validate_policy(self._policy)
            normalize_vault(self._vault)
        except (OSError, ValueError, PermissionError):
            return GateDecision(False, "invalid_policy", "Protected policy cannot be validated.")
        matched = [r for r in self._vault["rules"] if r["enabled"] and r["id"] not in CANONICAL_HARD
                   and ("*" in r["operations"] or op in r["operations"])]
        if any(r["action"] == "deny" for r in matched):
            return GateDecision(False, "scoped_rule_denied", "An enabled rule denies this operation.")
        spec = OPERATIONS[op]
        moral = evaluate_moral_case(moral_case, context_required=spec.moral_context_required)
        if moral.decision != "ALLOW":
            return GateDecision(False, moral.reason_code, moral.reason)
        # Planner claims of confirmed facts do not count as trusted review.
        needs_review = spec.moral_context_required or (moral_case is not None and moral_case.purpose != "ordinary")
        if needs_review:
            binding = {"request": {"operation": op, "params": request.params}, "case": asdict(moral_case)}
            if not self._session.grant_valid(moral_review, "moral.review", binding):
                return GateDecision(False, "owner_moral_review_required", "Owner must review the facts, context and proposed response.", True)
        needs_reauth = spec.sensitive or any(r["action"] == "require_reauth" for r in matched)
        if needs_reauth and not self._session.grant_valid(grant, op, request.params):
            return GateDecision(False, "exact_action_reauth_required", "Fresh authentication must match this exact action and parameters.", True)
        if spec.double_confirmation and not self._session.consume_double_confirmation(confirmation,op,request.params,consume=False):
            return GateDecision(False, "double_confirmation_required", "Two owner confirmations are required for permanent file deletion.", requires_confirmation=True)
        for rule in matched:
            if rule["action"] == "log_only":
                audit("rule.matched", operation=op, reason_code="scoped_log_rule")
        return GateDecision(True, "gate_passed", "Checks passed; execution remains confined to the registered handler.")

    def evaluate(self, request: ActionRequest, *, grant=None, confirmation=None, moral_case=None, moral_review=None) -> GateDecision:
        with self._lock:
            self.seal()
            try:
                request = self.prepare(request)
            except (ValueError, TypeError, KeyError):
                return GateDecision(False, "invalid_request", "Unknown operation or invalid action parameters.")
            return self._check(request, grant=grant, confirmation=confirmation, moral_case=moral_case, moral_review=moral_review)

    def execute(self, request: ActionRequest, *, grant=None, confirmation=None, moral_case=None, moral_review=None) -> Any:
        with self._lock:
            self.seal()
            request = self.prepare(request)
            decision = self._check(request, grant=grant, confirmation=confirmation, moral_case=moral_case, moral_review=moral_review)
            audit("gate.checked", operation=request.operation, reason_code=decision.reason_code)
            if not decision.allowed:
                raise PermissionError(decision.reason)
            spec = OPERATIONS[request.operation]
            if spec.double_confirmation and not self._session.consume_double_confirmation(confirmation, request.operation, request.params):
                raise PermissionError("Double confirmation is invalid, mismatched, expired or already used.")
            matched = [r for r in self._vault["rules"] if r["enabled"] and r["id"] not in CANONICAL_HARD
                       and ("*" in r["operations"] or request.operation in r["operations"])]
            if spec.sensitive or any(r["action"] == "require_reauth" for r in matched):
                if not self._session.grant_valid(grant, request.operation, request.params, consume=True):
                    raise PermissionError("Fresh action authorization was already used or revoked.")
            if spec.moral_context_required or (moral_case is not None and moral_case.purpose != "ordinary"):
                binding = {"request": {"operation": request.operation, "params": request.params}, "case": asdict(moral_case)}
                if not self._session.grant_valid(moral_review, "moral.review", binding, consume=True):
                    raise PermissionError("Moral review was already used or revoked.")
            self._session.require_valid()
            if self._generation != self._policy_generation():
                raise PermissionError("Policy changed before execution.")
            audit("action.started", operation=request.operation, reason_code="registered_handler")
            try:
                result = self._handlers[request.operation][0](request.params)
            except Exception:
                audit("action.failed", operation=request.operation, reason_code="handler_error")
                raise
            audit("action.completed", operation=request.operation, reason_code="registered_handler")
            return result

    def close(self) -> None:
        self._session.logout()

def is_sensitive_operation(operation: str) -> bool:
    name = LEGACY_OPERATIONS.get(operation, operation)
    return name not in OPERATIONS or OPERATIONS[name].sensitive

def evaluate_operation(operation: str, passphrase: str) -> dict:
    """Legacy diagnostic only: an allowed result never authorizes execution."""
    consume_fresh_auth(passphrase, operation="rules.check", payload={"operation": operation})
    name = LEGACY_OPERATIONS.get(operation, operation)
    vault = load_vault(passphrase)
    load_policy(passphrase)
    matched = [r for r in vault["rules"] if r["enabled"] and r["id"] not in CANONICAL_HARD and ("*" in r["operations"] or name in r["operations"])]
    denied = name not in OPERATIONS or any(r["action"] == "deny" for r in matched)
    reauth = not denied and (OPERATIONS[name].sensitive or any(r["action"] == "require_reauth" for r in matched))
    return {"allowed": not denied and not reauth, "requires_reauth": reauth,
            "execution_authorized": False, "reason": "Diagnostic only. Unknown actions are denied; actual execution needs the registered dispatcher."}

def delete_rule(rule_id: str, passphrase: str) -> dict:
    return mutate_soft_rule(rule_id, passphrase, operation="rules.delete")

def disable_rule(rule_id: str, passphrase: str) -> dict:
    return mutate_soft_rule(rule_id, passphrase, operation="rules.disable")
