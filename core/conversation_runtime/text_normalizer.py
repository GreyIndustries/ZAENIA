from __future__ import annotations

import re


def normalize_transcript_text(
    text: str,
) -> str:
    """
    Correct a small set of known STT mistakes.

    Keep this deliberately narrow so ZÆNIA does not
    aggressively rewrite Zack's actual wording.
    """

    text = text.strip()

    corrections = {
        r"\barm dash\b": "em dash",
    }

    for pattern, replacement in corrections.items():
        text = re.sub(
            pattern,
            replacement,
            text,
            flags=re.IGNORECASE,
        )

    return text


def normalize_generated_text(
    text: str,
) -> str:
    """
    Convert written punctuation that sounds unnatural
    through Piper into spoken-conversation punctuation.

    Normal hyphens are intentionally left alone.
    """

    if not text:
        return ""

    # Unicode dash characters commonly produced by LLMs.
    text = re.sub(
        r"\s*[—–―]\s*",
        ", ",
        text,
    )

    # Collapse accidental doubled punctuation/spaces.
    text = re.sub(
        r",\s*,+",
        ",",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()