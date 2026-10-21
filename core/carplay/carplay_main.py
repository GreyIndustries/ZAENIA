from core.foundation.local_entry import owner_command
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from core.carplay.carplay_manager import (
    build_carstartup_text,
    get_default_onedrive_path,
    load_message_config,
    validate_messages,
    write_carstartup_file,
)

app = typer.Typer()
console = Console()

CONFIG_PATH = Path("core") / "carplay" / "messages.yaml"


@app.command()
@owner_command('briefing.generate')
def preview():
    """
    Preview the CarStartup.txt output without writing it.
    """
    data = load_message_config(CONFIG_PATH)
    problems = validate_messages(data)

    if problems:
        console.print("[red]Problems found:[/red]")
        for problem in problems:
            console.print(f"- {problem}")
        raise typer.Exit(code=1)

    text = build_carstartup_text(data)
    console.print(text)


@app.command()
@owner_command('briefing.generate')
def validate():
    """
    Check if messages.yaml is safe for the iPhone Shortcut.
    """
    data = load_message_config(CONFIG_PATH)
    problems = validate_messages(data)

    if not problems:
        console.print("[green]CarPlay messages are valid.[/green]")
        return

    console.print("[red]Problems found:[/red]")
    for problem in problems:
        console.print(f"- {problem}")

    raise typer.Exit(code=1)


@app.command()
@owner_command('files.write')
def write(
    output: str = typer.Option(None, "--output", "-o"),
):
    """
    Write CarStartup.txt for the iPhone Shortcut.
    """
    data = load_message_config(CONFIG_PATH)
    problems = validate_messages(data)

    if problems:
        console.print("[red]Refusing to write because problems were found:[/red]")
        for problem in problems:
            console.print(f"- {problem}")
        raise typer.Exit(code=1)

    output_path = Path(output) if output else get_default_onedrive_path()
    text = build_carstartup_text(data)

    write_carstartup_file(output_path, text)

    console.print("[green]CarStartup.txt updated successfully.[/green]")
    console.print(f"[cyan]Path:[/cyan] {output_path}")


@app.command()
@owner_command('briefing.generate')
def show_path():
    """
    Show the default OneDrive CarStartup.txt path ZÆNIA will use.
    """
    path = get_default_onedrive_path()
    console.print(f"[cyan]Default path:[/cyan] {path}")


@app.command()
@owner_command('briefing.generate')
def table():
    """
    Show messages in table form.
    """
    data = load_message_config(CONFIG_PATH)
    messages = data["messages"]

    table_view = Table(title="ZÆNIA CarPlay Startup Messages")
    table_view.add_column("Day", style="cyan")
    table_view.add_column("Morning", style="green")
    table_view.add_column("Afternoon", style="yellow")
    table_view.add_column("Night", style="magenta")

    for day, blocks in messages.items():
        table_view.add_row(
            day,
            blocks.get("Morning", ""),
            blocks.get("Afternoon", ""),
            blocks.get("Night", ""),
        )

    console.print(table_view)


if __name__ == "__main__":
    app()