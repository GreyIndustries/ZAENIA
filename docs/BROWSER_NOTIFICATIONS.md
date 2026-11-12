# Browser notifications on your phone

ZAE can send visible notifications through your phone browser's Web Push service, including while her page is closed. The PC, ZAE API and internet connection must remain available. ZAE's local assistant and inbox still work without internet. No SMS subscription or paid notification service is required.

## Enable on your phone

1. Open ZAE's existing **HTTPS phone address** and sign in normally. An HTTP LAN address cannot enable Web Push.
2. On iPhone/iPad (16.4+), choose **Share → Add to Home Screen**, then open ZAE from that icon and sign in there.
3. Open **Settings → Notifications**. The same controls appear in **Tasks & Calendar → Reminders** and **Fitness & Health → Training program**.
4. Tap **Turn on notifications here** and allow the phone's notification permission.
5. Tap **Send test** for that device, then check the phone's Notification Center or lock screen.

Only the owner can grant the browser/OS permission on that phone; installing this update on the PC does not grant it. Android and desktop browsers are supported when they implement Push API and service workers. The native Windows app manages registered devices but does not register its embedded browser as a phone.

## Choices and delivery status

- Per device: reminders, calendar events, task deadlines, training reminders, important email, research updates, and other assistant notices. Connecting enables these categories; each can be switched off.
- Message previews default **off**. Notifications then show only “ZAE reminder/update — Open ZAE to view your notification.” Enable previews to show the notice's title and text. The phone's own notification privacy settings still apply.
- Shared **Assistant → Follow-through** pause, Pacific quiet hours, read state and snooze also apply to automatic phone delivery. An explicit test bypasses quiet hours; it is limited to one attempt per device per 30 seconds.
- **Turn off on this device** removes the server registration and browser subscription. It does not alter other browsers or OS permissions. A missing server registration offers **Reconnect**.
- “Accepted by the push service” confirms provider acceptance only. It cannot confirm display, sound, reading, or Focus/Do Not Disturb behavior on the phone. Zero acceptances never appears as a successful test.
- Training times remain in Training program. Important email/research alerts depend on those existing integrations producing a notice; notifications do not connect those accounts or invent alerts.

## Implementation and boundaries

The existing `core/api/web_push.py` VAPID/DPAPI implementation is retained and hardened. Subscription keys must be valid P-256 points and 16-byte auth secrets. Destinations are limited to browser push providers (Apple, Google FCM, Mozilla and Windows notification hosts); arbitrary HTTPS endpoints, credentials in URLs and nonstandard ports are refused. Sending has an 8-second request timeout and refuses HTTP redirects. VAPID contact uses the app's HTTPS origin rather than the former localhost contact; an optional valid `ZAENIA_PUSH_CONTACT` mailto/HTTPS setting can override it. Reconnect older registrations once so they retain their HTTPS origin.

`core/assistant_followthrough/push_delivery.py` reads the canonical inbox, covering both scheduled calendar/task notices and posted notices. It rechecks the existing read/write notification capabilities before taking each inbox snapshot. No model, learned memory or retrieved material grants subscription or execution authority. Existing API authentication and startup authentication are unchanged.

Delivery metadata is in ignored private `data/secure/push_delivery.sqlite3`; browser endpoints/keys remain in the existing ignored subscription file and the VAPID private key remains DPAPI-sealed. The ledger stores only hashed device IDs, notice IDs, generations, attempt counts, sanitized result codes and timestamps. It stores no message bodies, raw endpoints or credentials. API status omits endpoint URLs and keys.

Per-device SQLite claims prevent concurrent workers/restarts from routinely resending accepted notices. Network/temporary errors retry with exponential backoff (30 seconds up to 15 minutes, maximum 8 attempts), only while the current inbox item is eligible. A 120-second claim lease recovers a crashed sender. HTTP 404/410 removes expired subscriptions; permanent subscription/auth/payload failures stop that notice and appear in status. A crash after provider acceptance but before the receipt is saved can cause a duplicate; stable notification tags reduce duplicate displayed cards. This is best-effort delivery, not a guarantee of exactly-once display.

At most ten actual sends occur per worker pass; work stays off request/UI threads. Source cancellation, read, quiet hours, category filters, pause, snooze and expiry suppress subsequent automatic attempts. Provider TTL is bounded by the current notice's remaining validity, up to one hour. Old delivery metadata is pruned after 90 days; payloads never enter that ledger.

Training reminders now post through the same canonical inbox with a stable date/title identity and a 30-minute validity window, giving them the same delivery controls and restart deduplication. Nothing changes the training plan or nutrition calculations.

## Verification and rollout

Implemented and tested in isolation: due calendar/task routing, restart and concurrent-worker deduplication, per-device retries, pause/quiet/snooze/read suppression, category filtering, private previews, expired subscriptions, targeted tests/rate limiting, endpoint/key validation, no redirects, timeouts and API authentication/scope checks. Browser simulation covers permission timing, registration scope, failed registration repair, disable, status and safe notification clicks. Live phone receipt still requires the owner's permission tap and test on that phone.

Verification/build/install results are recorded in the master build plan, section 28. Rollback is a code revert plus rebuilding the browser and desktop apps; no personal reminder or calendar records are deleted. Previous installed executables are retained by the normal desktop updater.

Primary references checked 2026-10-25: [WebKit iPhone/iPad requirements](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/), [MDN Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API), and [pywebpush transport API](https://github.com/web-push-libs/pywebpush).
