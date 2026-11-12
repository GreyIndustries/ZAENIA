// Finger-snap detector (core/snapDetector.ts): synthetic energy frames, no microphone.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
const mod = {}; vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core/snapDetector.ts"), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText, { exports: mod, Math, Number, Infinity });
const { SnapDetector } = mod;
let count = 0; const check = run => { run(); count++; };
// frames every 20 ms: [bright, low]; quiet room, then bursts
const room = [0.0004, 0.002];
function play(spec, ms) { const d = new SnapDetector(); const events = []; for (let t = 0; t <= ms; t += 20) { const [b, l] = spec(t); const e = d.update(b, l, t); if (e) events.push([e, t]); } return events; }
const snapAt = (...times) => t => times.some(x => t === x) ? [0.05, 0.004] : times.some(x => t === x + 20) ? [0.004, 0.003] : room;

check(() => assert.deepEqual(play(snapAt(1000), 2500).map(e => e[0]), ["single"]));
check(() => assert.deepEqual(play(snapAt(1000, 1300), 2500).map(e => e[0]), ["double"]));
check(() => assert.deepEqual(play(snapAt(1000, 2000), 3500).map(e => e[0]), ["single", "single"]));   // too far apart for a double
check(() => assert.deepEqual(play(snapAt(1000, 1060), 2500).map(e => e[0]), ["single"]));              // one burst can't count twice
check(() => assert.deepEqual(play(() => room, 3000), []));
check(() => assert.deepEqual(play(t => t >= 1000 && t < 1800 ? [0.05, 0.4] : room, 3000), []));        // speech: low-heavy, not a snap
check(() => assert.deepEqual(play(t => t >= 1000 && t < 1400 ? [0.05, 0.004] : room, 3000), []));      // a long loud sound doesn't drop away at once
check(() => assert.deepEqual(play(snapAt(1000), 2500).length, 1));
check(() => assert.deepEqual(play(() => [NaN, 1], 500), []));
check(() => { const d = new SnapDetector(); assert.equal(d.update(-1, 1, 0), null); });
console.log(`${count} snap detector checks passed.`);
