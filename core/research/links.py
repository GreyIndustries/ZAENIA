"""Reading the links Grey sends, so ZAE can use what's actually in them.

- TikTok: the video's caption, author and length, plus the spoken words from
  TikTok's own auto-captions (the public WebVTT track the page lists). No
  video is downloaded.
- YouTube: title, channel, length and description (YouTube doesn't hand its
  captions to plain readers, so the spoken words aren't available).
- Any other page: its readable text, or its title and description when the
  page is mostly script.

Only public addresses are fetched (web.safe_url), with ZAE's honest user agent.
What comes back is untrusted data: it's read, never followed.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any, Callable
from urllib.parse import urlparse

from core.research import web

MAX_CHARS = 12_000
URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


def find_links(text: str, limit: int = 3) -> list[str]:
    found = []
    for url in URL.findall(str(text or "")):
        url = url.rstrip(".,;:!?")
        if url not in found:
            found.append(url)
    return found[:limit]


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")


def _meta(page: str, name: str) -> str:
    match = re.search(rf'<meta[^>]+(?:property|name)="{re.escape(name)}"[^>]+content="([^"]*)"', page, re.I) \
        or re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{re.escape(name)}"', page, re.I)
    return html.unescape(match.group(1)).strip() if match else ""


def vtt_text(vtt: str) -> str:
    """Spoken lines from a WebVTT caption file, without timings or repeats."""
    lines: list[str] = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or line.isdigit() or line.startswith(("NOTE", "Kind:", "Language:")):
            continue
        line = re.sub(r"<[^>]+>", "", html.unescape(line)).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return " ".join(lines)


def _tiktok(url: str, get_text: Callable[[str], str]) -> dict[str, str]:
    page = get_text(url)
    match = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>', page, re.S)
    if not match:
        raise ValueError("TikTok didn't return the video details (it may be private or removed).")
    item = (json.loads(match.group(1)).get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {})
            .get("itemInfo", {}).get("itemStruct") or {})
    if not item:
        raise ValueError("TikTok didn't return the video details (it may be private or removed).")
    video = item.get("video") or {}
    spoken = ""
    tracks = sorted(video.get("subtitleInfos") or [], key=lambda t: not str(t.get("LanguageCodeName", "")).startswith("eng"))
    for track in tracks[:2]:
        try:
            spoken = vtt_text(get_text(track["Url"]))
            if spoken:
                break
        except Exception:
            continue
    author = (item.get("author") or {}).get("uniqueId", "")
    music = (item.get("music") or {}).get("title", "")
    text = (f"TikTok video by @{author}, {video.get('duration', '?')} seconds long.\n"
            f"Caption: {item.get('desc', '').strip()}\n"
            + (f"Sound: {music}\n" if music else "")
            + (f"What's said in the video (TikTok's auto-captions):\n{spoken}" if spoken
               else "The video has no captions, so what's said or shown on screen isn't available; only the caption is."))
    return {"title": f"TikTok by @{author}", "kind": "TikTok video", "text": text}


def _youtube(url: str, get_text: Callable[[str], str]) -> dict[str, str]:
    page = get_text(url)
    match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\});(?:var |</script>)", page, re.S)
    details = json.loads(match.group(1)).get("videoDetails", {}) if match else {}
    title = details.get("title") or _meta(page, "og:title")
    if not title:
        raise ValueError("YouTube didn't return the video details.")
    minutes = round(int(details.get("lengthSeconds") or 0) / 60, 1)
    text = (f"YouTube video: {title}\nChannel: {details.get('author', '')}\nLength: {minutes} minutes\n"
            f"Description:\n{details.get('shortDescription') or _meta(page, 'og:description')}\n"
            "(YouTube doesn't share its captions with ZAE, so only the title and description are available, "
            "not what's said in the video.)")
    return {"title": title, "kind": "YouTube video", "text": text}


def read_link(url: str, *, get_text: Callable[[str], str] | None = None) -> dict[str, str]:
    """{title, kind, text} for a link. Raises ValueError with a plain reason when it can't be read."""
    get_text = get_text or web.get_text
    host = _host(url)
    if host.endswith("tiktok.com"):
        found = _tiktok(url, get_text)
    elif host in ("youtube.com", "youtu.be", "music.youtube.com"):
        found = _youtube(url, get_text)
    else:
        page = get_text(url)
        readable = web.readable(page)
        text = readable.get("text", "").strip()
        if len(text) < 200:  # mostly script (Instagram, X, apps): fall back to the page's own summary
            summary = " ".join(filter(None, (_meta(page, "og:title"), _meta(page, "og:description") or _meta(page, "description"))))
            text = summary or text
        if not text:
            raise ValueError("The page didn't have readable text (it may need a sign-in).")
        found = {"title": readable.get("title") or _meta(page, "og:title") or host, "kind": "web page", "text": text}
    found["text"] = found["text"][:MAX_CHARS]
    found["url"] = url
    return found


