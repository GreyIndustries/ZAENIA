"""Deterministic boundaries for reviewed action assessments, not a mind reader."""
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True)
class MoralCase:
    # Facts must come from trusted evidence/review. A planner's labels aren't proof.
    purpose: Literal["ordinary", "protect", "restore", "accountability", "interpret", "unknown"] = "ordinary"
    facts_confirmed: bool = False
    threats: tuple[str, ...] = ()
    proposed_methods: tuple[str, ...] = ()
    immediate_life_risk: bool = False
    proportionate: bool | None = None
    protective: bool | None = None
    contextual_scripture_reviewed: bool = False
    uncertainty: tuple[str, ...] = ()

@dataclass(frozen=True)
class MoralDecision:
    decision: Literal["ALLOW", "BLOCK", "ASK_FOR_CONTEXT"]
    reason_code: str
    reason: str
    principles: tuple[str, ...] = field(default_factory=tuple)

_FORBIDDEN = frozenset({
    "final_spiritual_condemnation", "claim_divine_authority", "impose_atonement",
    "vengeance", "dehumanize", "coerce", "exploit", "conceal_abuse",
    "manipulate", "force_reconciliation", "force_contact_with_abuser",
    "needless_harm", "betray_confidentiality",
})
_THREATS = frozenset({"coercion", "abuse", "exploitation", "betrayal", "manipulation", "life_threat", "animal_cruelty", "environmental_harm"})
_METHODS = _FORBIDDEN | frozenset({"protective_boundary", "seek_help", "fair_accountability", "deescalate", "listen", "restore", "ordinary_assistance"})

def evaluate_moral_case(case: MoralCase | None, *, context_required: bool = False) -> MoralDecision:
    if case is None:
        return MoralDecision("ASK_FOR_CONTEXT", "assessment_required", "This action needs a reviewed moral assessment.", ("M05", "M08")) if context_required else MoralDecision("ALLOW", "ordinary_assistance", "Ordinary assistance may proceed within the security rules.", ("M01", "M02"))
    if not isinstance(case, MoralCase):
        return MoralDecision("BLOCK", "invalid_assessment", "Malformed moral assessment.")
    if any(not isinstance(values,(list,tuple)) or any(not isinstance(v,str) or len(v)>4000 for v in values) for values in (case.threats,case.proposed_methods,case.uncertainty)) or any(v is not None and type(v) is not bool for v in (case.proportionate,case.protective)):
        return MoralDecision("BLOCK", "invalid_assessment", "Malformed moral assessment.")
    if not isinstance(case.purpose,str) or case.purpose not in {"ordinary", "protect", "restore", "accountability", "interpret", "unknown"} or any(type(flag) is not bool for flag in (case.facts_confirmed, case.immediate_life_risk, case.contextual_scripture_reviewed)):
        return MoralDecision("BLOCK", "invalid_assessment", "Malformed moral assessment.")
    if any(method not in _METHODS for method in case.proposed_methods) or any(threat not in _THREATS for threat in case.threats):
        return MoralDecision("ASK_FOR_CONTEXT", "undefined_concern", "Define the concern and proposed response; labels alone are not evidence.", ("M08", "M09"))
    if set(case.proposed_methods) & _FORBIDDEN:
        return MoralDecision("BLOCK", "moral_boundary", "The proposed method conflicts with dignity, protection, or limits on spiritual judgment.", ("M02", "M04", "M06", "M07"))
    if case.immediate_life_risk:
        if case.purpose == "protect" and case.protective is True and case.proportionate is True:
            return MoralDecision("ALLOW", "protect_life", "Prioritize a proportionate protective response. Tool permissions still apply.", ("M05", "M06"))
        return MoralDecision("ASK_FOR_CONTEXT", "protective_response_required", "Protect life promptly; clarify a safe protective response.", ("M05",))
    if case.uncertainty or case.purpose == "unknown":
        return MoralDecision("ASK_FOR_CONTEXT", "uncertain_application", "Obtain missing facts or context before a consequential judgment.", ("M03", "M08", "M09"))
    if case.threats and not case.facts_confirmed:
        return MoralDecision("ASK_FOR_CONTEXT", "threat_evidence_missing", "Protective boundaries may be prudent; a claim about another person's conduct still needs evidence.", ("M05", "M08"))
    if case.purpose == "accountability":
        if not case.facts_confirmed or case.protective is not True or case.proportionate is not True:
            return MoralDecision("ASK_FOR_CONTEXT", "accountability_needs_context", "Accountability must be evidence-based, protective and proportionate.", ("M05", "M06", "M08"))
        return MoralDecision("ALLOW", "protective_accountability", "Support fair accountability serving protection, without vengeance or spiritual condemnation.", ("M04", "M05", "M06"))
    if case.purpose == "interpret" and not case.contextual_scripture_reviewed:
        return MoralDecision("ASK_FOR_CONTEXT", "scripture_context_missing", "Original language, glosses, translations and passage context must be reviewed.", ("M09",))
    if context_required and not case.facts_confirmed:
        return MoralDecision("ASK_FOR_CONTEXT", "facts_missing", "The proposed action needs confirmed facts and relational context.", ("M07", "M08"))
    return MoralDecision("ALLOW", "consistent_with_compass", "Proceed with dignity, humility and care for relationships.", ("M01", "M02", "M03", "M07"))

def guidance_for_generation() -> str:
    """Guidance for an LLM; this text itself is not an authorization mechanism."""
    return (
        "ZÆNIA's owner-defined moral compass: God's love and Christ's example are central. "
        "Every human retains dignity as God's image; imperfect people can grow together. "
        "Protect life and relationships, including care for animals and nature. "
        "Accountability must serve protection; avoid vengeance, coercion, exploitation and dehumanization. "
        "Do not pronounce final spiritual condemnation or claim divine authority or atonement. "
        "For biblical discernment retain original-language evidence, glosses, translations, "
        "surrounding passage, time, culture, speaker, audience and situation. "
        "Disclose missing context; never fabricate scripture. Be concise; do not turn routine work into sermons. "
        "These principles do not grant command execution or permission to alter security rules."
    )
