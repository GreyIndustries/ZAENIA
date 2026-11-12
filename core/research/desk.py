"""Research Desk: one search across the Library, world news, scripture and Grey's notebook, run side by side.

Each source answers on its own: one that fails or is slow is named in "failed" and the others still show.
Titles and snippets come from outside sources and are untrusted data, never instructions.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Callable

SOURCES = ("library", "news", "scripture", "notebook")
PER_SOURCE = 6


def _library(query: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    from core.research import library as books
    found = books.search(query)
    items = [{"kind": "library", "title": b.get("title", ""), "meta": " · ".join(str(x) for x in (b.get("author"), b.get("year"), b.get("source")) if x),
              "url": b.get("readUrl") or b.get("url", ""), "page": b.get("url", ""), "readable": bool(b.get("readUrl")), "access": b.get("access", "")}
             for b in found.get("results", [])[:PER_SOURCE]]
    try:
        overview = books.overview(query)
    except Exception:
        overview = None
    return items, overview


def _news(query: str) -> list[dict[str, Any]]:
    from core.research import history as timeline
    return [{"kind": "news", "title": s.get("title", ""), "meta": " · ".join(x for x in (s.get("source", ""), str(s.get("published", ""))[:10]) if x),
             "url": s.get("link", ""), "readable": bool(s.get("link"))} for s in timeline.world_news(query[:80], 30)[:PER_SOURCE]]


def _scripture(query: str) -> list[dict[str, Any]]:
    from core.research import scripture
    return [{"kind": "scripture", "title": h.get("reference", ""), "meta": h.get("edition", ""), "text": h.get("text", "")}
            for h in scripture.search(query, limit=PER_SOURCE)]


def notebook_matches(query: str, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Topics and saved sources whose names share a word (3+ letters) with the search, best overlap first."""
    words = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 3}
    if not words:
        return []
    scored = []
    for topic in topics:
        for source in [None, *topic.get("sources", [])]:
            title = topic["name"] if source is None else source.get("title", "")
            hits = len(words & set(re.findall(r"[a-z0-9]+", title.lower())))
            if hits:
                scored.append((hits, source is None, {
                    "kind": "notebook", "title": title, "meta": "Topic" if source is None else f"In {topic['name']}",
                    "topicId": topic["id"], "sourceId": None if source is None else source.get("id"), "url": "" if source is None else source.get("url", ""),
                    "readable": source is not None}))
    scored.sort(key=lambda row: (-row[0], not row[1]))
    return [row[2] for row in scored[:PER_SOURCE]]


def _notebook(query: str) -> list[dict[str, Any]]:
    from core.research.notebook import Notebook
    return notebook_matches(query, Notebook().raw_topics())


def search(query: str, sources: tuple[str, ...] = SOURCES, *, finders: dict[str, Callable[[str], Any]] | None = None,
           timeout: float = 45) -> dict[str, Any]:
    query = " ".join(str(query).split())[:200]
    if not query:
        raise ValueError("Type something to research.")
    finders = finders or {"library": _library, "news": _news, "scripture": _scripture, "notebook": _notebook}
    chosen = [name for name in SOURCES if name in sources and name in finders]
    results: dict[str, list[dict[str, Any]]] = {}
    failed: list[str] = []
    overview = None
    pool = ThreadPoolExecutor(max_workers=len(chosen) or 1)
    jobs = {pool.submit(finders[name], query): name for name in chosen}
    done, _late = wait(jobs, timeout=timeout)
    pool.shutdown(wait=False, cancel_futures=True)
    for job, name in jobs.items():
        if job not in done or job.exception() is not None:
            failed.append(name)
            continue
        value = job.result()
        if name == "library" and isinstance(value, tuple):
            value, overview = value
        results[name] = list(value or [])
    items = [item for name in chosen for item in results.get(name, [])]
    return {"query": query, "results": items, "counts": {name: len(results.get(name, [])) for name in chosen},
            "failed": sorted(failed, key=SOURCES.index), "overview": overview}

