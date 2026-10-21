from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.brain.system_index import (
    load_index,
)


@dataclass
class SearchResult:
    """
    One local evidence result returned by ZÆNIA.

    score:
        Final combined ranking.

    lexical_score:
        Literal query-to-file relevance.

    topic_score:
        Relevance to the actual subject of Zack's question.

    authority_score:
        How authoritative the source is for the question.

    source_kind:
        General type of local source.

    authority_reason:
        Explanation of why the authority score changed.

    snippet:
        Small relevant evidence section.
    """

    score: float
    lexical_score: float
    topic_score: float
    authority_score: float

    root: str
    path: str
    display_path: str

    source_kind: str
    authority_reason: str

    snippet: str
    content_indexed: bool


STATE_WORDS = {
    "active",
    "currently",
    "current",
    "configured",
    "configuration",
    "disabled",
    "enabled",
    "is",
    "still",
    "status",
    "use",
    "used",
    "uses",
    "using",
    "running",
    "run",
    "provider",
}


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "it",
    "my",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "with",
    "you",
    "your",
}


BRAIN_INFRASTRUCTURE_TERMS = {
    "brain",
    "retrieval",
    "retrieve",
    "retriever",
    "index",
    "indexing",
    "search",
    "ranking",
    "rank",
    "awareness",
    "grounding",
    "grounded",
    "filesystem",
}


SELF_REFERENCE_FILES = {
    "core/brain/system_retriever.py",
    "core/brain/system_index.py",
    "core/brain/system_awareness_config.yaml",
}


def normalize_text(
    text: str,
) -> str:
    """
    Normalize text for local lexical comparisons.

    Example:

        ElevenLabs
        elevenlabs

    become comparable.
    """

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9_./\\\-: ]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def split_identifier_words(
    text: str,
) -> str:
    """
    Convert programming separators into normal spaces.

    Example:

        voice_output
            ->
        voice output
    """

    text = text.replace(
        "_",
        " ",
    )

    text = text.replace(
        "-",
        " ",
    )

    text = text.replace(
        "/",
        " ",
    )

    text = text.replace(
        "\\",
        " ",
    )

    return text


def raw_tokens(
    text: str,
) -> list[str]:
    """
    Return normalized words before semantic filtering.
    """

    normalized = normalize_text(
        split_identifier_words(
            text
        )
    )

    return [
        word
        for word in normalized.split()
        if len(word) >= 2
    ]


def tokenize(
    text: str,
) -> list[str]:
    """
    Return useful topic/search words.

    State words such as:

        enabled
        currently
        using

    are removed because they describe the QUESTION TYPE,
    not necessarily its SUBJECT.
    """

    tokens: list[str] = []

    for word in raw_tokens(
        text
    ):
        if word in STOP_WORDS:
            continue

        if word in STATE_WORDS:
            continue

        tokens.append(
            word
        )

    return tokens


def get_topic_tokens(
    query: str,
) -> list[str]:
    """
    Extract the actual subject of Zack's question.

    Example:

        Are we still using ElevenLabs?

    becomes approximately:

        ["elevenlabs"]
    """

    return tokenize(
        query
    )


def expand_query(
    query: str,
) -> list[str]:
    """
    Produce narrow local variants for known naming differences.

    This does not call an LLM or outside service.
    """

    variants = {
        query,
    }

    lowered = query.lower()

    if "eleven labs" in lowered:
        variants.add(
            re.sub(
                r"eleven\s+labs",
                "elevenlabs",
                query,
                flags=re.IGNORECASE,
            )
        )

    if "elevenlabs" in lowered:
        variants.add(
            re.sub(
                r"elevenlabs",
                "eleven labs",
                query,
                flags=re.IGNORECASE,
            )
        )

    if "text to speech" in lowered:
        variants.add(
            query + " tts voice"
        )

    if "speech to text" in lowered:
        variants.add(
            query + " stt transcription"
        )

    return list(
        variants
    )


def query_is_system_state(
    query: str,
) -> bool:
    """
    Determine whether Zack is asking about current
    configuration/runtime state.
    """

    words = set(
        raw_tokens(
            query
        )
    )

    return bool(
        words.intersection(
            STATE_WORDS
        )
    )


