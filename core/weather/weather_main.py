from core.foundation.local_entry import owner_command
import typer
from rich.console import Console
from rich.table import Table

from core.voice_output.speaker import speak
from core.weather.weather_client import get_weather_for_location
from core.weather.weather_selector import build_location_response, select_weather_location

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main():
    """
    ZÆNIA weather tools.
    """
    pass


@app.command("location")
@owner_command('weather.read')
def location_command(
    say: bool = typer.Option(False, "--say", help="Speak the selected weather location aloud."),
):
    """
    Show which weather location ZÆNIA should use right now.
    """
    location = select_weather_location()
    response = build_location_response(location)

    table = Table(title="ZÆNIA Weather Location")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Name", str(location.get("name")))
    table.add_row("Display Label", str(location.get("display_label")))
    table.add_row("Lookup Name", str(location.get("lookup_name")))
    table.add_row("Location Key", str(location.get("location_key")))
    table.add_row("Source", str(location.get("source")))
    table.add_row("Selected At", str(location.get("selected_at", "manual")))

    console.print(table)
    console.print(f"[cyan]{response}[/cyan]")

    if say:
        speak(response)


@app.command("now")
@owner_command('weather.read')
def now_command(
    say: bool = typer.Option(False, "--say", help="Speak the weather summary aloud."),
):
    """
    Get current weather for ZÆNIA's selected location.
    """
    location = select_weather_location()
    result = get_weather_for_location(location)

    geo = result["geocoded"]

    table = Table(title="ZÆNIA Weather Now")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Context", str(location.get("display_label")))
    table.add_row("Lookup", str(location.get("lookup_name")))
    table.add_row("Resolved Name", str(geo.get("name")))
    table.add_row("Latitude", str(geo.get("latitude")))
    table.add_row("Longitude", str(geo.get("longitude")))
    table.add_row("Timezone", str(geo.get("timezone")))

    console.print(table)
    console.print(f"[cyan]{result['summary']}[/cyan]")

    if say:
        speak(result["summary"])


@app.command("status")
@owner_command('weather.read')
def status_command():
    """
    Quick weather module status check.
    """
    location = select_weather_location()
    console.print("[green]Weather selector is working.[/green]")
    console.print(f"[cyan]Current weather context:[/cyan] {location.get('display_label')}")


if __name__ == "__main__":
    app()