"""Free research sources for the web agent (Grey, 2026-11-08: "as many free research sources as possible").

Every source here is free and needs no account or key. Each one returns results in the same shape:
    {"title", "url", "snippet", "text", "source", "kind"}
where `text` is the abstract, summary or answer the source gives directly (so the agent may not need to open the page).

Sources are grouped by kind. The agent always asks the general ones and adds a group when the question is about it
(science, health, drugs, tech, news, history, books), so one research job stays at a few dozen polite requests.
Everything goes through core.research.web: public addresses only, size caps, ZAE's honest user agent. What comes back is
untrusted data, never instructions. A source that fails, is slow or rate-limits is skipped and named; the others go on.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable
from urllib.parse import quote, quote_plus

from core.research import web

Result = dict[str, str]
_TAG = re.compile(r"<[^>]+>")


def _clean(value: Any, limit: int = 4000) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", str(value or ""))).split())[:limit]


def _result(title: Any, url: Any, text: Any = "", *, source: str, kind: str, snippet: Any = "", meta: str = "") -> Result | None:
    title, url = _clean(title, 300), str(url or "").strip()
    if not title or not url.startswith(("http://", "https://")):
        return None
    body = _clean(text)
    return {"title": title, "url": url, "snippet": _clean(snippet or body, 300), "text": body, "source": source, "kind": kind, "meta": meta[:120]}


def _keep(items: list[Result | None], limit: int) -> list[Result]:
    seen, out = set(), []
    for item in items:
        if item and item["url"] not in seen:
            seen.add(item["url"])
            out.append(item)
        if len(out) >= limit:
            break
    return out


# ---- general

def wikipedia(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://en.wikipedia.org/w/api.php", {"action": "query", "format": "json", "generator": "search", "gsrsearch": query,
                                                       "gsrlimit": limit, "prop": "extracts|info", "exintro": 1, "explaintext": 1,
                                                       "exchars": 1800, "inprop": "url"})
    pages = sorted((data.get("query", {}).get("pages", {}) or {}).values(), key=lambda page: page.get("index", 99))
    return _keep([_result(p.get("title"), p.get("fullurl"), p.get("extract"), source="Wikipedia", kind="reference") for p in pages], limit)


def duckduckgo_answer(query: str, limit: int = 1, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://api.duckduckgo.com/", {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
    if not data.get("AbstractText"):
        return []
    return _keep([_result(data.get("Heading") or query, data.get("AbstractURL"), data.get("AbstractText"), source=f"DuckDuckGo ({data.get('AbstractSource') or 'answer'})", kind="reference")], limit)


# ---- science and scholarship

def openalex(query: str, limit: int = 4, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://api.openalex.org/works", {"search": query, "per-page": limit, "select": "id,doi,display_name,publication_year,abstract_inverted_index,primary_location,cited_by_count"})
    out = []
    for work in data.get("results", []):
        index = work.get("abstract_inverted_index") or {}
        words = sorted(((position, word) for word, positions in index.items() for position in positions))
        landing = (work.get("primary_location") or {}).get("landing_page_url")
        out.append(_result(work.get("display_name"), work.get("doi") or landing or work.get("id"), " ".join(word for _, word in words),
                           source="OpenAlex", kind="science", meta=f"{work.get('publication_year') or ''} · cited {work.get('cited_by_count') or 0}"))
    return _keep(out, limit)


def arxiv(query: str, limit: int = 3, *, get_text: Callable = web.get_text) -> list[Result]:
    from core.research.evidence import terms
    words = [word for word in dict.fromkeys(terms(query)) if len(word) > 2][:4] or [query]
    # Every key word must appear (arXiv's plain "all:" search matches any one of them and returns unrelated physics papers).
    expression = "+AND+".join(f"all:{quote_plus(word)}" for word in words)
    feed = get_text(f"https://export.arxiv.org/api/query?search_query={expression}&start=0&max_results={limit}&sortBy=relevance")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in ET.fromstring(feed).findall("a:entry", ns):
        summary = entry.find("a:summary", ns)
        out.append(_result(entry.findtext("a:title", "", ns), entry.findtext("a:id", "", ns), " ".join(summary.itertext()) if summary is not None else "",
                           source="arXiv", kind="science", meta=(entry.findtext("a:published", "", ns) or "")[:10]))
    return _keep(out, limit)


def crossref(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://api.crossref.org/works", {"query": query, "rows": limit, "select": "DOI,title,abstract,issued,container-title"})
    out = []
    for item in data.get("message", {}).get("items", []):
        year = ((item.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append(_result((item.get("title") or [""])[0], f"https://doi.org/{item.get('DOI')}" if item.get("DOI") else "", item.get("abstract", ""),
                           source="Crossref", kind="science", meta=f"{year or ''} · {(item.get('container-title') or [''])[0]}"))
    return _keep(out, limit)


def semantic_scholar(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://api.semanticscholar.org/graph/v1/paper/search", {"query": query, "limit": limit, "fields": "title,abstract,url,year,citationCount,tldr"})
    out = []
    for paper in data.get("data", []) or []:
        summary = paper.get("abstract") or ((paper.get("tldr") or {}).get("text"))
        out.append(_result(paper.get("title"), paper.get("url"), summary, source="Semantic Scholar", kind="science",
                           meta=f"{paper.get('year') or ''} · cited {paper.get('citationCount') or 0}"))
    return _keep(out, limit)


def doaj(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get(f"https://doaj.org/api/search/articles/{quote(query)}", {"pageSize": limit})
    out = []
    for item in data.get("results", []):
        bib = item.get("bibjson", {})
        link = next((l.get("url") for l in bib.get("link", []) if l.get("url")), "")
        out.append(_result(bib.get("title"), link, bib.get("abstract"), source="DOAJ (open access)", kind="science", meta=str(bib.get("year") or "")))
    return _keep(out, limit)


def plos(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://api.plos.org/search", {"q": query, "rows": limit, "fl": "id,title_display,abstract,publication_date", "wt": "json"})
    out = []
    for doc in data.get("response", {}).get("docs", []):
        abstract = doc.get("abstract")
        out.append(_result(doc.get("title_display"), f"https://doi.org/{doc.get('id')}" if doc.get("id") else "",
                           " ".join(abstract) if isinstance(abstract, list) else abstract, source="PLOS", kind="science",
                           meta=str(doc.get("publication_date") or "")[:10]))
    return _keep(out, limit)


# ---- health and medicine

def pubmed(query: str, limit: int = 3, *, get: Callable = web.get_json, get_text: Callable = web.get_text) -> list[Result]:
    ids = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", {"db": "pubmed", "term": query, "retmax": limit, "retmode": "json", "sort": "relevance"})
    found = ids.get("esearchresult", {}).get("idlist", [])
    if not found:
        return []
    root = ET.fromstring(get_text("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id=" + ",".join(found)))
    out = []
    for article in root.iter("PubmedArticle"):
        pmid = article.findtext(".//PMID", "")
        abstract = " ".join("".join(part.itertext()) for part in article.iter("AbstractText"))
        out.append(_result("".join(article.find(".//ArticleTitle").itertext()) if article.find(".//ArticleTitle") is not None else "",
                           f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", abstract, source="PubMed", kind="health",
                           meta=article.findtext(".//PubDate/Year", "")))
    return _keep(out, limit)


def europe_pmc(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", {"query": query, "format": "json", "resultType": "core", "pageSize": limit})
    out = []
    for item in data.get("resultList", {}).get("result", []):
        url = f"https://europepmc.org/article/{item.get('source')}/{item.get('id')}" if item.get("id") else ""
        out.append(_result(item.get("title"), url, item.get("abstractText"), source="Europe PMC", kind="health", meta=str(item.get("pubYear") or "")))
    return _keep(out, limit)


def clinical_trials(query: str, limit: int = 2, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://clinicaltrials.gov/api/v2/studies", {"query.term": query, "pageSize": limit, "format": "json"})
    out = []
    for study in data.get("studies", []):
        section = study.get("protocolSection", {})
        ident = section.get("identificationModule", {})
        status = section.get("statusModule", {}).get("overallStatus", "")
        out.append(_result(ident.get("briefTitle"), f"https://clinicaltrials.gov/study/{ident.get('nctId')}" if ident.get("nctId") else "",
                           section.get("descriptionModule", {}).get("briefSummary"), source="ClinicalTrials.gov", kind="health", meta=status))
    return _keep(out, limit)


# ---- tech

def stack_exchange(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://api.stackexchange.com/2.3/search/advanced", {"q": query, "site": "stackoverflow", "order": "desc", "sort": "relevance",
                                                                     "pagesize": limit, "filter": "withbody", "answers": 1})
    return _keep([_result(item.get("title"), item.get("link"), item.get("body"), source="Stack Overflow", kind="tech",
                          meta=f"score {item.get('score', 0)}{' · answered' if item.get('is_answered') else ''}") for item in data.get("items", [])], limit)


def hacker_news(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://hn.algolia.com/api/v1/search", {"query": query, "tags": "story", "hitsPerPage": limit})
    return _keep([_result(hit.get("title"), hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}", hit.get("story_text"),
                          source="Hacker News", kind="tech", meta=f"{hit.get('points') or 0} points") for hit in data.get("hits", [])], limit)


# ---- news

def gdelt(query: str, limit: int = 4, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://api.gdeltproject.org/api/v2/doc/doc", {"query": query, "mode": "artlist", "format": "json", "maxrecords": limit, "sort": "hybridrel", "timespan": "1month"})
    return _keep([_result(item.get("title"), item.get("url"), "", source=f"GDELT ({item.get('domain', '')})", kind="news",
                          meta=str(item.get("seendate", ""))[:8]) for item in (data.get("articles") or [])], limit)


def google_news(query: str, limit: int = 4) -> list[Result]:
    from core.research.agent import news
    return _keep([_result(item["title"], item["url"], "", snippet=item.get("snippet", ""), source="Google News", kind="news",
                          meta=item.get("published", "")[:16]) for item in news(query, limit=limit)], limit)


# ---- history, books and public records

def library_of_congress(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://www.loc.gov/search/", {"q": query, "fo": "json", "c": limit}, timeout=25)
    out = []
    for item in data.get("results", [])[:limit]:
        description = item.get("description")
        out.append(_result(item.get("title"), item.get("url") or item.get("id"), " ".join(description) if isinstance(description, list) else description,
                           source="Library of Congress", kind="history", meta=str(item.get("date") or "")))
    return _keep(out, limit)


def open_library(query: str, limit: int = 3, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://openlibrary.org/search.json", {"q": query, "limit": limit, "fields": "key,title,author_name,first_publish_year,first_sentence"})
    out = []
    for doc in data.get("docs", []):
        sentence = doc.get("first_sentence")
        out.append(_result(doc.get("title"), f"https://openlibrary.org{doc.get('key')}" if doc.get("key") else "",
                           (sentence[0] if isinstance(sentence, list) and sentence else sentence) or "", source="Open Library", kind="books",
                           meta=f"{', '.join((doc.get('author_name') or [])[:2])} {doc.get('first_publish_year') or ''}".strip()))
    return _keep(out, limit)


def gutenberg(query: str, limit: int = 2, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://gutendex.com/books/", {"search": query}, timeout=25)
    out = []
    for book in data.get("results", [])[:limit]:
        summary = " ".join(book.get("summaries") or [])
        out.append(_result(book.get("title"), f"https://www.gutenberg.org/ebooks/{book.get('id')}", summary, source="Project Gutenberg", kind="books",
                           meta=", ".join(a.get("name", "") for a in (book.get("authors") or [])[:2])))
    return _keep(out, limit)


def internet_archive(query: str, limit: int = 2, *, get: Callable = web.get_json) -> list[Result]:
    data = get("https://archive.org/advancedsearch.php", {"q": f"({query}) AND mediatype:texts", "fl[]": ["identifier", "title", "description", "year"],
                                                         "rows": limit, "output": "json"}, timeout=25)
    out = []
    for doc in data.get("response", {}).get("docs", []):
        description = doc.get("description")
        out.append(_result(doc.get("title"), f"https://archive.org/details/{doc.get('identifier')}" if doc.get("identifier") else "",
                           " ".join(description) if isinstance(description, list) else description, source="Internet Archive", kind="books",
                           meta=str(doc.get("year") or "")))
    return _keep(out, limit)


def openfda(query: str, limit: int = 1, *, get: Callable = web.get_json) -> list[Result]:
    """US drug labels: what a medicine is for, warnings and interactions."""
    data = get("https://api.fda.gov/drug/label.json", {"search": query, "limit": limit})
    out = []
    for label in data.get("results", []):
        names = (label.get("openfda") or {}).get("brand_name") or (label.get("openfda") or {}).get("generic_name") or ["Drug label"]
        parts = [f"{field.replace('_', ' ').title()}: {' '.join(label[field])}" for field in ("indications_and_usage", "warnings", "drug_interactions", "dosage_and_administration") if label.get(field)]
        set_id = label.get("set_id", "")
        out.append(_result(f"{names[0]} (FDA drug label)", f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={quote_plus(names[0])}" if not set_id else
                           f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}", " ".join(parts), source="openFDA", kind="health"))
    return _keep(out, limit)


# ---- picking sources for a question

# Sources that allow only a request every few seconds without a key: asked once per job, with the first query.
RATE_LIMITED = {"gdelt", "semantic_scholar"}

SOURCES: dict[str, tuple[Callable[..., list[Result]], str]] = {
    "wikipedia": (wikipedia, "general"), "duckduckgo_answer": (duckduckgo_answer, "general"), "openalex": (openalex, "general"),
    "arxiv": (arxiv, "science"), "crossref": (crossref, "science"), "semantic_scholar": (semantic_scholar, "science"),
    "doaj": (doaj, "science"), "plos": (plos, "science"),
    "pubmed": (pubmed, "health"), "europe_pmc": (europe_pmc, "health"), "clinical_trials": (clinical_trials, "health"),
    "stack_exchange": (stack_exchange, "tech"), "hacker_news": (hacker_news, "tech"),
    "gdelt": (gdelt, "news"), "google_news": (google_news, "news"),
    "library_of_congress": (library_of_congress, "history"),
    "open_library": (open_library, "books"), "gutenberg": (gutenberg, "books"), "internet_archive": (internet_archive, "books"),
    "openfda": (openfda, "drugs"),
}

_TOPICS = {
    "science": r"stud(?:y|ies)|research|paper|scien|physic|chemi|biolog|plant|grow|hydropon|aquapon|aeropon|soil|nutrient|\bph\b|"
               r"energy|reactor|battery|solar|climate|ecolog|fish|algae|bacteria|molecul|quantum|material|engineer|evidence|experiment",
    "health": r"health|medic|disease|symptom|drug|dose|vitamin|supplement|nutrition|diet|protein|calorie|exercise|workout|muscle|"
              r"sleep|injur|pain|blood|heart|cancer|diabet|therapy|clinical|mental|anxiety|depress|weight|fitness",
    "tech": r"code|coding|python|javascript|typescript|rust|error|exception|bug|api|software|program|linux|windows|gpu|cpu|"
            r"\bai\b|model|llm|ollama|database|server|network|tauri|react|docker|git\b|compile",
    "news": r"latest|today|this week|this month|news|current|recent|announced|release|update|2026|2027",
    "history": r"histor|ancient|century|war\b|empire|archive|origin|founded|civilization|dynasty|medieval",
    "books": r"\bbooks?\b|novel|author|literature|poem|read(?:ing)? list",
    "drugs": r"drug|medicine|medication|pill|tablet|side effect|interaction|ibuprofen|acetaminophen|antibiotic|prescription",
}


def pick(question: str) -> list[str]:
    """The sources for a question: the general ones, plus each group the question is about."""
    text = str(question).lower()
    groups = {"general"} | {group for group, pattern in _TOPICS.items() if re.search(pattern, text)}
    return [name for name, (_fn, group) in SOURCES.items() if group in groups]


def search_all(queries: list[str], names: list[str], *, workers: int = 6, sources: dict[str, tuple[Callable, str]] | None = None) -> tuple[list[Result], dict[str, str]]:
    """Ask each named source each query, in parallel. Returns (results, status by source: "ok", "no results" or the error)."""
    sources = sources or SOURCES
    # Plain search words: question marks, quotes and colons break some APIs' query syntax (DOAJ, arXiv).
    queries = [cleaned for cleaned in (" ".join(re.sub(r"[?\"':()\[\]{}!]", " ", query).split()) for query in queries) if cleaned]
    jobs = [(name, query) for name in names if name in sources for query in (queries[:1] if name in RATE_LIMITED else queries)]
    results: list[Result] = []
    status: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(sources[name][0], query): name for name, query in jobs}
        for future in as_completed(futures):
            name = futures[future]
            try:
                found = future.result()
                results.extend(found)
                status[name] = "ok" if found or status.get(name) == "ok" else status.get(name, "no results")
            except Exception as error:
                status.setdefault(name, f"skipped ({type(error).__name__})")
    return results, status
