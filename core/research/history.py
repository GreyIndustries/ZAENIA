"""Historical connections: how often up to three words or phrases were written about, decade by decade.

Sources:
  * "newspapers": US newspapers 1770s-1960s (Library of Congress, Chronicling America)
  * "books": books and documents 1700s-2020s (Internet Archive)
  * "news": world online news since 2017 (GDELT)

Rates are per million pages (or, for news, GDELT's share of all coverage), so
busy decades with more printing don't look bigger just because more was printed.
The all-pages baselines are cached in data/research/history_cache.json.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.research import web

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = PROJECT_ROOT / "data" / "research" / "history_cache.json"
LOC = "https://www.loc.gov/collections/chronicling-america/"
ARCHIVE = "https://archive.org/advancedsearch.php"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
SOURCES = {
    "newspapers": "US newspapers 1770s-1960s (Library of Congress)",
    "books": "Books & documents 1700s-2020s (Internet Archive)",
    "news": "World online news since 2017 (GDELT)",
}
_LOCK = threading.Lock()
_GDELT_LAST = [0.0]


def terms_from(text: str) -> list[str]:
    terms = [" ".join(part.split())[:60] for part in str(text).split(",") if part.strip()]
    if not terms:
        raise ValueError("Type up to three words or phrases, separated by commas.")
    return terms[:3]


def _cache() -> dict[str, Any]:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember(key: str, value: Any) -> None:
    with _LOCK:
        data = _cache()
        data[key] = value
        try:
            from core.foundation.security.io import atomic_write
            atomic_write(CACHE_FILE, json.dumps(data).encode("utf-8"))
        except Exception:
            pass


LANGUAGES = ("english", "spanish", "german", "french", "italian", "norwegian", "polish")


def _loc_decades(term: str | None, get: Callable, language: str = "") -> dict[str, int]:
    params = {"fo": "json", "c": 1, "at": "facets"}
    if language:
        params["fa"] = f"language:{language}"
    if term:
        params["q"] = f'"{term}"'
    data = get(LOC, params, timeout=60)
    counts: dict[str, int] = {}
    for facet in data.get("facets") or []:
        if facet.get("type") == "dates":
            for item in facet.get("filters") or []:
                start = str(item.get("title", ""))[:4]
                if start.isdigit():
                    counts[start + "s"] = int(item.get("count") or 0)
    return counts


def _archive_decades(term: str | None, get: Callable) -> dict[str, int]:
    def one(start: int) -> tuple[str, int]:
        query = f"mediatype:texts AND year:[{start} TO {start + 9}]" + (f' AND "{term}"' if term else "")
        data = get(ARCHIVE, {"q": query, "fl[]": ["identifier"], "rows": 0, "output": "json"}, timeout=30)
        return f"{start}s", int((data.get("response") or {}).get("numFound") or 0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(one, range(1700, 2030, 10)))


def _gdelt_get(get: Callable, params: dict[str, Any]) -> Any:
    """GDELT allows about one request every five seconds."""
    for attempt in range(3):
        wait = 5.5 - (time.monotonic() - _GDELT_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _GDELT_LAST[0] = time.monotonic()
        try:
            return get(GDELT, params, timeout=40)
        except Exception as error:
            if "429" not in str(error) or attempt == 2:
                raise
    return {}


def _gdelt_years(term: str, get: Callable) -> dict[str, float]:
    end = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    data = _gdelt_get(get, {"query": f'"{term}"' if " " in term else term, "mode": "timelinevol", "format": "json",
                            "startdatetime": "20170101000000", "enddatetime": end, "timelinesmooth": 0})
    years: dict[str, list[float]] = {}
    for point in ((data.get("timeline") or [{}])[0].get("data") or []):
        years.setdefault(str(point.get("date", ""))[:4], []).append(float(point.get("value") or 0))
    return {year: round(sum(values) / len(values), 4) for year, values in sorted(years.items()) if year.isdigit() and values}


def track(text: str, source: str = "newspapers", get: Callable = web.get_json, language: str = "") -> dict[str, Any]:
    """A timeline per term: [{period, count, rate}]."""
    terms = terms_from(text)
    if source not in SOURCES:
        raise ValueError("Pick newspapers, books or news.")
    series = []
    if source == "news":
        for term in terms:
            years = _gdelt_years(term, get)
            series.append({"term": term, "points": [{"period": year, "count": None, "rate": value} for year, value in years.items()]})
        return {"source": source, "label": SOURCES[source], "unit": "% of all world news coverage", "series": series}
    language = language if source == "newspapers" and language in LANGUAGES else ""
    counter = (lambda term, fetch: _loc_decades(term, fetch, language)) if source == "newspapers" else _archive_decades
    key = f"baseline:{source}" + (f":{language}" if language else "")
    cached = _cache().get(key)
    baseline = cached or counter(None, get)
    if not cached and baseline:
        _remember(key, baseline)
    with ThreadPoolExecutor(max_workers=3) as pool:
        counts = list(pool.map(lambda term: counter(term, get), terms))
    for term, found in zip(terms, counts):
        points = [{"period": period, "count": found.get(period, 0),
                   "rate": round(found.get(period, 0) * 1_000_000 / total, 2) if total else 0.0}
                  for period, total in sorted(baseline.items())]
        series.append({"term": term, "points": points})
    return {"source": source, "label": SOURCES[source], "unit": "per million pages (relative)", "series": series}


def samples(term: str, source: str, period: str, get: Callable = web.get_json, language: str = "") -> list[dict[str, str]]:
    """What was written then: up to 8 rows of {when, what, where, url}."""
    term = " ".join(str(term).split())[:60]
    start = int(str(period)[:4])
    if source == "newspapers":
        params = {"q": f'"{term}"', "dates": f"{start}/{start + 9}", "fo": "json", "c": 8}
        if language in LANGUAGES:
            params["fa"] = f"language:{language}"
        data = get(LOC, params, timeout=60)
        rows = []
        for item in data.get("results") or []:
            where = ", ".join(str(x).title() for x in (item.get("location_city") or [])[:1] + (item.get("location_state") or [])[:1])
            text = " ".join(item.get("description") or []) if isinstance(item.get("description"), list) else str(item.get("description") or "")
            rows.append({"when": str(item.get("date", ""))[:10], "what": f"{item.get('title', '')}: {web.snippet(text, term, 160)}".strip(": "),
                         "where": where, "url": str(item.get("url") or item.get("id") or "")})
        return rows
    if source == "books":
        data = get(ARCHIVE, {"q": f'"{term}" AND mediatype:texts AND year:[{start} TO {start + 9}]',
                             "fl[]": ["identifier", "title", "year", "publisher", "creator"], "rows": 8, "output": "json"}, timeout=30)
        return [{"when": str(doc.get("year", "")), "what": str(doc.get("title", ""))[:200],
                 "where": str(doc.get("publisher") or doc.get("creator") or "")[:80],
                 "url": f"https://archive.org/details/{doc.get('identifier', '')}"}
                for doc in (data.get("response") or {}).get("docs") or []]
    data = _gdelt_get(get, {"query": f'"{term}"' if " " in term else term, "mode": "artlist", "format": "json", "maxrecords": 8,
                            "sort": "hybridrel", "startdatetime": f"{start}0101000000", "enddatetime": f"{start}1231235959"})
    return [{"when": str(article.get("seendate", ""))[:8], "what": str(article.get("title", ""))[:200],
             "where": f"{article.get('domain', '')} ({article.get('sourcecountry', '')})", "url": str(article.get("url", ""))}
            for article in data.get("articles") or []]


def world_news(keyword: str, days: int = 7, get: Callable = web.get_json, english: bool = True) -> list[dict[str, str]]:
    """News reader: articles from around the world that mention a keyword (GDELT), newest first."""
    keyword = " ".join(str(keyword).split())[:80]
    if not keyword:
        raise ValueError("Type a keyword.")
    term = f'"{keyword}"' if " " in keyword else keyword
    data = _gdelt_get(get, {"query": f"{term} sourcelang:english" if english else term, "mode": "artlist", "format": "json",
                            "maxrecords": 50, "sort": "datedesc", "timespan": f"{max(1, min(int(days), 90))}d"})
    return [{"title": str(article.get("title", ""))[:300], "link": str(article.get("url", "")),
             "source": str(article.get("domain", "")), "country": str(article.get("sourcecountry", "")),
             "published": str(article.get("seendate", ""))}
            for article in data.get("articles") or []]
