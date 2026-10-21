from __future__ import annotations

import queue
import threading
import time

import sounddevice as sd
from rich.console import Console

from core.conversation_runtime.interruptible_speaker import (
    InterruptibleSpeaker,
)
from core.conversation_runtime.turn_detector import (
    TurnDetector,
)
from core.voice_listener.voice_listener import (
    find_approved_input_device,
)


console = Console()

audio_queue: queue.Queue[bytes] = queue.Queue()


def microphone_callback(
    indata: bytes,
    frames: int,
    time_info,
    status,
) -> None:
    if status:
        console.print(
            f"[yellow]Mic status: {status}[/yellow]"
        )

    audio_queue.put(
        bytes(indata)
    )


def run_test() -> None:
    detector = TurnDetector()
    speaker = InterruptibleSpeaker()

    device_index, device = (
        find_approved_input_device()
    )

    test_text = (
        "Zack, this is the ZÆNIA barge in test. "
        "I am going to continue speaking for several seconds. "
        "While I am talking, say stop or begin speaking normally. "
        "If the interruption system is working correctly, "
        "my voice should stop as soon as your speech is detected. "
        "After that, the microphone remains available for your next turn."
    )

    console.print(
        "\n[bold cyan]"
        "ZÆNIA Barge-In Test"
        "[/bold cyan]"
    )

    console.print(
        f"[green]Mic:[/green] "
        f"{device['name']}"
    )

    console.print(
        "\nWait until ZÆNIA starts talking."
    )

    console.print(
        "Then say:"
    )

    console.print(
        '[cyan]"Stop."[/cyan]'
    )

    console.print(
        "\nExpected:"
    )

    console.print(
        "Your speech → VAD speech start "
        "→ Piper immediately stops.\n"
    )

    interrupted = False

    with sd.RawInputStream(
        samplerate=detector.sample_rate,
        blocksize=detector.frame_samples,
        device=device_index,
        dtype="int16",
        channels=1,
        callback=microphone_callback,
    ):
        speech_thread = threading.Thread(
            target=speaker.speak,
            args=(test_text,),
            daemon=True,
        )

        speech_thread.start()

        # Wait until playback actually begins before
        # allowing speech-start events to count as barge-in.
        start_deadline = (
            time.monotonic() + 10.0
        )

        while (
            not speaker.is_speaking()
            and speech_thread.is_alive()
            and time.monotonic() < start_deadline
        ):
            try:
                audio_queue.get(
                    timeout=0.05
                )
            except queue.Empty:
                pass

        detector.reset()

        # Throw away anything captured during Piper startup.
        while True:
            try:
                audio_queue.get_nowait()
            except queue.Empty:
                break

        console.print(
            "[green]"
            "ZÆNIA is speaking — interrupt now."
            "[/green]"
        )

        while speech_thread.is_alive():
            try:
                pcm = audio_queue.get(
                    timeout=0.10
                )

            except queue.Empty:
                continue

            events = detector.feed_pcm16(
                pcm
            )

            for event in events:
                if (
                    event.get("type")
                    == "speech_start"
                    and speaker.is_speaking()
                ):
                    console.print(
                        "\n[bold magenta]"
                        "BARGE-IN DETECTED"
                        "[/bold magenta]"
                    )

                    speaker.interrupt()

                    interrupted = True

                    break

            if interrupted:
                break

        speech_thread.join(
            timeout=5
        )

    if interrupted:
        console.print(
            "\n[bold green]"
            "Voice barge-in works."
            "[/bold green]"
        )

    else:
        console.print(
            "\n[yellow]"
            "No barge-in was detected."
            "[/yellow]"
        )


if __name__ == "__main__":
    try:
        run_test()

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]"
            "Barge-in test stopped."
            "[/yellow]"
        )