def links_as_files(message: str, *, reader: Callable[[str], dict[str, str]] = read_link) -> list[tuple[str, bytes]]:
    """Each link in the message as a labeled text 'file' for the shared-files answer path."""
    files = []
    for url in find_links(message):
        try:
            found = reader(url)
            body = f"LINK: {url}\nWHAT IT IS: {found['kind']}: {found['title']}\n\n{found['text']}"
        except Exception as error:
            reason = str(error) if isinstance(error, ValueError) else f"the site didn't answer ({type(error).__name__})"
            body = f"LINK: {url}\nZAE couldn't read this link: {reason}. Say so plainly; don't guess what it contains."
        name = f"link {_host(url)}{urlparse(url).path[:40]}".replace("/", "_") + ".txt"
        files.append((name[:120], body.encode("utf-8")))
    return files


def clarify_questions(message: str, material: str, ask: Callable[[str], str]) -> list[dict[str, Any]]:
    """Up to 4 multiple-choice questions when a request to make something personal needs details; else [].

    The questions are about Grey, not the link, so only a short note of what he shared goes in (the whole link
    text made the small model refuse or wander). It's framed as "write questions", which it does reliably; asked to
    "make a program" it sometimes refused outright.
    """
    shared = "; ".join(re.findall(r"WHAT IT IS: (.*)", material)) or material[:200]
    request = URL.sub("(link)", message).replace('"', "'")
    reply = ask(
        "Task: write clarifying questions, as JSON. Grey (an adult, the owner of this assistant) asked: "
        f"\"{request}\"" + (f" and shared: {shared}" if shared else "") + ". Write 2 to 4 short multiple-choice questions "
        "you'd ask him first about the details that would most change the result and that his request doesn't already "
        "say (for example goal, current level, days or time available, equipment, budget, preferences, limits or "
        "injuries). Each has 2 to 5 short choices. If his request already gives every detail that matters, return an "
        "empty list. Reply with JSON only: {\"questions\": [{\"question\": \"...\", \"options\": [\"...\", \"...\"]}]}")
    match = re.search(r"\{.*\}", reply, re.S)
    try:
        data = json.loads(match.group(0) if match else reply)
    except (ValueError, AttributeError):
        return []
    if not isinstance(data, dict):
        return []
    questions = []
    for item in (data.get("questions") or [])[:4]:
        text = " ".join(str(item.get("question", "")).split())[:200] if isinstance(item, dict) else ""
        options = [" ".join(str(o).split())[:80] for o in (item.get("options") or []) if str(o).strip()][:5] if text else []
        if text:
            questions.append({"question": text, "options": options})
    return questions


_CREATE = re.compile(r"\b(make|create|build|design|plan|write|put together|come up with|give me|set up|draft)\b.*\b("
                     r"program|programme|plan|routine|schedule|workout|training|diet|meal|budget|itinerary|trip|guide|"
                     r"strategy|regimen|split|course|curriculum|outline|list)\b", re.I | re.S)
ANSWERED = "My answers to your questions:"


def wants_clarify(message: str) -> bool:
    return ANSWERED not in message and bool(_CREATE.search(message))
