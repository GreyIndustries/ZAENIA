# Editable daily duty status

Open **Calendar**, select a date, choose **Duty status**, then **Save status**.

Choices:

- On duty
- Off duty / DONSA
- School / class
- On leave
- Use calendar status — clears your selection for that date and returns to the
  existing calendar rules.

Each selection is saved for that calendar date and takes priority over inferred
duty status. Calendar events and reminders remain independent. An amber dot marks
days with a saved selection. Changing months selects the first day of the new
month so the editor always has that month's status data.

The status is available to the existing calendar/briefing context and, when
calendar-reading permission is granted, to ZAE's conversation context for today.
Questions such as “Am I on duty tomorrow?” read calendar status directly. A daily
status does not establish specific duty/class hours or the owner's location.

Storage is local: `data/duty_status/overrides.json`, protected for the current
Windows account and SYSTEM. Writes are atomic and refuse stale revisions, so one
open window cannot silently overwrite another window's changes. Editing uses the
existing authenticated `ui.calendar.write` scope; reading uses `calendar.read`.
The owner calendar YAML, Google events and startup authentication are unchanged.

Verification: 261 isolated backend regression tests passed, including 11 new duty
status scenarios. Production web and native Windows release builds succeeded.
The browser fixture verified saving Off duty / DONSA, persistence after reload,
and changing the same date to School / class. Only isolated sample dates/data
were changed during verification; no real duty selection was made for the owner.

Restart the API and reopen the rebuilt desktop app to load the new route/UI.
The same editor is available in the rebuilt phone web app.

Pre-change source copies: `backups/duty-status-20261018/source/`.
