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

    device_index, device = (
        find_approved_input_device()
    )

    console.print(
        "\n[bold cyan]"
        "ZÆNIA Streaming Speech Test"
        "[/bold cyan]"
    )

    console.print(
        f"[green]Mic:[/green] "
        f"{device['name']}"
    )

    console.print(
        "\nSpeak normally. "
        "Partial words should appear while you talk.\n"
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

            result = transcriber.feed(
                pcm
            )

            if result["type"] == "partial":
                console.print(
                    f"[dim]"
                    f"Partial → {result['text']}"
                    f"[/dim]"
                )

            elif result["type"] == "final":
                console.print(
                    f"[bold cyan]"
                    f"Final → {result['text']}"
                    f"[/bold cyan]"
                )

            for event in vad_events:
                if event["type"] == "speech_start":
                    console.print(
                        "[green]SPEECH START[/green]"
                    )

                elif event["type"] == "speech_end":
                    remaining = (
                        transcriber.finalize()
                    )

                    if remaining:
                        console.print(
                            f"[bold cyan]"
                            f"Turn Final → {remaining}"
                            f"[/bold cyan]"
                        )

                    transcriber.reset()

                    console.print(
                        "[blue]SPEECH END[/blue]\n"
                    )


if __name__ == "__main__":
    try:
        run()

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]"
            "Streaming test stopped."
            "[/yellow]"
        )