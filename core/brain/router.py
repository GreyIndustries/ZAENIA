"""Which way a conversation turn goes (Grey, 2026-11-08). Rules only: instant, and they can be tested against a fixed set.

- chat: Talk answers.
- web: the question asks for online or current information. Only then does anything leave the PC.
- deep: an online question that needs many sources or a thorough answer. Talk says so and Study runs a research job.
- local: the question is about what Grey saved or ZAE researched. Those are searched first, on this PC.

`accuracy_matters` picks the writer of a web answer: numbers, health, money, law and safety go to Seek.
Deciding a route never grants an action.
"""
from __future__ import annotations

import re

_DEPTH = re.compile(
    r"\b(?:in[- ]depth|deep[- ]dive|thorough(?:ly)?|comprehensive(?:ly)?|literature review|systematic review|full report|detailed report|"
    r"everything (?:you can find|there is)|as much (?:info|information) as|many sources|multiple sources|several sources|"
    r"compare (?:the )?(?:studies|research|sources|evidence))\b", re.I)
_LOCAL = re.compile(
    r"\b(?:(?:in|from|check|search|look (?:in|through)) my (?:saved )?(?:notes?|notebook|research)|my (?:saved )?(?:notes?|notebook|research) (?:on|about|say)|"
    r"(?:you|we|i) (?:already )?(?:researched|looked up|found out)|(?:your|our|the) (?:earlier|last|previous) research|"
    r"what did (?:you|we) (?:find|research)|did (?:you|we) (?:already )?research)\b", re.I)
_ACCURACY = re.compile(
    r"\b(?:how (?:much|many|long|often)|dos(?:e|age)|mg|mcg|safe|safety|danger\w*|toxic\w*|side effects?|interacts?|interactions?|symptoms?|"
    r"medic\w+|drugs?|legal|illegal|laws?|taxe?s?|prices?|costs?|interest rate|percent\w*|voltage|amps?|ph|ec|ppm|temperature|ratio|"
    r"statistics?|figures?|numbers?)\b", re.I)


def route(question: str) -> str:
    """chat, web, deep or local."""
    from core.brain.seek import needs_web_evidence
    text = " ".join(str(question or "").split())
    if _LOCAL.search(text):
        return "local"
    if needs_web_evidence(text):
        return "deep" if _DEPTH.search(text) else "web"
    return "chat"


def accuracy_matters(question: str) -> bool:
    return bool(_ACCURACY.search(str(question or "")))
