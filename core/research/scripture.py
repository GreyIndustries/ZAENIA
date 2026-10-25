"""Scripture & ancient texts for the Research page.

Offline (on this PC): STEP Bible interlinear Hebrew (TAHOT) and Greek (TAGNT)
with transliteration, glosses and Strong's numbers, plus the ASV 1901 and
WEB Classic texts, with full-text word search. Online, public domain only:
KJV, Young's Literal (NT), Bible in Basic English and Darby from bible-api.com.
Bookmarks ("My marks") are kept in data/scripture/marks.json. Explanations
come from ZAE's own brain (core.research.analyze).
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.research import web

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARKS_FILE = PROJECT_ROOT / "data" / "scripture" / "marks.json"
ONLINE = {"KJV": "kjv", "YLT": "ylt", "BBE": "bbe", "DARBY": "darby"}
OFFLINE = {"WEB": "WEB-Classic", "ASV": "ASV1901"}
_REF = re.compile(r"^\s*(?P<book>[1-3]?\s*[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+){0,2})[ .]+(?P<chapter>\d{1,3})(?:[.:](?P<v1>\d{1,3})(?:\s*-\s*(?P<v2>\d{1,3}))?)?\s*$")
MAX_VERSES = 30
_LOCK = threading.Lock()


def parse_reference(text: str) -> tuple[str, int, int, int]:
    match = _REF.match(" ".join(str(text).split()))
    if not match:
        raise ValueError("Use a passage like John 3:16, John 3:16-18 or Psalm 23.")
    first = int(match.group("v1") or 1)
    last = int(match.group("v2") or (match.group("v1") or 0) or 0)
    if not match.group("v1"):
        last = first + MAX_VERSES - 1  # a whole chapter: up to 30 verses
    if last < first or last - first >= MAX_VERSES:
        raise ValueError(f"Up to {MAX_VERSES} verses at a time.")
    return match.group("book").strip(), int(match.group("chapter")), first, last


def _offline_verse(book: str, chapter: int, verse: int) -> dict[str, Any] | None:
    from core.assistant_platform.knowledge import scripture
    try:
        return scripture(f"{book} {chapter}:{verse}")
    except ValueError:
        return None


def passage(reference: str, translations: list[str], *, interlinear: bool = True,
            get: Callable = web.get_json, offline: Callable = _offline_verse) -> dict[str, Any]:
    book, chapter, first, last = parse_reference(reference)
    verses: list[dict[str, Any]] = []
    title = None
    for number in range(first, last + 1):
        found = offline(book, chapter, number)
        if found is None:
            if number == first:
                raise ValueError("That passage isn't in the Bible library on this PC. Check the book and chapter.")
            break  # past the end of the chapter
        title = title or found.get("book_name")
        texts = {short: found.get("translations", {}).get(edition, "") for short, edition in OFFLINE.items() if short in translations}
        words = [{"original": w.get("original"), "transliteration": w.get("transliteration"), "gloss": w.get("gloss"),
                  "strong": (re.findall(r"[GH]\d{3,5}[A-Za-z]?", str(w.get("lexical_and_morphology") or w.get("lexical") or "")) or [""])[0],
                  "morphology": w.get("morphology") or str(w.get("lexical_and_morphology") or "").split("=")[-1],
                  "dataset": w.get("dataset")} for w in found.get("words", [])] if interlinear else []
        verses.append({"verse": number, "texts": texts, "words": words})
    last = verses[-1]["verse"]
    label = f"{title or book} {chapter}:{first}" + (f"-{last}" if last > first else "")
    for short, code in ONLINE.items():
        if short not in translations:
            continue
        try:
            data = get(f"https://bible-api.com/{book} {chapter}:{first}-{last}", {"translation": code}, timeout=20)
            by_verse = {int(item["verse"]): " ".join(str(item.get("text", "")).split()) for item in data.get("verses") or []}
        except Exception:
            by_verse = {}
        for verse in verses:
            verse["texts"][short] = by_verse.get(verse["verse"], "")
    language = "Greek" if any(w["dataset"] == "TAGNT" for v in verses for w in v["words"]) else "Hebrew" if any(v["words"] for v in verses) else ""
    return {"reference": label, "book": title or book, "chapter": chapter, "verses": verses, "originalLanguage": language,
            "credit": "Interlinear: STEP Bible / Tyndale House Cambridge (CC BY 4.0). ASV 1901, WEB Classic (public domain, offline). "
                      "KJV, YLT, BBE, Darby via bible-api.com (public domain)."}


def search(words: str, limit: int = 40) -> list[dict[str, str]]:
    from core.foundation.moral_code.scripture_context import Corpus
    text = " ".join(str(words).split())[:200]
    if not text:
        raise ValueError("Type a word or phrase to search for.")
    return Corpus().search(text, limit=max(1, min(limit, 100)))


def passage_text(found: dict[str, Any]) -> str:
    """The passage as plain lines for her analysis: every translation, plus the original words."""
    lines = [found["reference"]]
    for verse in found["verses"]:
        for short, text in verse["texts"].items():
            if text:
                lines.append(f"v{verse['verse']} [{short}] {text}")
        if verse["words"]:
            lines.append(f"v{verse['verse']} [{found['originalLanguage']}] " + " ".join(
                f"{w['original']} ({w['transliteration']}, {w['strong']}: {w['gloss']})" for w in verse["words"]))
    return "\n".join(lines)


class Marks:
    def __init__(self, path: Path = MARKS_FILE):
        self.path = Path(path)

    def list(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def add(self, reference: str, note: str = "") -> dict[str, Any]:
        parse_reference(reference)
        record = {"id": uuid.uuid4().hex, "reference": " ".join(reference.split())[:60], "note": str(note)[:1000],
                  "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        from core.foundation.security.io import atomic_write
        with _LOCK:
            atomic_write(self.path, json.dumps((self.list() + [record])[-1000:], indent=1).encode("utf-8"))
        return record

    def delete(self, mark_id: str) -> None:
        from core.foundation.security.io import atomic_write
        with _LOCK:
            atomic_write(self.path, json.dumps([m for m in self.list() if m["id"] != mark_id], indent=1).encode("utf-8"))


ANCIENT = [
    {"title": "Apocrypha (KJV)", "query": "Apocrypha King James"},
    {"title": "Book of Enoch (R. H. Charles)", "query": "Book of Enoch Charles"},
    {"title": "Josephus: Antiquities of the Jews", "query": "Josephus Antiquities of the Jews"},
    {"title": "Josephus: The Jewish War", "query": "Josephus Wars of the Jews"},
    {"title": "The Apostolic Fathers", "query": "Apostolic Fathers Lightfoot"},
    {"title": "Eusebius: Church History", "query": "Eusebius Ecclesiastical History"},
    {"title": "Philo of Alexandria", "query": "Philo works Yonge"},
    {"title": "Dead Sea Scrolls (studies)", "query": "Dead Sea Scrolls"},
    {"title": "The Talmud (selections)", "query": "Talmud Rodkinson"},
    {"title": "Augustine: Confessions", "query": "Augustine Confessions"},
    {"title": "Epic of Gilgamesh", "query": "Epic of Gilgamesh"},
    {"title": "Egyptian Book of the Dead", "query": "Book of the Dead Budge"},
]
MORE_SITES = [
    ("BibleHub (parallel & lexicons)", "https://biblehub.com/{ref}"),
    ("Blue Letter Bible", "https://www.blueletterbible.org/search/preSearch.cfm?Criteria={q}"),
    ("STEP Bible", "https://www.stepbible.org/?q=reference={q}"),
    ("Bible Gateway", "https://www.biblegateway.com/passage/?search={q}"),
    ("Sefaria (Jewish texts)", "https://www.sefaria.org/search?q={q}"),
    ("CCEL (early church writings)", "https://www.ccel.org/search?qu={q}"),
]
