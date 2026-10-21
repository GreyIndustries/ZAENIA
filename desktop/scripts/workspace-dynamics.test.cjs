// Layout decisions only: no microphone, live API, or personal data.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const ts = require("typescript");
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core/workspaceDynamics.ts"), "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject });
const { workspacePhase, workspaceLayout, parseWorkspaceSettings, boundedConversationSize, DEFAULT_WORKSPACE } = exportsObject;
let checks = 0;
function check(run) { run(); checks++; }

check(() => assert.equal(workspacePhase({}), "idle"));
check(() => assert.equal(workspacePhase({ sending: true }), "thinking"));
check(() => assert.equal(workspacePhase({ transcribing: true }), "thinking"));
check(() => assert.equal(workspacePhase({ preparingSpeech: true }), "thinking"));
check(() => assert.equal(workspacePhase({ speaking: true, sending: true }), "speaking"));
check(() => assert.equal(workspacePhase({ hearing: true, speaking: true, sending: true }), "listening"));

const idle = workspaceLayout(DEFAULT_WORKSPACE, "idle", false, true);
const thinking = workspaceLayout(DEFAULT_WORKSPACE, "thinking", false, true);
check(() => assert.equal(idle.conversationVh, 36));
check(() => assert.ok(thinking.conversationVh > idle.conversationVh, "Writing an answer should make room for the conversation"));
check(() => assert.ok(thinking.coreScale < idle.coreScale));
check(() => assert.ok(workspaceLayout(DEFAULT_WORKSPACE, "listening", false, true).coreScale > 1));
check(() => assert.ok(workspaceLayout(DEFAULT_WORKSPACE, "idle", true, true).conversationVh > idle.conversationVh));
for (const phase of ["idle", "listening", "thinking", "speaking"]) {
  check(() => assert.equal(workspaceLayout(DEFAULT_WORKSPACE, phase, true, false).conversationVh, 36, "Reduced motion keeps the split stable"));
  check(() => assert.equal(workspaceLayout({ adaptive: false, conversationVh: 48 }, phase, true, true).conversationVh, 48, "Turning adaptive off preserves the chosen size"));
}
check(() => assert.equal(workspaceLayout({ adaptive: true, conversationVh: 58 }, "thinking", true, true).conversationVh, 58));
check(() => assert.equal(boundedConversationSize(-400), 26));
check(() => assert.equal(boundedConversationSize(400), 58));
check(() => assert.equal(boundedConversationSize(NaN), 36));
check(() => assert.equal(boundedConversationSize(Infinity), 36));
for (const malformed of [null, "", "{bad}", "[]", "null", "false", '{"adaptive":"yes","conversationVh":"999"}']) {
  check(() => { const settings = parseWorkspaceSettings(malformed); assert.equal(settings.adaptive, true); assert.equal(settings.conversationVh, 36); });
}
check(() => { const settings = parseWorkspaceSettings('{"adaptive":false,"conversationVh":100}'); assert.equal(settings.adaptive, false); assert.equal(settings.conversationVh, 58); });
check(() => { const settings = parseWorkspaceSettings('{"adaptive":true,"conversationVh":30}'); assert.equal(settings.adaptive, true); assert.equal(settings.conversationVh, 30); });
console.log(`${checks} workspace behavior checks passed.`);
