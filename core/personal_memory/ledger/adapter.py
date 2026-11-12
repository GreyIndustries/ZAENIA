"""Host-side integration helpers. No network/model API or live ZAENIA imports.

Authentication, attention gating, routing and capability checks stay in the host.
"""
from __future__ import annotations

import json
from typing import Any

from .user_learning import ObservationContext, UserMemory, turn_scope


def build_turn_context(memory: UserMemory, text: str, ctx: ObservationContext, *,
                       project_scopes: tuple[str, ...] = (), mode: str | None = None,
                       requested_detail: str | None = None,
                       include_sensitive: bool = False,
                       learn: bool = True) -> dict[str, Any]:
    """Call after the existing foundation has accepted the owner turn.

    requested_detail, project_scopes, mode and include_sensitive are host policy,
    never fields an untrusted memory proposal may set. This returns DATA.
    """
    ctx.validate()
    learned = memory.learn_text(text, ctx) if learn else []
    scopes = list(project_scopes)
    if mode:
        scopes.append("mode:" + mode)
    if ctx.session_id:
        scopes.append("session:" + ctx.session_id)
    scopes.append(turn_scope(ctx.message_id))
    result = memory.retrieve(text, scopes=scopes, namespace=ctx.namespace,
                             include_sensitive=include_sensitive, limit=12)
    # Retrieve style separately so a hardware question can still honor the
    # session's detail override. Budget this independently in the host prompt.
    style = memory.retrieve("communication detail tone catchphrases closers motivation avoid phrase",
                            scopes=scopes, namespace=ctx.namespace,
                            include_sensitive=False, limit=8, max_chars=4000)
    states = memory.retrieve("state energy tired", scopes=scopes, namespace=ctx.namespace,
                             include_sensitive=False, limit=3, max_chars=1800)
    detail = requested_detail
    if detail is None:
        item = next((m for m in style["memories"] if m["key"] == "communication.detail"), None)
        detail = item["value"] if item else None
        if any(m["key"] == "state.energy" and m["value"] == "tired" for m in states["memories"]):
            detail = "essentials and a clean stopping point"
    return {
        "data_only": True,
        "current_request_detail": requested_detail,
        "suggested_detail": detail,
        "relevant_memory": result,
        "style_memory": style,
        "temporary_state": states,
        "learning_changes": [{"key": r["key"], "status": r["status"]} for r in learned],
        "boundary": "The host's current instructions, authorization and attention rules remain authoritative.",
    }


def stage_model_proposals(memory: UserMemory, owner_text: str, proposals: list[dict[str, Any]],
                          ctx: ObservationContext, *, allowed_scopes: tuple[str, ...] = ("global",)) -> list[dict[str, Any]]:
    """Optional local-LLM extractor output is always candidate-only.

    Exact quote matching is a provenance check, not proof of a correct inference.
    Unsupported keys, large values and secrets are rejected by UserMemory.
    """
    ctx.validate()
    if not isinstance(proposals, list) or len(proposals) > 12:
        raise ValueError("Expected at most 12 memory proposals.")
    results = []
    for i, proposal in enumerate(proposals):
        if not isinstance(proposal, dict) or set(proposal) - {"key", "value", "quote", "scope", "suggested_kind"}:
            results.append({"index": i, "status": "rejected", "reason": "Invalid proposal fields."})
            continue
        quote = proposal.get("quote")
        scope = proposal.get("scope", "global")
        if not isinstance(quote, str) or not quote.strip() or len(quote) > 400 or quote not in owner_text:
            results.append({"index": i, "status": "rejected", "reason": "No exact bounded owner-text evidence."})
            continue
        if scope not in allowed_scopes:
            results.append({"index": i, "status": "rejected", "reason": "Scope is not allowed by the host."})
            continue
        try:
            item = memory.observe(proposal["key"], proposal["value"], ctx,
                                  kind="inference", evidence_type="assistant_hypothesis",
                                  scope=scope, quote=quote, confidence=.45,
                                  note="Model-extracted proposal, awaiting direct owner confirmation. "
                                       "Suggested kind: " + str(proposal.get("suggested_kind", "unknown"))[:40])
            results.append({"index": i, "id": item.get("id"), "status": item["status"]})
        except (ValueError, TypeError, KeyError, PermissionError) as exc:
            results.append({"index": i, "status": "rejected", "reason": str(exc)})
    return results


def as_data_message(context: dict[str, Any]) -> str:
    """Use as a clearly labeled data/tool message, never as executable instructions."""
    return json.dumps(context, ensure_ascii=False, sort_keys=True, allow_nan=False)
