from core.foundation.local_entry import owner_command
from datetime import date
from typing import Any

import typer
import yaml
from rich.console import Console
from rich.table import Table

from core.calendar_context.calendar_context import (
    CALENDAR_PATH,
    build_calendar_context,
    build_simple_calendar_sentence,
)

app = typer.Typer(no_args_is_help=True)
console = Console()

VALID_STATUSES = {
    "on_duty",
    "off_duty",
    "leave",
    "appointment",
    "field",
    "recovery",
}


def load_config() -> dict[str, Any]:
    if not CALENDAR_PATH.exists():
        raise FileNotFoundError(f"Calendar file not found: {CALENDAR_PATH}")

    with CALENDAR_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict[str, Any]) -> None:
    # [comment omitted from source review]
    # [comment omitted from source review]
    from core.foundation.rules.engine import RuleEngine
    from core.foundation.rules.models import ActionRequest
    from core.foundation.auth.passkey import require_passkey
    from core.foundation.security.io import atomic_write
    engine = RuleEngine.open(require_passkey())
    def validate(params):
        if set(params) != {"config"} or not isinstance(params["config"], dict):
            raise ValueError("Invalid calendar configuration.")
        yaml.safe_dump(params["config"])
        return params
    def commit(params):
        atomic_write(CALENDAR_PATH, yaml.safe_dump(params["config"], sort_keys=False,
                     allow_unicode=True).encode("utf-8"))
    engine.register("calendar.write", commit, validate)
    try:
        request = engine.prepare(ActionRequest("calendar.write", {"config": config}))
        console.print("Review calendar changes:", config)
        grant = engine.session.reauthenticate(request.operation, request.params)
        engine.execute(request, grant=grant)
    finally:
        engine.close()


def validate_date(value: str, today: date | None = None) -> str:
    """Accept YYYY-MM-DD or a spoken date like "November 8" / "the 8th of this month"."""
    from core.assistant_platform.reminders import parse_date
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        pass
    parsed = parse_date(value, today)
    if parsed is None:
        raise typer.BadParameter(
            f"Couldn't read the date '{value}'. Try YYYY-MM-DD, 'November 8' or 'the 8th of this month'."
        )
    return parsed.isoformat()


def validate_status(status: str) -> str:
    if status not in VALID_STATUSES:
        raise typer.BadParameter(
            f"Invalid status '{status}'. Use one of: {', '.join(sorted(VALID_STATUSES))}"
        )
    return status


def print_context(target_date: str) -> None:
    context = build_calendar_context(date.fromisoformat(target_date))

    table = Table(title=f"ZÆNIA Calendar — {target_date}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

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


@app.callback()
def main():
    """
    ZÆNIA local calendar updater.
    """
    pass


@app.command("set-status")
@owner_command('calendar.read')
def set_status_command(
    target_date: str = typer.Argument(..., help="YYYY-MM-DD, 'November 8' or 'the 8th of this month'"),
    status: str = typer.Argument(..., help="on_duty, off_duty, leave, appointment, field, recovery"),
    note: str = typer.Option("", "--note", help="Optional note for that date."),
):
    """
    Override Zack's normal schedule for a specific date.
    """
    target_date = validate_date(target_date)
    status = validate_status(status)

    config = load_config()
    special_dates = config.get("special_dates") or {}
    config["special_dates"] = special_dates

    special_dates[target_date] = {
        "status": status,
        "note": note or None,
    }

    save_config(config)

    console.print(f"[green]Saved {target_date} as {status}.[/green]")
    print_context(target_date)


@app.command("add-event")
@owner_command('calendar.read')
def add_event_command(
    target_date: str = typer.Argument(..., help="YYYY-MM-DD, 'November 8' or 'the 8th of this month'"),
    event_time: str = typer.Argument(..., help="Time format: HH:MM"),
    title: str = typer.Argument(..., help="Event title."),
    reminder: str = typer.Option("", "--reminder", help="Optional reminder ZÆNIA should mention."),
):
    """
    Add a one-time event to Zack's local ZÆNIA calendar.
    """
    target_date = validate_date(target_date)

    config = load_config()
    events = config.get("events") or []
    config["events"] = events

    events.append(
        {
            "date": target_date,
            "time": event_time,
            "title": title,
            "reminder": reminder or None,
        }
    )

    save_config(config)

    console.print(f"[green]Added event for {target_date}: {title}.[/green]")
    print_context(target_date)


@app.command("add-recurring")
@owner_command('calendar.read')
def add_recurring_command(
    day: str = typer.Argument(..., help="Weekday name, example: Monday"),
    event_time: str = typer.Argument(..., help="Time format: HH:MM"),
    title: str = typer.Argument(..., help="Recurring event title."),
    reminder: str = typer.Option("", "--reminder", help="Optional recurring reminder."),
):
    """
    Add a weekly recurring event.
    """
    valid_days = {
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    }

    day = day.capitalize()

    if day not in valid_days:
        raise typer.BadParameter("Use a weekday name: Monday through Sunday.")

    config = load_config()
    recurring_events = config.get("recurring_events") or []
    config["recurring_events"] = recurring_events

    recurring_events.append(
        {
            "day": day,
            "time": event_time,
            "title": title,
            "reminder": reminder or None,
        }
    )

    save_config(config)

    console.print(f"[green]Added recurring {day} event: {title}.[/green]")


@app.command("show")
@owner_command('calendar.read')
def show_command(
    target_date: str = typer.Argument(..., help="YYYY-MM-DD, 'November 8' or 'the 8th of this month'"),
):
    """
    Show ZÆNIA calendar context for a specific date.
    """
    target_date = validate_date(target_date)
    print_context(target_date)


if __name__ == "__main__":
    app()
