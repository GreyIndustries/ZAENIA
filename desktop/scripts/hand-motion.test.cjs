// Synthetic landmarks only; no camera, network, model runtime or owner data.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict");
const ts = require(require.resolve("typescript", { paths: [__dirname, path.join(__dirname, "../../desktop")] }));
const mod = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core/handGestures.ts"), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
vm.runInNewContext(code, { exports: mod, Math, Number, Array });
const { HandMotionController, normalizeHandSettings } = mod;
let count = 0;
function check(name, run) { run(); count++; console.log(`  OK ${name}`); }
function hand({ x = .5, y = .72, side = "Right", pose = "point", pinch = .08, score = .95 } = {}) {
  const p = Array.from({ length: 21 }, () => ({ x, y }));
  p[0] = { x, y };
  [5, 9, 13, 17].forEach((base, finger) => {
    const bx = x + (finger - 1.5) * .035, by = y - .16;
    const extended = pose === "palm" || (finger === 0 && pose !== "fist");
    p[base] = { x: bx, y: by };
    p[base + 1] = { x: bx, y: by - .035 };
    p[base + 2] = { x: bx, y: extended ? by - .08 : by + .01 };
    p[base + 3] = { x: bx, y: extended ? by - .14 : by + .045 };
  });
  p[1] = { x: x - .05, y: y - .02 }; p[2] = { x: x - .09, y: y - .06 }; p[3] = { x: x - .13, y: y - .12 };
  const scale = Math.hypot(p[9].x - x, p[9].y - y);
  p[4] = pose === "pinch" ? { x: p[8].x - scale * pinch, y: p[8].y } : { x: x - .21, y: y - .15 };
  return { points: p, handedness: side, score };
}
const target = () => "model:se";
function rig(settings) {
  const engine = new HandMotionController(settings); let at = 1000;
  return { engine, step: (hands, advance = 40, pick = target) => { const frame = engine.update(hands, at, pick); at += advance; return frame; } };
}
function grab(r, options = {}) {
  for (let i = 0; i < 7; i++) r.step([hand(options)]);
  let f; for (let i = 0; i < 7; i++) { f = r.step([hand({ ...options, pose: "pinch" })]); if (f.motion?.kind === "begin") return f; }
  assert.fail("fixture did not grab");
}

