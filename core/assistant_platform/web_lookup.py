"""Short internet look-ups so ZAE knows what she's looking at on screen.

Only a few search words ever leave the PC (a game's name, a named item or
error code), never a screenshot, the window text or anything personal. The
answers come from Wikipedia's page summaries and DuckDuckGo's instant answers,
both free and keyless, and are cached in data/web_cache/lookups.json for a
week. Look-ups are rate-limited, skipped for anything that looks private
(e-mail addresses, long numbers, paths, URLs), and are reference only: text
from the web never instructs ZAE.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = PROJECT_ROOT / "data" / "web_cache" / "lookups.json"
CACHE_SECONDS = 7 * 24 * 3600
MIN_GAP_SECONDS = 20.0
MAX_CACHE = 400
USER_AGENT = "ZAENIA/1.0 (personal assistant; local; screen reference look-ups)"

_PRIVATE = re.compile(r"@|https?://|www\.|[\\/]|\d{5,}|\b(?:password|passcode|token|ssn|account|bank|card)\b", re.I)
_LOCK = threading.Lock()


def safe_term(term: str) -> str | None:
    """The cleaned search words, or None when they shouldn't leave the PC."""
    if _PRIVATE.search(str(term)):
        return None
    clean = " ".join(re.sub(r"[^\w\s:'&+.-]", " ", str(term)).split())[:80]
    if len(clean) < 2 or len(clean.split()) > 8 or _PRIVATE.search(clean):
        return None
    return clean


def _get_json(url: str) -> Any:
    import requests
    reply = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=8)
    reply.raise_for_status()
    return reply.json()


def _wikipedia(term: str, fetch: Callable[[str], Any]) -> dict[str, str] | None:
    found = fetch("https://en.wikipedia.org/w/api.php?action=opensearch&limit=1&namespace=0&format=json&search=" + quote(term))
    titles = found[1] if isinstance(found, list) and len(found) > 1 else []
    if not titles:
        return None
    page = fetch("https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(str(titles[0]).replace(" ", "_")))
    extract = " ".join(str(page.get("extract") or "").split())
    if not extract or page.get("type") == "disambiguation":
        return None
    return {"title": str(page.get("title") or titles[0]), "summary": extract[:600],
            "source": "Wikipedia", "url": str(((page.get("content_urls") or {}).get("desktop") or {}).get("page") or "")}


def _duckduckgo(term: str, fetch: Callable[[str], Any]) -> dict[str, str] | None:
    data = fetch("https://api.duckduckgo.com/?no_html=1&skip_disambig=1&format=json&q=" + quote(term))
    text = " ".join(str(data.get("AbstractText") or data.get("Answer") or "").split())
    if not text:
        return None
    return {"title": str(data.get("Heading") or term), "summary": text[:600],
            "source": str(data.get("AbstractSource") or "DuckDuckGo"), "url": str(data.get("AbstractURL") or "")}


class WebLookup:
    def __init__(self, *, fetch: Callable[[str], Any] = _get_json, cache_file: Path = CACHE_FILE,
                 clock: Callable[[], float] = time.time) -> None:
        self.fetch, self.cache_file, self.clock = fetch, Path(cache_file), clock
        self.last_request = -1e9

    def _cache(self) -> dict[str, Any]:
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def lookup(self, term: str) -> dict[str, str] | None:
        """A short summary of `term` from the web, or None (private, rate-limited, offline or not found)."""
        clean = safe_term(term)
        if clean is None:
            return None
        key = clean.casefold()
        with _LOCK:
            cache = self._cache()
            hit = cache.get(key)
            if hit and self.clock() - float(hit.get("at", 0)) < CACHE_SECONDS:
                return hit.get("result")
            if self.clock() - self.last_request < MIN_GAP_SECONDS:
                return None
            self.last_request = self.clock()
        result = None
        for source in (_wikipedia, _duckduckgo):
            try:
                result = source(clean, self.fetch)
            except Exception:
                result = None
            if result:
                break
        with _LOCK:
            cache = self._cache()
            cache[key] = {"at": self.clock(), "result": result}
            if len(cache) > MAX_CACHE:
                for old in sorted(cache, key=lambda name: cache[name].get("at", 0))[: len(cache) - MAX_CACHE]:
                    cache.pop(old, None)
            try:
                from core.foundation.security.io import atomic_write
                atomic_write(self.cache_file, json.dumps(cache).encode("utf-8"))
            except Exception:
                pass
        return result


_LOOKUP: WebLookup | None = None


def web_lookup() -> WebLookup:
    global _LOOKUP
    if _LOOKUP is None:
        _LOOKUP = WebLookup()
    return _LOOKUP


_LOOKUP_LINE = re.compile(r"\bLOOKUP:\s*(?P<term>[^\n.;]{2,80})", re.I)


def split_lookup(note: str) -> tuple[str, str | None]:
    """A vision note may end with "LOOKUP: <name>"; returns (note without it, term)."""
    match = _LOOKUP_LINE.search(note)
    if not match:
        return note.strip(), None
    term = match.group("term").strip(" \"'")
    rest = (note[:match.start()] + note[match.end():]).strip()
    return " ".join(rest.split()), (None if term.casefold() in ("none", "n/a", "nothing") else term)
