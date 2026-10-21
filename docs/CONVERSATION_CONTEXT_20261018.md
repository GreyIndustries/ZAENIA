# Conversation context upgrade — October 18, 2026

ZAE now builds a bounded working view of the current discussion before answering.
The current UI, voice settings and chosen passkey startup authentication are
unchanged. No voice-only migration ran.

## Changes

- Read up to 64 recent messages from the existing bounded journal window instead
  of using only the last 12 messages. The model receives at most four recent
  exchanges plus four relevant older exchanges, bounded to 12,000 characters.
  A burst of receipts cannot crowd out the latest owner request.
- Retain a quoted discussion anchor and relevant owner constraints/corrections.
  Corrections stay in chronological order; model guidance tells ZAE to prefer the
  latest correction, resolve clear references and ask a specific clarification
  only when competing meanings would materially change the answer or action.
- Explicit topic changes reset working context for that topic without deleting
  the conversation journal. Independent unrelated questions do not promote old
  goals or constraints into the working notes. Explicit returns such as “back to
  the desk setup” can retrieve matching earlier exchanges across a topic change.
- Temporal weather/calendar follow-ups such as “what about tomorrow?” inherit a
  clear prior source topic and recheck that source with its existing permissions.
  They save the owner's original words rather than a rewritten request.
- Follow-ups to grounded system discussions preserve evidence routing. The
  grounded generation pass receives conversation context that it previously
  discarded. Refreshed local evidence and the existing verifier still establish
  installation facts; old replies and owner statements are not evidence of
  current configuration or successful execution.
- Typed fallback now uses the canonical BrainService path, matching streaming
  chat and PC voice instead of building a separate prompt/memory stack.
- Conversation exchange/receipt writes use a process-safe file lock as well as
  the existing thread lock, preventing the API and PC voice writers from
  interleaving the lines of an exchange.

This adds no model call for context preparation and no new permanent-memory
database, embeddings, summaries or microphone recording. Existing explicit
personal memory and optional inferred learning retain their existing behavior.
The history is still the existing shared owner conversation journal; this change
does not introduce independent chat threads or promise unlimited recall.

## Verification

250 isolated regression tests passed, including 16 new context scenarios:
references, ordered corrections, relevant older constraints, explicit/implicit
topic changes, source-backed follow-ups, no inferred action authority, prompt
budgets, receipt bursts, topic resumption, typed fallback and grounded-context forwarding.

Four synthetic live checks passed on the configured local `llama3.1:8b` model:

| Scenario | Observed response |
| --- | --- |
| Maple versus walnut, then “Why does that one fit better?” | Identified maple and tied the answer to the light-wood preference. |
| Correct $600 to $450, then ask the budget | Answered “$450.” |
| Twelve intervening exchanges before returning to the desk setup | Recalled the $450 ceiling and avoiding subscriptions. |
| Explicit new topic asking seven times eight | Answered 56 without bringing in the desk constraints. |

Observed local call durations were 0.14–0.88 seconds in that run. These are small
synthetic spot checks, not end-to-end microphone latency or a general model
comprehension benchmark. Full output is in `conversation-context-live-check.json`.
The initial local connection failure occurred in the restricted tool sandbox;
the installed model was reachable when checked outside that sandbox.

Re-run synthetic live checks with:

```powershell
Set-Location C:\Projects\ZAENIA
.venv\Scripts\python.exe -m scripts.check_conversation_context --live
```

Already-running API/listener processes need their normal restart to load the
updated Python modules. No running owner session was stopped for this change.
These are backend changes; rebuilding the unchanged desktop UI is unnecessary.

Pre-change source copies: `backups/conversation-context-20261018/source/`.
