from core.foundation.local_entry import owner_command
from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from core.calendar_context.calendar_context import (
    build_calendar_context,
    build_simple_calendar_sentence,
)

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main():
    """
    ZÆNIA local calendar context tools.
    """
    pass


@app.command("today")
@owner_command('calendar.read')
def today_command():
    """
    Show today's local ZÆNIA calendar context.
    """
    context = build_calendar_context()

    table = Table(title="ZÆNIA Calendar Context")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Date", context["date"])
    table.add_row("Weekday", context["weekday"])
    table.add_row("Status", context["status_label"])
    table.add_row("Status Note", str(context["status_note"] or "None"))
    table.add_row("Event Count", str(context["event_count"]))

    if context["first_event"]:
        table.add_row("First Event", context["first_event"]["title"])
    else:
        table.add_row("First Event", "None")

    if context["reminders"]:
        table.add_row("First Reminder", context["reminders"][0])
    else:
        table.add_row("First Reminder", "None")

    console.print(table)
    console.print(f"[cyan]{build_simple_calendar_sentence(context)}[/cyan]")


@app.command("date")
@owner_command('calendar.read')
def date_command(
    target_date: str = typer.Argument(..., help="Date to check, format YYYY-MM-DD"),
):
    """
    Show local ZÆNIA calendar context for a specific date.
    """
    parsed_date = date.fromisoformat(target_date)
    context = build_calendar_context(parsed_date)

    table = Table(title=f"ZÆNIA Calendar Context — {target_date}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Date", context["date"])
    table.add_row("Weekday", context["weekday"])
    table.add_row("Status", context["status_label"])
    table.add_row("Status Note", str(context["status_note"] or "None"))
    table.add_row("Event Count", str(context["event_count"]))

    if context["first_event"]:
        table.add_row("First Event", context["first_event"]["title"])
    else:
        table.add_row("First Event", "None")

    if context["reminders"]:
        table.add_row("First Reminder", context["reminders"][0])
    else:
        table.add_row("First Reminder", "None")

    console.print(table)
    console.print(f"[cyan]{build_simple_calendar_sentence(context)}[/cyan]")


if __name__ == "__main__":
    app()