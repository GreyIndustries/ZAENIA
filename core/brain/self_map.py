"""What's inside ZAE, and what isn't (Grey, 2026-11-08).

ZAE should know her own system, especially the desktop app, without guessing. This map is generated from her source
files, never written by hand:
- the app's pages from App.tsx (the sidebar list and each page's description) and every page's sub-tabs, read from
  App.tsx and the page components it renders;
- her backend areas from the docstrings of the API route modules and the component registry.
What she does NOT have comes from self_map_planned.yaml, a short list kept honest by hand: planned, partly built, or
only an idea.

A one-line-per-page summary goes into every conversation; the full map is added when a question is about ZAE herself
("do you have…", "where is…", "which tab…"). The map is rebuilt whenever one of its source files changes. It is
reference text only: it never grants an action or a permission.
"""
from __future__ import annotations

import ast
import re
import threading
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP = PROJECT_ROOT / "desktop" / "src" / "App.tsx"
PLANNED = Path(__file__).with_name("self_map_planned.yaml")
REGISTRY = Path(__file__).with_name("component_registry.yaml")
API = PROJECT_ROOT / "core" / "api"
FULL_LIMIT = 6000       # characters of the detailed map added to a question about herself

_TAB = re.compile(r"""\{\s*id:\s*["']([\w-]+)["']\s*,\s*label:\s*(["'])(.*?)\2""")  # (id, quote, label)
_TAB_LIST = re.compile(r"""const\s+tabs\b[^=]*=\s*(\[\[.*?\]\]);""", re.S)  # const tabs: [Tab, string][] = [["week", "Week"], ...];
_PAIR = re.compile(r"""\[\s*["']([\w-]+)["']\s*,\s*(["'])(.*?)\2\s*\]""")  # (id, quote, label)
_IMPORT = re.compile(r"""(?:import\s*\{([^}]*)\}\s*from\s*["'](\.[^"']+)["']|const\s+(\w+)\s*=\s*lazy\(\s*\(\)\s*=>\s*import\(\s*["'](\.[^"']+)["']\))""")
_cache: dict[str, Any] = {"key": None, "map": None}
_lock = threading.Lock()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def _block(text: str, start: str, end: str) -> str:
    begin = text.find(start)
    if begin < 0:
        return ""
    stop = text.find(end, begin + len(start))
    return text[begin:stop if stop > 0 else len(text)]


def _component_files(app: str, root: Path) -> dict[str, Path]:
    """Component name -> source file, from App.tsx's imports (plain and lazy)."""
    found: dict[str, Path] = {}
    for names, source, lazy_name, lazy_source in _IMPORT.findall(app):
        base = root / (source or lazy_source)
        file = next((candidate for candidate in (base.with_suffix(".tsx"), base.with_suffix(".ts"), base / "index.tsx") if candidate.is_file()), None)
        if not file:
            continue
        for name in ([lazy_name] if lazy_name else [n.strip().split(" as ")[-1] for n in names.split(",")]):
            if name:
                found[name] = file
    return found


def ui_pages(app_file: Path | None = None) -> list[dict[str, Any]]:
    """The app's sidebar pages in order, each with its description and sub-tabs."""
    app_file = app_file or APP
    app = _read(app_file)
    if not app:
        return []
    nav = _block(app, "const nav = ([", "] as {")
    sections = _block(app, "const sections:", "\n};")
    body = _block(app, "function sectionBody(", "default: return null;")
    files = _component_files(app, app_file.parent)
    describe = {key: desc for key, desc in re.findall(r"""^\s*['"]?(\w+)['"]?\s*:\s*\{\s*title:.*?description:\s*["'](.*?)["']\s*\}""", sections, re.M)}
    # Each page's code in the switch: from its case label to the next case that returns something else.
    chunks: dict[str, str] = {}
    pending: list[str] = []
    for part in re.split(r"""(?=\bcase\s+["']\w+["']\s*:)""", body)[1:]:
        label_end = re.match(r"""case\s+["'](\w+)["']\s*:""", part)
        pending.append(label_end.group(1))
        if re.sub(r"//[^\n]*", "", part[label_end.end():]).strip():  # an empty case falls through to the next one
            for name in pending:
                chunks[name] = part
            pending = []
    pages = []
    for page, _quote, label in _TAB.findall(nav):
        code = chunks.get(page, "")
        tabs = [found[2] for found in _TAB.findall(code)]
        rendered = re.search(r"return\s*<(\w+)", code)
        component = rendered.group(1) if rendered else ""
        if component and component != "PageTabs" and component in files:
            source = _read(files[component])
            listed = _TAB_LIST.search(source)
            inner = [found[2] for found in (_PAIR.findall(listed.group(1)) if listed else _TAB.findall(source))]
            tabs = inner + [t for t in tabs if t not in inner]
        pages.append({"id": page, "label": label, "description": describe.get(page, ""), "tabs": list(dict.fromkeys(tabs))})
    return pages


def backend_areas(api_dir: Path = API, registry: Path = REGISTRY) -> list[dict[str, str]]:
    """What each API route group serves (its module docstring) and the registry's components."""
    areas: list[dict[str, str]] = []
    for file in sorted(api_dir.glob("*_routes.py")):
        try:
            doc = ast.get_docstring(ast.parse(_read(file))) or ""
        except SyntaxError:
            doc = ""
        line = doc.strip().split("\n\n")[0].replace("\n", " ").split(". Operations")[0].strip()
        if line:
            areas.append({"name": file.stem.removesuffix("_routes").replace("_", " "), "about": line[:220]})
    try:
        components = (yaml.safe_load(_read(registry)) or {}).get("registry", {}).get("components", {}) or {}
    except yaml.YAMLError:
        components = {}
    for item in components.values():
        if isinstance(item, dict) and item.get("name"):
            areas.append({"name": str(item["name"]), "about": str(item.get("description", ""))[:220]})
    return areas


