from __future__ import annotations

import queue

import sounddevice as sd
from rich.console import Console

from core.conversation_runtime.turn_detector import TurnDetector
from core.voice_listener.voice_listener import find_approved_input_device


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
            f"[yellow]Audio status: {status}[/yellow]"
        )

    audio_queue.put(
        bytes(indata)
    )


def run_test() -> None:
    detector = TurnDetector()

    device_index, device = (
        find_approved_input_device()
    )

    sample_rate = detector.sample_rate
    frame_samples = detector.frame_samples

    console.print(
        "\n[bold cyan]"
        "ZÆNIA Live Turn Detection Test"
        "[/bold cyan]"
    )

    console.print(
        f"[green]Microphone:[/green] "
        f"{device['name']}"
    )

    console.print(
        f"[green]VAD sample rate:[/green] "
        f"{sample_rate} Hz"
    )

    console.print(
        f"[green]Frame size:[/green] "
        f"{frame_samples}"
    )

    try:
        sd.check_input_settings(
            device=device_index,
            channels=1,
            dtype="int16",
            samplerate=sample_rate,
        )

    except Exception as error:
        raise RuntimeError(
            "The approved microphone route could not "
            f"open directly at {sample_rate} Hz.\n"
            f"Details: {error}"
        ) from error

    console.print(
        "\nSay a sentence normally."
    )

    console.print(
        "Try pausing briefly in the middle."
    )

    console.print(
        "\n[dim]"
        "Press Ctrl+C when finished."
        "[/dim]\n"
    )

    with sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=frame_samples,
        device=device_index,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while True:
            pcm = audio_queue.get()

            events = detector.feed_pcm16(
                pcm
            )

            for event in events:
                event_type = event.get(
                    "type"
                )

                if event_type == "speech_start":
                    console.print(
                        "[bold green]"
                        "SPEECH START"
                        "[/bold green]"
                    )

                elif event_type == "speech_end":
                    console.print(
                        "[bold blue]"
                        "SPEECH END"
                        "[/bold blue]"
                    )


if __name__ == "__main__":
    try:
        run_test()

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]"
            "Turn detection test stopped."
            "[/yellow]"
        )