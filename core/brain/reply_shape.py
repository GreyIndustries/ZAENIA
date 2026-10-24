"""Brief first, deeper on request: how long each of ZAE's replies should be.

Every turn gets a short reply guide placed right before Zack's message. By
default she answers in a sentence or two, the way J.A.R.V.I.S. and F.R.I.D.A.Y.
do. When he asks for more ("why?", "explain", "go deeper", "walk me through
it", "tell me more"), she gives the full explanation, building on her last
answer instead of repeating it.
"""
from __future__ import annotations

import re

_DEEP = re.compile(
    r"\b(?:explain|elaborate|in (?:depth|detail)|more detail|deeper|go deeper|dig (?:in|deeper)|"
    r"break (?:it|that|this) down|walk me through|step by step|full (?:explanation|answer|rundown|picture)|"
    r"the long version|teach me|help me understand|how does (?:it|that|this) work|why (?:is|does|did|would|do)|"
    r"compare|pros and cons|differences? between|write (?:a|me)|draft|plan (?:for|out)|list (?:all|every))\b")
_MORE = re.compile(
    r"^(?:(?:ok(?:ay)?|and|so|alright|right|sure|yeah|yes)[, ]+)?(?:why\??|how so\??|how\??|go on|keep going|continue|"
    r"(?:tell|show) me more|more|say more|expand(?: on (?:that|it|this))?|elaborate|explain(?: (?:that|it|this|more|further))?|"
    r"what do you mean\??|meaning\??|like what\??|such as\??|and then\??|go deeper|in detail|details?)(?: please| pls)?[.!?]*$")


def wants_depth(text: str) -> bool:
    """True when Zack asked for the explanation, not just the answer."""
    clean = " ".join(str(text).casefold().split())
    return bool(_MORE.match(clean) or _DEEP.search(clean))


def is_follow_up_for_more(text: str) -> bool:
    """A bare "why?" / "tell me more": expand the previous answer."""
    return bool(_MORE.match(" ".join(str(text).casefold().split())))


def reply_guide(text: str, has_previous_answer: bool = False, style_hint: str | None = None) -> str:
    if wants_depth(text):
        if is_follow_up_for_more(text) and has_previous_answer:
            shape = ("REPLY SHAPE: he wants the deeper explanation of your last answer. Don't repeat it; go one level "
                     "deeper: the reasoning, how it works, and what matters in practice. Use short paragraphs or a few "
                     "bullets if that reads better. Stay plain and specific, no filler.")
        else:
            shape = ("REPLY SHAPE: he asked for an explanation. Open with the one-line answer, then explain properly: "
                     "short paragraphs or a few bullets, concrete and specific, no filler.")
    else:
        shape = ("REPLY SHAPE: brief. Give the answer in one or two sentences (about 40 words at most); for a "
                 "greeting or acknowledgement, a few words. No background, caveats or lists unless they change what "
                 "he should do. He'll ask if he wants the deeper explanation; don't offer it.")
    return f"{shape}\n{style_hint}" if style_hint else shape
