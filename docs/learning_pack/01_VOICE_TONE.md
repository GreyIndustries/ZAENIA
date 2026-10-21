# Voice tone, prosody and conversational understanding

Reference primer for Zae · Prepared October 18, 2026.

## Purpose and limits

Tone is a collection of vocal cues interpreted in context. Words, vocal delivery,
the situation and the speaker's own explanation can point in different directions.
An assistant should treat an emotion interpretation as a hypothesis, not a fact
about someone's private mental state. This file teaches concepts and proposes
an evaluation method. Importing text does not add an audio emotion model to Zae.

## What to listen for

Prosody concerns patterns such as pitch, timing, rhythm and emphasis. Pitch is
related to perceived highness or lowness; loudness concerns perceived intensity;
rate concerns how speech unfolds in time. Pauses, elongated syllables, breathiness,
roughness and voice quality may also affect a listener's impression. The same
acoustic pattern can have several causes, including the microphone or environment.

The following is an original analysis checklist, not a validated emotion decoder:

| Observation | Questions to consider before interpreting it |
|---|---|
| Louder delivery | Is the room noisy? Is this emphasis, excitement or frustration? |
| Faster speech | Is this the speaker's normal pace? Are they rushing or enthusiastic? |
| Long pause | Are they thinking, distracted, waiting or having trouble being heard? |
| Flat delivery | Is this their usual expression, fatigue, recording quality or intentional restraint? |
| Rising intonation | Is it a question, uncertainty, a dialect feature or conversational turn-taking? |
| Laughter | Does it express enjoyment, politeness, embarrassment or discomfort? |
| Emphasized word | Which part of the sentence is being contrasted or corrected? |

Source for the voice/communication background:
[NIDCD — Voice, Speech, and Language](https://www.nidcd.nih.gov/health/voice-speech-and-language).
For research on emotion-bearing vocal expression, see the RAVDESS paper below.

## Words, delivery and context

Use three separate records: what was said, what was acoustically observed, and
what interpretation is plausible. For example, “Fine, do whatever” could express
agreement, frustration, resignation, sarcasm or an ordinary preference depending
on delivery and context. Its transcript alone does not establish which meaning
was intended. A louder “stop” should not be ignored while trying to classify its
emotion: the literal instruction is already clear.

Sarcasm should be handled as contextual ambiguity. Look for a mismatch between
literal wording and the known situation; do not label every unusual pitch pattern
sarcastic. Friendly teasing, irony and annoyance are distinct possibilities.
When the distinction affects an action, ask one concise question about intent.
When it does not affect the answer, respond to the request without announcing
an unnecessary emotional diagnosis.

## Proposed response behavior

These examples are design recommendations, not claims that detection is installed:

- Explicit frustration: acknowledge the stated problem and offer a concrete next step.
- Uncertain delivery with an ambiguous command: clarify the command, not the person's mood.
- Apparent excitement: a warmer response may fit, while preserving factual accuracy.
- Very quiet or unclear audio: check what was heard before interpreting the delivery.
- Contradiction between an emotion guess and the user's correction: accept the correction.
- A request to stop: stop the relevant activity promptly, regardless of the emotion estimate.

Do not infer deception, consent, mental illness, dangerousness or identity from
vocal emotion. Speaker verification and emotion interpretation are different
tasks. A familiar voice does not authorize every instruction, and an irritated
voice should not lose access merely because it sounds irritated.

## Research material for a future audio module

[Livingstone and Russo, 2018 — RAVDESS](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0196391)
describes a validated collection of acted emotional speech and song. It includes
audio-only and audiovisual conditions, with North American English performances.
It is useful as a controlled research benchmark, not proof of performance on
spontaneous conversations or every language and accent.

The [researchers' dataset page](https://smartlaboratory.org/resources/speech-song-database-ravdess/)
links the recordings and paper. Check the current recording license separately
from the paper's license before redistribution or commercial training.

## Proposed evaluation plan

First evaluate transcription and audio quality separately. Then test any tone
model with recordings from speakers absent from its training set. Separate
recordings by speaker and session to reduce leakage. Include background noise,
different microphones, ordinary conversation and examples where several human
listeners disagree. Report per-category precision/recall, confusion patterns,
confidence calibration and the rate at which the model correctly abstains.

For personal adaptation, use only voluntarily supplied examples and corrections.
Do not silently record an ongoing household conversation to build a profile.
Retain the option “uncertain”; forcing every clip into an emotion label makes
the interface look more certain than its evidence allows.

An assistant-facing observation might be: “The speaker used a louder, faster
delivery than earlier; intent is unclear.” It should not become “The user is
angry” in permanent memory without their explicit confirmation.

## Study prompts

- Explain the difference between a transcript and prosodic evidence.
- Give three possible explanations for loud speech besides anger.
- Why is acted-dataset performance insufficient for everyday tone understanding?
- Design a clarification for an ambiguous instruction without claiming to read feelings.
- Identify what additional audio processing would be needed beyond this reference file.
