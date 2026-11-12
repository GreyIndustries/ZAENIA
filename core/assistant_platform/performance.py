"""Bounded model scheduling and prompt-free, in-memory response timings."""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import threading
import time

WORK_KIND = ContextVar("zae_work_kind", default="foreground")
# Set while this thread/context already holds a model slot, so a nested model call (for example Keep's
# insight learner calling its HTTP helper) reuses that slot instead of waiting forever for itself.
HOLDING = ContextVar("zae_holding_slot", default="")
STOP = ContextVar("zae_work_stop", default=None)


class WorkCancelled(RuntimeError):
    pass


class ModelCoordinator:
    def __init__(self):
        self.condition = threading.Condition()
        self.foreground = 0
        self.foreground_waiting = 0
        self.background = 0
        self.intent = 0
        self.epoch = 0
        self.samples = deque(maxlen=256)

    @contextmanager
    def slot(self, kind=None, cancel=None):
        kind = kind or WORK_KIND.get()
        if HOLDING.get() == kind:  # same kind of work already holds a slot in this context: reuse it
            yield {"queueMs": 0, "kind": kind, "nested": True}
            return
        if kind not in {"foreground","intent","background","deferred","priority"}:
            raise ValueError("Unknown model work priority.")
        cancel = cancel or STOP.get()
        started = time.monotonic()
        with self.condition:
            epoch = self.epoch
            if kind == "foreground":
                self.foreground_waiting += 1
                self.epoch += 1  # invalidate obsolete automatic work, never priority jobs
            try:
                while ((kind == "foreground" and self.foreground >= 1) or
                       (kind == "intent" and self.intent >= 1) or
                       (kind in {"background","deferred","priority"} and (self.background >= 1 or
                        kind in {"background","deferred"} and (self.foreground or self.foreground_waiting)))):
                    if cancel is not None and cancel.is_set():
                        raise WorkCancelled("Work cancelled.")
                    if kind == "background" and epoch != self.epoch:
                        raise WorkCancelled("Automatic analysis superseded by your current request.")
                    self.condition.wait(.05)
                if cancel is not None and cancel.is_set():
                    raise WorkCancelled("Work cancelled.")
                if kind == "foreground":
                    self.foreground += 1
                elif kind == "intent":
                    self.intent += 1
                else:
                    self.background += 1
            finally:
                if kind == "foreground":
                    self.foreground_waiting -= 1
        held = HOLDING.set(kind)
        try:
            yield {"queueMs": round((time.monotonic() - started) * 1000), "kind": kind}
        finally:
            HOLDING.reset(held)
            with self.condition:
                if kind == "foreground":
                    self.foreground -= 1
                elif kind == "intent":
                    self.intent -= 1
                else:
                    self.background -= 1
                self.condition.notify_all()

    def record(self, stage, milliseconds, **fields):
        with self.condition:
            self.samples.append({"stage": stage, "ms": max(0, round(milliseconds)), **fields})

    def snapshot(self):
        with self.condition:
            samples = list(self.samples)
            durations = sorted(row["ms"] for row in samples if row["stage"] == "first_text")
            return {"foreground": self.foreground, "background": self.background,
                    "intent": self.intent,
                    "queuedForeground": self.foreground_waiting, "samples": samples[-40:],
                    "firstTextP50Ms": durations[len(durations) // 2] if durations else None,
                    "firstTextP95Ms": durations[min(len(durations)-1, int(len(durations)*.95))] if durations else None}


COORDINATOR = ModelCoordinator()


@contextmanager
def work_context(kind="background", stop=None):
    token = WORK_KIND.set(kind)
    cancel = STOP.set(stop)
    try:
        yield
    finally:
        WORK_KIND.reset(token)
        STOP.reset(cancel)


def model_call(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with COORDINATOR.slot() as timing:
            started = time.monotonic()
            try:
                return function(*args, **kwargs)
            finally:
                COORDINATOR.record("model_call", (time.monotonic()-started)*1000, **timing)
    return wrapped


def model_stream(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with COORDINATOR.slot() as timing:
            started = time.monotonic()
            first = True
            for chunk in function(*args, **kwargs):
                stop = STOP.get()
                if stop is not None and stop.is_set():
                    raise WorkCancelled("Work cancelled.")
                if first and chunk:
                    COORDINATOR.record("first_text", (time.monotonic()-started)*1000, **timing)
                    first = False
                yield chunk
            COORDINATOR.record("model_stream", (time.monotonic()-started)*1000, **timing)
    return wrapped


def background_call(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        with work_context("background"):
            return model_call(function)(*args,**kwargs)
    return wrapped


def intent_call(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        with work_context("intent"):
            return model_call(function)(*args,**kwargs)
    return wrapped


def measure(stage):
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            start=time.monotonic()
            try: return function(*args,**kwargs)
            finally: COORDINATOR.record(stage,(time.monotonic()-start)*1000)
        return wrapped
    return decorate
