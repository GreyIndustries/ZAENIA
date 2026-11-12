// Run the actual briefing component with controlled hooks, events and deferred API results.
// No server, browser, audio device or additional testing library is required.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const assert = require("node:assert/strict"), ts = require("typescript");
const componentPath = path.join(__dirname, "../src/components/phone/BrowserBriefing.tsx");
const source = fs.readFileSync(componentPath, "utf8");
const componentCode = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const appText = fs.readFileSync(path.join(__dirname, "../src/App.tsx"), "utf8");
const app = ts.createSourceFile("App.tsx", appText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let invocation;
function visit(node) {
  if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(app) === "BrowserBriefing") invocation = node.getText(app);
  ts.forEachChild(node, visit);
}
visit(app);
assert.ok(invocation, "The live app must mount BrowserBriefing");
const runtime = { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
const appExports = {};
const beforePlay = () => {};
const onActive = () => {};
vm.runInNewContext(ts.transpileModule(`export function screen(isPhone: boolean) { return ${invocation}; }`, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText, {
  exports: appExports, require: () => runtime, BrowserBriefing: "BrowserBriefing", onAuthLost: undefined,
  setBriefingActive: onActive, speech: { stop: beforePlay },
});

function setup(isPhone) {
  const slots = [], listeners = new Map(), requests = [], exports = {};
  let cursor = 0, effects = [], sequence = 0;
  const hooks = {
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial;
      return [slots[index], next => { slots[index] = typeof next === "function" ? next(slots[index]) : next; }];
    },
    useRef(initial) { const index = cursor++; return slots[index] ?? (slots[index] = { current: initial }); },
    useEffect(effect, dependencies) {
      const index = cursor++, old = slots[index];
      if (!old || !dependencies || dependencies.some((value, i) => value !== old.dependencies[i])) {
        slots[index] = { dependencies };
        effects.push(() => { old?.cleanup?.(); slots[index].cleanup = effect(); });
      }
    },
  };
  class BridgeError extends Error {}
  const api = (method, url, body) => new Promise((resolve, reject) => requests.push({ method, url, body, resolve, reject }));
  vm.runInNewContext(componentCode, {
    exports, require(name) {
      if (name === "react") return hooks;
      if (name === "react/jsx-runtime") return runtime;
      if (name.endsWith("/bridge")) return { api, BridgeError, errorText: String, briefingAudio() { throw new Error("Audio was not requested"); } };
      if (name.endsWith("/speech")) return { SILENT_WAV: "silent" };
      if (name.endsWith("/briefRequest")) return { BRIEF_EVENT: "zae:brief" };
      if (name.endsWith(".css")) return {};
      throw new Error(`Unexpected dependency: ${name}`);
    },
    window: {
      addEventListener(name, callback) { listeners.set(name, callback); },
      removeEventListener(name) { listeners.delete(name); },
    },
    crypto: { randomUUID: () => `request-${++sequence}` }, URL, Set, Boolean, Date,
  });
  const props = appExports.screen(isPhone).props;
  function render() {
    cursor = 0; effects = [];
    const tree = exports.BrowserBriefing(props);
    effects.forEach(effect => effect());
    return tree;
  }
  const ask = () => { assert.ok(listeners.has("zae:brief")); listeners.get("zae:brief")(); };
  return { render, ask, requests };
}
function descendants(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(descendants);
  return [node, ...descendants(node.props?.children)];
}
const toggle = tree => descendants(tree).find(node => node.props?.className === "browser-briefing__toggle");
// Drain promises crossing the VM realm before re-rendering the completed request.
const settled = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  const desktop = setup(false);
  assert.equal(toggle(desktop.render()), undefined, "Desktop keeps its word-triggered brief without a toggle button");
  const phone = setup(true);
  assert.equal(toggle(phone.render()).type, "button", "The actual app wiring retains the phone button");

  desktop.ask();
  desktop.ask();
  assert.equal(desktop.requests.length, 1, "Immediate duplicate requests share the in-flight generation");
  desktop.render();
  desktop.ask();
  assert.equal(desktop.requests.length, 1, "Re-rendering while busy does not bypass inFlight");
  desktop.requests[0].resolve({ session_id: "first", generated_at: "2026-11-07T19:00:00Z", briefing_text: "Old schedule", audio_ready: false });
  await settled();
  let tree = desktop.render();
  assert.equal(descendants(tree).find(node => node.props?.id === "browser-briefing-panel").props.hidden, false);

  desktop.ask();
  assert.equal(desktop.requests.length, 2, "An explicit request refreshes an already-open completed brief");
  assert.notEqual(desktop.requests[0].body.request_id, desktop.requests[1].body.request_id, "Refresh receives a new request identity");
  desktop.ask();
  assert.equal(desktop.requests.length, 2, "The refreshed generation is also protected from duplicates");
  desktop.requests[1].resolve({ session_id: "second", generated_at: "2026-11-07T19:05:00Z", briefing_text: "Updated schedule", audio_ready: false });
  await settled();
  tree = desktop.render();
  assert.equal(descendants(tree).find(node => node.props?.className === "browser-briefing__text").props.children, "Updated schedule");
  console.log("Briefing lifecycle passed: fresh repeated requests, in-flight suppression, updated content and phone-only button.");
})().catch(error => { console.error(error); process.exitCode = 1; });
