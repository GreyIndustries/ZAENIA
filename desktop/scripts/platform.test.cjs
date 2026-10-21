// Pure routing/gesture checks: no live camera, credentials, or model calls.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
function compile(file, modules = {}) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core", file), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
  vm.runInNewContext(code, { exports, require: name => { if (!(name in modules)) throw new Error(name); return modules[name]; }, Date, Intl });
  return exports;
}
const model = compile("platformModel.ts"), gestures = compile("handGestures.ts"), task = compile("taskModel.ts"), actions = compile("assistantActions.ts", { "./taskModel": task });
let count = 0; const check = run => { run(); count++; };
const summary = { jobs: [{ id: "abc", title: "Priority analysis", priority: true, status: "running", stage: "Analyzing", detail: "Local sources", completedUnits: null, totalUnits: null, elapsedSeconds: 12 }], policy: { voiceAutomatic: ["task.create"], chatAutomatic: [] }, metrics: { firstTextP50Ms: 90, firstTextP95Ms: null, samples: [] }, activeWorkspace: null };
check(() => assert.equal(model.parsePlatformSummary(summary).jobs[0].priority, true));
check(() => assert.equal(model.jobPercent(summary.jobs[0]), null));
check(() => assert.equal(model.jobPercent({ completedUnits: 5, totalUnits: 10 }), 50));
check(() => assert.equal(model.jobPercent({ completedUnits: 50, totalUnits: 10 }), 100));
check(() => assert.equal(model.jobPercent({ completedUnits: 0, totalUnits: 0 }), null));
check(() => assert.equal(model.parsePlatformSummary({ ...summary, policy: { voiceAutomatic: ["files.delete", "app.launch"], chatAutomatic: [] } }).policy.voiceAutomatic.join(","), "app.launch"));
check(() => assert.equal(model.parsePlatformSummary(null), null));
check(() => assert.equal(model.parsePlatformSummary({ ...summary, jobs: [{ id: "../evil", title: "x", stage: "x", status: "running" }] }).jobs.length, 0));
check(() => assert.equal(model.parsePlatformSummary({ ...summary, metrics: { firstTextP50Ms: NaN, firstTextP95Ms: -2 } }).metrics.firstTextP50Ms, null));
check(() => {
  const data = { "zaenia.shellWindows": "[]", "zaenia.phone.token": "must-not-travel", "zaenia.autoRecovery": "1" };
  assert.equal(JSON.stringify(model.displayPreferences({ getItem: name => data[name] ?? null })), '{"zaenia.shellWindows":"[]"}');
});
const launch = { kind: "app.launch", title: "Open registered target", parameters: { id: "123abc", name: "Blender" } };
const workspace = { kind: "workspace.restore", title: "Restore Coding", parameters: { id: "123abc", name: "Coding", revision: 2 } };
check(() => assert.ok(actions.parseAssistantProposal(launch)));
check(() => assert.equal(actions.parseAssistantProposal({ ...launch, parameters: { ...launch.parameters, command: "arbitrary" } }), null));
check(() => assert.equal(actions.parseAssistantProposal({ ...launch, parameters: { ...launch.parameters, id: "../../escape" } }), null));
check(() => assert.equal(actions.confirmedAssistantAction(launch, { id: "other", name: "Blender", status: "opened" }), null));
check(() => assert.ok(actions.confirmedAssistantAction(launch, { id: "123abc", name: "Blender", status: "launched" })));
check(() => assert.ok(actions.parseAssistantProposal(workspace)));
check(() => assert.equal(actions.parseAssistantProposal({ ...workspace, parameters: { ...workspace.parameters, revision: 0 } }), null));
check(() => assert.equal(actions.confirmedAssistantAction(workspace, { workspace: { id: "123abc", name: "Coding", revision: 3 }, apps: [] }), null));
check(() => assert.ok(actions.confirmedAssistantAction(workspace, { workspace: { id: "123abc", name: "Coding", revision: 2 }, apps: [{ status: "failed" }] }).includes("Some registered apps")));
check(() => assert.equal(gestures.classifyHand(Array(21).fill({ x: 0, y: 0 })), null));
check(() => assert.equal(gestures.classifyHand([{ x: 0, y: 0 }]), null));
check(() => {
  const engine = new gestures.GestureInterpreter();
  assert.equal(engine.update({ kind: "palm", x: .5, y: .5, span: 1 }, 0).length, 0);
  assert.equal(engine.update({ kind: "palm", x: .5, y: .5, span: 1 }, 300).length, 0);
  assert.equal(engine.update({ kind: "palm", x: .5, y: .5, span: 1 }, 500)[0].kind, "stop");
  assert.equal(engine.update({ kind: "palm", x: .5, y: .5, span: 1 }, 4000).length, 0);
});
check(() => {
  const engine = new gestures.GestureInterpreter();
  assert.equal(engine.update({ kind: "pinch", x: .5, y: .5, span: .1 }, 0)[0].kind, "move");
  assert.equal(engine.update(null, 100)[0].kind, "release");
  assert.equal(engine.update(null, 200).length, 0);
});
check(() => {
  const engine = new gestures.GestureInterpreter();
  assert.equal(engine.update({ kind: "point", x: .5, y: .5, span: .8 }, 0).length, 0);
  assert.equal(engine.update({ kind: "point", x: .5, y: .5, span: .8 }, 260)[0].kind, "point");
});
check(() => {
  const engine = new gestures.GestureInterpreter();
  engine.update({ kind: "fist", x: .3, y: .5, span: .5 }, 0);
  assert.equal(engine.update({ kind: "fist", x: .35, y: .5, span: .5 }, 200).length, 0);
  assert.equal(engine.update({ kind: "fist", x: .6, y: .5, span: .5 }, 300)[0].kind, "next");
  assert.equal(engine.update({ kind: "fist", x: .9, y: .5, span: .5 }, 400).length, 0);
});
console.log(`${count} assistant platform and gesture checks passed.`);
