// When the neural core animates (Claude, 2026-11-11): pure decisions only, no browser or owner data.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const ts = require("typescript");
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core/coreVisibility.ts"), "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject });
const { samplePoints, fullyCovered, coreVisible, renderScale, OPAQUE_SURFACES } = exportsObject;
let checks = 0;
function check(run) { run(); checks++; }
const on = { connected: true, onScreen: true, width: 800, height: 450 };

check(() => assert.deepEqual(JSON.parse(JSON.stringify(samplePoints({ left: 0, top: 0, width: 100, height: 50 }))), [[50, 25], [20, 10], [20, 40], [80, 10], [80, 40]]));
check(() => assert.equal(fullyCovered(["opaque", "opaque", "opaque", "opaque", "opaque"]), true));
check(() => assert.equal(fullyCovered(["opaque", "opaque", "core", "opaque", "opaque"]), false, "a visible corner keeps it running"));
check(() => assert.equal(fullyCovered(["opaque", "other", "opaque", "opaque", "opaque"]), false, "translucent layers never pause it"));
check(() => assert.equal(fullyCovered(["outside", "opaque", "outside", "opaque", "outside"]), true, "off-viewport points are ignored"));
check(() => assert.equal(fullyCovered(["outside", "outside", "outside", "outside", "outside"]), false));
check(() => assert.equal(coreVisible({ ...on, hits: ["core", "core", "core", "core", "core"] }), true));
check(() => assert.equal(coreVisible({ ...on, hits: Array(5).fill("opaque") }), false, "under a window or sheet"));
check(() => assert.equal(coreVisible({ ...on, connected: false, hits: [] }), false, "between slots"));
check(() => assert.equal(coreVisible({ ...on, onScreen: false, hits: ["core"] }), false, "scrolled away"));
check(() => assert.equal(coreVisible({ ...on, width: 0, hits: ["core"] }), false, "collapsed"));
check(() => assert.equal(renderScale(560, 824), 0.68, "orbit view draws at its shown size"));
check(() => assert.equal(renderScale(1800, 824), 1, "zooming in never enlarges the buffer"));
check(() => assert.equal(renderScale(10, 824), 0.25));
check(() => assert.equal(renderScale(100, 0), 1));
check(() => assert.match(OPAQUE_SURFACES, /\.os-window/));
check(() => assert.match(OPAQUE_SURFACES, /\.navhub--workspace/));
check(() => assert.doesNotMatch(OPAQUE_SURFACES, /orbit/, "orbit view is glass, not opaque"));
console.log(`core visibility: ${checks} checks passed`);

// C1 docked orb layout: the rings fill the small 96 px drawing box without spilling out; Home layout unchanged.
{
  const load = (file, sandbox) => { const out = {}; vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, file), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText, { exports: out, require: sandbox, Math, Float32Array }); return out; };
  const wake = load("../src/core/coreWake.ts", () => ({}));
  const field = load("../src/components/core/neuralField.ts", () => wake);
  const mic = field.computeLayout(96, 96, true);
  check(() => assert.ok(mic.r * field.RING_OUTER <= 48 && mic.r * field.RING_OUTER > 44, `rings fill the 96 px orb box: ${mic.r}`));
  check(() => assert.equal(mic.cx, 48)); check(() => assert.equal(mic.cy, 48));
  const home = field.computeLayout(824, 458, true);
  check(() => assert.ok(home.r >= 48 && home.cy === 458 * 0.45, "Home layout unchanged"));
  console.log(`core orb layout: ${checks} checks passed in total`);
}
