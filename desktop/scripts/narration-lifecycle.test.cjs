// Exercise the real chat lifecycle callbacks with simulated state, without an app or API.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const assert = require("node:assert/strict"), ts = require("typescript");
const source = ts.createSourceFile("App.tsx", fs.readFileSync(path.join(__dirname, "../src/App.tsx"), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
function callback(name) {
  let found;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === name) found = node.getText(source);
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === name && node.initializer && ts.isArrowFunction(node.initializer)) found = `const ${name} = ${node.initializer.getText(source)};`;
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(found, `Missing production callback: ${name}`);
  return found;
}
const callbacks = ts.transpileModule(["interrupt", "end", "complete", "fail"].map(callback).join("\n"), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
function scenario(action, added = true) {
  const reply = { id: 1, text: "", added, at: "2026-11-04T12:00:00Z", progress: ["I'm looking at the file now."] };
  const state = { chat: added ? [{ ...reply, role: "assistant", streaming: true }] : [], cancelled: false, sending: true, streaming: 1 };
  class BridgeError extends Error {}
  const context = {
    reply, id: 1, key: "m1", live: () => true, timer: null, filler: null, photoQuestion: false, speakIt: false,
    speech: { stop() {} }, voice: {}, messageCounter: { current: 1 }, BridgeError, errorText: String,
    streamRef: { current: { cancel() { state.cancelled = true; } } }, sendingRef: { current: true },
    replyRef: { current: reply }, turnRef: { current: 1 }, followUntil: { current: 0 }, FOLLOW_UP_MS: 1000,
    setChat(update) { state.chat = update(state.chat); }, setSending(value) { state.sending = value; },
    setStreamingId(value) { state.streaming = value; }, Date,
  };
  vm.runInNewContext(callbacks + `\n${action}`, context);
  assert.equal(state.sending, false);
  assert.equal(state.streaming, null);
  const saved = state.chat.find(message => message.id === 1);
  assert.ok(saved);
  assert.equal(saved.streaming, false);
  assert.equal(saved.progress[0], reply.progress[0]);
  assert.equal(context.replyRef.current, null);
  return state;
}
assert.equal(scenario("interrupt();").cancelled, true);
assert.equal(scenario("interrupt();", false).chat[0].interrupted, true);
assert.equal(scenario('complete("", false);').chat[0].interrupted, false);
const failed = scenario('fail(new Error("reader unavailable"));');
assert.equal(failed.chat[0].interrupted, true);
assert.equal(failed.chat[1].role, "error");
assert.match(failed.chat[1].text, /reader unavailable/);
console.log("4 progress-only lifecycle scenarios passed: Stop, early Stop, empty completion, and failure.");
