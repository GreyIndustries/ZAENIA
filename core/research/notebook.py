"""Research notebook: topics, the sources gathered for each, and Grey's own notes.

Kept on this PC in data/research/notebook.json. Source text is an excerpt kept
for ZAE's analysis (summary, comparison, claims vs evidence, timeline,
patterns, next steps); it's untrusted data, never instructions.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_FILE = PROJECT_ROOT / "data" / "research" / "notebook.json"
MAX_TOPICS = 200
MAX_SOURCES = 60
MAX_SOURCE_TEXT = 20_000
KINDS = ("book", "news", "history", "web", "pasted")
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Notebook:
    def __init__(self, path: Path = NOTEBOOK_FILE):
        self.path = Path(path)

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and isinstance(data.get("topics"), list) else {"topics": []}
        except (OSError, ValueError):
            return {"topics": []}

    def _save(self, data: dict[str, Any]) -> None:
        from core.foundation.security.io import atomic_write
        atomic_write(self.path, json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))

    def _topic(self, data: dict[str, Any], topic_id: str) -> dict[str, Any]:
        for topic in data["topics"]:
            if topic["id"] == topic_id:
                return topic
        raise KeyError("That topic no longer exists.")

    def topics(self) -> list[dict[str, Any]]:
        data = self._load()
        return [{"id": t["id"], "name": t["name"], "sources": len(t.get("sources", [])), "updatedAt": t.get("updatedAt")}
                for t in sorted(data["topics"], key=lambda t: t.get("updatedAt", ""), reverse=True)]

    def get(self, topic_id: str) -> dict[str, Any]:
        topic = dict(self._topic(self._load(), topic_id))
        topic["sources"] = [{k: v for k, v in source.items() if k != "text"} | {"chars": len(source.get("text", ""))}
                            for source in topic.get("sources", [])]
        return topic

    def create(self, name: str) -> dict[str, Any]:
        name = " ".join(str(name).split())[:120]
        if not name:
            raise ValueError("Give the topic a name.")
        with _LOCK:
            data = self._load()
            if len(data["topics"]) >= MAX_TOPICS:
                raise ValueError("The notebook is full; delete an old topic first.")
            topic = {"id": uuid.uuid4().hex, "name": name, "notes": "", "sources": [], "createdAt": _now(), "updatedAt": _now()}
            data["topics"].append(topic)
            self._save(data)
        return self.get(topic["id"])

    def delete(self, topic_id: str) -> None:
        with _LOCK:
            data = self._load()
            data["topics"] = [t for t in data["topics"] if t["id"] != topic_id]
            self._save(data)

    def set_notes(self, topic_id: str, notes: str) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            topic = self._topic(data, topic_id)
            topic["notes"], topic["updatedAt"] = str(notes)[:50_000], _now()
            self._save(data)
        return {"ok": True, "updatedAt": topic["updatedAt"]}

    def add_source(self, topic_id: str, *, title: str, kind: str = "web", url: str = "", text: str = "", meta: str = "") -> dict[str, Any]:
        title = " ".join(str(title).split())[:300]
        if not title:
            raise ValueError("A source needs a title.")
        with _LOCK:
            data = self._load()
            topic = self._topic(data, topic_id)
            if len(topic["sources"]) >= MAX_SOURCES:
                raise ValueError("This topic has the most sources it can hold.")
            topic["sources"].append({"id": uuid.uuid4().hex, "title": title, "kind": kind if kind in KINDS else "web",
                                     "url": str(url)[:1000], "meta": str(meta)[:300], "text": str(text)[:MAX_SOURCE_TEXT],
                                     "addedAt": _now()})
            topic["updatedAt"] = _now()
            self._save(data)
        return self.get(topic_id)

    def remove_source(self, topic_id: str, source_id: str) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            topic = self._topic(data, topic_id)
            topic["sources"] = [s for s in topic["sources"] if s["id"] != source_id]
            topic["updatedAt"] = _now()
            self._save(data)
        return self.get(topic_id)

    def material(self, topic_id: str) -> dict[str, Any]:
        """Everything ZAE analyses for a topic (full source excerpts and the notes)."""
        return dict(self._topic(self._load(), topic_id))
