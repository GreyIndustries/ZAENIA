from core.foundation.local_entry import owner_command
from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from core.briefing.drive_briefing import build_drive_briefing
from core.voice_output.speaker import speak

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main():
    """
    ZÆNIA drive briefing tools.
    """
    pass


@app.command("now")
@owner_command('briefing.generate')
def now_command(
    say: bool = typer.Option(False, "--say", help="Speak the drive briefing aloud."),
    force_traffic: bool = typer.Option(
        False,
        "--force-traffic",
        help="Include I-5 traffic even outside the normal traffic windows.",
    ),
    calendar_date: str | None = typer.Option(
        None,
        "--calendar-date",
        help="Preview briefing using a specific calendar date, format YYYY-MM-DD.",
    ),
):
    """
    Build a drive briefing with weather, calendar context, personality, and optional I-5 traffic.
    """
    preview_date = date.fromisoformat(calendar_date) if calendar_date else None

    briefing = build_drive_briefing(
        include_traffic_force=force_traffic,
        calendar_date=preview_date,
    )

    table = Table(title="ZÆNIA Drive Briefing")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Weather Location", str(briefing["weather_location"].get("display_label")))
    table.add_row("Calendar Date", str(briefing["calendar_context"].get("date")))
    table.add_row("Calendar Status", str(briefing["calendar_context"].get("status_label")))
    table.add_row("Event Count", str(briefing["calendar_context"].get("event_count")))
    table.add_row("Traffic Included", str(briefing["traffic_included"]))
    table.add_row("Traffic Window", str(briefing["traffic_window"] or "None"))

    first_event = briefing["calendar_context"].get("first_event")
    if first_event:
        table.add_row("First Event", str(first_event.get("title")))
    else:
        table.add_row("First Event", "None")

    console.print(table)
    console.print(f"[cyan]{briefing['spoken_briefing']}[/cyan]")

    if say:
        speak(briefing["spoken_briefing"])


if __name__ == "__main__":
    app()