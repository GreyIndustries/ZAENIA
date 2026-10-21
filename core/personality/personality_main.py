from core.foundation.local_entry import owner_command
import typer
from rich.console import Console
from rich.table import Table

from core.personality.personality_manager import (
    PERSONALITY_PATH,
    add_avoid,
    add_preference,
    apply_to_carplay,
    get_summary,
    load_yaml,
    log_feedback,
    read_feedback_log,
)

app = typer.Typer()
console = Console()


@app.command("show")
@owner_command('personality.read')
def show_command():
    """
    Show ZÆNIA's current personality profile for Zack.
    """
    data = load_yaml(PERSONALITY_PATH)
    summary = get_summary()

    console.print("[cyan]ZÆNIA Personality Profile[/cyan]")
    console.print(f"[green]User:[/green] {data.get('core_identity', {}).get('user_name')}")
    console.print(f"[green]Assistant:[/green] {data.get('core_identity', {}).get('assistant_name')}")

    table = Table(title="Personality Summary")
    table.add_column("Preferred", style="green")
    table.add_column("Avoid", style="red")

    max_len = max(len(summary["preferred"]), len(summary["avoided"]))

    for i in range(max_len):
        preferred = summary["preferred"][i] if i < len(summary["preferred"]) else ""
        avoided = summary["avoided"][i] if i < len(summary["avoided"]) else ""
        table.add_row(preferred, avoided)

    console.print(table)


@app.command("feedback")
@owner_command('personality.write')
def feedback_command(note: str):
    """
    Save feedback from Zack for future personality tuning.
    """
    log_feedback(note)
    console.print("[green]Feedback saved.[/green]")


@app.command("add-preference")
@owner_command('personality.write')
def add_preference_command(text: str):
    """
    Add a personality preference.
    """
    added = add_preference(text)

    if added:
        console.print(f"[green]Preference added:[/green] {text}")
    else:
        console.print("[yellow]Preference already exists.[/yellow]")


@app.command("add-avoid")
@owner_command('personality.write')
def add_avoid_command(text: str):
    """
    Add a phrase, tone, or behavior ZÆNIA should avoid.
    """
    added = add_avoid(text)

    if added:
        console.print(f"[green]Avoid rule added:[/green] {text}")
    else:
        console.print("[yellow]Avoid rule already exists.[/yellow]")


@app.command("apply-carplay")
@owner_command('personality.write')
def apply_carplay_command():
    """
    Apply ZÆNIA's personality profile to the CarPlay message config.
    """
    result = apply_to_carplay()

    console.print("[green]Personality applied to CarPlay config.[/green]")
    console.print(f"[cyan]Style items added:[/cyan] {result['style_added']}")
    console.print(f"[cyan]Avoid items added:[/cyan] {result['avoid_added']}")


@app.command("recent-feedback")
@owner_command('personality.read')
def recent_feedback_command(lines: int = typer.Option(20, "--lines", "-n")):
    """
    Show recent personality feedback.
    """
    entries = read_feedback_log(limit=lines)

    if not entries:
        console.print("[yellow]No feedback saved yet.[/yellow]")
        return

    table = Table(title="Recent Personality Feedback")
    table.add_column("Time", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Note", style="white")

    for entry in entries:
        table.add_row(
            entry.get("timestamp", ""),
            entry.get("category", ""),
            entry.get("note", ""),
        )

    console.print(table)


if __name__ == "__main__":
    app()
