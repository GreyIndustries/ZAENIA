from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
import re
from dataclasses import dataclass
from typing import Any

from core.brain.component_registry import (
    ComponentRecord,
    get_components,
)
from core.brain.local_embeddings import (
    cosine_similarity,
    embed_text,
)
from core.brain.semantic_index import (
    load_semantic_index,
)
from core.brain.system_retriever import (
    SearchResult,
    classify_source,
    query_is_system_state,
    search_index,
    should_exclude_self_reference,
)


@dataclass
class SemanticCandidate:
    """
    Best semantic match found for one approved local file.
    """

    root: str
    path: str
    display_path: str
    extension: str

    similarity: float
    chunk_number: int
    text: str


@dataclass
class HybridSearchResult:
    """
    Final hybrid evidence result.

    Ranking combines:

        lexical relevance
        semantic similarity
        component-registry role knowledge

    Architectural role knowledge comes from
    component_registry.yaml rather than being duplicated here.
    """

    hybrid_score: float

    lexical_component: float
    semantic_component: float
    role_adjustment: float

    lexical_score: float
    semantic_similarity: float

    root: str
    path: str
    display_path: str

    source_kind: str
    capability_intent: str

    registry_components: list[str]
    registry_roles: list[str]

    snippet: str

    lexical_match: bool
    semantic_match: bool


CAPABILITY_ALIASES = {
    "speech_output": (
        "make your voice",
        "makes your voice",
        "create your voice",
        "creates your voice",
        "generate your voice",
        "generates your voice",
        "produce your voice",
        "produces your voice",
        "make you talk",
        "makes you talk",
        "make you speak",
        "makes you speak",
        "how do you talk",
        "how do you speak",
        "what makes you talk",
        "what makes you speak",
        "voice output",
        "speech output",
        "text to speech",
        "tts",
    ),

    "speech_input": (
        "hear me",
        "hear what i say",
        "understand my speech",
        "understand what i say",
        "listen to me",
        "listening to me",
        "speech recognition",
        "voice recognition",
        "speech input",
        "voice input",
        "speech to text",
        "stt",
        "transcribe me",
        "transcription",
    ),
}


RELATED_ROLE_GROUPS = {
    "speech_output": {
        "speech_output",
        "speech_input",
    },

    "speech_input": {
        "speech_input",
        "speech_output",
    },
}


