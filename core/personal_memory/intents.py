"""Conservative explicit memory requests; parsing never saves or deletes data."""
from __future__ import annotations

import re
from typing import Any

from .store import COMMUNICATION_PREFERENCE_KEYS, MAX_KEY, MAX_VALUE, normalize_key, validate_memory

_ADDRESS = re.compile(r"^(?:hey\s+)?(?:zae|zay|zænia|zaenia)(?:\s*[,!:]\s*|\s+)", re.IGNORECASE)
_POLITE = re.compile(r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?", re.IGNORECASE)
_REMEMBER = re.compile(r"^(?:remember|save\s+(?:a\s+)?memory\s+(?:that\s+)?)\b\s*(?:that\s+)?(?P<body>.*)$", re.IGNORECASE)
_FORGET = re.compile(r"^(?:forget|delete\s+(?:the\s+)?memory(?:\s+(?:about|for))?)\b\s*(?P<body>.*)$", re.IGNORECASE)
_RECALL = re.compile(
    r"^(?:what\s+do\s+you\s+(?:remember|know)(?:\s+about\s+(?P<about>.*))?|"
    r"(?:do\s+you\s+remember|recall)\s+(?P<recall>.*)|"
    r"(?:show|list)\s+(?:me\s+)?(?:my|the|your|all)\s+(?:personal\s+)?memories)$", re.IGNORECASE
)
_MULTI = re.compile(
    r"\b(?:and|then|also)\s+(?:(?:please\s+)?(?:add|create|schedule|delete|remove|send|email|"
    r"ignore|execute|run|cancel|set|update|remember|forget)\b|(?:my\s+.+?\s+(?:is|are)|I\s+(?:am|will|prefer))\b)"
    r"|\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b", re.IGNORECASE
)
_NONREQUEST = re.compile(r"^(?:if|unless|maybe|perhaps|hypothetically|for\s+example|don't|do\s+not|never)\b", re.IGNORECASE)


def _refusal(operation: str, reply: str) -> dict[str, Any]:
    # Never include the original request/value in a refusal or diagnostic.
    return {"operation": operation, "reply": reply}


def _category(key: str, value: str) -> str:
    text = key.casefold()
    if text in COMMUNICATION_PREFERENCE_KEYS:
        return "preference"
    if re.search(r"\b(?:goals?|ambitions?)\b", text):
        return "goal"
    if re.search(r"\b(?:commitments?|promises?)\b", text):
        return "commitment"
    if re.search(r"\b(?:wife|husband|partner|mother|father|mom|dad|brother|sister|son|daughter|friend|manager|colleague)\b", text):
        return "person"
    if re.search(r"\b(?:favou?rite|prefer(?:ence|ences|red)?|like|dislike)\b", text):
        return "preference"
    return "fact"


def parse_memory_request(message: str) -> dict[str, Any] | None:
    """Recognize a single direct request without learning from ordinary chat.

    Natural ``my <key> is <value>`` requests have a stable correctable key.
    Other short ``remember that <statement>`` facts use the literal statement
    as their key; no personal attributes are derived from its meaning.
    """
    if not isinstance(message, str) or not message.strip() or len(message) > 8000:
        return None
    text = message.strip()
    if any(not char.isprintable() for char in text):
        return None
    text = _ADDRESS.sub("", text, count=1)
    text = _POLITE.sub("", text, count=1).strip()
    # Trim only request punctuation, preserving apostrophes inside names.
    text = re.sub(r"(?:,\s+please)?[.!?]?$", "", text, flags=re.IGNORECASE).strip()
    recall = _RECALL.fullmatch(text)
    if recall:
        query = (recall["about"] or recall["recall"] or "").strip()
        if query.casefold() in {"me", "myself", "my memories", "everything", "all"}:
            query = ""
        query = re.sub(r"^my\s+", "", query, flags=re.IGNORECASE)
        return {"operation": "recall", "query": query}
    match = _REMEMBER.fullmatch(text)
    operation = "remember"
    if match is None:
        match = _FORGET.fullmatch(text)
        operation = "forget"
    if match is None:
        return None
    body = match["body"].strip()
    if not body or _NONREQUEST.search(body) or _MULTI.search(body) or any(token in body for token in ('"', '“', '”', '`', ';', '&&', '||')):
        return _refusal(operation, "Give one explicit memory at a time, using an exact key such as 'my favorite color'.")
    if operation == "forget":
        body = re.sub(r"^(?:the\s+)?memory\s+(?:about|for)\s+", "", body, flags=re.IGNORECASE)
        if body.casefold() in {"everything", "all", "all memories", "all my memories", "me", "myself"} or re.search(r"\b(?:and|or)\b", body):
            return _refusal(operation, "Choose one exact memory key to forget. You can inspect personal memory first.")
        try:
            key = normalize_key(body)
        except ValueError:
            return _refusal(operation, "Give one exact memory key of 1 to 120 characters to forget.")
        return {"operation": "forget", "key": key}
    # Do not turn questions, speculation, or multiple statements into facts.
    if "?" in body or len(body) > MAX_VALUE:
        return _refusal(operation, "State one explicit fact to remember, using 'Remember my key is value'.")
    parts = re.fullmatch(r"my\s+(?P<key>.+?)\s+(?:is|are)\s+(?P<value>.+)", body, flags=re.IGNORECASE)
    if parts:
        key, value = parts["key"], parts["value"]
    else:
        key, value = body, body
    category = _category(key, value)
    try:
        key, value = validate_memory(key, value, category)
    except ValueError as error:
        if "credentials" in str(error):
            return _refusal(operation, "I cannot save passwords, API keys, passkeys, tokens, or other credentials as personal memory.")
        if len(key) > MAX_KEY:
            return _refusal(operation, "Give this memory a short explicit key: 'Remember my key is value'.")
        return _refusal(operation, "Give one memory with a key of 1 to 120 characters and a value of 1 to 800 characters.")
    return {"operation": "remember", "key": key, "value": value, "category": category}
