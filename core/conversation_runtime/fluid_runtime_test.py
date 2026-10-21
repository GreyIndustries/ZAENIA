from __future__ import annotations

import queue
import threading
from typing import Any

import sounddevice as sd
from rich.console import Console

from core.brain.brain_service import (
    BrainService,
)
from core.brain.dialogue_manager import (
    return_to_background,
)
from core.conversation.conversation_state import (
    activate_conversation,
    is_conversation_active,
    record_user_speech,
)
from core.conversation_runtime.partial_transcriber import (
    PartialTranscriber,
)
from core.conversation_runtime.speech_queue import (
    SentenceBuffer,
    SpeechQueue,
)
from core.conversation_runtime.text_normalizer import (
    normalize_generated_text,
    normalize_transcript_text,
)
from core.conversation_runtime.turn_detector import (
    TurnDetector,
)
from core.conversation_runtime.turn_manager import (
    TurnManager,
)
from core.voice_listener.cognitive_filter import (
    filter_utterance,
)
from core.voice_listener.voice_listener import (
    find_approved_input_device,
)


console = Console()

audio_queue: queue.Queue[bytes] = (
    queue.Queue()
)


def microphone_callback(
    indata: bytes,
    frames: int,
    time_info: Any,
    status: Any,
) -> None:
    """
    Copy microphone audio into the runtime queue.

    The sounddevice callback should remain lightweight.
    Heavy speech processing happens outside this callback.
    """

    if status:
        console.print(
            f"[yellow]"
            f"Mic status: {status}"
            f"[/yellow]"
        )

    audio_queue.put(
        bytes(
            indata
        )
    )


