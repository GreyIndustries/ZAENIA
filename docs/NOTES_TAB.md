# Notes — API 0.9.1

Open **Notes** in ZAE's main sidebar or phone tab bar. Select **New note**, add
a title and text, then **Save note**. Saved notes persist on the PC and are
available through the existing authenticated API on paired devices.

- Search matches titles and text, including Unicode case-insensitive matches.
- Pinned notes appear first. Notes support up to 30,000 characters each.
- Archive keeps a note recoverable. Select **Show archived notes**, open it,
  then **Restore note**. There is no permanent-delete action in this tab.
- **Let ZAE reference this note in relevant conversations** is off for new
  notes. Opted-in active notes can supply relevant excerpts to conversation.
  Archived notes do not enter that context.
- “Search my notes for spare tire” explicitly searches active saved notes,
  including notes that are not opted into automatic conversation reference.
- “Open my notes” opens the window through the app's existing layout controls.
  Notes can move, resize, minimize and travel in named workspace layouts.
- Notes are included in encrypted portable profile version 3. Existing versions
  1 and 2 still restore. Profile size limits and local owner authentication stay
  in effect.

Edits save explicitly. A draft stays in memory while moving between tabs or
closing/reopening the Notes window during the current app session. Closing or
reloading the app with unsaved edits requests the browser's standard warning
where supported; unsaved drafts are not written to browser storage. Save before
quitting. Typing updates the editor without rerendering the whole neural core.

Concurrent edits use the saved revision: an outdated device cannot silently
overwrite another device's changes. If a save reports a conflict, the editor
keeps your text. Copy any changes you need, then **Discard edits** to load the
latest saved version before merging and saving again.

Storage is the existing private
`data/assistant_platform/platform.sqlite3`, record kind `note`. Notes use the
existing `memory.read` / `memory.write` permissions. Notes are reference data,
never execution instructions or permission. No startup authentication, model
provider, microphone, camera, or deletion policy was changed.

Validation: 313 backend checks and 183 frontend checks passed; TypeScript,
web and Windows release builds succeeded. Isolated browser checks covered
create/save, pin/reference choices, draft survival across window reopening,
archive/restore, content search, saved-note persistence after reload, and a
390px phone layout. Notes/editor widths matched their scroll widths on desktop
and phone. Screenshots `notes-preview.png` and `notes-mobile-preview.png` contain
only temporary sample data. No notes were added to the owner's real data.

The running API reported version 0.9.1 at the final check. Restart the desktop
app normally, or reload the phone page, to load the new Notes interface if it is
not yet visible. Existing startup authentication remains required; this work did
not stop or change authentication for the running API.
