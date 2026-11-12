from __future__ import annotations

import time

from rich.console import Console

from core.brain.local_llm import (
    stream_chat_local,
)
from core.conversation_runtime.speech_queue import (
    SentenceBuffer,
    SpeechQueue,
)


console = Console()


def timestamp() -> str:
    return time.strftime(
        "%H:%M:%S"
    )


def sentence_started(
    sentence: str,
) -> None:
    console.print(
        f"\n[green]"
        f"[{timestamp()}] SPEAKING → "
        f"{sentence}"
        f"[/green]"
    )


def sentence_finished(
    sentence: str,
    completed: bool,
) -> None:
    if completed:
        console.print(
            f"[dim]"
            f"[{timestamp()}] Sentence finished"
            f"[/dim]"
        )

    else:
        console.print(
            f"[yellow]"
            f"[{timestamp()}] Sentence interrupted"
            f"[/yellow]"
        )


def run_test() -> None:
    buffer = SentenceBuffer()

    speech = SpeechQueue(
        on_sentence_start=sentence_started,
        on_sentence_end=sentence_finished,
    )

    speech.start()

    prompt = (
        "/no_think "
        "Reply conversationally in exactly four short sentences. "
        "Explain why a fluid voice assistant should begin speaking "
        "before its entire response has finished generating. "
        "Use plain spoken English and no markdown."
    )

    console.print(
        "\n[bold cyan]"
        "ZÆNIA Streaming Voice Pipeline"
        "[/bold cyan]\n"
    )

    console.print(
        "[dim]"
        "Qwen is generating while Piper speaks completed sentences."
        "[/dim]\n"
    )

    try:
        for chunk in stream_chat_local(
            prompt
        ):
            console.print(
                chunk,
                end="",
                highlight=False,
            )

            sentences = buffer.feed(
                chunk
            )

            for sentence in sentences:
                speech.enqueue(
                    sentence
                )

        remaining = buffer.flush()

        if remaining:
            speech.enqueue(
                remaining
            )

        console.print(
            "\n\n[cyan]"
            "Qwen generation finished."
            "[/cyan]"
        )

        speech.finish()

        speech.wait()

        console.print(
            "\n[bold green]"
            "Streaming speech pipeline complete."
            "[/bold green]"
        )

    except KeyboardInterrupt:
        speech.interrupt()

        console.print(
            "\n[yellow]"
            "Streaming speech interrupted."
            "[/yellow]"
        )


if __name__ == "__main__":
    run_test()