def query_is_about_brain_infrastructure(
    query: str,
) -> bool:
    """
    Determine whether the question is actually about ZÆNIA's
    retrieval/indexing/system-awareness infrastructure.

    Examples that return True:

        How does your retrieval engine work?
        How do you rank files?
        What does your system index contain?
        How does filesystem grounding work?

    A question such as:

        Are we still using ElevenLabs?

    returns False.
    """

    query_words = set(
        raw_tokens(
            query
        )
    )

    return bool(
        query_words.intersection(
            BRAIN_INFRASTRUCTURE_TERMS
        )
    )


def classify_source(
    record: dict[str, Any],
) -> str:
    """
    Classify one local evidence source.
    """

    path = str(
        record.get(
            "path",
            "",
        )
    ).lower()

    extension = str(
        record.get(
            "extension",
            "",
        )
    ).lower()

    file_name = Path(
        path
    ).name.lower()

    if extension in {
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
    }:
        return "configuration"

    if (
        "config" in file_name
        or "settings" in file_name
    ):
        return "configuration"

    if extension == ".ps1":
        return "script"

    if path.startswith(
        "core/brain/"
    ):
        return "brain_infrastructure"

    if extension in {
        ".py",
        ".rs",
        ".js",
        ".ts",
    }:
        return "runtime_code"

    if extension in {
        ".md",
        ".txt",
    }:
        return "documentation"

    return "other"


def should_exclude_self_reference(
    record: dict[str, Any],
    query: str,
) -> bool:
    """
    Prevent ZÆNIA's search-engine implementation from becoming
    fake evidence for unrelated system questions.

    Example:

        system_retriever.py

    contains the word ElevenLabs because we used it in example
    code.

    That file should NOT be evidence for:

        Are we still using ElevenLabs?

    But it SHOULD remain searchable for:

        How does your retriever handle ElevenLabs queries?
    """

    path = str(
        record.get(
            "path",
            "",
        )
    ).lower()

    if path not in SELF_REFERENCE_FILES:
        return False

    if query_is_about_brain_infrastructure(
        query
    ):
        return False

    return True


def count_token_matches(
    token: str,
    text: str,
) -> int:
    """
    Count literal occurrences of one token.
    """

    if not token:
        return 0

    return text.count(
        token
    )


def calculate_topic_score(
    record: dict[str, Any],
    query: str,
) -> float:
    """
    Measure how strongly the actual query subject appears in
    the file.

    Path matches receive greater weight than content matches.
    """

    topic_tokens = get_topic_tokens(
        query
    )

    if not topic_tokens:
        return 0.0

    path = normalize_text(
        split_identifier_words(
            str(
                record.get(
                    "path",
                    "",
                )
            )
        )
    )

    content = normalize_text(
        str(
            record.get(
                "content",
                "",
            )
        )
    )

    score = 0.0

    for token in topic_tokens:
        path_matches = (
            count_token_matches(
                token,
                path,
            )
        )

        content_matches = (
            count_token_matches(
                token,
                content,
            )
        )

        score += min(
            path_matches,
            2,
        ) * 12.0

        score += min(
            content_matches,
            5,
        ) * 4.0

    return score


def calculate_lexical_score(
    record: dict[str, Any],
    query: str,
) -> float:
    """
    Measure literal query relevance.

    State words are not counted.
    """

    path = normalize_text(
        split_identifier_words(
            str(
                record.get(
                    "path",
                    "",
                )
            )
        )
    )

    content = normalize_text(
        str(
            record.get(
                "content",
                "",
            )
        )
    )

    query_tokens = tokenize(
        query
    )

    if not query_tokens:
        return 0.0

    score = 0.0

    for token in query_tokens:
        path_matches = (
            count_token_matches(
                token,
                path,
            )
        )

        content_matches = (
            count_token_matches(
                token,
                content,
            )
        )

        score += min(
            path_matches,
            3,
        ) * 8.0

        score += min(
            content_matches,
            8,
        ) * 2.0

    return score


