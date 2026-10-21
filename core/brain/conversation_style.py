"""Keep conversation user-led without delaying ordinary token streaming.

Only familiar, optional closing invitations are suppressed. Actual questions,
clarifications, quoted material, and requests to write dialogue stay intact.
This module has no memory, speech, or action authority.
"""
from __future__ import annotations

import re
from typing import Iterable, Iterator


_PREFIXES = (
    "would you like", "do you want", "want to know", "let me know",
    "is there anything else", "can i help", "anything else",
)
_INVITATION = re.compile(
    r"(?:"
    r"(?:would you like|do you want)(?: me)? to "
    r"(?:know more|learn more|hear more|continue|go into (?:more |further )?detail|"
    r"explore (?:this|that|it)(?: further)?|"
    r"explain (?:more|further|this|that|it)(?: in (?:more )?detail)?|"
    r"help(?: you)?(?: (?:with (?:anything else|something else|this|that)|further))?)"
    r"(?: about (?:this|that|it|anything else))?|"
    r"want to know more|"
    r"let me know if (?:you (?:want|need|would like) (?:to know more|more details|"
    r"anything else|any (?:more )?help|help|more information)|"
    r"there(?:'s| is) anything else(?: i can help (?:you )?with)?)|"
    r"is there anything else(?: (?:i can help (?:you )?with|you(?:'d| would) like to know))?|"
    r"can i help (?:you )?with anything else|anything else"
    r")[?!.]*", re.IGNORECASE,
)
_REQUESTED_TEXT = re.compile(
    r"\b(?:quot(?:e|ed|ing)|translat\w*|roleplay|role.play|dialogue|script|"
    r"interview|quiz|questions?|survey|exact(?:ly)?|verbatim|code)\b", re.IGNORECASE,
)
_ESSENTIAL_CONTEXT = re.compile(
    r"\b(?:approval|permission|consent|confirmation|authorize|authorise|"
    r"irreversible|permanent|payment|purchase|charge|cost)\b|"
    r"\b(?:cannot|can't) be undone\b", re.IGNORECASE,
)


def user_led_stream(chunks: Iterable[str], *, question: str = "") -> Iterator[str]:
    """Release normal prose immediately; hold only a possible closing invitation.

    A candidate is discarded only at end of output, after substantive text,
    and when its entire text matches a small invitation allowlist. Embedded
    examples and required clarification questions are not blanket-filtered.
    Holding is capped at 2,048 characters so a false candidate cannot stall a long reply.
    """
    if _REQUESTED_TEXT.search(question):
        yield from chunks
        return
    boundary = True
    prior = False
    pending = ""
    suspect = False
    context = ""
    required = bool(_ESSENTIAL_CONTEXT.search(question))
    for chunk in chunks:
        released: list[str] = []
        for char in str(chunk):
            if suspect:
                complete = pending.rstrip().endswith(('.', '!', '?')) and bool(_INVITATION.fullmatch(pending.strip()))
                pending += char
                # Release a required question as soon as its sentence ends,
                # or a candidate becomes an embedded part of a longer answer.
                false_ending = char in ".!?\n" and not _INVITATION.fullmatch(pending.strip())
                continuing = complete and not char.isspace() and char not in ".!?"
                if len(pending) > 2048 or false_ending or continuing:
                    released.append(pending)
                    context = (context + pending)[-1024:]
                    pending = ""
                    suspect = False
                    boundary = char in ".!?\n"
                continue
            if boundary and prior:
                pending += char
                probe = pending.lstrip().casefold()
                if not probe:
                    continue
                if any(prefix.startswith(probe) for prefix in _PREFIXES):
                    if probe in _PREFIXES:
                        suspect = True
                    continue
                released.append(pending)
                context = (context + pending)[-1024:]
                pending = ""
                boundary = char in ".!?\n"
                continue
            released.append(char)
            context = (context + char)[-1024:]
            if not char.isspace():
                prior = True
            boundary = char in ".!?\n"
        if released:
            yield "".join(released)
    if pending and not (suspect and _INVITATION.fullmatch(pending.strip())
                        and not required and not _ESSENTIAL_CONTEXT.search(context)):
        yield pending


def user_led_answer(text: str, *, question: str = "") -> str:
    return "".join(user_led_stream([text], question=question)).strip()
