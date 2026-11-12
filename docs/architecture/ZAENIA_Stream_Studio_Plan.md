# ZÆNIA Stream Studio — Twitch and YouTube automation plan

Date: 2026-11-06 | Owner: Grey | Status: proposed; integrations not implemented

Requested outcome: use ZÆNIA for Twitch and YouTube in place of Streamer.bot. This plan is an architectural and delivery proposal, not permission to connect accounts, run moderation, publish a broadcast, migrate credentials, or deploy code. It supplements [Master Build Plan section 31](ZAENIA_Master_Build_Plan.md#31-stream-studio--twitch-and-youtube-automation).

## 1. What the finished experience should do

Add **Stream Studio** under **Create**, retaining the existing ZÆNIA appearance. Grey can prepare a broadcast, see both chats, run approved commands and alerts, control OBS, manage configured moderation, and review what happened afterward. Ordinary commands and alerts run deterministically even with every language model unavailable. Optional local AI adds useful channel conversation and summaries without becoming the authority for actions.

Example owner workflows:

- “Prepare my stream” loads a named streaming workspace and checks connections, selected channel/broadcast, OBS scenes, public audio, queue state and resource headroom. It displays problems before going live.
- “Switch to BRB” changes to the configured OBS scene and verifies the resulting state through an authenticated local owner control.
- A viewer types `!schedule`; ZAE returns the approved public channel schedule to that platform. It does not retrieve Grey's personal calendar.
- A permitted Twitch redemption queues its configured overlay and sound, records completion, and updates the redemption only when ZAE has the required app authority.
- “Quiet mode” suppresses configured public AI speech and alerts while essential moderation and controls remain available.
- “End the session” presents the authorized end-of-stream checklist and produces a local summary from the events actually observed. Stopping transmission follows the configured owner approval policy.

OBS remains responsible for capture, encoding and transmission. Account eligibility, platform availability and any simulcasting/output arrangement remain separate prerequisites. Supporting two chats does not itself provide video distribution to two destinations. The working assumption is OBS Studio on Windows 11; Streamlabs Desktop would need a separate adapter assessment.

## 2. Verified starting point

Read-only source inspection on 2026-11-06 found no Twitch, YouTube Live Chat, OBS WebSocket or Streamer.bot adapter in the searched application code and architecture documents. Existing Music platform tracking is project/release/manual-stat functionality; its platform connection descriptors say `not_connected`. It does not provide livestream chat or events.

| Existing source | Reuse | New work still required |
|---|---|---|
| `core/brain/conductor.py` | Existing Talk, Seek, Study and Keep routing | A stream-aware resource policy and restricted public context |
| `core/assistant_platform/jobs.py`, `performance.py`, `game_mode.py` | Priority, cancellation, stages, model coordination and gaming behavior | Dedicated bounded event/action lanes; measure contention with OBS/gameplay |
| `core/assistant_platform/actions.py` | Approval/history and receipt patterns | Explicit stream action schemas, permissions and result reconciliation; Undo only where actually supported |
| `core/api/platform_routes.py`, `auth.py`, `core/foundation/client_gate.py` | Owner-authenticated controls and desktop proof patterns | Narrow stream capabilities and an overlay interface that cannot access private Core APIs |
| `core/conversation_runtime/speech_queue.py`, `desktop/src/core/speech.ts` | Existing speech queue/interruption behavior | A separate public broadcast audio route and queue |
| `core/assistant_followthrough/service.py`, `push_delivery.py` | Private health notices and owner delivery patterns | Stream connection/queue/resource notices with appropriate quiet and urgency settings |
| `core/assistant_platform/personal_tools.py`, `MusicStudio.tsx` | Existing platform identity vocabulary and presentation | Actual live-platform integrations; do not label existing music records as connected |

These are source observations, not live platform or OBS tests. No private profiles, tokens, session logs, chat histories or Streamer.bot exports were read for this plan.

## 3. Scope and feature priorities

| Capability | First usable release | Later expansion / conditions |
|---|---|---|
| Combined chat | Owner-only Twitch/YouTube tabs plus merged timeline with platform badges; replies go to the originating platform | Configured destination-specific announcements after policy checks; no default public mirroring or echo loops |
| Commands | Aliases, arguments, viewer/mod/owner roles, per-user/global cooldowns, public FAQ replies | Scoped AI replies to explicit mentions or `!zae`; configurable allowed topics |
| Automation builder | Trigger → conditions → ordered steps, delay, variable update and approved actions; test before enable | Explicit parallel groups, reusable routines and more adapters |
| Alerts/overlays | Configurable cards, sounds and approved TTS; serialized playback; skip/pause/replay-as-test | Themes, transitions, milestones and platform-specific paid/member events |
| OBS controls | Read scene/source state; configured scene changes, source visibility, mute state and media actions | Recording/replay controls and additional OBS capabilities after separate tests |
| Moderation | Moderator tools, link/length/repetition filters, flags and approved temporary enforcement | Contextual AI suggestions; consequential decisions initially stay with a human |
| Twitch interaction | Authorized follows, raids, subscriptions/gifts, cheers and reward events | Polls/predictions and other features after channel capability/scope verification |
| YouTube interaction | Live chat plus available membership, paid-message and gift events | Poll controls and other supported event types after schema/live verification |
| Timers/counters | Live-only timers; explicit per-platform or combined chat thresholds; durable counters | Local loyalty/rewards if Grey wants them; no claim of native cross-platform currency |
| Owner controls | Desktop controls, approved local voice commands, existing authenticated phone interface | Hotkeys/Stream Deck/MIDI using the same scoped action definitions |
| Reports | Actual observed event counts, connection health, failed actions, moderation review and quota usage | Highlights/clip candidates and comparative analytics; separate estimates from platform measurements |
| Additional services | None required for the core replacement | Donation services, lights, Discord, games and custom plugins only after inventory and explicit scope |

The replacement target is **Grey's required workflows**, not every Streamer.bot feature or third-party extension. Mark every workflow unmapped, planned, implemented, replay-tested, integration-tested, or live-verified.

## 4. Architecture within the existing three engines

```text
Twitch / YouTube adapters
          |
          v
Normalized event inbox + durable processing state
          |
          v
Deterministic rules + authenticated role/capability checks
          |
          v
Bounded action queues ---- optional restricted AI drafting
          |
          v
OBS / platform chat / overlays / public audio
          |
          v
Effect receipts, health state and recovery review
```

**Engine 1** interprets owner requests and optionally drafts public replies. **Engine 2** stores scoped stream configuration, approved channel facts and justified operational history. **Engine 3** validates and executes actions. The existing Conductor and background-job infrastructure coordinate optional reasoning. There is no fourth engine, replacement personal memory store or general viewer-to-agent tool route.

Implementation should first inspect and extend existing registries, stores and workers. A small `core/streaming/` subsystem and `StreamStudio` client area are possible boundaries, not instructions to create duplicate modules. Select the protocol libraries and persistence placement in a reviewed implementation packet; preserve Python 3.11.9 compatibility.

### Event handling and state

Each normalized event needs platform, channel/broadcast ID, stable platform user ID where present, provider event ID, event kind, provider time, received time, processing/version state and correlation ID. Record provenance: external, own-bot, internally generated, test or replay. Exclude own-bot/test/replay events from normal command triggers and live metrics; explicitly configured action chaining needs depth/cycle limits. Keep platform-specific fields rather than flattening unlike events into misleading equivalents. Equal display names never establish a shared identity.

Twitch EventSub duplicates retain the same message ID, so persist deduplication state. YouTube gift-combo updates may reuse an ID: process them as a versioned update/delta instead of blindly discarding every repeated ID. Avoid triggering old alerts from YouTube's initial recent-history batch. Persist enough processing state to recognize updates without retaining unnecessary raw chat. Provider-specific fixtures and live tests must define replay windows and update semantics. [Twitch EventSub](https://dev.twitch.tv/docs/eventsub/), [YouTube chat-message schema](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages).

Persist action lifecycle: received → eligible → queued → running → succeeded/failed/expired/cancelled/uncertain. Associate effects with event and rule version; make cooldowns, counters and local balances atomic. Avoid exactly-once promises for external APIs. If a request times out after possible execution, reconcile observable state or present uncertainty before retrying an effect that could duplicate. Prefer explicit state such as `scene=BRB` and `muted=true` over toggles.

### Queue behavior

| Lane | Behavior |
|---|---|
| Emergency / owner | Local emergency disable and public-audio stop must remain available when queues/models stall |
| OBS control | Short, ordered, acknowledged state changes; no arbitrary source/plugin execution |
| Alerts / public audio | Serialized by default; bounded backlog, duration, skip, pause and expiry |
| Chat output | Separate platform budgets; rate-header handling, retries, expiry and delivered-result checks |
| AI assistance | Small concurrency/response budgets; cancel stale drafts; no blocking the other lanes |

Preserve imported behavior deliberately. Streamer.bot supports action-local arguments, persistent variables, concurrent queues and blocking queues. A superficial command-name copy can change order or timing. Its timers can combine elapsed time and chat lines; ZAE should explicitly distinguish per-platform versus combined activity thresholds. [Actions/queues](https://docs.streamer.bot/guide/core/actions), [variables](https://docs.streamer.bot/guide/core/variables), [timers](https://docs.streamer.bot/guide/core/timers).

## 5. Twitch integration

1. Register a dedicated application and use the documented installed-client OAuth approach appropriate to the selected owner/bot identities. Keep authentication in Core; never embed reusable secrets in the UI or overlay. Review the flow and scopes before account setup.
2. Use **EventSub WebSocket** for the desktop integration. It suits an installed chatbot and avoids a public webhook listener for the first release. Start with read access; add chat write, moderation, follower or redemption permissions only when enabling those features. A separate bot account is an optional, separately authenticated identity. [Twitch authentication](https://dev.twitch.tv/docs/chat/authenticating/).
3. Handle welcome, keepalive, reconnect, revocation and refresh/validation. Ordinary disconnects can lose events that Twitch does not replay; show the observation gap rather than inventing missing alerts. [WebSocket lifecycle](https://dev.twitch.tv/docs/eventsub/handling-websocket-events/).
4. Use the supported chat send endpoint and inspect delivery fields such as `is_sent`/`drop_reason`. Apply account/channel rate limits and reserve capacity for important messages; do not assume verified-bot privileges. [Chat send/receive](https://dev.twitch.tv/docs/chat/send-receive-messages/), [chat limits](https://dev.twitch.tv/docs/chat/).
5. Detect supported event types from actual channel permissions/capabilities. Subscriptions, Bits, rewards, polls and predictions must not appear enabled merely because a UI card exists. [EventSub types](https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/).
6. Plan reward migration explicitly: only the application that created a custom reward can manage its updates and redemption status. Streamer.bot-created rewards may need owner-approved recreation and mapping to ZAE-managed rewards; reconcile outstanding redemptions before cutover. Do not treat external rewards as fully manageable or hard-code historical eligibility assumptions. [Create custom rewards](https://dev.twitch.tv/docs/api/reference/#create-custom-rewards), [update redemption status](https://dev.twitch.tv/docs/api/reference/#update-redemption-status).

## 6. YouTube integration

1. Use an owner-controlled Google API project with YouTube APIs enabled. Confirm the correct channel/Brand Account and livestream availability. Public chat reads may use an API key, but writes and private/owned broadcast operations require OAuth. Service accounts are not a substitute for the owner's channel identity. Review OAuth testing/production settings, scope approval and token behavior before onboarding. [Authorization](https://developers.google.com/youtube/data/live/authentication).
2. Select the intended broadcast and its `liveChatId`; use **`liveChatMessages.streamList`** as the primary reader. It streams new messages and supplies a continuation token for reconnects. Use `list` only as a compatible fallback, respecting `pollingIntervalMillis` and page tokens. Current documentation lists 5 quota units per streamList/list call; measure actual project use and reconnect behavior. [streamList](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/streamList), [list](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/list).
3. Add chat output and authorized moderation incrementally. Current insert/delete documentation lists 20 units per call, so avoid chatty scheduled spam and keep quota for moderation. Track the project's actual quota allocation and errors; do not assume infinite availability or a fixed capacity across every project. [Insert](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/insert), [delete](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/delete), [quota](https://developers.google.com/youtube/data/determine_quota_cost).
4. Support the actual message schema for available Super Chats, Super Stickers, member events, gifted memberships and gifts. These depend on the channel/platform feature being available. Test combo updates and poll payloads against fixtures and the real connection; current resource documentation has poll naming inconsistencies. [Chat-message resource](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages).
5. Keep free subscribers, paid members, paid messages and gifts distinct. Do not promise an immediate alert for every subscriber, identifiable likes from every viewer, complete viewer watch time, or Twitch-style native channel points. YouTube push notifications cover video changes rather than a universal live-event feed, and subscriber listing has visibility/completeness limits. [Push notifications](https://developers.google.com/youtube/data/guides/push_notifications), [subscriptions list](https://developers.google.com/youtube/data/reference/rest/v3/subscriptions/list).

### Simulcasting and destination routing

The merged chat timeline is **for Grey's private control surface**. During a simulcast, Twitch's current terms restrict combining other platforms' activity into the Twitch broadcast and directing Twitch viewers to another concurrent livestream. Keep public cross-platform chat/alert routing disabled until the current rules, Grey's applicable agreement and the intended output design are checked. Review FAQ replies, timers, announcements and public AI output for the same restrictions. [Twitch terms, Simulcasting](https://legal.twitch.com/en/legal/terms-of-service), [simulcasting FAQ](https://help.twitch.tv/s/article/simulcasting-guidelines?language=en_US).

Every public effect needs a destination. If one OBS audio/video output feeds both platforms, anything embedded there appears on both; use a policy-compatible common output or separately configured destination outputs. Merely labelling an overlay “YouTube” does not isolate it from a shared Twitch feed. Never capture the owner-only combined chat or private moderation panels into a broadcast.

Core deterministic OBS controls remain usable during an internet outage. Twitch/YouTube operations require network access; queue only effects that remain valid and clearly report unavailable actions. Optional cloud AI is never required for core stream automation.

## 7. OBS, public overlays and audio

Use official **OBS WebSocket v5**, built into OBS Studio 28+. Target the local connection, commonly `127.0.0.1:4455`, keep authentication enabled and verify network exposure. Binding/firewall choices must be inspected before configuration changes. Discover supported requests and scene/source IDs rather than guessing from display labels. [OBS remote control](https://obsproject.com/kb/remote-control-guide), [official protocol](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md).

The adapter should read state and subscribe to events, correlate requests/results, reconnect with backoff, and recheck state before resuming. Allowlist controllable scenes/sources and parameter types. Changes to scene collections need a mapping review. Streaming/recording start or stop, destination changes, and broad plugin actions remain owner controls with their applicable approval policies; routine pre-approved scene changes should not prompt every time.

Create a narrow overlay service/projection containing sanitized display fields only. No private routes, raw HTML execution, unrestricted URLs, owner bearer token or general Core API credential. Any capability credential must be limited, revocable and protected from logging/leakage; validate connection origins and handle OBS Browser Source reconnects. Treat overlay content and media as untrusted input, with escaping, length/type limits and bounded lifetimes.

**Use a dedicated public audio player/browser source for broadcast TTS and alerts.** Keep private ZAE speech, passkey prompts, reminders and notifications outside that route. Capturing the whole ZAE process is insufficient if it produces both public and private audio. Broad desktop-audio capture can reintroduce excluded sound. This is a design inference from OBS audio routing, and must be proved on both stream and recording tracks using a local recording. Provide public mute, queue clear, ducking and a physical/hotkey emergency stop. [OBS application-audio capture](https://obsproject.com/kb/application-audio-capture-guide).

Configure an **OBS-native hotkey to mute the public audio source** as an independent fallback if Core/UI hangs. Distinguish stopping current playback, suppressing future effects and disabling automations; none implicitly stops broadcast transmission. Test the independent fallback and ZAE's own emergency controls separately.

## 8. Public audience and private assistant separation

| Boundary | Required behavior |
|---|---|
| Viewer input | Untrusted text, username, reward text or media metadata; cannot grant permissions, edit rules, run shell commands or read private files |
| Identity | Roles come from authenticated provider metadata and stable IDs, never display-name claims; cross-platform linking is opt-in |
| Public knowledge | Approved channel FAQ, rules, public links, current game and deliberately shared session context |
| Private knowledge | Calendar, health, personal memory, documents, passwords and development sessions stay inaccessible to the stream persona |
| Public AI | Separate conversation IDs, retrieval namespaces, reusable caches and context construction; allowlisted outputs/actions; no calls to the owner's existing private-chat endpoint |
| Local voice | Owner authentication and a deliberately armed streaming control channel; game/viewer audio must not become an owner command |
| Moderators | Channel moderation permissions only; no access to owner tools, credentials, private settings or security-policy editing |
| Learning | Channel-specific suggestions reviewed off-air; no automatic rule/policy changes or training from audience text |

Use the current owner authentication system. Stream mode must not bypass Calm/password protection or weaken voice verification. Existing owner API capabilities include private memory/calendar/files; never give that credential to an overlay, chat participant or bot-facing client.

Moderation starts with transparent configured filters, rate limits and human review for contextual concerns. AI may explain or flag a case; permanent bans and other consequential decisions initially remain human actions. Set per-command role requirements, profanity/link/media controls, cooldowns and maximum public speech length. A chat message saying “ignore your rules” must have no privileged effect.

Minimize retained chat. Proposed default: transient live chat, short-lived redacted execution/health records, and only the durable counters/configuration Grey selects. Final retention, refresh/deletion behavior and analytics must satisfy platform policies and the reviewed privacy scope. Never commit runtime chat, user lists, credentials or exports to Git. Provide inspect/export/delete controls and document what backups retain.

## 9. Performance with the four brains

Ordinary commands, cooldowns, counters, alert scheduling and OBS operations run on the CPU through deterministic code. Do not ask a model to interpret every message. Cache approved answers and batch optional summaries.

| Brain | Optional streaming responsibility |
|---|---|
| Talk | Brief, explicitly addressed public replies from approved channel context; separate owner context |
| Seek | Owner-requested lookup from approved sources; no unrestricted viewer web/file access |
| Keep | Small checkpoints and bounded summaries when resources permit |
| Study | Off-air analysis, automation proposals and development; normally defer during gameplay/streaming |

Measure actual GPU/RAM/CPU headroom while the game and OBS run on Grey's workstation. The reported 16 GB GPU is shared with inference; existing game-mode/model-release behavior must be reconciled with an opt-in stream assistant. Honor owner-marked priorities and show progress, while protecting encoding/audio responsiveness. Use OBS statistics to detect encoding/render lag and resource pressure. Reduce optional AI, decorative animation and background indexing before impairing commands or capture; offer owner-controlled stream profiles.

Initial engineering goals, subject to measurement: p95 internal rule dispatch under 100 ms at 10× the measured normal event rate; local OBS state acknowledgement typically within one second on a healthy connection; emergency public mute available without an LLM. These are proposed targets, not achieved benchmarks or guarantees about platform delivery latency. Record queue delay, misses, reconnect gaps, frame/render/encode lag and peak resources against the same OBS/game baseline.

## 10. User interface

Keep the existing visual language. Stream Studio should offer:

1. **Dashboard:** channel/broadcast status, OBS state, live/recording indicators, resource pressure, connection gaps and emergency public-output stop.
2. **Chat:** owner-only combined/platform views, badges, reply target, moderator actions and explicit public-AI enable/disable; public projections are separate and destination-limited.
3. **Actions:** searchable trigger/rule cards, ordered step editor, cooldowns, permissions, variables, test event, dry run and version history.
4. **Alerts & overlays:** preview with synthetic data, queue state, themes, source links, public-audio routing test and replay marked as test.
5. **OBS:** allowlisted scenes/sources, verified current state and owner controls; unavailable items visibly disabled.
6. **Moderation:** review queue, configured filters, reasons, platform receipts and human decisions.
7. **Session report:** measured activity, errors, quota, suggested improvements and a clear observed-data window.
8. **Connections & recovery:** feature-specific permissions, reconnect/revoke, configuration backup, migration parity and rollback controls.

Allow resizable/rearrangeable panels through the existing window system. Use concise status updates; ZAE should answer or perform the requested action without adding generic follow-up questions. Voice output on stream is explicit and bounded. Authenticated phone controls use the same action policies and do not expose OBS or owner API ports directly to the internet.

## 11. Migration from Streamer.bot

### Step A — Inventory and preserve

With Grey selecting the configuration/export scope, capture required commands, aliases, triggers, variables, timers, queues, rewards, OBS mappings, assets, custom code/plugins and third-party services. Record which workflows are essential. Preserve an untouched known-good Streamer.bot profile and OBS collection backup outside the active migration copy; verify a separate restore before relying on it. Inventory inspection does not authorize reading unrelated settings or secrets.

Streamer.bot's native export can include actions, triggers, queues, commands, timers and WebSocket definitions. Build a reviewed importer that produces a mapping report and disabled draft actions. Do not import credentials or automatically execute custom C#/plugins; translate or adapt them individually. [Import/export](https://docs.streamer.bot/guide/core/import-export).

### Step B — Replay offline

Use sanitized, versioned fixtures and stub outputs to compare expected action plans, timing, conditions, counter changes and permissions. Test and shadow executions use separate counters, balances, cooldowns and receipt namespaces/stores; they cannot mutate live ledgers. Block all external side effects, including indirect notification/file/tool actions; only explicitly authorized read connections are permitted in connected shadow mode. Cover custom code deliberately. Show unmapped features instead of silently dropping them. The migration ledger records original workflow, ZAE equivalent, dependencies, owner, tests and rollback instruction.

### Step C — Observe without outputs

Run read-only shadow mode on authorized connections. Streamer.bot remains the sole executor. ZAE records what she would have done, with all chat writes, moderation, OBS modifications, public audio and reward updates disabled in code. Compare several sessions; a test flag alone must not rely on model cooperation.

### Step D — Rehearse and transfer by workflow

Test on a local recording and, when Grey chooses, a private/unlisted test broadcast where supported. Prove audio/privacy isolation first. Disable a workflow in Streamer.bot before enabling its equivalent in ZAE. Keep one executor for every migrated action, counter and reward ledger. Reconcile in-flight redemptions and provider app ownership. Test restarts, token expiry and reconnect gaps before expanding the cutover.

### Step E — Retire after evidence

Require all critical workflows to pass and at least three successful full sessions covering them, including a deliberate reconnect/recovery trial. Keep the known-good profile and rollback instructions. Returning to Streamer.bot first disables ZAE effects and reconciles outstanding actions, counters and rewards; it must not leave both systems posting. A temporary read-only bridge is acceptable for migration, but the finished replacement must not require Streamer.bot for the migrated functions.

## 12. Build order and delivery gates

Milestones are ordered by evidence rather than promised calendar dates. Estimate effort after inventory; custom scripts and integrations can change scope substantially. The October 2027 self-upgrading-coder objective in master section 30 remains separate, and clean-checkout tests/CI remain a shared foundation priority.

| Milestone | Deliverable | Gate before proceeding |
|---|---|---|
| 0. Scope and baseline | Required-workflow matrix; selected OBS/platform configuration; known-good backup/restore; reproducible test baseline | Grey reviews scope, account identities, permissions and public/private routing |
| 1. Local foundation | Rule schema, event fixtures, action/receipt queues, preview UI, read-only OBS, kill switch | Commands/replays work with all models unavailable; roles and queue limits tested |
| 2. Twitch pilot | Read-only EventSub/chat; then explicitly enabled commands, basic alerts and selected OBS actions | OAuth/reconnect/dedup/rate tests and local audio recording pass |
| 3. YouTube and parity | streamList/fallback, combined chat, quota display, selected member/paid events and migration drafts | Correct target channel; history/update handling; quotas and provider-specific differences verified |
| 4. Controlled interaction | Reviewed moderation, manageable rewards, timers/counters, phone/voice controls | No audience privilege escalation; receipts/uncertain outcomes and migration ownership tested |
| 5. AI and efficiency | Restricted public Talk replies, summaries, stream profiles and measured resource limits | Prompt-injection/audio privacy/load tests pass; no required cloud or frame-performance regression |
| 6. Full cutover | Workflow-by-workflow activation, live evidence, restore/runbook and release receipts | All required workflows live-verified; successful sessions and rollback rehearsal complete |

Every application implementation release needs both native desktop and `desktop/dist-web` builds, relevant tests, secret scanning before a push, and owner-authorized promotion. When applying an update, install/verify the desktop output and refresh/verify the served website. This planning-only change requires no app build and does not update the live application.

## 13. Verification and release acceptance

- **Functional parity:** commands, aliases, permissions, cooldowns, variables, timing/order, alerts, scenes, moderation and required rewards each have expected-output cases. Local loyalty is labelled separately from platform points.
- **Event reliability:** duplicates, delayed/out-of-order events, self-bot/recursive triggers, test/live state isolation, YouTube combo updates/recent history, Twitch lost-event gaps, chat end and revocation are tested. Crash during processing does not silently duplicate local effects or hide ambiguous external ones.
- **Network/API failures:** disconnect, OBS restart, token expiry/revocation, 429/backoff, quota exhaustion and changed/missing scenes yield honest status and controlled recovery. Old alerts/timers do not flood the stream after reconnect.
- **Privacy:** adversarial viewer messages/role claims cannot access owner tools or memory, including private sessions, retrieval and caches. Overlay output is escaped. No owner credential reaches public clients/logs. Local stream and recording captures demonstrate private speech, reminders, combined control chat and authentication prompts stay private; destination routing respects the reviewed simulcast policy.
- **Performance:** commands/alerts function with all models disabled; load test at 10× measured normal activity with bounded queues. Compare OBS/game performance before and after; record actual latency/resources and optional-AI degradation behavior.
- **Control/recovery:** pause, skip, emergency disable, public mute and authenticated owner actions remain usable during AI stalls. Restore/revoke and one-executor rollback are rehearsed. Undo claims are restricted to genuinely reversible supported actions; sent messages or missed events are not assumed recoverable.
- **Evidence:** separate unit/replay, adapter integration, local audio recording and real broadcast results. Store redacted receipts, software/model versions and known limitations. A green simulated event is not a verified live subscription/reward.

## 14. Cost, decisions and the next implementation packet

Use OBS, direct official platform interfaces and existing local inference first. No additional AI subscription is part of the core design. APIs still have authorization, quota, eligibility and policy requirements; extra destinations, donation services, assets or optional cloud calls can have separate costs. Do not assume paid API capacity or external-account access is authorized.

Before implementation, resolve:

- OBS Studio versus another broadcasting application, selected Twitch/YouTube accounts and whether streams are simultaneous or alternating.
- Grey's five most important existing automations and the full required-workflow inventory, including custom scripts/services.
- Whether ZAE speaks publicly, on which triggers, and what approved channel facts/voice/audio route she can use.
- Bot identity, permitted moderation/reward actions and owner-approved role/scope boundaries.
- Runtime retention and any optional loyalty/analytics features.

The recommended first coding packet is **local fixtures + deterministic actions + read-only OBS health + Stream Studio preview + emergency public mute**, using synthetic events and no platform writes. After that passes, request only the specific account/configuration authorizations needed for the Twitch pilot. Do not start by giving a model broad account or desktop control.
