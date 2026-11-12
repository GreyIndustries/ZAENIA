// What the SE picture shows for each brain (components/tools/seActivity.ts).
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
const mod = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/components/tools/seActivity.ts"), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
vm.runInNewContext(code, { exports: mod, Date, Number, Object });
const { trackUse, readBrain, HOT_MS } = mod;
let count = 0;
const check = (fn) => { fn(); count++; };
// objects built inside the sandbox have their own prototypes, so compare their JSON form
const same = (a, b) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), b);

const T0 = 1_000_000;
const row = (id, until, installed = true) => ({ id, installed, loaded: until === null ? null : { until } });

check(() => {  // first sight of a loaded model: remembered, but we can't say it just answered
  const seen = trackUse({}, [row("talk", "2026-11-05T10:00:00-08:00")], T0);
  same(seen.talk, { until: "2026-11-05T10:00:00-08:00", usedAt: 0 });
  assert.equal(readBrain("talk", row("talk", "2026-11-05T10:00:00-08:00"), seen, T0).state, "loaded");
});
check(() => {  // the keep-alive moved later: it answered just now
  const first = trackUse({}, [row("seek", "2026-11-04T10:30:00-08:00")], T0);
  const second = trackUse(first, [row("seek", "2026-11-04T10:30:09-08:00")], T0 + 4000);
  assert.equal(second.seek.usedAt, T0 + 4000);
  const reading = readBrain("seek", row("seek", "x"), second, T0 + 5000);
  same([reading.state, reading.level, reading.words], ["working", 1, "working now"]);
});
check(() => {  // Talk says "speaking" and the others say "working"
  const seen = { talk: { until: "a", usedAt: T0 } };
  assert.equal(readBrain("talk", row("talk", "a"), seen, T0 + 1000).words, "speaking now");
});
check(() => {  // the same keep-alive time again: nothing new happened, the old mark stays
  const a = trackUse({}, [row("study", "2026-11-04T10:30:00-08:00")], T0);
  const b = trackUse(a, [row("study", "2026-11-04T10:30:05-08:00")], T0 + 4000);
  const c = trackUse(b, [row("study", "2026-11-04T10:30:05-08:00")], T0 + 8000);
  assert.equal(c.study.usedAt, T0 + 4000);
});
check(() => {  // working fades back to loaded after HOT_MS
  const seen = { keep: { until: "a", usedAt: T0 } };
  assert.equal(readBrain("keep", row("keep", "a"), seen, T0 + HOT_MS - 1).state, "working");
  assert.equal(readBrain("keep", row("keep", "a"), seen, T0 + HOT_MS + 1).state, "loaded");
});
check(() => {  // levels: Talk rests lower than the others; ready and missing are dark
  assert.equal(readBrain("talk", row("talk", "a"), {}, T0).level, 0.4);
  assert.equal(readBrain("seek", row("seek", "a"), {}, T0).level, 0.55);
  same(readBrain("study", row("study", null), {}, T0), { level: 0, installed: true, state: "ready", words: "ready, loads when needed" });
  same(readBrain("keep", row("keep", null, false), {}, T0), { level: 0, installed: false, state: "missing", words: "not installed" });
  assert.equal(readBrain("keep", undefined, {}, T0).state, "missing");
});
check(() => {  // a model that unloads is forgotten, so loading it again starts fresh
  const loaded = trackUse({}, [row("study", "a")], T0);
  const gone = trackUse(loaded, [row("study", null)], T0 + 4000);
  same(gone, {});
  const again = trackUse(gone, [row("study", "b")], T0 + 8000);
  assert.equal(again.study.usedAt, 0);
});
check(() => {  // unparseable but changed keep-alive text still counts as an answer; a missing time never throws
  const a = trackUse({}, [row("talk", "soon")], T0);
  const b = trackUse(a, [row("talk", "later")], T0 + 4000);
  assert.equal(b.talk.usedAt, T0 + 4000);
  assert.doesNotThrow(() => trackUse({}, [{ id: "talk", installed: true, loaded: {} }, { id: "seek", installed: true, loaded: true }], T0));
});
console.log(`${count} SE activity checks passed.`);
