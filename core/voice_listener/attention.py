"""Local attention decisions; no transcripts, recordings, storage, or execution.

An attention call can occur anywhere in a sentence. A follow-up is considered
only inside a live conversation by its caller. Importance/fatigue signals alone
never become permission to run a command.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", text.casefold().replace("’", "'"))).strip()


@dataclass(frozen=True)
class AttentionCall:
    start: int
    end: int
    phrase: str


def find_attention_call(text: str, names: Iterable[str], calls: Iterable[str] = ()) -> AttentionCall | None:
    """Find a vocative without interpreting ordinary 'say' as a wake word.

    Explicit quotations and obvious reported/name-description uses are ignored.
    The local speech recognizer cannot recover all real-world conversational
    intent, so this is a conservative routing cue, never an identity proof.
    """
    choices = sorted({str(name).strip() for name in (*names, *calls) if str(name).strip()}, key=len, reverse=True)
    candidates = []
    for phrase in choices:
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in phrase.split()) + r"(?!\w)"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            before, after = text[:match.start()], text[match.end():]
            # A quoted example, a person's name, or reported speech is not a call.
            if len(re.findall(r'["“”]', before)) % 2:
                continue
            prefix = normalize(before)
            suffix = normalize(after)
            if re.search(r"\b(?:named|called|about|say|said|says|asked|told|heard|mention|mentioned|spelled|spell|word)\s*$", prefix):
                continue
            if re.search(r"\b(?:asked|said|told)\s+(?:to|about)\s*$", prefix):
                continue
            if re.search(r"\bremember\b.+\bis\s*$", prefix):
                continue
            if suffix.startswith(("means ", "mean ", "stands for ")):
                continue
            # Talking about someone rather than to ZAE: "my friend Zay said hi",
            # "Xenia is my cousin", "say goodnight to Zay".
            if re.search(r"\b(?:my|his|her|their|our|your|friend|cousin|sister|brother|mom|dad|with|to|for|from)\s*$", prefix):
                continue
            if re.match(r"(?:said|says|told|asked|went|wants|wanted|thinks|thought|"
                        r"(?:is|was) (?:my|a|an|the|his|her|their|our|not|also|from|here|coming)|'s)(?:\s|$)", suffix):
                continue
            candidates.append(AttentionCall(match.start(), match.end(), phrase))
    return min(candidates, key=lambda item: (item.start, -(item.end - item.start))) if candidates else None


def strip_attention(text: str, call: AttentionCall | None) -> str:
    """Remove one matched address while preserving dates, times, and fact values."""
    if call is None:
        return " ".join(text.split())
    before = text[:call.start].rstrip(" ,:;!?.")
    after = text[call.end:].lstrip(" ,:;!?.")
    # A greeting immediately before the name belongs to the address, including
    # an embedded 'could you, hey ZAE, ...'. Do not remove words from the request.
    before = re.sub(r"(?:^|\s)(?:hey|hi|hello|okay|ok|yo)[ ,]*$", "", before, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", f"{before} {after}").strip(" ,:;!?.")


_FILLERS = re.compile(r"^(?:(?:okay|ok|so|well|and|but|then|also|actually|wait|please)\s+)+")
_QUESTION = re.compile(r"^(?:what|what's|whats|why|how|how's|where|where's|when|when's|which|who|who's|whose)\b")
_DIRECT = re.compile(
    r"^(?:(?:can|could|would|will|do|did|are|have)\s+you\b|"
    r"(?:is|was|does|did|can|could|would|will|should|has)\s+(?:it|that|this|there|the|my|we|i)\b|"
    r"(?:tell|show|help|remind)\s+me\b|(?:explain|describe|compare|summarize|continue|repeat|expand|clarify)\b|"
    r"(?:add|create|schedule|remember|forget|check|find|open|read|list|search|update|change|move|reschedule|complete|cancel)\b|"
    r"(?:make|keep)\s+(?:it|that|this)\b|(?:i\s+(?:need|want|meant)|let's)\b)"
)
_SHORT = re.compile(r"^(?:what about|how about|and (?:that|this)|the (?:first|second|third|other) one|"
                    r"that one|this one|a little (?:more|less)|more (?:detail|details)|less detail|go on|"
                    r"again|yes|no|no thanks|thanks|thank you|got it|okay|ok|cool|right|exactly|correct|"
                    r"that's right|not quite|stop|wait|hold on|never ?mind|cancel that action|confirm that action)$")


def is_conversational_follow_up(text: str) -> bool:
    """Recognize a question, directed request, or brief conversational reply.

    This deliberately does not accept every utterance during the timeout. It
    does not claim a question in nearby human conversation can be distinguished
    perfectly without additional signals.
    """
    clean = normalize(text)
    if not clean or len(clean) > 8000 or text.lstrip().startswith(('"', '“')):
        return False
    if re.match(r"^(?:he|she|they|someone|somebody|the tv|the television)\b", clean):
        return False
    if _SHORT.fullmatch(clean):
        return True
    clean = _FILLERS.sub("", clean)
    return bool(_QUESTION.match(clean) or _DIRECT.match(clean) or re.match(r"^(?:what|how) about\b", clean))


def is_quiet_acknowledgement(text: str) -> bool:
    """A conversational receipt, never an action confirmation or answer choice."""
    return normalize(text) in {'cool', 'thanks', 'thank you', 'got it', 'okay', 'ok'}


def is_pending_action_reply(text: str) -> bool:
    """Only exact confirmation/cancellation or a date/time slot outlive chat."""
    clean = normalize(text)
    if clean in {"confirm that action", "cancel that action", "never mind", "nevermind"}:
        return True
    # Reuse the action dialogue's exact temporal grammar; it performs a second
    # validation and cannot create an action from a slot alone.
    from core.assistant_dialogue import _TEMPORAL_REPLY, normalize_spoken_clocks
    return bool(_TEMPORAL_REPLY.fullmatch(normalize_spoken_clocks(text.strip().rstrip(".!?"))))


class ConversationAttention:
    """Session-local follow-up window. Persisted state cannot wake a new run."""

    def __init__(self, seconds: float = 30, clock: Callable[[], float] = time.monotonic):
        self.seconds = min(60.0, max(5.0, float(seconds)))
        self.clock = clock
        self.until = 0.0

    def open(self) -> None:
        self.until = self.clock() + self.seconds

    def close(self) -> None:
        self.until = 0.0

    def is_active(self, *, replying: bool = False) -> bool:
        return replying or self.clock() < self.until

    def accepts(self, text: str, *, pending: bool = False, replying: bool = False) -> bool:
        if pending and is_pending_action_reply(text):
            return True
        return self.is_active(replying=replying) and is_conversational_follow_up(text)
