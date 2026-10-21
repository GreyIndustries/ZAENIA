from core.foundation.local_entry import owner_command
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import typer
import yaml
from rich.console import Console
from rich.table import Table

from core.traffic.traffic_client import get_i5_traffic_summary
from core.voice_output.speaker import speak

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAFFIC_CONFIG_PATH = PROJECT_ROOT / "core" / "traffic" / "traffic_config.yaml"

app = typer.Typer(no_args_is_help=True)
console = Console()


def load_traffic_config() -> dict[str, Any]:
    if not TRAFFIC_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Traffic config not found: {TRAFFIC_CONFIG_PATH}")

    with TRAFFIC_CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError("traffic_config.yaml is empty or invalid.")

    return data


def parse_clock(value: str) -> time:
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def get_now(config: dict[str, Any]) -> datetime:
    timezone_name = config.get("traffic_system", {}).get("timezone", "America/Los_Angeles")
    return datetime.now(ZoneInfo(timezone_name))


def get_active_window(config: dict[str, Any]) -> str | None:
    now = get_now(config)
    current_day = now.strftime("%A")
    current_time = now.time()

    windows = config.get("check_windows", {})

    for window_name, window in windows.items():
        if not window.get("enabled", False):
            continue

        if current_day not in window.get("days", []):
            continue

        start = parse_clock(window["start_time"])
        end = parse_clock(window["end_time"])

        if start <= current_time <= end:
            return window_name

    return None


@app.callback()
def main():
    """
    ZÆNIA traffic tools.
    """
    pass


@app.command("status")
@owner_command('traffic.read')
def status_command():
    """
    Show traffic module status and whether traffic should be included right now.
    """
    config = load_traffic_config()
    active_window = get_active_window(config)

    table = Table(title="ZÆNIA Traffic Status")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Enabled", str(config.get("traffic_system", {}).get("enabled", False)))
    table.add_row("Provider", str(config.get("traffic_system", {}).get("provider")))
    table.add_row("Route", str(config.get("route_focus", {}).get("display_name")))
    table.add_row("Area", str(config.get("route_focus", {}).get("area_label")))
    table.add_row("Active Window", active_window or "None")

    console.print(table)

    if active_window:
        console.print("[green]Traffic should be included right now.[/green]")
    else:
        console.print("[yellow]Outside traffic check window. Traffic will be skipped unless forced.[/yellow]")


@app.command("now")
@owner_command('traffic.read')
def now_command(
    say: bool = typer.Option(False, "--say", help="Speak the traffic summary aloud."),
    force: bool = typer.Option(False, "--force", help="Check traffic even outside normal windows."),
):
    """
    Check I-5 traffic near Lacey, JBLM, and Tacoma.
    """
    config = load_traffic_config()

    if not config.get("traffic_system", {}).get("enabled", False):
        console.print("[red]Traffic system is disabled.[/red]")
        raise typer.Exit(code=1)

    active_window = get_active_window(config)

    if not active_window and not force:
        message = config.get("default_behavior", {}).get(
            "outside_check_window",
            "Traffic is outside the normal check window."
        )
        console.print(f"[yellow]{message}[/yellow]")
        return

    result = get_i5_traffic_summary()

    table = Table(title="ZÆNIA I-5 Traffic")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Active Window", active_window or "Forced")
    table.add_row("Total WSDOT Flow Points", str(result["total_flow_points"]))
    table.add_row("Matched I-5 Area Points", str(result["matched_i5_points"]))

    console.print(table)
    console.print(f"[cyan]{result['summary']}[/cyan]")

    if say:
        speak(result["summary"])


if __name__ == "__main__":
    app()