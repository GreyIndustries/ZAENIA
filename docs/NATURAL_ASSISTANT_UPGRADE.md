# Natural assistant upgrade

The existing UI appearance, local model, voice, and owner security stay in place.
This update adds responsive movement, user-led conversation, and a review-first
maintenance process. It does not install a bigger model or remove project files.

## Workspace behavior

With Ambient motion and Adaptive workspace enabled, the core gently changes size
and position as ZAE listens, thinks, and speaks. Chat gains room during activity
and while its controls have focus. A settling delay prevents the layout bouncing
between speech clips. Navigation, module focus, and panel openings have short
transitions that use the existing glass, blue, and amber styling.

The existing Visual Source settings include **Adaptive workspace**, **Larger
core**, **Larger chat**, and **Reset**. Size preferences stay on this device.
Turning off Ambient motion or using the operating system's reduced-motion setting
disables automatic movement. Manual size controls remain available. The layout
stays bounded on smaller windows and phones.

## Natural attention and replies

An explicit address can appear anywhere: `What time is it, ZAE?` or `Could you,
Zay, explain that?`. Names include ZAE, ZÆNIA, ZAENIA, Zay, and the configured
recognizer variants. `Hey assistant` and `Okay assistant` are additional calls.
Saying a name alone silently opens the conversation instead of producing a
canned greeting. Edit calls in `core/voice_listener/voice_listener_config.yaml`;
do not add ordinary words such as `say` as aliases.

After addressing her or receiving a reply, a 30-second window accepts questions,
directed requests, corrections, and brief conversational replies without another
name. The window starts again after speech ends. Unrelated statements, obvious
reported speech, and quoted examples do not automatically start a conversation.
The PC voice window is session-local, so saved state cannot wake a restarted
listener. Pending action confirmations and date/time clarifications retain the
action's existing short expiry.

Brief acknowledgements such as `Cool`, `Thanks`, and `Got it` keep an active
conversation open silently, without spending a model turn on another acknowledgement.

This is a conservative local attention classifier, not complete understanding of
who every nearby sentence is directed toward. An initial ambiguous ambient
question remains background speech. The user can explicitly address ZAE or use
the microphone button. Importance/fatigue signals alone do not trigger speech or
authorize actions. The secured PC listener still verifies the owner and approved
microphone; the app microphone still uses its protected API connection.

ZAE answers and leaves the next turn to Zack. The model prompt forbids generic
invitations, and a streaming filter suppresses familiar optional closing lines
such as `Do you want to know more?`. Ordinary answer tokens still stream promptly.
Required clarification questions and explicitly requested questions, quotations,
scripts, or translations are preserved. This filter is narrow; it does not
promise to catch every possible paraphrase from the model.

## Speed and maintenance

Conversation recall reads a 256 KiB tail and at most 200 lines of its journal,
then selects the existing recent-message limit. The journal is not rewritten or
trimmed. This bounds disk reads as conversation history grows. The legacy
conversation entry point uses the same bounded reader.

The root requirements list's broken `sounddevicetzdata` package name is corrected
to `sounddevice`; `tzdata` remains a separate dependency and duplicate entries
were removed. The separate pinned security/API requirements remain available.
No packages were downloaded, replaced, or uninstalled.

See [CLEANUP_REVIEW.md](CLEANUP_REVIEW.md) for verified cleanup candidates and the
repeatable metadata-only scanner. The complete inventory is private under
`data/cleanup_review/`. Detection does not grant deletion authority. Review and
select exact items first; a later cleanup must recheck the selection, preserve
active executables and runtime data, and use existing sensitive-operation owner
reauthentication and double confirmation for `files.delete`. The scanner has no
delete command.

## Activation and limits

Use the rebuilt `desktop/src-tauri/target/release/desktop.exe` or reload the web
app after the API restarts. API version 0.7.0 supplies the new voice routing cue.
Existing installed shortcuts are not replaced. Start PC voice normally and enter
the existing passkey locally to activate the updated verified listener.
Physical microphone recognition, speaker verification accuracy, and audio timing
require a live hardware session. Automated tests use simulated voice and
temporary stores; the visual preview uses sample data.

## Verification for this delivery

- 186 Python tests ran: 185 passed, one actual symlink-creation check skipped
  because this Windows account lacks that privilege. Reparse-point handling,
  path containment, protected-state exclusions, and stale-inventory comparisons
  were tested with fixtures.
- 50 simulated voice-security checks and 122 frontend checks passed (74 action
  and inbox, 15 voice routing, 33 workspace behavior).
- Desktop and phone/web production builds passed. Browser checks covered manual
  resizing, keyboard controls, reset, reduced motion, 1280×720 desktop, 390×844
  and 390×568 phones, and a short 390×430 keyboard/landscape viewport.
- The final Windows release build passed; `desktop.exe` is 11,217,408 bytes,
  built on October 16, 2026 at 22:45 local time. API 0.7.0 was restarted in its
  existing unattended mode on localhost:8766; health returned 200 and reported
  the follow-through worker running. Existing API credentials were retained.
- The sample-data screenshot is `docs/assistant-motion-preview.jpg`; the preview
  fixture and its browser tabs were closed after inspection.

Repeat from the project directory:

```powershell
.venv\Scripts\python.exe -m unittest core.brain.conversation_style_test core.voice_listener.attention_test core.assistant_dialogue_test core.api.assistant_actions_test core.api.assistant_stream_test core.api.assistant_upgrade_test core.personal_memory.memory_test core.assistant_followthrough.service_test core.voice_security.actions_test scripts.cleanup_audit_test
.venv\Scripts\python.exe -m core.voice_security.self_test
```

From `desktop`, run `npm run test:actions`,
`node scripts/voice-attention.test.cjs`,
`node scripts/workspace-dynamics.test.cjs`, `npm run build`,
`npm run build:web`, and `npm run tauri build -- --no-bundle`.
