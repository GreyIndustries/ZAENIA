# Browser briefing and voice sign-in

Open the existing Zae phone app at its secure `/app/` address. Choose **Brief me**
to generate and hear a fresh schedule, weather, and traffic briefing. **Refresh**
requests another full briefing, even if an earlier daily briefing was already
played. An empty schedule says **“Nothing on schedule.”** Playback controls stay
available if the phone requires another tap to start audio.

The Windows desktop app also has **Brief me**. Its audio is fetched through
the existing private desktop bridge, so credentials stay outside the page.
After building the Windows release, `scripts/update_desktop_app.ps1` updates
the installed copy, keeps a backup, and reopens Zae.

## One-time voice setup

The enrolled voice profile is encrypted. On the PC that hosts Zae, run
`scripts/enable_mobile_voice.ps1`, or:

```powershell
.\.venv\Scripts\python.exe -m core.api.mobile_voice_profile enable
```

Enter the owner passkey in that local console. Setup seals only the enrolled
voice embedding and existing calibrated threshold to the current Windows
account. It does not store the passphrase or an API token. No re-enrollment is
needed when the existing profile and calibration are valid.

On the phone, choose **Verify my voice**, then **Record these words**. Read all
six displayed words and tap **Verify voice**. The PC checks both the spoken
words and the enrolled speaker before creating a browser session. Audio is
processed locally in memory and discarded; no raw recording is saved.

The browser also still accepts the existing access token. **Forget this phone**
revokes its voice session and removes its saved token. Voice sessions expire
after 30 minutes without activity or 8 hours in total, and after a server restart.

## Access boundaries

Voice sign-in uses an HttpOnly, SameSite Strict cookie over the secure app
connection. Prompts expire after 90 seconds, are bound to the requesting browser
and peer, and are consumed on the first verification attempt. Attempts are rate
limited. The existing per-operation client gate still applies. Voice sign-in
does not issue a desktop approval key or an owner passkey session.

Disable mobile voice sign-in and revoke its sessions on the PC with:

```powershell
.\.venv\Scripts\python.exe -m core.api.mobile_voice_profile disable
```

Changes to the owner credential, enrolled speaker profile, or calibration
invalidate the sealed reference and require setup again. The same speaker
threshold is preserved; matching from the phone's microphone needs a live
acceptance check. A fresh prompt rejects a recording made for a different
prompt; it is not a general defense against synthetic or relayed voices.

The browser uses `/api/briefing`, `/api/briefing/audio`, and
`/api/briefing/played`. Existing CarPlay endpoints remain compatible.

## Verification

Automated checks use simulated speaker matches, audio, and isolated stores.
Run `python -m unittest core.api.mobile_auth_test core.api.browser_briefing_test`
with the project environment, and `node scripts/mobile-browser.test.cjs` from
`desktop`. Build the phone app with `npm run build:web` from `desktop`.
`python -m scripts.mobile_ui_preview` serves the isolated sample UI on port
8878; its known fixture token must never be used by the real service.