check("requires pointing at one target before a deliberate pinch hold", () => {
  const r = rig();
  for (let i = 0; i < 20; i++) assert.equal(r.step([hand({ pose: "pinch" })]).motion, null);
  const begun = grab(r); assert.equal(begun.motion.kind, "begin"); assert.equal(begun.target, "model:se");
});
check("changing targets during activation cannot grab", () => {
  const r = rig(); for (let i = 0; i < 7; i++) r.step([hand()]);
  for (let i = 0; i < 7; i++) assert.equal(r.step([hand({ pose: "pinch" })], 40, () => "window:other").motion, null);
});
check("array reordering keeps primary hand and target", () => {
  const r = rig(); grab(r, { x: .35 });
  const primary = hand({ x: .35, pose: "pinch" }), other = hand({ x: .8, side: "Left" });
  const a = r.step([primary, other]), b = r.step([other, primary]);
  assert.equal(a.phase, "grab"); assert.equal(b.phase, "grab"); assert.equal(b.target, "model:se");
  assert.ok(Math.abs(b.motion.dx) < .001);
});
check("loss ends once and never transfers a grab to the other hand", () => {
  const r = rig(); grab(r, { x: .35 });
  const lost = r.step([hand({ x: .7, pose: "pinch", side: "Left" })]);
  assert.equal(lost.motion.kind, "end"); assert.match(lost.motion.reason, /lost/);
  for (let i = 0; i < 10; i++) assert.equal(r.step([hand({ x: .7, pose: "pinch", side: "Left" })]).motion, null);
  assert.equal(grab(r, { x: .7, side: "Left" }).motion.kind, "begin");
});
check("a held pinch cannot re-grab after tracking loss", () => {
  const r = rig(); grab(r); assert.equal(r.step([]).motion.kind, "end");
  for (let i = 0; i < 10; i++) assert.equal(r.step([hand({ pose: "pinch" })]).motion, null);
  assert.equal(grab(r).motion.kind, "begin");
});
check("pinch release hysteresis tolerates threshold jitter", () => {
  const r = rig(); grab(r);
  for (const pinch of [.29, .38, .3, .41]) assert.equal(r.step([hand({ pose: "pinch", pinch })]).motion.kind, "change");
  assert.equal(r.step([hand({ pose: "pinch", pinch: .44 })]).motion.kind, "end");
});
check("second-hand acquisition and release rebase without position jumps", () => {
  const r = rig(); grab(r, { x: .3 });
  const primary = hand({ x: .3, pose: "pinch" });
  const both = r.step([primary, hand({ x: .7, side: "Left", pose: "pinch" })]);
  assert.equal(both.phase, "two-hand"); assert.equal(both.motion.dx, 0); assert.equal(both.motion.dy, 0); assert.equal(both.motion.scale, 1); assert.equal(both.motion.angle, 0);
  const one = r.step([primary]); assert.equal(one.phase, "grab"); assert.equal(one.motion.dx, 0); assert.equal(one.motion.scale, 1);
});
check("two pinches scale and twist with bounded incremental transforms", () => {
  const r = rig(); grab(r, { x: .3 });
  const primary = hand({ x: .3, pose: "pinch" });
  r.step([primary, hand({ x: .65, side: "Left", pose: "pinch" })]);
  const out = r.step([hand({ x: .73, y: .66, side: "Left", pose: "pinch" }), primary]);
  assert.equal(out.phase, "two-hand"); assert.ok(out.motion.scale > 1 && out.motion.scale <= 1.25);
  assert.ok(Math.abs(out.motion.angle) > .001 && Math.abs(out.motion.angle) <= .18);
  assert.ok(Math.abs(out.motion.dx) > 0 && Math.abs(out.motion.dx) < .055);
});
check("symmetric two-hand separation scales without translating the target", () => {
  const r = rig(); grab(r, { x: .3 });
  r.step([hand({ x: .3, pose: "pinch" }), hand({ x: .7, side: "Left", pose: "pinch" })]);
  const out = r.step([hand({ x: .26, pose: "pinch" }), hand({ x: .74, side: "Left", pose: "pinch" })]);
  assert.equal(out.phase, "two-hand"); assert.ok(out.motion.scale > 1);
  assert.ok(Math.abs(out.motion.dx) < .00001); assert.ok(Math.abs(out.motion.dy) < .00001);
});
check("ambiguous identity is canceled instead of selected by array order", () => {
  const r = rig(); grab(r);
  const out = r.step([hand({ x: .49, pose: "pinch" }), hand({ x: .51, pose: "pinch" })]);
  assert.equal(out.motion.kind, "end");
});
check("stale, malformed, low-confidence and delayed frames fail closed", () => {
  let r = rig(); grab(r); const stale = r.engine.update([hand({ pose: "pinch" })], 1, target); assert.equal(stale.motion.kind, "end");
  r = rig(); grab(r); const malformed = hand({ pose: "pinch" }); malformed.points[8].x = NaN; assert.equal(r.step([malformed]).motion.kind, "end");
  r = rig(); grab(r); assert.equal(r.step([hand({ pose: "pinch", score: .2 })]).motion.kind, "end");
  r = rig(); grab(r); r.step([hand({ pose: "pinch" })], 500); assert.equal(r.step([hand({ pose: "pinch" })]).motion.kind, "end");
});
check("dominant-hand preference is honored and settings are sanitized", () => {
  const r = rig({ hand: "Left" }); assert.equal(r.step([hand()]).cursor, null); assert.ok(r.step([hand({ side: "Left" })]).cursor);
  const settings = normalizeHandSettings({ hand: "bad", sensitivity: Infinity, range: { left: .9, right: .1, top: -3, bottom: 9 } });
  assert.equal(settings.hand, "auto"); assert.equal(settings.sensitivity, 1); assert.ok(settings.range.right > settings.range.left); assert.equal(settings.range.top, 0); assert.equal(settings.range.bottom, 1);
});
check("cursor and deltas stay bounded under fast movement", () => {
  const r = rig({ sensitivity: 2 }); grab(r);
  const out = r.step([hand({ x: .66, y: .72, pose: "pinch" })]);
  assert.equal(out.motion.kind, "change"); assert.ok(out.cursor.x >= 0 && out.cursor.x <= 1); assert.ok(Math.abs(out.motion.dx) <= .055); assert.ok(Math.abs(out.motion.dy) <= .055);
});
check("open palm stops once per hold and never issues a navigation action", () => {
  const r = rig(); let stops = 0;
  for (let i = 0; i < 30; i++) { const frame = r.step([hand({ pose: "palm" })]); stops += Number(frame.stop); assert.equal(frame.motion, null); }
  assert.equal(stops, 1); r.step([hand()]);
  for (let i = 0; i < 15; i++) stops += Number(r.step([hand({ pose: "palm" })]).stop);
  assert.equal(stops, 2);
});
check("reset requires fresh targeting and callback failure cannot invent a target", () => {
  const r = rig(); grab(r); r.engine.reset();
  for (let i = 0; i < 10; i++) assert.equal(r.step([hand({ pose: "pinch" })]).motion, null);
  for (let i = 0; i < 12; i++) assert.equal(r.step([hand()], 40, () => { throw new Error("detached target"); }).target, null);
});
console.log(`${count} hand motion checks passed.`);
