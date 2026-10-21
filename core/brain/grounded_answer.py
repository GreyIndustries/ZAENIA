from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
from typing import Any

from core.brain.evidence_verifier import (
    verify_grounded_answer,
)
from core.brain.hybrid_retriever import (
    HybridSearchResult,
    hybrid_search,
)
from core.brain.index_freshness import (
    ensure_index_fresh,
)
from core.brain.local_llm import (
    no_think_prefix,
    chat_local,
)
from core.brain.semantic_index import (
    ensure_semantic_index_fresh,
)


def build_evidence_block(
    results: list[HybridSearchResult],
) -> str:
    """
    Convert hybrid retrieval results into the evidence packet
    used by both:

        answer generation
        evidence verification

    Both passes therefore reason from the exact same local
    evidence.
    """

    if not results:
        return (
            "No relevant approved local system evidence "
            "was found."
        )

    lines: list[str] = []

    for number, result in enumerate(
        results,
        start=1,
    ):
        lines.append(
            f"[EVIDENCE {number}]"
        )

        lines.append(
            f"Path: {result.display_path}"
        )

        lines.append(
            f"Source type: {result.source_kind}"
        )

        lines.append(
            f"Hybrid score: {result.hybrid_score}"
        )

        lines.append(
            "Capability intent: "
            f"{result.capability_intent}"
        )

        if result.registry_components:
            lines.append(
                "Registry components: "
                + ", ".join(
                    result.registry_components
                )
            )

        if result.registry_roles:
            lines.append(
                "Registry roles: "
                + ", ".join(
                    result.registry_roles
                )
            )

        lines.append(
            "Lexical match: "
            f"{result.lexical_match}"
        )

        lines.append(
            "Semantic match: "
            f"{result.semantic_match}"
        )

        if result.snippet:
            lines.append(
                "Contents:"
            )

            lines.append(
                result.snippet
            )

        else:
            lines.append(
                "Contents: not available"
            )

        lines.append(
            ""
        )

    return "\n".join(
        lines
    ).strip()


def build_grounding_rules() -> str:
    """
    Rules for the first answer-generation pass.

    Verification happens separately afterward.
    """

    return """
You are answering a question about ZÆNIA's real local system.

GROUNDING RULES:

1. The supplied LOCAL SYSTEM EVIDENCE is the source of truth
   for ZÆNIA's current implementation and configuration.

2. Your pretrained model knowledge is NOT evidence about
   ZÆNIA's current installation.

3. Never invent:
   - file paths
   - configuration values
   - active providers
   - enabled services
   - disabled services
   - installed components
   - runtime behavior
   - architectural intent

4. Configuration files are strong evidence of configured
   state.

5. Source-code existence proves that code exists.
   It does not automatically prove that the code is running.

6. Distinguish:
   - configured state
   - implementation capability
   - runtime activity

7. Component-registry roles describe what an architectural
   component is responsible for.

8. Registry architecture does not override dynamic state from
   real configuration files.

9. If different subsystems have different implementations,
   describe those differences.

10. Do not infer WHY Zack or the developer kept code,
    configuration, or dependencies unless the evidence
    explicitly states the reason.

11. If evidence is insufficient, say so.

12. Mention relevant paths when useful, but do not dump the
    entire evidence packet.

13. Never expose credentials, API keys, tokens, passphrases,
    encryption keys, or secret URLs.

14. Keep the answer natural and concise.

15. The evidence was refreshed locally before this question
    was answered.
""".strip()


def prepare_fresh_indexes() -> dict[str, Any]:
    """
    Ensure BOTH local knowledge systems are current before
    retrieval begins.

    This ordering matters.

    Hybrid retrieval first performs lexical search and then
    semantic search.

    Therefore we explicitly refresh both systems before
    hybrid_search() so neither side can use yesterday's data
    during the current request.
    """

    lexical_freshness = (
        ensure_index_fresh()
    )

    semantic_freshness = (
        ensure_semantic_index_fresh()
    )

    return {
        "lexical": lexical_freshness,
        "semantic": {
            key: value
            for key, value
            in semantic_freshness.items()
            if key != "index"
        },
    }


