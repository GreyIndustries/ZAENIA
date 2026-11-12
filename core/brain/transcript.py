"""The live transcript: what ZAE says, in the order the conductor decides (Grey, 2026-11-03).

Only Talk speaks. The other brains (Seek reading a file, Study digging deeper) think and post findings; the lines that
reach Grey, in words, all go through this one queue so two things are never said at once or out of order.

Each line has a stage. Stages only move forward: once a later stage has been said, an earlier one that arrives late is
dropped (a "first impression" that finishes after the summary would only be noise). Within a stage the first line posted
wins. One line is "in flight" at a time: `lines()` hands out the next only after the consumer asks for it again.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Iterator

STAGES = ("start", "plan", "impression", "progress", "summary", "answer")
REPEATABLE = frozenset({"progress", "answer"})   # a long read can report more than once
STAGE_ORDER = {name: index for index, name in enumerate(STAGES)}


@dataclass
class Line:
    stage: str
    text: str
    source: str = "talk"          # who wrote the words; the conductor only lets Talk's through
    seq: int = 0
    meta: dict = field(default_factory=dict)


class Transcript:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._pending: list[Line] = []
        self._said_stage = -1          # the highest stage already handed out
        self._closed = False
        self._seq = 0
        self.dropped: list[Line] = []

    def post(self, stage: str, text: str, *, source: str = "talk", **meta) -> bool:
        """Offer a line. Returns False when it can't be said: not Talk's words, empty, or its stage has passed."""
        text = " ".join(str(text or "").split())
        if stage not in STAGE_ORDER or not text:
            return False
        with self._cond:
            line = Line(stage, text, source, self._seq, meta)
            self._seq += 1
            if source != "talk" or self._closed or STAGE_ORDER[stage] < self._said_stage or (
                    STAGE_ORDER[stage] == self._said_stage and stage not in REPEATABLE):
                self.dropped.append(line)
                return False
            if any(item.stage == stage for item in self._pending) and stage not in REPEATABLE:
                self.dropped.append(line)      # first line of a stage wins
                return False
            self._pending.append(line)
            self._cond.notify_all()
            return True

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def drain(self) -> list[Line]:
        """The lines ready now, in order, without waiting (for one thread that both posts and says them)."""
        with self._cond:
            ready = sorted(self._pending, key=lambda item: (STAGE_ORDER[item.stage], item.seq))
            self._pending = []
            if ready:
                self._said_stage = max(self._said_stage, STAGE_ORDER[ready[-1].stage])
            return ready

    def lines(self, *, wait: float = 0.2) -> Iterator[Line]:
        """Hand out lines in stage order, one at a time, until closed and empty."""
        while True:
            with self._cond:
                while not self._pending and not self._closed:
                    self._cond.wait(wait)
                if not self._pending:
                    return
                self._pending.sort(key=lambda item: (STAGE_ORDER[item.stage], item.seq))
                line = self._pending.pop(0)
                self._said_stage = max(self._said_stage, STAGE_ORDER[line.stage])
                # Anything earlier that is still waiting has been overtaken.
                overtaken = [item for item in self._pending if STAGE_ORDER[item.stage] < self._said_stage]
                self.dropped.extend(overtaken)
                self._pending = [item for item in self._pending if item not in overtaken]
            yield line
