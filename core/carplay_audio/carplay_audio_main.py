from __future__ import annotations
from core.foundation.local_entry import owner_command

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from core.carplay_audio.carplay_audio import (
    build_and_save_carplay_audio,
    get_default_audio_path,
    get_default_text_path,
)


app = typer.Typer(
    no_args_is_help=True
)

console = Console()


@app.callback()
def main(
) -> None:
    """
    ZÆNIA local CarPlay briefing tools.
    """

    pass


@app.command(
    "paths"
)
@owner_command('briefing.generate')
def paths_command(
) -> None:
    """
    Show CarPlay briefing output locations.
    """

    table = Table(
        title=(
            "ZÆNIA CarPlay Briefing Paths"
        )
    )

    table.add_column(
        "File",
        style="cyan",
    )

    table.add_column(
        "Path",
        style="green",
    )

    table.add_row(
        "Audio WAV",
        str(
            get_default_audio_path()
        ),
    )

    table.add_row(
        "Text Backup",
        str(
            get_default_text_path()
        ),
    )

    console.print(
        table
    )


@app.command(
    "generate"
)
@owner_command('briefing.generate')
def generate_command(
    force_traffic: bool = typer.Option(
        False,
        "--force-traffic",
        help=(
            "Include traffic even outside "
            "configured traffic windows."
        ),
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help=(
            "Optional custom WAV output path."
        ),
    ),
) -> None:
    """
    Build a fresh current briefing and render it with local
    Piper.
    """

    result = (
        build_and_save_carplay_audio(
            force_traffic=(
                force_traffic
            ),
            output_path=(
                output
            ),
        )
    )

    table = Table(
        title=(
            "ZÆNIA CarPlay Briefing Generated"
        )
    )

    table.add_column(
        "Field",
        style="cyan",
    )

    table.add_column(
        "Value",
        style="green",
    )

    table.add_row(
        "Audio Path",
        result[
            "audio_path"
        ],
    )

    table.add_row(
        "Text Path",
        result[
            "text_path"
        ],
    )

    table.add_row(
        "Traffic Included",
        str(
            result[
                "traffic_included"
            ]
        ),
    )

    table.add_row(
        "Traffic Window",
        str(
            result[
                "traffic_window"
            ]
            or "None"
        ),
    )

    table.add_row(
        "Voice Provider",
        "Local Piper",
    )

    console.print(
        table
    )

    console.print()

    console.print(
        "[bold cyan]"
        "Current briefing:"
        "[/bold cyan]"
    )

    console.print(
        result[
            "text"
        ]
    )


if __name__ == "__main__":
    app()