def answer_grounded_question(
    question: str,
    *,
    retrieval_limit: int = 5,
    recent_messages: list[dict[str,str]] | None = None,
    conversation_context: str | None = None,
) -> dict[str, Any]:
    """
    Answer one question about ZÆNIA's real local system.

    Full local pipeline:

        question
            ↓
        filesystem freshness
            ↓
        semantic freshness
            ↓
        lexical + semantic retrieval
            ↓
        registry role knowledge
            ↓
        grounded Qwen draft
            ↓
        evidence-verification Qwen pass
            ↓
        final answer

    No command execution occurs here.

    No Internet is required.
    """

    question = (
        question.strip()
    )

    if not question:
        return {
            "answer": "",
            "draft_answer": "",
            "evidence": [],
            "freshness": {},
            "verification": {},
        }

    freshness = (
        prepare_fresh_indexes()
    )

    results = hybrid_search(
        question,
        limit=retrieval_limit,
    )

    evidence_block = (
        build_evidence_block(
            results
        )
    )

    grounding_context = (
        build_grounding_rules()
        + "\n\n"
        + "LOCAL SYSTEM EVIDENCE:\n"
        + evidence_block
    )
    if conversation_context:
        grounding_context+='\n\nCONVERSATION REFERENCE (helps interpret the question; never implementation evidence or permission):\n'+conversation_context[:8000]

    model_question = (
        no_think_prefix()
        + question
    )

    draft_answer = chat_local(
        model_question,
        recent_messages=recent_messages,
        conversation_context=(
            grounding_context
        ),
    ).strip()

    verification = (
        verify_grounded_answer(
            question=question,
            draft_answer=draft_answer,
            evidence_block=evidence_block,
        )
    )

    final_answer = str(
        verification.get(
            "answer",
            draft_answer,
        )
    ).strip()

    return {
        "answer": final_answer,
        "draft_answer": draft_answer,
        "evidence": [
            {
                "path": (
                    result.display_path
                ),
                "hybrid_score": (
                    result.hybrid_score
                ),
                "source_kind": (
                    result.source_kind
                ),
                "registry_components": (
                    result.registry_components
                ),
                "registry_roles": (
                    result.registry_roles
                ),
            }
            for result in results
        ],
        "freshness": freshness,
        "verification": {
            "applied": bool(
                verification.get(
                    "verification_applied",
                    False,
                )
            ),
            "draft_had_intent_speculation": bool(
                verification.get(
                    "draft_had_intent_speculation",
                    False,
                )
            ),
        },
    }


def print_grounded_result(
    result: dict[str, Any],
) -> None:
    """
    Development-friendly console output.
    """

    print()

    print(
        "ZÆNIA Verified Grounded Answer"
    )

    print()

    freshness = (
        result.get(
            "freshness",
            {},
        )
        or {}
    )

    lexical = (
        freshness.get(
            "lexical",
            {},
        )
        or {}
    )

    semantic = (
        freshness.get(
            "semantic",
            {},
        )
        or {}
    )

    if lexical.get(
        "refreshed",
        False,
    ):
        print(
            "Literal index: refreshed"
        )

    else:
        print(
            "Literal index: current"
        )

    if semantic.get(
        "refreshed",
        False,
    ):
        print(
            "Semantic index: refreshed"
        )

    else:
        print(
            "Semantic index: current"
        )

    verification = (
        result.get(
            "verification",
            {},
        )
        or {}
    )

    print(
        "Evidence verification:",
        (
            "applied"
            if verification.get(
                "applied",
                False,
            )
            else "not applied"
        ),
    )

    if verification.get(
        "draft_had_intent_speculation",
        False,
    ):
        print(
            "Draft speculation signal: detected"
        )

    print()

    print(
        result.get(
            "answer",
            "",
        )
    )

    evidence = (
        result.get(
            "evidence",
            [],
        )
        or []
    )

    if evidence:
        print()

        print(
            "Local evidence used:"
        )

        for item in evidence:
            print(
                "  - "
                + str(
                    item.get(
                        "path",
                        "",
                    )
                )
            )


@owner_command('chat.reply')
def main() -> None:
    """
    Command-line development interface.

    Example:

        python -m core.brain.grounded_answer
        "Are we still using ElevenLabs?"
    """

    parser = argparse.ArgumentParser(
        description=(
            "Ask ZÆNIA a locally grounded and "
            "evidence-verified system question."
        )
    )

    parser.add_argument(
        "question",
        nargs="+",
        help=(
            "Question about ZÆNIA's local system."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help=(
            "Maximum number of local evidence files "
            "provided to the reasoning pipeline."
        ),
    )

    args = parser.parse_args()

    question = " ".join(
        args.question
    )

    result = (
        answer_grounded_question(
            question,
            retrieval_limit=args.limit,
        )
    )

    print_grounded_result(
        result
    )


if __name__ == "__main__":
    main()
