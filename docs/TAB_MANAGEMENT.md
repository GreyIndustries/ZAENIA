# Zae tab management

Select **Manage tabs** at the top of the workspace. The manager lists open,
minimized, and closed tabs. Open, focus, restore, or close a tab from its row.
Use **Minimize all**, **Restore all**, or **Close all** for the workspace.

Select a tab to adjust its width and height independently, place it in a corner,
center it, or maximize it. Drag any edge or corner to resize directly. Resize
handles also accept arrow keys; Shift uses a larger step. Double-click the title
bar or use its square button to maximize or restore the previous size.
Positions and sizes remain within the workspace and are saved on this device.

Spoken and typed commands use the same immediate layout handler. Pointing at a
tab or working in its fields makes it the target of **it**, **this tab**, and
**the current tab**. Clicking the chat or microphone preserves that target.
Closed or minimized tabs are skipped when resolving a normal current-tab
command, with the active visible tab as fallback. With no visible tab, Zae says
there is no open tab to change. Naming a tab explicitly selects that tab.

Examples:

- **Close all:** “close all”, “shut all windows”, “close every tab”.
- **Minimize all:** “minimize all”, “hide everything”, “put all tabs away”.
- **Close the current tab:** “close it”, “close this tab”, “close the tab I'm working on”.
- **Minimize the current tab:** “minimize”, “hide this window”, “tuck it away”.
- **Move:** “put in right top corner”, “move it to the upper right”, “dock this window at the lower left”.
- **Resize:** “make it bigger”, “make it wider”, “make this tab narrower”, “make it taller”, “make it shorter”.
- **Restore:** “restore all tabs”, “bring everything back”.

The manager's **Voice command examples** section shows alternatives. A catalog
of 44 paraphrases is checked against the parser. Corner directions accept both
“top right” and “right top”. Width-only and height-only commands preserve the
other dimension. Unsupported exceptions such as “close all except Calendar”
are not silently treated as “close all”. Commands apply to Zae's workspace tabs.

Verification includes parser, geometry, attention routing, and browser checks
for contextual targeting after clicking chat, independent resizing, bulk
minimize/restore/close, and availability of the manager after closing all tabs.
