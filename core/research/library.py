"""Library: find books in Project Gutenberg, Open Library and the Internet Archive, with a Wikipedia overview.

Only books that are free and legal to read are opened here; for the rest ZAE
shows how to borrow them or where to find them.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from core.research import web

READ_HOSTS = ("www.gutenberg.org", "gutenberg.org", "archive.org", "ia800", "ia600", "ia900")
OPEN_LIBRARY_ACCESS = {"public": "Free to read", "borrowable": "Borrow free (Open Library account)",
                       "printdisabled": "Print-disabled access only"}


def _gutenberg(query: str, get: Callable) -> list[dict[str, Any]]:
    data = get("https://gutendex.com/books/", {"search": query})
    found = []
    for book in (data.get("results") or [])[:20]:
        formats = book.get("formats") or {}
        text = next((url for kind, url in formats.items() if kind.startswith("text/plain") and not url.endswith(".zip")), None)
        authors = book.get("authors") or [{}]
        found.append({"id": f"gutenberg:{book.get('id')}", "title": book.get("title", ""), "author": authors[0].get("name", ""),
                      "year": None, "source": "Project Gutenberg", "access": "Free to read",
                      "url": f"https://www.gutenberg.org/ebooks/{book.get('id')}", "readUrl": text})
    return found


def _open_library(query: str, get: Callable) -> list[dict[str, Any]]:
    data = get("https://openlibrary.org/search.json",
               {"q": query, "limit": 20, "fields": "key,title,author_name,first_publish_year,ebook_access,ia"})
    found = []
    for book in data.get("docs") or []:
        access = OPEN_LIBRARY_ACCESS.get(book.get("ebook_access"), "Catalog only: find it in a library")
        ia = (book.get("ia") or [None])[0]
        found.append({"id": f"openlibrary:{book.get('key')}", "title": book.get("title", ""),
                      "author": (book.get("author_name") or [""])[0], "year": book.get("first_publish_year"),
                      "source": "Open Library", "access": access, "url": "https://openlibrary.org" + str(book.get("key", "")),
                      "readUrl": f"https://archive.org/download/{ia}/{ia}_djvu.txt" if ia and book.get("ebook_access") == "public" else None})
    return found


def _archive(query: str, get: Callable) -> list[dict[str, Any]]:
    data = get("https://archive.org/advancedsearch.php",
               {"q": f"({query}) AND mediatype:texts AND NOT collection:inlibrary AND NOT collection:printdisabled",
                "fl[]": ["identifier", "title", "creator", "year"], "rows": 20, "output": "json"})
    found = []
    for item in (data.get("response") or {}).get("docs") or []:
        ident = item.get("identifier", "")
        creator = item.get("creator")
        found.append({"id": f"archive:{ident}", "title": item.get("title", ""),
                      "author": creator[0] if isinstance(creator, list) else (creator or ""), "year": item.get("year"),
                      "source": "Internet Archive", "access": "Free to read", "url": f"https://archive.org/details/{ident}",
                      "readUrl": f"https://archive.org/download/{ident}/{ident}_djvu.txt"})
    return found


def overview(query: str, get: Callable = web.get_json) -> dict[str, str] | None:
    """A Wikipedia summary of the subject, for the side pane."""
    found = get("https://en.wikipedia.org/w/api.php", {"action": "query", "list": "search", "srsearch": query,
                                                       "srlimit": 1, "format": "json"})
    hits = ((found or {}).get("query") or {}).get("search") or []
    if not hits:
        return None
    title = hits[0]["title"]
    page = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + title.replace(" ", "_"), None)
    extract = " ".join(str(page.get("extract") or "").split())
    return {"title": page.get("title", title), "summary": extract[:1500],
            "url": (((page.get("content_urls") or {}).get("desktop") or {}).get("page")) or ""} if extract else None


def search(query: str, get: Callable = web.get_json) -> dict[str, Any]:
    """Books from all three catalogues (free-to-read first), plus which catalogues didn't answer."""
    query = " ".join(str(query).split())[:200]
    if not query:
        raise ValueError("Type a title, author or subject.")
    results, skipped = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {name: pool.submit(fn, query, get) for name, fn in
                (("Project Gutenberg", _gutenberg), ("Open Library", _open_library), ("Internet Archive", _archive))}
        for name, job in jobs.items():
            try:
                results.extend(job.result(timeout=25))
            except Exception as error:
                skipped.append(f"{name}: {type(error).__name__}")
    order = {"Free to read": 0, "Borrow free (Open Library account)": 1, "Print-disabled access only": 2}
    results.sort(key=lambda book: order.get(book["access"], 3))
    readable = sum(1 for book in results if book.get("readUrl"))
    return {"query": query, "results": results, "readable": readable, "skipped": skipped}


def read_text(url: str, get_text: Callable[[str], str] = web.get_text, limit: int = 400_000) -> str:
    """The plain text of a free book (Gutenberg or Internet Archive only), without licence boilerplate."""
    host = re.sub(r"^https?://", "", str(url)).split("/")[0]
    if not url.startswith("https://") or not any(host == allowed or host.startswith(allowed) for allowed in READ_HOSTS):
        raise ValueError("Only free books from Project Gutenberg or the Internet Archive can be read here.")
    text = get_text(url)
    start = re.search(r"\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text, re.I)
    end = re.search(r"\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG", text, re.I)
    if start:
        text = text[start.end(): end.start() if end else None]
    return text.strip()[:limit]
