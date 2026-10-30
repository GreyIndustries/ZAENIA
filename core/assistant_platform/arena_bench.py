"""Arena "Benchmark lab" (Grey's pick C, 2026-10-30): your own test questions, run on every chosen model and graded.

Each question has what a good answer should mention, as comma-separated phrases. An answer that mentions all of
them scores 1, some of them ½, none 0. Runs go one model at a time in the background (the graphics card holds one
model at a time), and the last run's grid is kept in data/arena_bench.json.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.assistant_platform.arena import PROJECT_ROOT, ask_model

BENCH_FILE = PROJECT_ROOT / "data" / "arena_bench.json"
MAX_QUESTIONS = 30
_LOCK = threading.Lock()


def grade(answer: str, expect: str) -> float:
    wanted = [p.strip().lower() for p in expect.split(",") if p.strip()]
    if not wanted:
        return 0.0
    text = " ".join(re.sub(r"[^\w%.\-–/ ]", " ", answer.lower()).split())
    hits = sum(1 for phrase in wanted if " ".join(re.sub(r"[^\w%.\-–/ ]", " ", phrase).split()) in text)
    return 1.0 if hits == len(wanted) else 0.5 if hits else 0.0


class Bench:
    def __init__(self, path: Path = BENCH_FILE, ask: Callable[[str, str], dict[str, Any]] = ask_model):
        self.path, self.ask = Path(path), ask
        self.running: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("questions"), list):
                return data
        except (OSError, ValueError):
            pass
        return {"questions": [], "run": None}

    def _save(self, data: dict[str, Any]) -> None:
        from core.foundation.security.io import atomic_write
        atomic_write(self.path, json.dumps(data, indent=1).encode("utf-8"))

    def view(self) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
        return {**data, "running": self.running}

    def add(self, question: str, expect: str) -> dict[str, Any]:
        question, expect = " ".join(question.split())[:600], " ".join(expect.split())[:300]
        if len(question) < 3 or not expect:
            raise ValueError("Write the question and what a good answer mentions.")
        with _LOCK:
            data = self._load()
            if len(data["questions"]) >= MAX_QUESTIONS:
                raise ValueError(f"The test set holds {MAX_QUESTIONS} questions. Remove one first.")
            data["questions"].append({"id": uuid.uuid4().hex, "question": question, "expect": expect})
            self._save(data)
        return self.view()

    def remove(self, question_id: str) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            data["questions"] = [q for q in data["questions"] if q["id"] != question_id]
            self._save(data)
        return self.view()

    def start(self, models: list[str], *, wait: bool = False) -> dict[str, Any]:
        models = [m for m in dict.fromkeys(str(m)[:80] for m in models) if m][:6]
        with _LOCK:
            questions = self._load()["questions"]
            if self.running:
                raise ValueError("A run is already going.")
            if not questions or not models:
                raise ValueError("Add a test question and pick at least one model.")
            self.running = {"done": 0, "total": len(questions) * len(models), "models": models}

        def work():
            started = datetime.now(timezone.utc)
            cells: dict[str, dict[str, float]] = {q["id"]: {} for q in questions}
            seconds: dict[str, float] = {}
            try:
                for model in models:
                    for q in questions:
                        try:
                            reply = self.ask(model, q["question"])
                            cells[q["id"]][model] = grade(reply.get("answer", ""), q["expect"])
                            seconds[model] = seconds.get(model, 0.0) + float(reply.get("seconds") or 0)
                        except Exception:
                            cells[q["id"]][model] = 0.0
                        self.running["done"] += 1
            finally:
                run = {"at": started.isoformat(timespec="seconds"), "models": models, "cells": cells,
                       "totals": {m: sum(cells[q["id"]].get(m, 0) for q in questions) for m in models},
                       "seconds": {m: round(s, 1) for m, s in seconds.items()}, "questions": len(questions)}
                with _LOCK:
                    data = self._load()
                    data["run"] = run
                    self._save(data)
                    self.running = None

        if wait:
            work()
        else:
            threading.Thread(target=work, name="zaenia-arena-bench", daemon=True).start()
        return self.view()


_instance: Bench | None = None


def bench() -> Bench:
    global _instance
    if _instance is None:
        _instance = Bench()
    return _instance
