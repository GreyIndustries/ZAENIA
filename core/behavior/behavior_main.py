from __future__ import annotations
from core.foundation.local_entry import owner_command

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.behavior.behavior_engine import (
    build_situational_line,
    get_behavior_guidance,
    load_behavior_profile,
    record_command,
    record_correction,
    record_feedback,
    summarize_behavior_state,
)

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main():
    """
    ZÆNIA behavior learning tools.
    """
    pass


@app.command("status")
@owner_command('behavior.read')
def status_command():
    """
    Show ZÆNIA's current behavior-learning state.
    """
    profile = load_behavior_profile()
    behavior_profile = profile.get("behavior_profile", {})
    summary = summarize_behavior_state()

    table = Table(title="ZÆNIA Behavior State")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Enabled", str(behavior_profile.get("enabled", False)))
    table.add_row("Owner", str(behavior_profile.get("owner_name", "Unknown")))
    table.add_row("Assistant", str(behavior_profile.get("assistant_name", "ZÆNIA")))
    table.add_row("Time Context", str(summary["time_context"]))
    table.add_row("Recent Events", str(summary["recent_event_count"]))
    table.add_row("Event Counts", json.dumps(summary["event_type_counts"]))

    console.print(table)


@app.command("guide")
@owner_command('behavior.read')
def guide_command(
    command_text: str = typer.Argument("", help="Command or situation text to evaluate."),
    error: bool = typer.Option(False, "--error", help="Treat this as an error/debugging situation."),
    repeated_error: bool = typer.Option(False, "--repeated-error", help="Treat this as a repeated error."),
    carplay: bool = typer.Option(False, "--carplay", help="Treat this as a CarPlay briefing."),
    danger: bool = typer.Option(False, "--danger", help="Treat this as an urgent safety situation."),
    events: int = typer.Option(0, "--events", help="Calendar event count."),
):
    """
    Show how ZÆNIA should talk for a situation.
    """
    guidance = get_behavior_guidance(
        command_text,
        is_error=error,
        repeated_error=repeated_error,
        is_carplay=carplay,
        is_danger=danger,
        event_count=events,
    )

    table = Table(title="ZÆNIA Behavior Guidance")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    for key, value in guidance.items():
        table.add_row(str(key), str(value))

    console.print(table)

    situational_line = build_situational_line(
        guidance["situation"],
        event_count=events,
        first_event_title="first required item" if events else None,
    )

    if situational_line:
        console.print(Panel(situational_line, title="Situational Line", border_style="yellow"))
    else:
        console.print("[yellow]No extra phrase needed for this situation.[/yellow]")


@app.command("log-command")
@owner_command('behavior.record')
def log_command_command(
    command_text: str = typer.Argument(..., help="Command Zack used."),
):
    """
    Log a command so ZÆNIA can learn usage patterns.
    """
    record_command(command_text)
    console.print(f"[green]Logged command:[/green] {command_text}")


@app.command("feedback")
@owner_command('behavior.record')
def feedback_command(
    feedback: str = typer.Argument(..., help="Behavior feedback from Zack."),
):
    """
    Log feedback from Zack.
    """
    record_feedback(feedback)
    console.print(f"[green]Feedback logged:[/green] {feedback}")


@app.command("correction")
@owner_command('behavior.record')
def correction_command(
    correction: str = typer.Argument(..., help="Correction Zack gave ZÆNIA."),
):
    """
    Log a correction from Zack.
    """
    record_correction(correction)
    console.print(f"[green]Correction logged:[/green] {correction}")


@app.command("recent")
@owner_command('behavior.read')
def recent_command():
    """
    Show recent behavior events.
    """
    summary = summarize_behavior_state(limit=12)
    events = summary["recent_events"]

    if not events:
        console.print("[yellow]No behavior events logged yet.[/yellow]")
        return

    table = Table(title="Recent Behavior Events")
    table.add_column("Time", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Message", style="yellow")
    table.add_column("Metadata", style="magenta")

    for event in events:
        table.add_row(
            str(event.get("timestamp", "")),
            str(event.get("event_type", "")),
            str(event.get("message", "")),
            json.dumps(event.get("metadata", {}), ensure_ascii=False),
        )

    console.print(table)


if __name__ == "__main__":
    app()