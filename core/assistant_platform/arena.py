"""Arena: the same question to two or three local models, side by side, to pick ZAE's best brain.

Each model answers with ZAE's usual system prompt, so it's a fair test of how
she'd sound. Grey votes for the best answer; votes build a leaderboard in
data/arena.json. "Use as her brain" switches the brain model through
data/ui/brain_model.json (kept out of git), and is undone the same way.
Models run one after another so the graphics card holds one at a time.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARENA_FILE = PROJECT_ROOT / "data" / "arena.json"
BRAIN_OVERRIDE = PROJECT_ROOT / "data" / "ui" / "brain_model.json"
_LOCK = threading.Lock()


def local_models() -> list[dict[str, Any]]:
    import requests
    data = requests.get("http://127.0.0.1:11434/api/tags", timeout=5).json()
    models = []
    for item in data.get("models") or []:
        details = item.get("details") or {}
        families = " ".join(details.get("families") or [details.get("family", "")])
        if "bert" in families or "embed" in item.get("name", ""):
            continue  # embedding models can't chat
        models.append({"name": item.get("name"), "size": round((item.get("size") or 0) / 2**30, 1),
                       "parameters": details.get("parameter_size", ""), "quantization": details.get("quantization_level", "")})
    return models


def ask_model(model: str, question: str) -> dict[str, Any]:
    import requests
    from core.brain.local_llm import get_brain_settings, get_system_prompt
    settings = get_brain_settings()
    started = time.monotonic()
    body = {"model": model, "stream": False, "think": False, "keep_alive": "30s",
            "options": {"temperature": 0.6, "num_ctx": settings["context_window"]},
            "messages": [{"role": "system", "content": get_system_prompt()}, {"role": "user", "content": question}]}
    reply = requests.post(settings["endpoint"], json=body, timeout=300)
    reply.raise_for_status()
    data = reply.json()
    seconds = time.monotonic() - started
    tokens = int(data.get("eval_count") or 0)
    eval_seconds = (data.get("eval_duration") or 0) / 1e9
    return {"model": model, "answer": str(data.get("message", {}).get("content", "")).strip(), "seconds": round(seconds, 1),
            "tokensPerSecond": round(tokens / eval_seconds, 1) if eval_seconds else None,
            "loadSeconds": round((data.get("load_duration") or 0) / 1e9, 1)}


class Arena:
    def __init__(self, path: Path = ARENA_FILE, override: Path = BRAIN_OVERRIDE):
        self.path, self.override = Path(path), Path(override)

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"rounds": []}
        except (OSError, ValueError):
            return {"rounds": []}

    def _save(self, data: dict[str, Any]) -> None:
        from core.foundation.security.io import atomic_write
        data["rounds"] = data["rounds"][-200:]
        atomic_write(self.path, json.dumps(data, indent=1).encode("utf-8"))

    def run(self, question: str, models: list[str], ask: Callable[[str, str], dict[str, Any]] = ask_model) -> dict[str, Any]:
        question = " ".join(str(question).split())[:1000]
        models = [m for m in dict.fromkeys(models) if m][:3]
        if not question or len(models) < 2:
            raise ValueError("Pick two or three models and ask a question.")
        answers = []
        for model in models:
            try:
                answers.append(ask(model, question))
            except Exception as error:
                answers.append({"model": model, "answer": "", "error": type(error).__name__, "seconds": None})
        round_ = {"id": uuid.uuid4().hex, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "question": question,
                  "answers": answers, "winner": None}
        with _LOCK:
            data = self._load()
            data["rounds"].append(round_)
            self._save(data)
        return round_

    def vote(self, round_id: str, model: str) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            found = next((r for r in data["rounds"] if r["id"] == round_id), None)
            if found is None or model not in [a["model"] for a in found["answers"]]:
                raise KeyError("That round or model isn't in the arena.")
            found["winner"] = model
            self._save(data)
        return self.board()

    def board(self) -> dict[str, Any]:
        stats: dict[str, dict[str, Any]] = {}
        for round_ in self._load()["rounds"]:
            for answer in round_["answers"]:
                entry = stats.setdefault(answer["model"], {"model": answer["model"], "rounds": 0, "wins": 0, "seconds": []})
                entry["rounds"] += 1
                entry["wins"] += 1 if round_.get("winner") == answer["model"] else 0
                if answer.get("seconds"):
                    entry["seconds"].append(answer["seconds"])
        board = [{"model": e["model"], "rounds": e["rounds"], "wins": e["wins"],
                  "winRate": round(e["wins"] / e["rounds"], 2) if e["rounds"] else 0,
                  "avgSeconds": round(sum(e["seconds"]) / len(e["seconds"]), 1) if e["seconds"] else None} for e in stats.values()]
        board.sort(key=lambda e: (e["winRate"], e["wins"]), reverse=True)
        return {"board": board, "rounds": self._load()["rounds"][-10:][::-1], "brain": self.brain()}

    def brain(self) -> dict[str, Any]:
        from core.brain.local_llm import get_brain_settings
        try:
            override = json.loads(self.override.read_text(encoding="utf-8")).get("model")
        except (OSError, ValueError):
            override = None
        return {"model": get_brain_settings()["model"], "override": override}

    def use_as_brain(self, model: str | None) -> dict[str, Any]:
        from core.foundation.security.io import atomic_write
        if model:
            if model not in [m["name"] for m in local_models()]:
                raise ValueError("That model isn't downloaded.")
            atomic_write(self.override, json.dumps({"model": model, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}).encode("utf-8"))
        else:
            try:
                self.override.unlink()
            except OSError:
                pass
        return self.brain()


_ARENA: Arena | None = None


def arena() -> Arena:
    global _ARENA
    if _ARENA is None:
        _ARENA = Arena()
    return _ARENA
