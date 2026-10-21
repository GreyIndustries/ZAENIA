/** Curated paraphrases, also checked against the command parser in tests. */
export const LAYOUT_PHRASES = [
  { intent: "close", label: "Close all tabs", examples: ["close all", "close all tabs", "shut all windows", "close everything", "close every tab"] },
  { intent: "minimize", label: "Minimize all tabs", examples: ["minimize all", "minimise all windows", "hide everything", "hide all of them", "put all tabs away"] },
  { intent: "close", label: "Close the tab in use", examples: ["close it", "close this tab", "close the active window", "close the tab I'm working on", "close the one I'm looking at", "get rid of this panel"] },
  { intent: "minimize", label: "Minimize the tab in use", examples: ["minimize", "minimize it", "hide this window", "tuck it away", "put this out of the way", "minimize the current tab"] },
  { intent: "place", label: "Move the tab in use", examples: ["put in right top corner", "move it to the upper right", "put the active tab in the top right corner", "dock this window at the lower left", "move the tab I'm working on to the right top corner", "put it in the center"] },
  { intent: "size", label: "Change size", examples: ["make it bigger", "make this tab a bit smaller", "shrink this window", "expand it", "make it wider", "make this tab narrower", "make the current tab taller", "make it shorter", "make it more compact"] },
  { intent: "maximize", label: "Maximize", examples: ["maximize it", "make this tab full screen", "full screen the active tab"] },
  { intent: "restore", label: "Bring tabs back", examples: ["restore all tabs", "restore every window", "bring all tabs back", "bring everything back"] },
] as const;
