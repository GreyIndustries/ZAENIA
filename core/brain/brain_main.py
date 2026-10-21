from __future__ import annotations
from core.foundation.local_entry import owner_command

import argparse

from core.brain.brain_service import (
    BrainService,
    print_result,
    run_self_test,
)


@owner_command('chat.reply')
def main() -> None:
    """
    Official command-line entry point for ZÆNIA's local brain.

    All normal callers should go through BrainService.
    """

    parser = argparse.ArgumentParser(
        description=(
            "ZÆNIA consolidated local-first "
            "brain interface."
        )
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    ask_parser = (
        subparsers.add_parser(
            "ask",
            help=(
                "Ask ZÆNIA's consolidated "
                "local brain."
            ),
        )
    )

    ask_parser.add_argument(
        "question",
        nargs="+",
    )

    ask_parser.add_argument(
        "--no-memory",
        action="store_true",
        help=(
            "Do not save this development "
            "exchange into local memory."
        ),
    )

    subparsers.add_parser(
        "self-test",
        help=(
            "Run the consolidated brain "
            "confirmation test."
        ),
    )

    args = parser.parse_args()

    if args.command == "ask":
        service = (
            BrainService()
        )

        question = " ".join(
            args.question
        )

        result = service.ask(
            question,
            remember=(
                not args.no_memory
            ),
        )

        print_result(
            result
        )

        return

    if args.command == "self-test":
        passed = (
            run_self_test()
        )

        if not passed:
            raise SystemExit(
                1
            )


if __name__ == "__main__":
    main()