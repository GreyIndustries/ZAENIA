from __future__ import annotations

from typing import Any

from core.brain.local_llm import (
    no_think_prefix,
    chat_local,
)


SPECULATIVE_INTENT_TERMS = (
    "reserved for",
    "kept for",
    "intended for",
    "meant for",
    "probably kept",
    "likely kept",
    "future reactivation",
    "future use",
    "planned to",
    "designed to eventually",
)


def contains_obvious_intent_speculation(
    text: str,
) -> bool:
    """
    Detect common unsupported statements about developer intent.

    This is not the main verifier.

    It is a diagnostic signal that helps us determine whether
    the first draft contained wording that should receive
    especially strict review.
    """

    lowered = text.lower()

    return any(
        phrase in lowered
        for phrase in SPECULATIVE_INTENT_TERMS
    )


def build_verification_rules() -> str:
    """
    Rules for the second local reasoning pass.

    The verifier's job is not to create a new answer from
    imagination.

    Its job is to audit the first answer against the supplied
    local evidence and rewrite it when necessary.
    """

    return """
You are ZÆNIA's local evidence-verification layer.

You are given:

1. Zack's original question.
2. ZÆNIA's draft answer.
3. The exact local evidence used to create that answer.

Your task is to return a corrected final answer.

VERIFICATION RULES:

1. Every factual claim about ZÆNIA's current system must be
   supported by the supplied local evidence.

2. Do not use pretrained model knowledge as evidence about
   ZÆNIA's current installation.

3. Remove or correct claims that go beyond the evidence.

4. Never infer developer or user intent from the mere
   existence of code.

   Unsupported examples include:
   - "reserved for future use"
   - "kept for reactivation"
   - "intended as a backup"
   - "probably left there"
   - "designed for future migration"

   Those claims are allowed only if the supplied evidence
   explicitly states that intent.

5. Distinguish carefully between:
   - configured and enabled
   - configured but disabled
   - source code merely existing
   - a script referencing a capability
   - verified runtime activity

6. A function existing in source code does NOT prove that
   the function is currently being executed.

7. A configuration value such as:
       enabled: false
   is evidence that the feature is configured as disabled.

8. A provider field is evidence of configured provider state,
   not necessarily proof that a process is currently running
   at this exact millisecond.

9. Do not describe something as:
   - dormant
   - active
   - running
   - unused
   - legacy
   unless the supplied evidence supports that wording.

   If only code existence is proven, say that the code
   "exists" or "remains present."

10. If multiple subsystems differ, explain the distinction.

11. If evidence is insufficient for part of the question,
    explicitly say that the supplied local evidence does not
    establish that part.

12. Never invent:
    - paths
    - filenames
    - providers
    - configuration values
    - dependencies
    - runtime state
    - reasons for architectural decisions

13. Never expose secrets, API keys, passphrases, tokens,
    encryption keys, or secret URLs.

14. Preserve useful factual details from the draft when they
    are supported.

15. Keep the answer natural and concise.

16. Return ONLY the corrected user-facing answer.
    Do not explain your verification process.
""".strip()


def verify_grounded_answer(
    *,
    question: str,
    draft_answer: str,
    evidence_block: str,
) -> dict[str, Any]:
    """
    Run a second local Qwen pass whose only job is verifying
    the proposed answer against the evidence.

    This gives us two different cognitive jobs:

        generation
        verification

    rather than asking one model pass to both answer and
    police itself simultaneously.
    """

    question = question.strip()

    draft_answer = (
        draft_answer.strip()
    )

    if not draft_answer:
        return {
            "answer": "",
            "verification_applied": False,
            "draft_had_intent_speculation": False,
        }

    speculation_detected = (
        contains_obvious_intent_speculation(
            draft_answer
        )
    )

    verification_context = (
        build_verification_rules()
        + "\n\n"
        + "LOCAL EVIDENCE:\n"
        + evidence_block
        + "\n\n"
        + "ORIGINAL QUESTION:\n"
        + question
        + "\n\n"
        + "DRAFT ANSWER:\n"
        + draft_answer
    )

    verification_prompt = (
        no_think_prefix()
        + "Verify the draft answer against the supplied "
        "local evidence and return the corrected final answer."
    )

    verified_answer = chat_local(
        verification_prompt,
        conversation_context=verification_context,
    ).strip()

    if not verified_answer:
        verified_answer = (
            draft_answer
        )

    return {
        "answer": verified_answer,
        "verification_applied": True,
        "draft_had_intent_speculation": (
            speculation_detected
        ),
    }