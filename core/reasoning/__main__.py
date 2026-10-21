"""Authenticated foreground CLI. Credentials are prompted only inside the gate."""
from __future__ import annotations

import argparse
from contextlib import nullcontext, redirect_stdout
from datetime import datetime
import getpass
import json
import os
import sys
from zoneinfo import ZoneInfo

from .benchmark import run_benchmark
from .engine import ReasoningEngine
from .models import ReasoningError, ReasoningRequest
from .providers import ExistingLocalProvider, OpenAIProvider


def _provider(options: dict):
    if options["provider"] == "local":
        return ExistingLocalProvider(timeout=options["timeout"])
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        if not sys.stdin.isatty():
            raise ReasoningError("Set OPENAI_API_KEY locally or run in an interactive terminal for the hidden key prompt.")
        key = getpass.getpass("OpenAI API key (hidden; this module does not save it): ").strip()
    return OpenAIProvider(key, options["model"], effort=options["effort"],
                          timeout=options["timeout"], max_output_tokens=options["max_output_tokens"])


def _protected_guidance() -> str:
    try:
        from core.foundation.moral_code.vault import default_charter
        from core.foundation.moral_code.engine import guidance_for_generation
        default_charter()
        return guidance_for_generation()
    except Exception:
        raise ReasoningError("Protected guidance could not be verified. Repair Module 1 before using live reasoning.") from None


def _progress(index: int, total: int, case: str, status: str) -> None:
    print("[" + str(index) + "/" + str(total) + "] " + case + ": " + status,
          file=sys.stderr, flush=True)


def authorised_run(options: dict):
    """The only foreground generation path. Never catches or bypasses auth failures."""
    try:
        from core.foundation.local_entry import owner_execute
    except (ImportError, AttributeError):
        raise ReasoningError("Module 1's owner_execute gate is unavailable. Repair it before using live reasoning.") from None

    def handler(params: dict):
        guidance = _protected_guidance()
        provider = _provider(params)
        engine = ReasoningEngine(provider, protected_guidance=guidance)
        if params["command"] == "benchmark":
            return run_benchmark(engine, limit=params["limit"], repeats=params["repeats"],
                                 progress=_progress if params["progress"] else None)
        now = datetime.now(ZoneInfo("America/Los_Angeles")).isoformat()
        result = engine.reason(ReasoningRequest(params["question"], now))
        return result.to_dict()

    # The owner gate sees the provider/model/settings and question, never the API key.
    # The operation is the already-reviewed chat.reply scope. There is no executor.
    return owner_execute("chat.reply", options, handler)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ZÆNIA Stage 1 reasoning: advisory decisions and synthetic benchmarks.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="Isolated simulated checks; no keys, private files, or live model calls.")
    for name in ("benchmark", "ask"):
        sub = commands.add_parser(name)
        sub.add_argument("--provider", choices=("openai", "local"), required=True)
        sub.add_argument("--model", default="gpt-6.1-sol", help="OpenAI model; local mode uses the existing brain configuration.")
        sub.add_argument("--effort", choices=("low", "medium", "high"), default="medium")
        sub.add_argument("--timeout", type=int, default=45)
        sub.add_argument("--max-output-tokens", type=int, default=4096)
        sub.add_argument("--json", action="store_true", help="Print structured results to stdout; progress goes to stderr.")
        if name == "benchmark":
            sub.add_argument("--limit", type=int, default=6, help="First 1-14 synthetic cases; defaults to 6 to limit calls.")
            sub.add_argument("--repeats", type=int, default=1)
        else:
            sub.add_argument("question", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if args.command == "self-test":
        from .self_test import run_self_test
        return 0 if run_self_test() else 1
    if not 1 <= args.timeout <= 300 or not 512 <= args.max_output_tokens <= 16384:
        print("Invalid timeout or token limit.", file=sys.stderr)
        return 2
    if args.command == "benchmark" and (not 1 <= args.limit <= 14 or not 1 <= args.repeats <= 5):
        print("Use --limit 1-14 and --repeats 1-5.", file=sys.stderr)
        return 2
    options = {"command": args.command, "provider": args.provider, "model": args.model,
               "effort": args.effort, "timeout": args.timeout,
               "max_output_tokens": args.max_output_tokens,
               "question": " ".join(args.question) if args.command == "ask" else "",
               "limit": args.limit if args.command == "benchmark" else 1,
               "repeats": args.repeats if args.command == "benchmark" else 1,
               "progress": True}
    try:
        # Existing gate review messages belong on stderr when JSON is requested.
        with redirect_stdout(sys.stderr) if args.json else nullcontext():
            report = authorised_run(options)
    except PermissionError:
        print("Owner authentication or policy denied this request. The reasoning layer executed no actions.", file=sys.stderr)
        return 2
    except (ReasoningError, ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception as error:
        print("Reasoning stopped: " + type(error).__name__ + ". The foundation or provider failed; no proposed action was executed.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    elif args.command == "benchmark":
        print("Provider: " + report["provider"] + " | Model: " + report["model"])
        print("SYNTHETIC BENCHMARK: " + str(report["passed"]) + "/" + str(report["attempted"])
              + " passed (" + str(report["score_percent"]) + "%).")
        print("Valid decisions: " + str(report["valid_outputs"]) + "/" + str(report["attempted"]))
        if report["median_seconds"] is not None:
            print("Median response: " + str(report["median_seconds"]) + " seconds.")
        for row in report["results"]:
            if row["status"] != "passed":
                print(row["case_id"] + ": " + "; ".join(row["reasons"]))
        print("Executed actions: 0. This result does not establish ChatGPT-level capability.")
    else:
        decision = report["decision"]
        print(decision["message"])
        for question in decision["questions"]:
            print(question)
        for action in decision["actions"]:
            print("PROPOSED " + action["operation"] + ": " + action["parameters_json"])
        print("Execution status: not_executed")
    return 0 if args.command == "ask" or report["passed"] == report["attempted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
