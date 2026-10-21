from __future__ import annotations

import queue
import re
import threading
from typing import Callable

from core.conversation_runtime.interruptible_speaker import (
    InterruptibleSpeaker,
)
from core.conversation_runtime.text_normalizer import (
    normalize_generated_text,
)


class SentenceBuffer:
    """
    Collect streamed brain text and release complete,
    speakable sentences as soon as possible.

    This works with both:

        live Qwen chunks

    and:

        complete verified grounded answers
    """

    def __init__(
        self,
    ) -> None:
        self.buffer = ""

    def reset(
        self,
    ) -> None:
        self.buffer = ""

    def _clean_for_speech(
        self,
        text: str,
    ) -> str:
        """
        Normalize generated text before Piper receives it.
        """

        text = (
            normalize_generated_text(
                text
            )
        )

        text = (
            text.strip()
        )

        # Remove Markdown characters that should not normally
        # be pronounced aloud.
        text = re.sub(
            r"[*_`#>]",
            "",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return (
            text.strip()
        )

    def feed(
        self,
        chunk: str,
    ) -> list[str]:
        """
        Add one BrainService text chunk.

        Complete sentences are returned immediately.

        Raw chunks remain unmodified until a sentence boundary
        exists, preventing streamed token spacing from being
        damaged.
        """

        if not chunk:
            return []

        self.buffer += (
            chunk
        )

        completed: list[str] = []

        while True:
            match = re.search(
                r"(.+?[.!?])(?:\s+|$)",
                self.buffer,
                flags=re.DOTALL,
            )

            if not match:
                break

            sentence = (
                match.group(
                    1
                )
            )

            self.buffer = (
                self.buffer[
                    match.end():
                ]
            )

            cleaned = (
                self._clean_for_speech(
                    sentence
                )
            )

            if cleaned:
                completed.append(
                    cleaned
                )

        return completed

    def flush(
        self,
    ) -> str:
        """
        Return remaining text when the brain stream ends.
        """

        remaining = (
            self._clean_for_speech(
                self.buffer
            )
        )

        self.buffer = ""

        return remaining


class SpeechQueue:
    """
    Background Piper speech worker.

    The brain can continue generating while Piper speaks
    already-completed sentences.

    The queue also supports immediate barge-in.

    A separate finish flag prevents interruption from
    accidentally deleting the worker's shutdown signal and
    causing a thread to hang.
    """

    def __init__(
        self,
        *,
        on_sentence_start: (
            Callable[
                [str],
                None,
            ]
            | None
        ) = None,
        on_sentence_end: (
            Callable[
                [str, bool],
                None,
            ]
            | None
        ) = None,
    ) -> None:
        self.speaker = (
            InterruptibleSpeaker()
        )

        self.queue: (
            queue.Queue[
                str | None
            ]
        ) = queue.Queue()

        self.on_sentence_start = (
            on_sentence_start
        )

        self.on_sentence_end = (
            on_sentence_end
        )

        self._interrupt_event = (
            threading.Event()
        )

        self._finish_requested = (
            threading.Event()
        )

        self._worker_exited = (
            threading.Event()
        )

        self._worker: (
            threading.Thread | None
        ) = None

    def start(
        self,
    ) -> None:
        """
        Start the speech worker once.
        """

        if (
            self._worker
            is not None
            and self._worker.is_alive()
        ):
            return

        self._interrupt_event.clear()

        self._finish_requested.clear()

        self._worker_exited.clear()

        self._worker = (
            threading.Thread(
                target=self._run,
                daemon=True,
            )
        )

        self._worker.start()

    def enqueue(
        self,
        sentence: str,
    ) -> None:
        """
        Queue a completed sentence for Piper.

        No new sentences are accepted after interruption or
        after shutdown has been requested.
        """

        sentence = (
            sentence.strip()
        )

        if not sentence:
            return

        if (
            self._interrupt_event.is_set()
            or self._finish_requested.is_set()
        ):
            return

        self.queue.put(
            sentence
        )

    def _run(
        self,
    ) -> None:
        """
        Background sentence playback loop.
        """

        try:
            while True:
                item = (
                    self.queue.get()
                )

                try:
                    if item is None:
                        return

                    if self._interrupt_event.is_set():
                        continue

                    if self.on_sentence_start:
                        self.on_sentence_start(
                            item
                        )

                    completed = (
                        self.speaker.speak(
                            item
                        )
                    )

                    if self.on_sentence_end:
                        self.on_sentence_end(
                            item,
                            completed,
                        )

                finally:
                    self.queue.task_done()

        finally:
            self._worker_exited.set()

    def _drain_pending_queue(
        self,
    ) -> None:
        """
        Remove sentences that have not yet been spoken.

        If a shutdown marker is removed during the drain, the
        caller can safely restore one afterward.
        """

        while True:
            try:
                self.queue.get_nowait()

                self.queue.task_done()

            except queue.Empty:
                break

    def interrupt(
        self,
    ) -> None:
        """
        Stop current Piper audio and discard unsaid sentences.

        Important:

        If finish() was already called, draining the queue may
        remove its None shutdown marker.

        We therefore restore that marker afterward so wait()
        can never hang on a worker waiting forever.
        """

        self._interrupt_event.set()

        self.speaker.interrupt()

        self._drain_pending_queue()

        if (
            self._finish_requested.is_set()
            and self._worker is not None
            and self._worker.is_alive()
        ):
            self.queue.put(
                None
            )

    def finish(
        self,
    ) -> None:
        """
        Tell the speech worker no additional sentences will be
        queued.

        This method is idempotent.
        """

        if self._finish_requested.is_set():
            return

        self._finish_requested.set()

        self.queue.put(
            None
        )

    def wait(
        self,
    ) -> None:
        """
        Wait for the Piper worker to exit.
        """

        if self._worker is not None:
            self._worker.join()

    def is_speaking(
        self,
    ) -> bool:
        """
        True only while Piper audio is actively playing.
        """

        return (
            self.speaker.is_speaking()
        )