def planned(path: Path = PLANNED) -> list[dict[str, str]]:
    try:
        items = (yaml.safe_load(_read(path)) or {}).get("items", []) or []
    except yaml.YAMLError:
        return []
    return [{key: str(item.get(key, "")) for key in ("name", "status", "what", "note", "plan")} for item in items if isinstance(item, dict) and item.get("name")]


def _sources(app_file: Path) -> list[Path]:
    root = app_file.parent
    found = [app_file, PLANNED, REGISTRY, *sorted(API.glob("*_routes.py"))]
    found += sorted(set(_component_files(_read(app_file), root).values()))
    return found


def build(app_file: Path | None = None) -> dict[str, Any]:
    """The whole map, rebuilt only when a source file changed."""
    app_file = app_file or APP
    sources = _sources(app_file)
    key = tuple((str(path), path.stat().st_mtime_ns if path.exists() else 0) for path in sources)
    with _lock:
        if _cache["key"] == key and _cache["map"] is not None:
            return _cache["map"]
    result = {"pages": ui_pages(app_file), "backend": backend_areas(), "planned": planned()}
    with _lock:
        _cache.update(key=key, map=result)
    return result


def summary(app_file: Path | None = None) -> str:
    """The short version for every conversation: one line per page with its sub-tabs."""
    app_file = app_file or APP
    pages = build(app_file)["pages"]
    if not pages:
        return ""
    lines = [f"- {page['label']} page" + (f", sub-tabs: {', '.join(page['tabs'])}" if page["tabs"] else "") for page in pages]
    return ("WHAT'S INSIDE YOU (generated from your own source files): your desktop app's pages, each with its sub-tabs:\n"
            + "\n".join(lines) +
            "\nIf a page, tab or feature isn't in what you've been told about yourself, you don't have it yet: say so plainly "
            "instead of guessing. Never invent a page, tab, button or feature.")


_ABOUT_SELF = re.compile(
    r"\b(?:do|does|can|could|will) (?:you|zae|zaenia|the app|your app)\b.{0,40}\b(?:have|has|track|show|support|handle|control|monitor|connect|run|use|access|see|watch|manage)\b"
    r"|\b(?:what else )?can you do\b"
    r"|\b(?:is|are) there (?:a|an|any)\b.{0,30}\b(?:tab|page|window|feature|button|setting|tool|way)\b"
    r"|\bwhere(?:'s| is| are| do| can| would)\b.{0,40}\b(?:tab|page|window|setting|button|feature|in (?:the|your) app)\b"
    r"|\b(?:which|what) (?:tab|page|window|section)\b"
    r"|\bwhat(?:'s| is) (?:inside|in) (?:you|your (?:app|system|code|ui))\b"
    r"|\bwhat (?:can you do|are you able to do|features|tabs|pages)\b"
    r"|\b(?:your|the) (?:app|ui|interface|system|features?|tabs?|pages?|code)\b.{0,30}\b(?:have|has|include|got|missing|lack)\b"
    r"|\b(?:have|has) (?:you|zae) got\b|\bare you able to\b|\bnot built\b|\bplanned\b",
    re.I)


def about_self(text: str) -> bool:
    """True when the question is about what ZAE has, does or where something is in her app, including a question that
    names one of her pages ("what's in Code Doctor?", "how do I use Fitness?")."""
    text = str(text or "")
    if _ABOUT_SELF.search(text):
        return True
    if not _QUESTION.search(text):
        return False
    try:
        names = {part.strip().casefold() for page in build()["pages"] for part in page["label"].split("&")}
    except Exception:
        return False
    lowered = text.casefold()
    return any(len(name) > 3 and re.search(rf"\b{re.escape(name)}\b", lowered) for name in names)


_QUESTION = re.compile(r"\b(?:what(?:'s| is| are)? (?:in|on|inside|under)|what does|where|which|how (?:do|can) i|is there|are there|tabs?|pages?)\b", re.I)


def full_text(app_file: Path | None = None, limit: int = FULL_LIMIT) -> str:
    """The detailed map for a question about herself: pages with descriptions and tabs, backend areas, and what's missing."""
    app_file = app_file or APP
    data = build(app_file)
    pages = "\n".join(f'- Page "{page["label"]}"' + (f" has the sub-tabs {', '.join(page['tabs'])}." if page["tabs"] else " (no sub-tabs).")
                      + (f" It's for: {page['description']}" if page["description"] else "") for page in data["pages"])
    not_yet = "\n".join(f"- {item['name']} ({item['status'].upper()}): {item['what']}" + (f" {item['note']}" if item["note"] else "")
                        + (f" [{item['plan']}]" if item["plan"] else "") for item in data["planned"])
    backend = "\n".join(f"- {area['name']}: {area['about']}" for area in data["backend"])
    text = ("ZAE SELF-MAP. Generated from your source files; answer questions about yourself from this, not from memory.\n"
            f"APP PAGES AND TABS:\n{pages}\n\n"
            f"NOT BUILT YET (say so plainly; PARTIAL means some pieces exist but the whole workflow doesn't):\n{not_yet}\n\n"
            f"BEHIND THE APP (server areas and core components):\n{backend}")
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0] + "\n(more not shown)"