def calculate_authority_score(
    record: dict[str, Any],
    query: str,
    *,
    topic_score: float,
) -> tuple[float, str]:
    """
    Determine how authoritative the source is.

    Authority is only granted when the file is actually
    topically relevant.
    """

    path = str(
        record.get(
            "path",
            "",
        )
    ).lower()

    content = str(
        record.get(
            "content",
            "",
        )
    ).lower()

    source_kind = classify_source(
        record
    )

    state_query = query_is_system_state(
        query
    )

    topically_relevant = (
        topic_score > 0
    )

    adjustment = 0.0

    reasons: list[str] = []

    if (
        state_query
        and topically_relevant
    ):
        if source_kind == "configuration":
            adjustment += 28.0

            reasons.append(
                "topically relevant configuration is authoritative for current state"
            )

        if (
            "config" in path
            or "settings" in path
        ):
            adjustment += 10.0

            reasons.append(
                "topically relevant configuration path"
            )

        state_markers = (
            "enabled:",
            "enabled =",
            '"enabled"',
            "provider:",
            "provider =",
            '"provider"',
            "fallback_order:",
        )

        if any(
            marker in content
            for marker in state_markers
        ):
            adjustment += 10.0

            reasons.append(
                "topically relevant file contains explicit state markers"
            )

    if (
        source_kind
        == "brain_infrastructure"
        and not query_is_about_brain_infrastructure(
            query
        )
    ):
        adjustment -= 8.0

        reasons.append(
            "brain infrastructure is secondary for unrelated subsystem queries"
        )

    if not topically_relevant:
        reasons.append(
            "no authority bonus because file does not match the query topic"
        )

    if not reasons:
        reasons.append(
            "no authority adjustment"
        )

    return (
        adjustment,
        "; ".join(
            reasons
        ),
    )


def find_best_snippet(
    content: str,
    query: str,
    *,
    max_chars: int = 900,
) -> str:
    """
    Extract evidence around the actual query topic.

    This avoids passing complete source files into Qwen when
    only a small section is needed.
    """

    if not content:
        return ""

    query_tokens = get_topic_tokens(
        query
    )

    lowered = content.lower()

    candidate_positions: list[int] = []

    for token in query_tokens:
        position = lowered.find(
            token.lower()
        )

        if position >= 0:
            candidate_positions.append(
                position
            )

    if not candidate_positions:
        return content[
            :max_chars
        ].strip()

    best_position = min(
        candidate_positions
    )

    half = max_chars // 2

    start = max(
        0,
        best_position - half,
    )

    end = min(
        len(content),
        best_position + half,
    )

    snippet = content[
        start:end
    ]

    if start > 0:
        first_newline = snippet.find(
            "\n"
        )

        if first_newline >= 0:
            snippet = snippet[
                first_newline + 1:
            ]

    if end < len(content):
        last_newline = snippet.rfind(
            "\n"
        )

        if last_newline >= 0:
            snippet = snippet[
                :last_newline
            ]

    return snippet.strip()


