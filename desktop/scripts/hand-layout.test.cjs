// Exercise actual window layout behavior with synthetic hand transforms.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict");
const ts = require(require.resolve("typescript", { paths: [__dirname, path.join(__dirname, "../../desktop")] }));
const mod = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core/windowLayout.ts"), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
vm.runInNewContext(code, { exports: mod, Math, Number });
const { handWindowRect, boundedWindow, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT } = mod;
const plain = value => JSON.parse(JSON.stringify(value));
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-10, `${a} differs from ${b}`);
const within = r => { for (const value of Object.values(r)) assert.ok(Number.isFinite(value)); assert.ok(r.w >= MIN_WINDOW_WIDTH && r.w <= 1); assert.ok(r.h >= MIN_WINDOW_HEIGHT && r.h <= 1); assert.ok(r.x >= 0 && r.y >= 0); assert.ok(r.x + r.w <= 1 + 1e-12); assert.ok(r.y + r.h <= 1 + 1e-12); };
let count = 0; function check(name, run) { run(); count++; console.log(`  OK ${name}`); }
const rect = { x: .25, y: .2, w: .4, h: .4 }, viewport = { width: 1600, height: 1000 }, stage = { width: 800, height: 800 };
check("maps normalized viewport deltas into stage dimensions", () => {
  const out = handWindowRect(rect, { dx: .025, dy: .04, scale: 1 }, viewport, stage);
  near(out.x, .3); near(out.y, .25); near(out.w, .4); near(out.h, .4);
});
check("movement increments compose without changing size", () => {
  let out = rect; for (let i = 0; i < 4; i++) out = handWindowRect(out, { dx: .01, dy: -.01, scale: 1 }, viewport, stage);
  near(out.x, .33); near(out.y, .15); near(out.w, rect.w); near(out.h, rect.h);
});
check("two-hand scaling preserves the center away from screen boundaries", () => {
  const out = handWindowRect(rect, { dx: 0, dy: 0, scale: 1.2 }, viewport, stage);
  near(out.x + out.w / 2, rect.x + rect.w / 2); near(out.y + out.h / 2, rect.y + rect.h / 2);
  near(out.w, .48); near(out.h, .48);
  const shrunk = handWindowRect(out, { dx: 0, dy: 0, scale: 1 / 1.2 }, viewport, stage);
  for (const key of ["x", "y", "w", "h"]) near(shrunk[key], rect[key]);
});
check("translation and scale combine around the translated center", () => {
  const out = handWindowRect(rect, { dx: .025, dy: .04, scale: 1.2 }, viewport, stage);
  near(out.x + out.w / 2, rect.x + rect.w / 2 + .05); near(out.y + out.h / 2, rect.y + rect.h / 2 + .05);
});
check("extreme transforms keep every window within the reachable stage", () => {
  for (const dx of [-1e300, -.1, 0, .1, 1e300]) for (const dy of [-1e300, .1, 1e300]) for (const scale of [-1e300, .001, 1, 1e300]) {
    within(handWindowRect(rect, { dx, dy, scale }, viewport, stage));
    within(handWindowRect(rect, { dx, dy, scale }, { width: Number.MAX_VALUE, height: Number.MAX_VALUE }, { width: Number.MIN_VALUE, height: Number.MIN_VALUE }));
  }
  near(handWindowRect(rect, { dx: 0, dy: 0, scale: 100 }, viewport, stage).w, .5);
  near(handWindowRect(rect, { dx: 0, dy: 0, scale: -100 }, viewport, stage).w, .32);
});
check("invalid motion or viewport numbers leave a bounded window unchanged", () => {
  for (const field of ["dx", "dy", "scale"]) for (const value of [NaN, Infinity, -Infinity]) {
    const motion = { dx: .1, dy: .1, scale: 1.2, [field]: value };
    assert.deepEqual(plain(handWindowRect(rect, motion, viewport, stage)), rect);
  }
  for (const field of ["width", "height"]) {
    assert.deepEqual(plain(handWindowRect(rect, { dx: .1, dy: .1, scale: 1.2 }, { ...viewport, [field]: NaN }, stage)), rect);
    for (const value of [NaN, Infinity, 0, -1]) assert.deepEqual(plain(handWindowRect(rect, { dx: .1, dy: .1, scale: 1.2 }, viewport, { ...stage, [field]: value })), rect);
  }
});
check("malformed original rectangles are normalized before hand movement", () => {
  const malformed = { x: NaN, y: Infinity, w: NaN, h: -99 };
  const out = handWindowRect(malformed, { dx: 0, dy: 0, scale: 1 }, viewport, stage);
  within(out); assert.deepEqual(plain(out), plain(boundedWindow(malformed)));
});
console.log(`${count} hand layout checks passed.`);