def normalize_console_text(
    text: str,
) -> str:
    """
    Compress multiline evidence for terminal display.
    """

    text = text.replace(
        "\n",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_query(
    query: str,
) -> str:
    """
    Normalize natural-language input for deterministic
    capability-intent detection.
    """

    text = query.lower()

    text = re.sub(
        r"[^a-z0-9 ]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def determine_capability_intent(
    query: str,
) -> str:
    """
    Determine which system capability the question refers to.

    Example:

        "What actually makes your voice?"

    becomes:

        speech_output

    This layer identifies the REQUESTED ROLE.

    The component registry then determines which actual local
    files provide that role.
    """

    text = normalize_query(
        query
    )

    for (
        capability,
        phrases,
    ) in CAPABILITY_ALIASES.items():

        if any(
            phrase in text
            for phrase in phrases
        ):
            return capability

    return "general"


def semantic_search(
    query: str,
    *,
    minimum_similarity: float = 0.20,
) -> dict[str, SemanticCandidate]:
    """
    Search the automatically refreshed local semantic index.

    Only the strongest semantic chunk from each file is kept.
    """

    query = query.strip()

    if not query:
        return {}

    semantic_index = (
        load_semantic_index()
    )

    query_vector = (
        embed_text(
            query
        )
    )

    if not query_vector:
        return {}

    candidates: dict[
        str,
        SemanticCandidate,
    ] = {}

    for chunk in semantic_index.get(
        "chunks",
        [],
    ):
        path = str(
            chunk.get(
                "path",
                "",
            )
        )

        if not path:
            continue

        pseudo_record = {
            "path": path,
            "extension": chunk.get(
                "extension",
                "",
            ),
        }

        if should_exclude_self_reference(
            pseudo_record,
            query,
        ):
            continue

        vector = (
            chunk.get(
                "embedding",
                [],
            )
            or []
        )

        if not vector:
            continue

        similarity = cosine_similarity(
            query_vector,
            vector,
        )

        if similarity < minimum_similarity:
            continue

        existing = candidates.get(
            path
        )

        if (
            existing is not None
            and existing.similarity
            >= similarity
        ):
            continue

        root = str(
            chunk.get(
                "root",
                "",
            )
        )

        display_path = str(
            chunk.get(
                "display_path",
                "",
            )
        )

        if not display_path:
            display_path = (
                f"{root}:{path}"
            )

        candidates[
            path
        ] = SemanticCandidate(
            root=root,
            path=path,
            display_path=display_path,
            extension=str(
                chunk.get(
                    "extension",
                    "",
                )
            ),
            similarity=similarity,
            chunk_number=int(
                chunk.get(
                    "chunk_number",
                    0,
                )
            ),
            text=str(
                chunk.get(
                    "text",
                    "",
                )
            ),
        )

    return candidates


def lexical_results_by_path(
    results: list[SearchResult],
) -> dict[str, SearchResult]:
    """
    Convert lexical results into a path-addressable mapping.
    """

    return {
        result.path: result
        for result in results
    }


def get_lexical_max_score(
    results: list[SearchResult],
) -> float:
    """
    Return the strongest lexical score for normalization.
    """

    if not results:
        return 0.0

    return max(
        result.score
        for result in results
    )


def choose_weights(
    query: str,
) -> tuple[float, float]:
    """
    Current-state questions favor exact evidence.

    More conceptual questions favor semantic meaning.
    """

    if query_is_system_state(
        query
    ):
        return (
            0.65,
            0.35,
        )

    return (
        0.40,
        0.60,
    )


def normalize_registry_path(
    path: str,
) -> str:
    """
    Normalize registry and retrieval paths for comparison.
    """

    return (
        path.replace(
            "\\",
            "/",
        )
        .strip()
        .lower()
    )


def build_registry_path_map() -> dict[
    str,
    list[ComponentRecord],
]:
    """
    Build:

        source file path
            ->
        components that claim it as architectural evidence

    Example:

        core/voice_output/speaker.py
            ->
        [Voice Output]

    This is where retrieval learns what a file DOES.

    The mapping comes entirely from component_registry.yaml.
    """

    mapping: dict[
        str,
        list[ComponentRecord],
    ] = {}

    components = (
        get_components()
    )

    for component in (
        components.values()
    ):
        for path in (
            component.evidence_paths
        ):
            normalized = (
                normalize_registry_path(
                    path
                )
            )

            mapping.setdefault(
                normalized,
                [],
            ).append(
                component
            )

    return mapping


def get_components_for_path(
    path: str,
    registry_path_map: dict[
        str,
        list[ComponentRecord],
    ],
) -> list[ComponentRecord]:
    """
    Return every registry component associated with a file.
    """

    normalized = (
        normalize_registry_path(
            path
        )
    )

    return list(
        registry_path_map.get(
            normalized,
            [],
        )
    )


def calculate_registry_role_adjustment(
    *,
    path: str,
    capability_intent: str,
    registry_path_map: dict[
        str,
        list[ComponentRecord],
    ],
) -> tuple[
    float,
    list[str],
    list[str],
]:
    """
    Apply architectural relevance from the component registry.

    Example:

        requested capability:
            speech_output

        file:
            core/voice_output/speaker.py

        registry says:
            component = Voice Output
            role = speech_output

        result:
            positive adjustment

    But:

        file:
            core/voice_listener/voice_listener.py

        registry says:
            role = speech_input

        result:
            penalty for a speech-output question

    No voice-output paths are hard-coded here.
    """

    components = (
        get_components_for_path(
            path,
            registry_path_map,
        )
    )

    if not components:
        return (
            0.0,
            [],
            [],
        )

    component_ids = [
        component.component_id
        for component in components
    ]

    roles = sorted(
        {
            component.role
            for component in components
        }
    )

    if capability_intent == "general":
        return (
            0.0,
            component_ids,
            roles,
        )

    adjustment = 0.0

    matching_components = [
        component
        for component in components
        if component.role
        == capability_intent
    ]

    if matching_components:
        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        adjustment += 0.28

        # [comment omitted from source review]
        # [comment omitted from source review]
        if any(
            component.scope == "core"
            for component
            in matching_components
        ):
            adjustment += 0.04

        # [comment omitted from source review]
        # [comment omitted from source review]
        if any(
            component.local_first
            for component
            in matching_components
        ):
            adjustment += 0.03

        return (
            adjustment,
            component_ids,
            roles,
        )

    related_roles = (
        RELATED_ROLE_GROUPS.get(
            capability_intent,
            {
                capability_intent,
            },
        )
    )

    if any(
        role in related_roles
        for role in roles
    ):
        # [comment omitted from source review]
        # [comment omitted from source review]

        # [comment omitted from source review]
        # [comment omitted from source review]
        # [comment omitted from source review]
        adjustment -= 0.18

    return (
        adjustment,
        component_ids,
        roles,
    )


def build_result_snippet(
    lexical: SearchResult | None,
    semantic: SemanticCandidate | None,
) -> str:
    """
    Prefer exact lexical evidence when available.

    Otherwise use the strongest semantic chunk.
    """

    if (
        lexical is not None
        and lexical.snippet
    ):
        return lexical.snippet

    if (
        semantic is not None
        and semantic.text
    ):
        return semantic.text

    return ""


def determine_source_kind(
    lexical: SearchResult | None,
    semantic: SemanticCandidate | None,
) -> str:
    """
    Determine general evidence type.
    """

    if lexical is not None:
        return lexical.source_kind

    if semantic is None:
        return "other"

    pseudo_record: dict[str, Any] = {
        "path": semantic.path,
        "extension": semantic.extension,
    }

    return classify_source(
        pseudo_record
    )


def hybrid_search(
    query: str,
    *,
    limit: int = 8,
    lexical_limit: int = 12,
    minimum_semantic_similarity: float = 0.20,
) -> list[HybridSearchResult]:
    """
    Search ZÆNIA's local knowledge using:

        lexical evidence
        semantic meaning
        registry-defined architectural roles

    Architecture:

        question
           │
           ├── lexical retrieval
           │
           ├── semantic retrieval
           │
           └── capability intent
                    ↓
            component registry
                    ↓
           architectural relevance
                    ↓
             hybrid ranking

    No cloud service is involved.
    """

    query = query.strip()

    if not query:
        return []

    capability_intent = (
        determine_capability_intent(
            query
        )
    )

    registry_path_map = (
        build_registry_path_map()
    )

    lexical_results = search_index(
        query,
        limit=lexical_limit,
    )

    lexical_by_path = (
        lexical_results_by_path(
            lexical_results
        )
    )

    semantic_by_path = (
        semantic_search(
            query,
            minimum_similarity=(
                minimum_semantic_similarity
            ),
        )
    )

    all_paths = set(
        lexical_by_path.keys()
    )

    all_paths.update(
        semantic_by_path.keys()
    )

    if not all_paths:
        return []

    max_lexical_score = (
        get_lexical_max_score(
            lexical_results
        )
    )

    (
        lexical_weight,
        semantic_weight,
    ) = choose_weights(
        query
    )

    results: list[
        HybridSearchResult
    ] = []

    for path in all_paths:

        lexical = (
            lexical_by_path.get(
                path
            )
        )

        semantic = (
            semantic_by_path.get(
                path
            )
        )

        if lexical is not None:
            lexical_score = max(
                0.0,
                lexical.score,
            )

        else:
            lexical_score = 0.0

        if (
            max_lexical_score > 0.0
            and lexical_score > 0.0
        ):
            normalized_lexical = min(
                1.0,
                lexical_score
                / max_lexical_score,
            )

        else:
            normalized_lexical = 0.0

        if semantic is not None:
            semantic_similarity = max(
                0.0,
                min(
                    1.0,
                    semantic.similarity,
                ),
            )

        else:
            semantic_similarity = 0.0

        lexical_component = (
            normalized_lexical
            * lexical_weight
        )

        semantic_component = (
            semantic_similarity
            * semantic_weight
        )

        (
            role_adjustment,
            registry_components,
            registry_roles,
        ) = (
            calculate_registry_role_adjustment(
                path=path,
                capability_intent=(
                    capability_intent
                ),
                registry_path_map=(
                    registry_path_map
                ),
            )
        )

        hybrid_score = (
            lexical_component
            + semantic_component
            + role_adjustment
        )

        if lexical is not None:
            root = (
                lexical.root
            )

            display_path = (
                lexical.display_path
            )

        elif semantic is not None:
            root = (
                semantic.root
            )

            display_path = (
                semantic.display_path
            )

        else:
            continue

        results.append(
            HybridSearchResult(
                hybrid_score=round(
                    hybrid_score,
                    6,
                ),
                lexical_component=round(
                    lexical_component,
                    6,
                ),
                semantic_component=round(
                    semantic_component,
                    6,
                ),
                role_adjustment=round(
                    role_adjustment,
                    6,
                ),
                lexical_score=round(
                    lexical_score,
                    4,
                ),
                semantic_similarity=round(
                    semantic_similarity,
                    6,
                ),
                root=root,
                path=path,
                display_path=(
                    display_path
                ),
                source_kind=(
                    determine_source_kind(
                        lexical,
                        semantic,
                    )
                ),
                capability_intent=(
                    capability_intent
                ),
                registry_components=(
                    registry_components
                ),
                registry_roles=(
                    registry_roles
                ),
                snippet=(
                    build_result_snippet(
                        lexical,
                        semantic,
                    )
                ),
                lexical_match=(
                    lexical is not None
                ),
                semantic_match=(
                    semantic is not None
                ),
            )
        )

    results.sort(
        key=lambda item: (
            -item.hybrid_score,
            -item.role_adjustment,
            -item.lexical_component,
            -item.semantic_component,
            item.path.lower(),
        )
    )

    return results[
        :limit
    ]


def results_to_dicts(
    results: list[HybridSearchResult],
) -> list[dict[str, Any]]:
    """
    Convert hybrid results into ordinary dictionaries.
    """

    return [
        {
            "hybrid_score": (
                result.hybrid_score
            ),
            "lexical_component": (
                result.lexical_component
            ),
            "semantic_component": (
                result.semantic_component
            ),
            "role_adjustment": (
                result.role_adjustment
            ),
            "lexical_score": (
                result.lexical_score
            ),
            "semantic_similarity": (
                result.semantic_similarity
            ),
            "root": result.root,
            "path": result.path,
            "display_path": (
                result.display_path
            ),
            "source_kind": (
                result.source_kind
            ),
            "capability_intent": (
                result.capability_intent
            ),
            "registry_components": (
                result.registry_components
            ),
            "registry_roles": (
                result.registry_roles
            ),
            "snippet": result.snippet,
            "lexical_match": (
                result.lexical_match
            ),
            "semantic_match": (
                result.semantic_match
            ),
        }
        for result in results
    ]


def format_results(
    results: list[HybridSearchResult],
) -> str:
    """
    Human-readable diagnostic output.
    """

    if not results:
        return (
            "No relevant local evidence found."
        )

    lines: list[str] = []

    for number, result in enumerate(
        results,
        start=1,
    ):
        lines.append(
            f"{number}. "
            f"{result.display_path}"
        )

        lines.append(
            "   Hybrid score: "
            f"{result.hybrid_score}"
        )

        lines.append(
            "   Lexical contribution: "
            f"{result.lexical_component}"
        )

        lines.append(
            "   Semantic contribution: "
            f"{result.semantic_component}"
        )

        lines.append(
            "   Registry role adjustment: "
            f"{result.role_adjustment}"
        )

        lines.append(
            "   Capability intent: "
            f"{result.capability_intent}"
        )

        if result.registry_components:
            lines.append(
                "   Registry components: "
                + ", ".join(
                    result.registry_components
                )
            )

        else:
            lines.append(
                "   Registry components: none"
            )

        if result.registry_roles:
            lines.append(
                "   Registry roles: "
                + ", ".join(
                    result.registry_roles
                )
            )

        else:
            lines.append(
                "   Registry roles: none"
            )

        lines.append(
            "   Original lexical score: "
            f"{result.lexical_score}"
        )

        lines.append(
            "   Semantic similarity: "
            f"{result.semantic_similarity}"
        )

        lines.append(
            "   Source type: "
            f"{result.source_kind}"
        )

        lines.append(
            "   Lexical match: "
            f"{result.lexical_match}"
        )

        lines.append(
            "   Semantic match: "
            f"{result.semantic_match}"
        )

        if result.snippet:
            compact = (
                normalize_console_text(
                    result.snippet
                )
            )

            if len(
                compact
            ) > 700:
                compact = (
                    compact[
                        :700
                    ]
                    + "..."
                )

            lines.append(
                "   Evidence: "
                f"{compact}"
            )

        lines.append(
            ""
        )

    return "\n".join(
        lines
    ).rstrip()


@owner_command('files.read')
def main() -> None:
    """
    Development interface for registry-driven hybrid search.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Search ZÆNIA's approved local project using "
            "lexical, semantic, and component-registry "
            "architectural retrieval."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help=(
            "Natural-language question or search."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=8,
    )

    args = parser.parse_args()

    query = " ".join(
        args.query
    )

    capability_intent = (
        determine_capability_intent(
            query
        )
    )

    results = hybrid_search(
        query,
        limit=args.limit,
    )

    print()

    print(
        "ZÆNIA Hybrid Local Retrieval"
    )

    print(
        "Query:",
        query,
    )

    print(
        "Capability intent:",
        capability_intent,
    )

    print(
        "Architecture source: "
        "component registry"
    )

    if query_is_system_state(
        query
    ):
        print(
            "Mode: current-state "
            "(lexical authority favored)"
        )

    else:
        print(
            "Mode: semantic "
            "(meaning favored)"
        )

    print()

    print(
        format_results(
            results
        )
    )


if __name__ == "__main__":
    main()