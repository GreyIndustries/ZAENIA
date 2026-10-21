from core.foundation.local_entry import owner_command
from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from core.google_calendar_sync.google_calendar_ics import (
    ICS_URL_PATH,
    get_google_events_between,
    sync_google_calendar_to_local,
)

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main():
    """
    ZÆNIA Google Calendar iCal sync tools.
    """
    pass


@app.command("status")
@owner_command('calendar.read')
def status_command():
    """
    Check whether the private Google Calendar iCal URL is saved.
    """
    table = Table(title="ZÆNIA Google Calendar Sync Status")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("iCal URL File", str(ICS_URL_PATH))
    table.add_row("Exists", str(ICS_URL_PATH.exists()))

    if ICS_URL_PATH.exists():
        url = ICS_URL_PATH.read_text(encoding="utf-8").strip()
        table.add_row("URL Saved", str(bool(url)))
    else:
        table.add_row("URL Saved", "False")

    console.print(table)


@app.command("preview")
@owner_command('calendar.read')
def preview_command(
    start_date: str | None = typer.Option(
        None,
        "--start-date",
        help="Start date to preview, format YYYY-MM-DD. Defaults to today.",
    ),
    days: int = typer.Option(
        2,
        "--days",
        help="Number of days to preview.",
    ),
):
    """
    Preview Google Calendar events without saving them into ZÆNIA.
    """
    parsed_start = date.fromisoformat(start_date) if start_date else None
    parsed_start = parsed_start or date.today()

    events = get_google_events_between(start_date=parsed_start, days=days)

    table = Table(title="Google Calendar iCal Preview")
    table.add_column("Date", style="cyan")
    table.add_column("Time", style="green")
    table.add_column("Title", style="yellow")
    table.add_column("Reminder", style="magenta")

    for event in events:
        table.add_row(
            str(event.get("date", "")),
            str(event.get("time", "")),
            str(event.get("title", "")),
            str(event.get("reminder") or ""),
        )

    console.print(table)
    console.print(f"[green]Found {len(events)} Google Calendar event(s).[/green]")


@app.command("sync")
@owner_command('calendar.read')
def sync_command(
    start_date: str | None = typer.Option(
        None,
        "--start-date",
        help="Start date to sync, format YYYY-MM-DD. Defaults to today.",
    ),
    days: int = typer.Option(
        2,
        "--days",
        help="Number of days to sync into ZÆNIA local calendar.",
    ),
):
    """
    Sync Google Calendar iCal events into ZÆNIA's local calendar file.
    """
    parsed_start = date.fromisoformat(start_date) if start_date else None

    result = sync_google_calendar_to_local(
        start_date=parsed_start,
        days=days,
    )

    table = Table(title="Google Calendar Synced to ZÆNIA")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Start Date", result["start_date"])
    table.add_row("Days", str(result["days"]))
    table.add_row("Imported Events", str(result["imported_count"]))
    table.add_row("Target Dates", ", ".join(result["target_dates"]))

    console.print(table)

    if result["events"]:
        event_table = Table(title="Imported Events")
        event_table.add_column("Date", style="cyan")
        event_table.add_column("Time", style="green")
        event_table.add_column("Title", style="yellow")
        event_table.add_column("Reminder", style="magenta")

        for event in result["events"]:
            event_table.add_row(
                str(event.get("date", "")),
                str(event.get("time", "")),
                str(event.get("title", "")),
                str(event.get("reminder") or ""),
            )

        console.print(event_table)
    else:
        console.print("[yellow]No Google Calendar events found for this window.[/yellow]")


if __name__ == "__main__":
    app()