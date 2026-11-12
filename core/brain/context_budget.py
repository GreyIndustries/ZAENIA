"""Context budget for the local brain (Reasoning engine).

The model reads at most `context_window` tokens per turn (8,192 by default).
Ollama silently drops the *start* of an over-long prompt, which is where the
system prompt and moral charter sit, so an overflowing turn loses its most
important instructions. This module keeps every prompt inside the window:

* reference context is split into labelled sections (ABOUT GREY, TECH NEWS,
  SAVED SOURCE LIBRARY, ...), each with a priority and a size cap;
* if the total still doesn't fit, the lowest-priority sections shrink first,
  then the oldest conversation turns are dropped (the newest are kept);
* room is always reserved for the answer.

It is pure text arithmetic: no model calls, no I/O, no permissions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CHARS_PER_TOKEN = 3.4          # conservative for English with JSON/YAML mixed in
ANSWER_RESERVE_TOKENS = 1100   # room left for ZAE's reply
MESSAGE_OVERHEAD_TOKENS = 6    # role markers per chat message
KEEP_LAST_MESSAGES = 4         # newest history messages are never dropped

# (header prefix, priority, cap in characters). Higher priority survives longer.
SECTION_RULES: tuple[tuple[str, int, int], ...] = (
    ("CONVERSATION TOPIC NOTES", 90, 1800),
    ("QUOTED WORKING CONTEXT", 85, 1500),
    ("SCREEN WATCH", 85, 1600),
    ("TECH NEWS", 80, 2400),
    ("EMAIL", 80, 2400),
    ("ABOUT GREY", 75, 2600),
    ("RELEVANT THINGS YOU KNOW ABOUT GREY", 75, 1600),
    ("PERSONAL MEMORY", 70, 2000),
    ("SAVED SOURCE LIBRARY", 55, 4000),
    ("FROM GREY'S ASSESSMENT", 50, 1200),
    ("USER LEARNING REFERENCE", 45, 1000),
    ("AMBIENT", 40, 1000),
    ("LOCAL ZÆNIA BEHAVIOR PROFILE", 35, 1800),
    ("CONVERSATION STATE", 15, 500),
    ("VOICE CONTEXT STATE", 10, 500),
)
DEFAULT_PRIORITY, DEFAULT_CAP = 50, 2000
# A section starts with at least two upper-case words ("TECH NEWS from ...").
_HEADER = re.compile(r"^[A-ZÆ][A-ZÆ0-9'’&-]+(?: [A-ZÆ0-9'’&-]+)+\b")


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


@dataclass
class Section:
    text: str
    priority: int
    cap: int

    @property
    def header(self) -> str:
        return self.text.split("\n", 1)[0][:60]


def _rule(text: str) -> tuple[int, int]:
    head = text.lstrip().upper()
    for prefix, priority, cap in SECTION_RULES:
        if head.startswith(prefix):
            return priority, cap
    return DEFAULT_PRIORITY, DEFAULT_CAP


def split_sections(text: str | None) -> list[Section]:
    """Blocks joined by blank lines; a block that doesn't start with a header
    belongs to the section before it."""
    sections: list[Section] = []
    for block in (text or "").split("\n\n"):
        if not block.strip():
            continue
        first = block.lstrip().split("\n", 1)[0]
        if sections and not _HEADER.match(first):
            sections[-1].text += "\n\n" + block
            continue
        priority, cap = _rule(block)
        sections.append(Section(block, priority, cap))
    return sections


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit < 80:
        return ""
    cut = text[:limit - 40]
    cut = cut[:max(cut.rfind("\n"), cut.rfind(". ") + 1, limit // 2)]
    return cut.rstrip() + "\n[… shortened to fit]"


def fit_sections(sections: list[Section], budget_chars: int) -> list[Section]:
    """Apply caps, then shrink lowest-priority sections until the total fits."""
    for section in sections:
        section.text = _trim(section.text, section.cap)
    total = sum(len(s.text) for s in sections)
    for section in sorted(sections, key=lambda s: s.priority):
        if total <= budget_chars:
            break
        excess = total - budget_chars
        keep = max(0, len(section.text) - excess)
        before = len(section.text)
        section.text = _trim(section.text, keep) if keep else ""
        total -= before - len(section.text)
    return [s for s in sections if s.text]


@dataclass
class Fitted:
    behavior: str | None
    conversation: str | None
    history: list[dict[str, str]]
    dropped_messages: int
    prompt_tokens: int


def fit_prompt(*, fixed_text: str, question: str, behavior: str | None, conversation: str | None,
               history: list[dict[str, str]] | None, context_window: int) -> Fitted:
    """Fit reference context and history into the model's window.

    fixed_text: everything that is always sent (system prompt, charter
    guidance, clock). The question is never shortened.
    """
    history = [dict(m) for m in (history or []) if m.get("content")]
    available = context_window - ANSWER_RESERVE_TOKENS - estimate_tokens(fixed_text) - estimate_tokens(question) - 4 * MESSAGE_OVERHEAD_TOKENS
    available_chars = int(max(0, available) * CHARS_PER_TOKEN)

    behavior_sections = split_sections(behavior)
    conversation_sections = split_sections(conversation)
    history_chars = sum(len(m["content"]) + MESSAGE_OVERHEAD_TOKENS * CHARS_PER_TOKEN for m in history)

    # History gets what it needs up to 45% of the room; reference context the rest.
    context_budget = max(int(available_chars * 0.55), available_chars - int(history_chars))
    tagged = [(0, s) for s in behavior_sections] + [(1, s) for s in conversation_sections]
    kept = fit_sections([s for _, s in tagged], context_budget)
    kept_ids = {id(s) for s in kept}
    behavior_text = "\n\n".join(s.text for which, s in tagged if which == 0 and id(s) in kept_ids) or None
    conversation_text = "\n\n".join(s.text for which, s in tagged if which == 1 and id(s) in kept_ids) or None

    used = len(behavior_text or "") + len(conversation_text or "")
    history_room = available_chars - used
    dropped = 0
    while history and len(history) > KEEP_LAST_MESSAGES and \
            sum(len(m["content"]) + MESSAGE_OVERHEAD_TOKENS * CHARS_PER_TOKEN for m in history) > history_room:
        history.pop(0)
        dropped += 1
    # The newest messages stay; shorten very long ones if the room is still short.
    while sum(len(m["content"]) for m in history) > max(0, history_room) and any(len(m["content"]) > 600 for m in history):
        longest = max(history, key=lambda m: len(m["content"]))
        longest["content"] = _trim(longest["content"], max(600, len(longest["content"]) // 2))

    prompt_chars = len(fixed_text) + len(question) + used + sum(len(m["content"]) for m in history)
    return Fitted(behavior_text, conversation_text, history, dropped, estimate_tokens(" " * prompt_chars))
