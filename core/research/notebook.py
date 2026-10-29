"""Research notebook: topics, the sources gathered for each, and Grey's own notes.

Each topic's notes ARE a note in the Notes tab (one shared set of notes for
Notes, the Research notebook and Workbench): the topic keeps the note's id,
and reading or writing the topic's notes reads or writes that note. Older
topics get their note made the first time they're opened. Deleting a topic
keeps its note. Topics and sources are kept on this PC in
data/research/notebook.json. Source text is an excerpt kept
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
COLUMNS = ("supports", "contradicts", "open")
MAX_CLAIMS = 80
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Notebook:
    def __init__(self, path: Path = NOTEBOOK_FILE, store: Any = None):
        self.path = Path(path)
        self._store = store

    @property
    def notes(self):
        from core.assistant_platform.notes import Notes
        if self._store is None:
            from core.assistant_platform.service import platform
            self._store = platform().store
        return Notes(self._store)

    def _note_id(self, data: dict[str, Any], topic: dict[str, Any]) -> str:
        """The topic's shared note, made from its old notes text the first time (caller holds the lock and saves)."""
        note_id = topic.get("noteId")
        if note_id:
            try:
                self.notes.get(note_id)
                return note_id
            except ValueError:
                pass
        note = self.notes.create(f"Research: {topic['name']}"[:160], topic.get("notes", ""))
        topic["noteId"] = note["id"]
        return note["id"]

    def _notes_text(self, topic: dict[str, Any]) -> str:
        try:
            return self.notes.get(topic["noteId"])["body"] if topic.get("noteId") else topic.get("notes", "")
        except ValueError:
            return topic.get("notes", "")

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
        return [{"id": t["id"], "name": t["name"], "sources": len(t.get("sources", [])), "updatedAt": t.get("updatedAt"), "noteId": t.get("noteId")}
                for t in sorted(data["topics"], key=lambda t: t.get("updatedAt", ""), reverse=True)]

    def get(self, topic_id: str) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            raw = self._topic(data, topic_id)
            if not raw.get("noteId"):
                self._note_id(data, raw)
                self._save(data)
        topic = dict(raw)
        topic["notes"] = self._notes_text(topic)
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
            self._note_id(data, topic)
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
            note_id = self._note_id(data, topic)
            topic["notes"], topic["updatedAt"] = "", _now()
            self._save(data)
        self.notes.set_body(note_id, str(notes)[:30_000])
        return {"ok": True, "updatedAt": topic["updatedAt"], "noteId": note_id}

    def link_note(self, note_id: str) -> dict[str, Any]:
        """Make an existing note (from Notes or Workbench) a research topic, sharing the same text."""
        note = self.notes.get(note_id)
        with _LOCK:
            data = self._load()
            existing = next((t for t in data["topics"] if t.get("noteId") == note_id), None)
            if existing is None:
                if len(data["topics"]) >= MAX_TOPICS:
                    raise ValueError("The notebook is full; delete an old topic first.")
                existing = {"id": uuid.uuid4().hex, "name": note["title"].removeprefix("Research: ")[:120], "notes": "", "sources": [],
                            "noteId": note_id, "createdAt": _now(), "updatedAt": _now()}
                data["topics"].append(existing)
                self._save(data)
        return self.get(existing["id"])

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

    def raw_topics(self) -> list[dict[str, Any]]:
        """Topics with their sources' titles (no text), for searching the notebook."""
        return [{"id": t["id"], "name": t["name"], "sources": [{k: v for k, v in s.items() if k != "text"} for s in t.get("sources", [])]}
                for t in self._load()["topics"]]

    def source(self, topic_id: str, source_id: str) -> dict[str, Any]:
        """One saved source with its kept text, for the Reader."""
        topic = self._topic(self._load(), topic_id)
        for source in topic.get("sources", []):
            if source["id"] == source_id:
                return dict(source) | {"topicId": topic_id, "topicName": topic["name"]}
        raise KeyError("That source no longer exists.")

    # Evidence board: the question a topic is trying to answer, and claims Grey sorts into columns.
    def set_question(self, topic_id: str, question: str) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            topic = self._topic(data, topic_id)
            topic["question"], topic["updatedAt"] = " ".join(str(question).split())[:300], _now()
            self._save(data)
        return self.get(topic_id)

    def add_claim(self, topic_id: str, text: str, column: str = "open", source: str = "") -> dict[str, Any]:
        text = " ".join(str(text).split())[:500]
        if not text:
            raise ValueError("Write the claim first.")
        with _LOCK:
            data = self._load()
            topic = self._topic(data, topic_id)
            claims = topic.setdefault("claims", [])
            if len(claims) >= MAX_CLAIMS:
                raise ValueError("This board has the most claims it can hold.")
            claims.append({"id": uuid.uuid4().hex, "text": text, "column": column if column in COLUMNS else "open",
                           "source": " ".join(str(source).split())[:200], "addedAt": _now()})
            topic["updatedAt"] = _now()
            self._save(data)
        return self.get(topic_id)

    def update_claim(self, topic_id: str, claim_id: str, *, column: str | None = None, text: str | None = None) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            topic = self._topic(data, topic_id)
            claim = next((c for c in topic.get("claims", []) if c["id"] == claim_id), None)
            if claim is None:
                raise KeyError("That claim no longer exists.")
            if column is not None:
                if column not in COLUMNS:
                    raise ValueError("Unknown column.")
                claim["column"] = column
            if text is not None and " ".join(text.split()):
                claim["text"] = " ".join(text.split())[:500]
            topic["updatedAt"] = _now()
            self._save(data)
        return self.get(topic_id)

    def remove_claim(self, topic_id: str, claim_id: str) -> dict[str, Any]:
        with _LOCK:
            data = self._load()
            topic = self._topic(data, topic_id)
            topic["claims"] = [c for c in topic.get("claims", []) if c["id"] != claim_id]
            topic["updatedAt"] = _now()
            self._save(data)
        return self.get(topic_id)

    def material(self, topic_id: str) -> dict[str, Any]:
        """Everything ZAE analyses for a topic (full source excerpts and the notes)."""
        topic = dict(self._topic(self._load(), topic_id))
        topic["notes"] = self._notes_text(topic)
        return topic
