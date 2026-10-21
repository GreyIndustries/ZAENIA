# Adaptive user learning in Zae

Updated October 18, 2026. This is Zae's local implementation, not a copy of
OpenAI's private personalization algorithm or a claim of identical behavior.
Public background: [OpenAI session-memory guidance](https://developers.openai.com/cookbook/examples/agents_sdk/session_memory)
describes managing and selecting conversation context. This implementation
adds its own local, reviewable user-learning rules.

## How it works

The existing conversation history, explicit personal-memory database and learning
library remain separate. Inferred personal points live in
`data/personal_memory/insights.json`. A background local model extracts up to
four durable preferences, interests, routines, goals or working patterns after
the configured number of eligible turns (six by default).

Each new model-extracted point must include an exact supporting quote from the
user's eligible conversation input. Unsupported quotes, excluded sensitive
content and obvious hypothetical/quoted/third-party framing are discarded.
Literal quote matching reduces unsupported claims; it does not prove that every
interpretation of a quote is correct. Points remain reviewable guesses.

New points are tentative. Three independent extraction batches can label a
repeated point supported; that is an evidence category, not a calibrated
probability or confirmation by the user. Duplicate candidates from the same
batch cannot inflate the count. Historical points without batch provenance
remain tentative. The latest short supporting quote is available for review.

Only eligible direct conversation turns enter durable learning. Ambient speech
and PC-window activity are excluded from this extractor. Sensitive/credential
filters remain conservative. Learning and retrieval remain controlled by the
existing memory.write and memory.read permissions. Raw audio is not added to
this memory system.

## Review and correction

Open **Assistant → What ZÆNIA has learned**:

- **That's right** marks a point confirmed by you.
- **Correct** edits and confirms it.
- **Delete** rejects it and removes it from ordinary retrieval.

Model extraction cannot overwrite a reviewed point. Corrections and rejection
increment a feedback revision so an extraction already running against an old
revision cannot undo that feedback. A stale edit from another device receives
a conflict response instead of silently overwriting newer feedback.

`insights.feedback.json` stores rejection fingerprints and revision metadata,
without the deleted sentences or supporting quotes. Lexically matching guesses
are suppressed across restarts, including when an old record is restored.
This matching is bounded and approximate: a substantially different paraphrase
may require another rejection. It is not a guarantee of semantic erasure from
every old conversation, exported backup, profile file or learning-library document.
Deleting a learned point does not delete those separate sources.

## Use in replies

The current question selects relevant points, with working-style preferences
available more broadly. User-confirmed points rank ahead of inferred ones.
Unconfirmed points not reinforced for over 90 days are excluded from replies
but remain visible for review. Current statements and explicit personal memory
take precedence over older inferred patterns. These records are reference,
never instructions or authorization to act.

Learning can be disabled through `learning.enabled` in the existing
`core/brain/brain_config.yaml`. The learned-point controls affect this learning
store, while Personal memory and Learning library have their own controls.

## The personal profile

[About Zack](ABOUT_ZACK_FOR_ZAE.md) is an editable file based on the available
conversation. It labels direct statements, observations, tentative impressions
and unknowns. It is not automatically imported or treated as blanket confirmation
of inferred traits. Import it as reference if desired; review uncertain statements
before turning them into confirmed personal memories.
