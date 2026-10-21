from __future__ import annotations

import queue

import sounddevice as sd
from rich.console import Console

from core.conversation_runtime.partial_transcriber import (
    PartialTranscriber,
)
from core.conversation_runtime.turn_detector import (
    TurnDetector,
)
from core.conversation_runtime.turn_manager import (
    TurnManager,
)
from core.voice_listener.voice_listener import (
    find_approved_input_device,
)


console = Console()

audio_queue: queue.Queue[bytes] = queue.Queue()


def audio_callback(
    indata: bytes,
    frames: int,
    time_info,
    status,
) -> None:
    if status:
        console.print(
            f"[yellow]{status}[/yellow]"
        )

    audio_queue.put(
        bytes(indata)
    )


def run() -> None:
    detector = TurnDetector()

    transcriber = PartialTranscriber(
        sample_rate=detector.sample_rate,
    )

    manager = TurnManager()

    device_index, device = (
        find_approved_input_device()
    )

    console.print(
        "\n[bold cyan]"
        "ZÆNIA Natural Turn Test"
        "[/bold cyan]"
    )

    console.print(
        f"[green]Mic:[/green] "
        f"{device['name']}"
    )

    console.print(
        "\nTry saying:"
    )

    console.print(
        '[cyan]"I think we should..."[/cyan]'
    )

    console.print(
        "pause briefly, then continue:"
    )

    console.print(
        '[cyan]"change how the voice system works."[/cyan]\n'
    )

    console.print(
        "[dim]Press Ctrl+C to stop.[/dim]\n"
    )

    with sd.RawInputStream(
        samplerate=detector.sample_rate,
        blocksize=detector.frame_samples,
        device=device_index,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while True:
            pcm = audio_queue.get()

            vad_events = detector.feed_pcm16(
                pcm
            )

            transcript = transcriber.feed(
                pcm
            )

            if transcript["type"] == "partial":
                manager.update_partial(
                    transcript["text"]
                )

                console.print(
                    f"[dim]"
                    f"Partial → "
                    f"{transcript['text']}"
                    f"[/dim]"
                )

            elif transcript["type"] == "final":
                manager.add_final_segment(
                    transcript["text"]
                )

                console.print(
                    f"[dim]"
                    f"Segment → "
                    f"{transcript['text']}"
                    f"[/dim]"
                )

            for event in vad_events:
                if event["type"] == "speech_start":
                    manager.speech_started()

                    console.print(
                        "[green]"
                        "SPEECH START"
                        "[/green]"
                    )

                elif event["type"] == "speech_end":
                    manager.speech_ended()

                    console.print(
                        "[yellow]"
                        "PAUSE DETECTED — waiting..."
                        "[/yellow]"
                    )

            if manager.should_finalize():

                remaining = (
                    transcriber.finalize()
                )

                if remaining:
                    manager.add_final_segment(
                        remaining
                    )

                full_turn = (
                    manager.consume_turn()
                )

                transcriber.reset()

                if full_turn:
                    console.print(
                        "\n[bold cyan]"
                        f"TURN COMPLETE → {full_turn}"
                        "[/bold cyan]\n"
                    )


if __name__ == "__main__":
    try:
        run()

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]"
            "Natural turn test stopped."
            "[/yellow]"
        )