"""Fetching for Research: public sources only, size-capped, and never this PC's own network.

`safe_url` refuses anything that isn't plain http(s) to a public internet
address, so a link inside a page or feed can't make ZAE reach her own API, the
router, or other machines on the home network. Readable text is pulled out of
pages without running any of their scripts.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlparse

USER_AGENT = "ZAENIA/1.0 (personal research assistant; +local)"
MAX_BYTES = 4_000_000


def safe_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return False
    host = parsed.hostname
    if host in ("localhost",) or host.endswith((".local", ".internal", ".ts.net", ".lan", ".home")):
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)}
    except OSError:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
        if ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10"):  # Tailscale / carrier NAT
            return False
    return True


def _get(url: str, *, params: dict[str, Any] | None = None, timeout: float = 15, accept: str = "*/*") -> Any:
    """GET with two retries for dropped connections (the Library of Congress drops some)."""
    import requests
    for attempt in range(3):
        try:
            return _get_once(url, params=params, timeout=timeout, accept=accept)
        except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError):
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


def _get_once(url: str, *, params: dict[str, Any] | None, timeout: float, accept: str) -> Any:
    import requests
    if not safe_url(url):
        raise ValueError("That address isn't a public web page.")
    reply = requests.get(url, params=params, timeout=timeout, stream=True, allow_redirects=True,
                         headers={"User-Agent": USER_AGENT, "Accept": accept})
    if not safe_url(reply.url):
        reply.close()
        raise ValueError("The page redirected somewhere private.")
    reply.raise_for_status()
    body = b""
    for chunk in reply.iter_content(65536):
        body += chunk
        if len(body) > MAX_BYTES:
            break
    reply.close()
    reply._content = body[:MAX_BYTES]
    return reply


def get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 15) -> Any:
    reply = _get(url, params=params, timeout=timeout, accept="application/json")
    reply.encoding = "utf-8"  # some APIs (GDELT) don't say, and the guess garbles accents
    return reply.json()


def post_json(url: str, body: dict[str, Any], timeout: float = 20) -> Any:
    """POST for search APIs that only take POST (Sefaria). Same public-address rule as GET."""
    import requests
    if not safe_url(url):
        raise ValueError("That address isn't a public web page.")
    reply = requests.post(url, json=body, timeout=timeout, allow_redirects=False,
                          headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    reply.raise_for_status()
    if len(reply.content) > MAX_BYTES:
        raise ValueError("The answer was too large.")
    reply.encoding = "utf-8"
    return reply.json()


def get_text(url: str, timeout: float = 20) -> str:
    reply = _get(url, timeout=timeout)
    reply.encoding = reply.encoding or "utf-8"
    return reply.text


def readable(html: str) -> dict[str, str]:
    """Title and plain paragraphs of an article, without menus, ads or scripts."""
    import lxml.html
    try:
        root = lxml.html.fromstring(html)
    except Exception:
        return {"title": "", "text": ""}
    for bad in root.xpath("//script|//style|//noscript|//nav|//header|//footer|//aside|//form|//iframe|//svg|//button"):
        bad.drop_tree()
    title = (root.xpath("string(//meta[@property='og:title']/@content)") or root.xpath("string(//title)") or "").strip()
    body = root.xpath("//article") or root.xpath("//main") or [root]
    paragraphs = []
    for node in body[0].iter("p", "h2", "h3", "li"):
        text = " ".join(node.text_content().split())
        if len(text) >= 40 or (node.tag in ("h2", "h3") and text):
            paragraphs.append(text)
    return {"title": " ".join(title.split())[:300], "text": "\n\n".join(paragraphs)[:60_000]}


def snippet(text: str, term: str, width: int = 220) -> str:
    clean = " ".join(str(text or "").split())
    match = re.search(re.escape(term), clean, re.I)
    if not match:
        return clean[:width]
    start = max(0, match.start() - width // 2)
    return ("…" if start else "") + clean[start:start + width] + ("…" if start + width < len(clean) else "")