def search_index(
    query: str,
    *,
    limit: int = 8,
    minimum_topic_score: float = 1.0,
) -> list[SearchResult]:
    """
    Search ZÆNIA's approved local index.

    Ranking combines:

        lexical relevance
        +
        topic relevance
        +
        source authority

    Self-referential retrieval files are excluded from
    unrelated subsystem searches.

    Everything happens locally.
    """

    query = query.strip()

    if not query:
        return []

    index = load_index()

    files = (
        index.get(
            "files",
            [],
        )
        or []
    )

    query_variants = expand_query(
        query
    )

    scored: list[
        tuple[
            float,
            float,
            float,
            float,
            str,
            dict[str, Any],
        ]
    ] = []

    for record in files:
        if should_exclude_self_reference(
            record,
            query,
        ):
            continue

        best_lexical_score = 0.0
        best_topic_score = 0.0

        for variant in query_variants:
            lexical_score = (
                calculate_lexical_score(
                    record,
                    variant,
                )
            )

            topic_score = (
                calculate_topic_score(
                    record,
                    variant,
                )
            )

            best_lexical_score = max(
                best_lexical_score,
                lexical_score,
            )

            best_topic_score = max(
                best_topic_score,
                topic_score,
            )

        if (
            best_topic_score
            < minimum_topic_score
        ):
            continue

        (
            authority_score,
            authority_reason,
        ) = calculate_authority_score(
            record,
            query,
            topic_score=best_topic_score,
        )

        final_score = (
            best_lexical_score
            + best_topic_score
            + authority_score
        )

        scored.append(
            (
                final_score,
                best_lexical_score,
                best_topic_score,
                authority_score,
                authority_reason,
                record,
            )
        )

    scored.sort(
        key=lambda item: (
            -item[0],
            -item[2],
            -item[1],
            str(
                item[5].get(
                    "path",
                    "",
                )
            ).lower(),
        )
    )

    results: list[SearchResult] = []

    for (
        final_score,
        lexical_score,
        topic_score,
        authority_score,
        authority_reason,
        record,
    ) in scored[
        :limit
    ]:
        content = str(
            record.get(
                "content",
                "",
            )
        )

        snippet = find_best_snippet(
            content,
            query,
        )

        results.append(
            SearchResult(
                score=round(
                    final_score,
                    2,
                ),
                lexical_score=round(
                    lexical_score,
                    2,
                ),
                topic_score=round(
                    topic_score,
                    2,
                ),
                authority_score=round(
                    authority_score,
                    2,
                ),
                root=str(
                    record.get(
                        "root",
                        "",
                    )
                ),
                path=str(
                    record.get(
                        "path",
                        "",
                    )
                ),
                display_path=str(
                    record.get(
                        "display_path",
                        "",
                    )
                ),
                source_kind=classify_source(
                    record
                ),
                authority_reason=(
                    authority_reason
                ),
                snippet=snippet,
                content_indexed=bool(
                    record.get(
                        "content_indexed",
                        False,
                    )
                ),
            )
        )

    return results


def results_to_dicts(
    results: list[SearchResult],
) -> list[dict[str, Any]]:
    """
    Convert SearchResult objects into ordinary dictionaries.

    This will be used by the grounded-answer layer next.
    """

    return [
        {
            "score": result.score,
            "lexical_score": (
                result.lexical_score
            ),
            "topic_score": (
                result.topic_score
            ),
            "authority_score": (
                result.authority_score
            ),
            "root": result.root,
            "path": result.path,
            "display_path": (
                result.display_path
            ),
            "source_kind": (
                result.source_kind
            ),
            "authority_reason": (
                result.authority_reason
            ),
            "snippet": result.snippet,
            "content_indexed": (
                result.content_indexed
            ),
        }
        for result in results
    ]


def format_results(
    results: list[SearchResult],
) -> str:
    """
    Produce human-readable console output.
    """

    if not results:
        return (
            "No relevant local files found."
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
            "   Final score: "
            f"{result.score}"
        )

        lines.append(
            "   Lexical relevance: "
            f"{result.lexical_score}"
        )

        lines.append(
            "   Topic relevance: "
            f"{result.topic_score}"
        )

        lines.append(
            "   Authority adjustment: "
            f"{result.authority_score}"
        )

        lines.append(
            "   Source type: "
            f"{result.source_kind}"
        )

        lines.append(
            "   Authority: "
            f"{result.authority_reason}"
        )

        lines.append(
            "   Content indexed: "
            f"{result.content_indexed}"
        )

        if result.snippet:
            compact = result.snippet.replace(
                "\n",
                " ",
            )

            compact = re.sub(
                r"\s+",
                " ",
                compact,
            ).strip()

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
    Command-line retrieval test.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Search ZÆNIA's approved local system index."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help=(
            "Question or local search terms."
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

    results = search_index(
        query,
        limit=args.limit,
    )

    print()

    print(
        "ZÆNIA Local Retrieval"
    )

    print(
        "Query:",
        query,
    )

    print()

    print(
        format_results(
            results
        )
    )


if __name__ == "__main__":
    main()