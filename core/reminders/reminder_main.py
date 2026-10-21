from __future__ import annotations
from core.foundation.local_entry import owner_command

from datetime import datetime
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.table import Table

from core.reminders.reminder_engine import (
    build_reminder_proposal,
    execute_reminder_proposal,
    load_reminders,
)


app = typer.Typer(
    no_args_is_help=True
)

console = Console()


@app.callback()
def main():
    """
    ZÆNIA local reminder tools.
    """
    pass


@app.command("detect")
def detect_command(
    utterance: str = typer.Argument(
        ...,
        help="Sentence to inspect for reminder intent.",
    ),
):
    """
    Detect and preview a reminder without saving it.
    """

    result = (
        build_reminder_proposal(
            utterance
        )
    )

    console.print(
        result
    )


@app.command("list")
@owner_command('calendar.read')
def list_command():
    """
    Display locally stored reminders.
    """

    data = (
        load_reminders()
    )

    reminders = (
        data.get(
            "reminders",
            [],
        )
        or []
    )

    table = Table(
        title="ZÆNIA Reminders"
    )

    table.add_column(
        "Status"
    )

    table.add_column(
        "Due"
    )

    table.add_column(
        "Reminder"
    )

    for reminder in reminders:
        table.add_row(
            str(
                reminder.get(
                    "status",
                    "",
                )
            ),
            str(
                reminder.get(
                    "due_at",
                    "",
                )
                or "Unscheduled"
            ),
            str(
                reminder.get(
                    "title",
                    "",
                )
            ),
        )

    console.print(
        table
    )


@app.command("self-test")
def self_test_command():
    """
    Validate reminder detection, context resolution,
    scheduling, and the execution security gate.

    This test does not save a real reminder.
    """

    test_time = datetime(
        2026,
        9,
        23,
        14,
        0,
        tzinfo=ZoneInfo(
            "America/Los_Angeles"
        ),
    )

    false_positive = (
        build_reminder_proposal(
            "I remember doing that last year.",
            reference_time=test_time,
        )
    )

    if false_positive[
        "is_reminder"
    ]:
        raise RuntimeError(
            "False-positive reminder detection failed."
        )

    direct = (
        build_reminder_proposal(
            "Remind me tomorrow at 7 PM "
            "to bring the radio.",
            reference_time=test_time,
        )
    )

    if not direct[
        "is_reminder"
    ]:
        raise RuntimeError(
            "Direct reminder detection failed."
        )

    direct_proposal = (
        direct[
            "proposal"
        ]
    )

    if direct_proposal is None:
        raise RuntimeError(
            "Direct reminder proposal missing."
        )

    if (
        direct_proposal[
            "title"
        ].lower()
        != "bring the radio"
    ):
        raise RuntimeError(
            "Direct reminder title extraction failed: "
            f"{direct_proposal['title']!r}"
        )

    if not str(
        direct_proposal[
            "due_at"
        ]
    ).startswith(
        "2026-09-24T19:00"
    ):
        raise RuntimeError(
            "Reminder date/time resolution failed."
        )

    contextual = (
        build_reminder_proposal(
            "Remind me to do that tonight.",
            conversation_context=[
                "I have to update the radio numbers "
                "before tomorrow's brief."
            ],
            reference_time=test_time,
        )
    )

    proposal = (
        contextual[
            "proposal"
        ]
    )

    if proposal is None:
        raise RuntimeError(
            "Contextual reminder proposal missing."
        )

    if (
        proposal[
            "title"
        ].lower()
        != (
            "update the radio numbers "
            "before tomorrow's brief"
        )
    ):
        raise RuntimeError(
            "Conversation context resolution failed: "
            f"{proposal['title']!r}"
        )

    try:
        execute_reminder_proposal(
            proposal,
            authorized=False,
        )

    except PermissionError:
        pass

    else:
        raise RuntimeError(
            "Security gate failed. "
            "Unauthorized reminder was accepted."
        )

    console.print(
        "[green]"
        "ZÆNIA Reminder Engine PASS"
        "[/green]"
    )

    console.print(
        "False-positive rejection: PASS"
    )

    console.print(
        "Direct reminder parsing: PASS"
    )

    console.print(
        "Natural date/time parsing: PASS"
    )

    console.print(
        "Conversation context resolution: PASS"
    )

    console.print(
        "Unauthorized execution blocked: PASS"
    )


if __name__ == "__main__":
    app()