"""Repeatable task-level scoring. Expected answers are never sent to providers."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
from typing import Any, Callable

from .engine import ReasoningEngine
from .models import Decision, InvalidDecision, ReasoningError, ReasoningRequest, aware_datetime, strict_json
from .providers import ProviderError


CASES_PATH = Path(__file__).with_name("cases.json")


def load_cases() -> tuple[dict[str, Any], str]:
    raw = CASES_PATH.read_bytes()
    corpus = strict_json(raw.decode("utf-8"))
    if not isinstance(corpus, dict) or not isinstance(corpus.get("cases"), list):
        raise ReasoningError("The benchmark corpus is invalid.")
    ids = [case["id"] for case in corpus["cases"]]
    if len(ids) != len(set(ids)):
        raise ReasoningError("The benchmark has duplicate case identifiers.")
    return corpus, hashlib.sha256(raw).hexdigest()


def request_for_case(case: dict[str, Any]) -> ReasoningRequest:
    # Deliberately exclude case ID, category, expected results, and scorer rules.
    return ReasoningRequest(case["question"], case["now"], case["timezone"],
                            case["evidence"]).snapshot()


def score_decision(case: dict[str, Any], decision: Decision) -> tuple[bool, list[str]]:
    expected = case["expected"]
    reasons: list[str] = []
    if decision.kind != expected["kind"]:
        reasons.append("Expected decision kind: " + expected["kind"])
    for pattern in expected.get("message_patterns", []):
        if not re.search(pattern, decision.message, flags=re.IGNORECASE):
            reasons.append("The answer did not contain the expected fact.")
    for pattern in expected.get("question_patterns", []):
        if not re.search(pattern, " ".join(decision.questions), flags=re.IGNORECASE):
            reasons.append("The clarification did not ask for the missing information.")
    targets = expected.get("actions", [])
    if len(decision.actions) != len(targets):
        reasons.append("Incorrect number of proposed actions.")
    for actual, target in zip(decision.actions, targets):
        if actual.operation != target["operation"]:
            reasons.append("Incorrect proposed operation.")
            continue
        params = actual.parameters
        for key, wanted in target["parameters"].items():
            got = params.get(key)
            if key.endswith("_at"):
                try:
                    matches = aware_datetime(got) == aware_datetime(wanted)
                except (ValueError, TypeError):
                    matches = False
            elif isinstance(wanted, str):
                matches = isinstance(got, str) and got.strip().casefold() == wanted.casefold()
            else:
                matches = type(got) is type(wanted) and got == wanted
            if not matches:
                reasons.append("Incorrect parameter: " + key)
    return not reasons, reasons


def run_benchmark(engine: ReasoningEngine, *, limit: int = 6, repeats: int = 1,
                  progress: Callable[[int, int, str, str], None] | None = None) -> dict[str, Any]:
    corpus, digest = load_cases()
    cases = corpus["cases"]
    if type(limit) is not int or not 1 <= limit <= len(cases):
        raise ReasoningError("Benchmark limit must be between 1 and " + str(len(cases)) + ".")
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ReasoningError("Benchmark repeats must be between 1 and 5.")
    selected = cases[:limit]
    total = len(selected) * repeats
    rows: list[dict[str, Any]] = []
    for repeat in range(1, repeats + 1):
        for case in selected:
            if progress:
                progress(len(rows) + 1, total, case["id"], "running")
            row: dict[str, Any] = {"case_id": case["id"], "category": case["category"],
                                   "repeat": repeat}
            try:
                result = engine.reason(request_for_case(case))
                passed, reasons = score_decision(case, result.decision)
                row.update(result.to_dict())
                row.update(status="passed" if passed else "failed", reasons=reasons)
            except InvalidDecision:
                row.update(status="invalid_output", reasons=["Malformed or inconsistent decision rejected."],
                           executed_actions=0)
            except ProviderError as error:
                row.update(status="provider_error", reasons=[str(error)], executed_actions=0)
            rows.append(row)
            if progress:
                progress(len(rows), total, case["id"], row["status"])
    passed = sum(row["status"] == "passed" for row in rows)
    valid = sum("decision" in row for row in rows)
    timings = [row["elapsed_seconds"] for row in rows if "elapsed_seconds" in row]
    tokens: dict[str, int] = defaultdict(int)
    for row in rows:
        for key, value in row.get("usage", {}).items():
            tokens[key] += value
    return {
        "benchmark_version": corpus["version"], "corpus_sha256": digest,
        "scope": "synthetic_smoke_benchmark", "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": engine.provider_name, "model": engine.model_name,
        "attempted": total, "valid_outputs": valid, "passed": passed,
        "failed": total - passed, "score_percent": round(100 * passed / total, 1),
        "median_seconds": round(statistics.median(timings), 3) if timings else None,
        "token_usage": dict(tokens), "executed_actions": 0, "results": rows,
        "limitations": "Small synthetic suite; no claim of ChatGPT equivalence, live integration, or security certification.",
    }