class StreamingResponse:
    """
    One active ZÆNIA response.

    BrainService now owns:

        memory context
        behavior context
        brain routing
        normal Qwen streaming
        grounded retrieval
        evidence verification

    This class owns:

        sentence buffering
        Piper queueing
        interruption
        spoken-response completion

    That keeps cognition and audio delivery separate.
    """

    def __init__(
        self,
        brain: BrainService,
        user_text: str,
    ) -> None:
        self.brain = brain

        self.user_text = (
            user_text
        )

        self.cancel_event = (
            threading.Event()
        )

        self.active_event = (
            threading.Event()
        )

        self.finished_event = (
            threading.Event()
        )

        self.sentence_buffer = (
            SentenceBuffer()
        )

        self.speech = SpeechQueue(
            on_sentence_start=(
                self._sentence_started
            ),
            on_sentence_end=(
                self._sentence_ended
            ),
        )

        self.thread: (
            threading.Thread | None
        ) = None

        self.generated_parts: list[str] = []

        self.final_result: (
            dict[str, Any] | None
        ) = None

        self.route: str | None = None

        self.streaming_mode: (
            str | None
        ) = None

    def _sentence_started(
        self,
        sentence: str,
    ) -> None:
        """
        Display exactly what Piper is about to speak.
        """

        console.print(
            f"\n[cyan]"
            f"ZÆNIA → {sentence}"
            f"[/cyan]"
        )

    def _sentence_ended(
        self,
        sentence: str,
        completed: bool,
    ) -> None:
        """
        Report interrupted speech during development.
        """

        if not completed:
            console.print(
                "[dim]"
                "Speech interrupted."
                "[/dim]"
            )

    def _handle_route_event(
        self,
        event: dict[str, Any],
    ) -> None:
        """
        Record BrainService's routing decision.

        Examples:

            normal / live_tokens

            grounded_system / verified_final
        """

        self.route = str(
            event.get(
                "route",
                "unknown",
            )
        )

        self.streaming_mode = str(
            event.get(
                "streaming_mode",
                "unknown",
            )
        )

        console.print(
            "[dim]"
            f"Brain route: "
            f"{self.route} "
            f"({self.streaming_mode})"
            "[/dim]"
        )

    def _handle_text_event(
        self,
        event: dict[str, Any],
    ) -> None:
        """
        Feed safe BrainService text into the sentence buffer.

        For normal conversation these may be tiny live Qwen
        chunks.

        For grounded system answers the BrainService releases
        only the final verified answer.
        """

        text = str(
            event.get(
                "text",
                "",
            )
        )

        if not text:
            return

        self.generated_parts.append(
            text
        )

        sentences = (
            self.sentence_buffer.feed(
                text
            )
        )

        for sentence in sentences:
            if self.cancel_event.is_set():
                break

            self.speech.enqueue(
                sentence
            )

    def start(self) -> None:
        """
        Start cognition and speech delivery in the background.
        """

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )

        self.thread.start()

    def _run(self) -> None:
        """
        Run one complete BrainService response.

        Memory is deliberately disabled inside stream_ask().

        We save the exchange ourselves only AFTER speech
        completes successfully.

        That prevents a fully generated but interrupted answer
        from being stored as though Zack heard all of it.
        """

        self.active_event.set()

        self.speech.start()

        try:
            for event in self.brain.stream_ask(
                self.user_text,
                remember=False,
            ):
                if self.cancel_event.is_set():
                    break

                event_type = str(
                    event.get(
                        "type",
                        "",
                    )
                )

                if event_type == "route":
                    self._handle_route_event(
                        event
                    )

                elif event_type == "text":
                    self._handle_text_event(
                        event
                    )

                elif event_type == "final":
                    self.final_result = (
                        dict(
                            event
                        )
                    )

            if self.cancel_event.is_set():
                self.speech.interrupt()

                self.speech.finish()

                self.speech.wait()

                return

            remaining = (
                self.sentence_buffer.flush()
            )

            if remaining:
                self.speech.enqueue(
                    remaining
                )

            self.speech.finish()

            self.speech.wait()

            # [comment omitted from source review]
            # [comment omitted from source review]
            if self.cancel_event.is_set():
                return

            if self.final_result is not None:
                complete_reply = str(
                    self.final_result.get(
                        "answer",
                        "",
                    )
                ).strip()

                final_route = str(
                    self.final_result.get(
                        "route",
                        self.route
                        or "normal",
                    )
                )

            else:
                complete_reply = "".join(
                    self.generated_parts
                ).strip()

                final_route = (
                    self.route
                    or "normal"
                )

            complete_reply = (
                normalize_generated_text(
                    complete_reply
                )
            )

            if complete_reply:
                self.brain.remember_exchange(
                    question=(
                        self.user_text
                    ),
                    answer=(
                        complete_reply
                    ),
                    route=(
                        final_route
                    ),
                )

        except Exception as error:
            console.print(
                f"\n[red]"
                f"Streaming brain error: "
                f"{error}"
                f"[/red]"
            )

            try:
                self.speech.interrupt()

                self.speech.finish()

                self.speech.wait()

            except Exception:
                pass

        finally:
            self.active_event.clear()

            self.finished_event.set()

    def interrupt(self) -> None:
        """
        Immediately stop spoken output and mark the brain
        response as cancelled.

        Normal Qwen streaming will stop on the next yielded
        event.

        A grounded reasoning operation may still finish its
        current local verification computation internally,
        but its answer will not be spoken after cancellation.
        """

        if self.finished_event.is_set():
            return

        self.cancel_event.set()

        self.speech.interrupt()

        console.print(
            "\n[bold magenta]"
            "BARGE-IN"
            "[/bold magenta]"
        )

    def is_active(self) -> bool:
        return (
            self.active_event.is_set()
        )

    def is_speaking(self) -> bool:
        return (
            self.speech.is_speaking()
        )


class FluidRuntime:
    def __init__(self):
        raise PermissionError("Legacy unverified voice runtime is retired. Use core.voice_security.runtime.")


def run():
    from core.voice_security.runtime import run as secured_run
    secured_run()


if __name__ == "__main__":
    try: run()
    except KeyboardInterrupt: print("Voice stopped.")
