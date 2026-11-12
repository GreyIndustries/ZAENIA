"""Scripture & ancient texts for the Research page.

Bible. Offline (on this PC): STEP Bible interlinear Hebrew (TAHOT) and Greek
(TAGNT) with transliteration, glosses and Strong's numbers, plus the ASV 1901
and WEB Classic texts, with full-text word search. Online, public domain only:
KJV, Young's Literal (NT), Bible in Basic English and Darby from bible-api.com,
and the full Hebrew verses (Masoretic text) from Sefaria.
Jewish texts (Mishnah, Talmud, Midrash, Pirkei Avot and more): Sefaria's free
API, Hebrew/Aramaic with English. Quran: Arabic (Uthmani), transliteration and
the Pickthall, Yusuf Ali and Saheeh International translations from
alquran.cloud.
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
SEFARIA = "https://www.sefaria.org/api/v3/texts/"
QURAN_EDITIONS = {"AR": "quran-uthmani", "TR": "en.transliteration", "PICKTHALL": "en.pickthall",
                  "YUSUFALI": "en.yusufali", "SAHIH": "en.sahih"}
_QURAN_REF = re.compile(r"^\s*(?:(?:surah|sura|quran|qur'an)\s+)?(?P<surah>\d{1,3})(?:\s*[:.]\s*(?P<a1>\d{1,3})(?:\s*-\s*(?P<a2>\d{1,3}))?)?\s*$", re.I)
_TAGS = re.compile(r"<[^>]+>")
_INLINE = re.compile(r"</?(?:b|i|em|strong|small|big|span|u)(?:\s[^>]*)?>")
_FOOTNOTES = re.compile(r'<sup class="footnote-marker">.*?</sup>|<i class="footnote">.*?</i>', re.S)
_CANTILLATION = re.compile("[\u0591-\u05AF\u05BD\u05C0\u05C3]")
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
    if "HEB" in translations:
        try:
            versions = _sefaria(f"{title or book}.{chapter}.{first}-{last}", ["hebrew"], get)[1]
            hebrew = next((v for v in versions if v.get("language") == "he"), {})
            lines = _segments(hebrew.get("text"))
        except Exception:
            lines = []  # the New Testament isn't on Sefaria; the column just says "not available"
        for index, verse in enumerate(verses):
            verse["texts"]["HEB"] = lines[index] if index < len(lines) else ""
    return {"reference": label, "book": title or book, "chapter": chapter, "verses": verses, "originalLanguage": language,
            "source": "bible", "rtl": ["HEB"],
            "credit": "Interlinear: STEP Bible / Tyndale House Cambridge (CC BY 4.0). ASV 1901, WEB Classic (public domain, offline). "
                      "KJV, YLT, BBE, Darby via bible-api.com (public domain). Hebrew verses: Miqra according to the Masorah via Sefaria (CC BY-SA)."}


def _clean(text: Any) -> str:
    return " ".join(_CANTILLATION.sub("", _TAGS.sub(" ", _INLINE.sub("", _FOOTNOTES.sub("", str(text or ""))))).replace("&nbsp;", " ").split())


def _segments(text: Any) -> list[str]:
    """Sefaria text is a string (one segment) or a list, sometimes nested (a whole chapter of a two-level ref)."""
    if isinstance(text, list):
        out: list[str] = []
        for item in text:
            out.extend(_segments(item) if isinstance(item, list) else [_clean(item)])
        return out
    return [_clean(text)] if text else []


def _sefaria(reference: str, versions: list[str], get: Callable) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ref = " ".join(str(reference).split())[:80].replace(" ", "_")
    if not ref or not re.fullmatch(r"[\w'.,:\-]+", ref):
        raise ValueError("Use a reference like Pirkei Avot 1, Mishnah Berakhot 1:1, Berakhot 2a or Genesis Rabbah 1:1.")
    data = get(SEFARIA + ref, {"version": versions}, timeout=20)
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError(f"Sefaria doesn't know that reference: {str(data.get('error', '')).strip() if isinstance(data, dict) else ''}".rstrip(": "))
    return data, list(data.get("versions") or [])


def jewish(reference: str, *, get: Callable = web.get_json) -> dict[str, Any]:
    """A Jewish text from Sefaria, Hebrew/Aramaic beside English, up to MAX_VERSES segments."""
    data, versions = _sefaria(reference, ["english", "hebrew"], get)
    by_lang = {v.get("language"): v for v in versions}
    english, hebrew = _segments(by_lang.get("en", {}).get("text")), _segments(by_lang.get("he", {}).get("text"))
    count = min(max(len(english), len(hebrew)), MAX_VERSES)
    if not count:
        raise ValueError("Sefaria has no text for that reference.")
    start = data.get("sections") or []
    first = int(start[-1]) if start and str(start[-1]).isdigit() and len(start) == len(data.get("sectionNames") or start) else 1
    verses = [{"verse": first + i, "texts": {"EN": english[i] if i < len(english) else "", "HE": hebrew[i] if i < len(hebrew) else ""}, "words": []}
              for i in range(count)]
    credit = "; ".join(f"{'English' if lang == 'en' else 'Hebrew/Aramaic'}: {v.get('versionTitle')} ({v.get('license') or 'see Sefaria'})"
                       for lang, v in by_lang.items() if v)
    return {"reference": data.get("ref") or reference, "heReference": data.get("heRef", ""), "book": data.get("book") or reference,
            "chapter": 0, "verses": verses, "originalLanguage": "", "source": "jewish", "rtl": ["HE"],
            "credit": f"Sefaria.org (free API). {credit}." + (" Showing the first 30 segments." if max(len(english), len(hebrew)) > MAX_VERSES else "")}


def parse_quran(reference: str) -> tuple[int, int, int | None]:
    match = _QURAN_REF.match(str(reference))
    if not match:
        raise ValueError("Use a surah and verses, like 1, 2:255 or 36:1-12.")
    surah = int(match.group("surah"))
    first = int(match.group("a1") or 1)
    last = int(match.group("a2")) if match.group("a2") else first if match.group("a1") else None
    if not 1 <= surah <= 114:
        raise ValueError("The Quran has 114 surahs.")
    if last is not None and (last < first or last - first >= MAX_VERSES):
        raise ValueError(f"Up to {MAX_VERSES} verses at a time.")
    return surah, first, last


def quran(reference: str, translations: list[str], *, get: Callable = web.get_json) -> dict[str, Any]:
    surah, first, last = parse_quran(reference)
    wanted = [short for short in QURAN_EDITIONS if short in translations] or ["AR", "PICKTHALL"]
    limit = (last - first + 1) if last else MAX_VERSES
    data = get(f"https://api.alquran.cloud/v1/surah/{surah}/editions/" + ",".join(QURAN_EDITIONS[s] for s in wanted),
               {"offset": first - 1, "limit": limit}, timeout=20)
    editions = data.get("data") if isinstance(data, dict) else None
    if not editions or not editions[0].get("ayahs"):
        raise ValueError("That surah doesn't have those verses.")
    verses: dict[int, dict[str, Any]] = {}
    for short, edition in zip(wanted, editions):
        for ayah in edition.get("ayahs") or []:
            number = int(ayah["numberInSurah"])
            verses.setdefault(number, {"verse": number, "texts": {}, "words": []})["texts"][short] = " ".join(str(ayah.get("text", "")).lstrip("\ufeff").split())
    ordered = [verses[n] for n in sorted(verses)]
    head = editions[0]
    end = ordered[-1]["verse"]
    more = "" if last or end >= int(head.get("numberOfAyahs") or end) else f" (first {MAX_VERSES} of {head.get('numberOfAyahs')} verses)"
    return {"reference": f"Surah {surah} ({head.get('englishName')}) {first}" + (f"-{end}" if end > first else "") + more,
            "book": f"Surah {head.get('englishName')}", "chapter": surah, "verses": ordered, "originalLanguage": "", "source": "quran", "rtl": ["AR"],
            "meaning": head.get("englishNameTranslation", ""),
            "credit": "alquran.cloud: Uthmani Arabic text; transliteration; Pickthall (1930) and Yusuf Ali (1934) translations; "
                      "Saheeh International (used for reading, not redistributed)."}


def search(words: str, limit: int = 40, source: str = "bible", *, get: Callable = web.get_json,
           post: Callable = web.post_json) -> list[dict[str, str]]:
    text = " ".join(str(words).split())[:200]
    if not text:
        raise ValueError("Type a word or phrase to search for.")
    limit = max(1, min(limit, 100))
    if source == "quran":
        data = get(f"https://api.alquran.cloud/v1/search/{text}/all/en.pickthall", timeout=20)
        matches = (data.get("data") or {}).get("matches") or [] if isinstance(data, dict) and data.get("code") == 200 else []
        return [{"reference": f"{m['surah']['number']}:{m['numberInSurah']}", "edition": f"Surah {m['surah'].get('englishName', '')}",
                 "text": m.get("text", "")} for m in matches[:limit]]
    if source == "jewish":
        data = post("https://www.sefaria.org/api/search-wrapper", {"query": text, "type": "text", "size": limit, "field": "naive_lemmatizer",
                                                                   "source_proj": True, "filters": [], "filter_fields": []})
        seen: set[str] = set()
        results = []
        for hit in (data.get("hits") or {}).get("hits") or []:
            found = hit.get("_source") or {}
            ref = found.get("ref")
            if not ref or ref in seen:
                continue
            seen.add(ref)
            snippet = ((hit.get("highlight") or {}).get("naive_lemmatizer") or [found.get("exact", "")])[0]
            results.append({"reference": ref, "edition": str(found.get("version") or "")[:60], "text": _clean(snippet)[:300]})
        return results
    from core.foundation.moral_code.scripture_context import Corpus
    return Corpus().search(text, limit=limit)


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

    def add(self, reference: str, note: str = "", source: str = "bible") -> dict[str, Any]:
        if source == "bible":
            parse_reference(reference)
        elif source not in ("jewish", "quran") or not reference.strip():
            raise ValueError("Unknown source.")
        record = {"id": uuid.uuid4().hex, "reference": " ".join(reference.split())[:80], "note": str(note)[:1000], "source": source,
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
    ("Quran.com", "https://quran.com/search?q={q}"),
    ("CCEL (early church writings)", "https://www.ccel.org/search?qu={q}"),
]
