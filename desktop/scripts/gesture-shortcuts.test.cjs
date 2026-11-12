// Custom hand shortcuts: typed text per hand shape (core/gestureShortcuts.ts and GestureActions.setCustom).
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
const load = (file, extra = {}) => { const mod = {}; const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core", file), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText; vm.runInNewContext(code, { exports: mod, Math, Set, Map, JSON, Array, Number, ...extra }); return mod; };
const { normalizeShortcuts, withShortcut, withoutShortcut, cleanText, CUSTOM_SHAPES } = load("gestureShortcuts.ts");
const { GestureActions } = load("gestureActions.ts");
const poses = load("handPoses.ts");
const same = (a, b) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), b);
let count = 0; const check = run => { run(); count++; };

check(() => assert.equal(cleanText("  brief \n\t me  \u0007now "), "brief me now"));
check(() => assert.equal(cleanText("x".repeat(500)).length, 160));
check(() => assert.equal(cleanText(42), ""));
check(() => same(normalizeShortcuts("nope"), []));
check(() => same(normalizeShortcuts([{ shape: "five", text: "stop" }, { shape: "pinch", text: "x" }, { shape: "other", text: "x" }]), []));  // reserved shapes are refused
check(() => same(normalizeShortcuts([{ shape: "fist", text: "a" }, { shape: "fist", text: "b" }, { shape: "one", text: "  " }, null, 3]), [{ shape: "fist", text: "a" }]));
check(() => same(withShortcut([{ shape: "fist", text: "a" }], "fist", "new"), [{ shape: "fist", text: "new" }]));
check(() => same(withoutShortcut([{ shape: "fist", text: "a" }, { shape: "one", text: "b" }], "fist"), [{ shape: "one", text: "b" }]));
check(() => assert.equal(CUSTOM_SHAPES.length, 8));

// A thumbs-up hand (same landmark layout as gestures.test.cjs)
function hand(thumb) {
  const p = Array.from({ length: 21 }, () => ({ x: 0, y: 0 })), wx = 0.5, wy = 0.75; p[0] = { x: wx, y: wy };
  [5, 9, 13, 17].forEach((k, i) => { const bx = wx + [-0.06, -0.02, 0.02, 0.06][i], by = wy - 0.2; p[k] = { x: bx, y: by }; p[k + 1] = { x: bx, y: by - 0.04 }; p[k + 2] = { x: bx, y: by + 0.01 }; p[k + 3] = { x: bx, y: by + 0.05 }; });
  p[1] = { x: wx - 0.05, y: wy - 0.04 }; p[2] = { x: wx - 0.09, y: wy - 0.08 };
  const t = thumb === "up" ? [[wx - 0.1, wy - 0.17], [wx - 0.1, wy - 0.27]] : [[wx - 0.06, wy - 0.12], [wx - 0.05, wy - 0.17]];
  p[3] = { x: t[0][0], y: t[0][1] }; p[4] = { x: t[1][0], y: t[1][1] }; return p;
}
const run = (engine, pts, from, to) => { let last; for (let at = from; at <= to; at += 50) { last = engine.update(pts, at); if (last.action) return last.action; } return null; };

check(() => { const e = new GestureActions(); same(run(e, hand("up"), 0, 1500), { kind: "confirm" }); });                       // default still works
check(() => { const e = new GestureActions(); e.setCustom([{ shape: "thumbsUp", text: "brief me" }]); same(run(e, hand("up"), 0, 1500), { kind: "command", text: "brief me" }); });
check(() => { const e = new GestureActions(); e.setCustom([{ shape: "thumbsUp", text: "brief me" }]); assert.equal(run(e, hand("up"), 0, 700), null); });  // needs the full hold
check(() => { const e = new GestureActions(); e.setCustom([{ shape: "thumbsUp", text: "brief me" }]); same(run(e, hand("in"), 0, 1500), { kind: "calm" }); });  // other shapes keep their default
check(() => { const e = new GestureActions(); e.setCustom([{ shape: "thumbsUp", text: "brief me" }]); e.setCustom([]); same(run(e, hand("up"), 0, 1500), { kind: "confirm" }); });

// ---- taught poses
function fingers(up, wx = 0.5, wy = 0.75, scale = 1) {
  const p = Array.from({ length: 21 }, () => ({ x: 0, y: 0 })); p[0] = { x: wx, y: wy };
  [5, 9, 13, 17].forEach((k, i) => { const bx = wx + [-0.06, -0.02, 0.02, 0.06][i] * scale, by = wy - 0.2 * scale; p[k] = { x: bx, y: by };
    p[k + 1] = { x: bx, y: by - (up[i] ? 0.06 : 0.04) * scale }; p[k + 2] = { x: bx, y: by - (up[i] ? 0.11 : -0.01) * scale }; p[k + 3] = { x: bx, y: by - (up[i] ? 0.16 : -0.05) * scale }; });
  p[1] = { x: wx - 0.05 * scale, y: wy - 0.04 * scale }; p[2] = { x: wx - 0.09 * scale, y: wy - 0.08 * scale }; p[3] = { x: wx - 0.06 * scale, y: wy - 0.12 * scale }; p[4] = { x: wx - 0.05 * scale, y: wy - 0.17 * scale };
  return p;
}
const noisy = (pts, n) => pts.map((q, i) => ({ x: q.x + Math.sin(i * 7 + n) * 0.004, y: q.y + Math.cos(i * 5 + n) * 0.004 }));
const frames = pts => Array.from({ length: 12 }, (_, n) => poses.template(noisy(pts, n)));
const mk = (id, name, pts, action) => ({ id, name, template: poses.buildPose(frames(pts)), action });
const fingerPose = [false, false, false, false], flat = [true, true, true, true];

check(() => assert.equal(poses.template([]), null));
check(() => assert.ok(poses.template(fingers(flat)).length === 42));
check(() => { const a = poses.template(fingers(flat)), b = poses.template(fingers(flat, 0.3, 0.6, 1.7)); assert.ok(poses.distance(a, b) < 0.02); });   // same pose, other place and size
check(() => assert.ok(poses.distance(poses.template(fingers(flat)), poses.template(fingers(fingerPose))) > 0.15));
check(() => assert.equal(poses.buildPose([poses.template(fingers(flat))]), null));                                                          // too few frames
check(() => { const wild = Array.from({ length: 12 }, (_, n) => poses.template(fingers(n % 2 ? flat : fingerPose))); assert.equal(poses.buildPose(wild), null); });  // hand moved about
check(() => { const list = [mk("a", "Snap hand", fingers(fingerPose), { kind: "close" })]; const m = poses.makeMatcher(list); assert.equal(m(noisy(fingers(fingerPose, 0.4, 0.6, 1.3), 3)).id, "a"); assert.equal(m(fingers(flat)), null); });
check(() => { const list = [mk("a", "A", fingers(fingerPose), { kind: "close" }), mk("b", "B", fingers(flat), { kind: "next" })]; const m = poses.makeMatcher(list); assert.equal(m(fingers(flat)).id, "b"); });
check(() => same(poses.normalizePoses([{ id: "a", name: "ok", template: new Array(42).fill(0.1), action: { kind: "close" } }, { id: "a", name: "dup", template: new Array(42).fill(0), action: { kind: "close" } },
  { id: "b", name: "bad action", template: new Array(42).fill(0), action: { kind: "delete everything" } }, { id: "c", name: "", template: new Array(42).fill(0), action: { kind: "home" } },
  { id: "d", name: "short", template: [1], action: { kind: "home" } }, { id: "e", name: "cmd", template: new Array(42).fill(0), action: { kind: "command", text: " brief  me " } }]).map(x => [x.id, x.action]),
  [["a", { kind: "close" }], ["e", { kind: "command", text: "brief me" }]]));
check(() => { const list = [mk("a", "Snap hand", fingers(fingerPose), { kind: "close" })]; const e = new GestureActions(); e.setPoses(poses.makeMatcher(list));
  let act = null; for (let at = 0; at <= 1500 && !act; at += 50) act = e.update(fingers(fingerPose), at).action; same(act, { kind: "close" }); });
check(() => { const list = [mk("a", "Snap hand", fingers(fingerPose), { kind: "close" })]; const e = new GestureActions(); e.setPoses(poses.makeMatcher(list));
  let act = null; for (let at = 0; at <= 500 && !act; at += 50) act = e.update(fingers(fingerPose), at).action; assert.equal(act, null); });   // needs the hold
// A tracking watchdog, resize or mode change cancels a taught hold completely.
check(() => {
  const e = new GestureActions(), pts = fingers(fingerPose);
  e.setPoses(poses.makeMatcher([mk("a", "Close", pts, { kind: "close" })]));
  assert.equal(e.update(pts, 0).action, null);
  assert.equal(e.update(pts, 500).action, null);
  e.reset();
  assert.equal(e.update(pts, 1000).action, null);
  assert.equal(e.update(pts, 1699).action, null);
  same(e.update(pts, 1700).action, { kind: "close" });
});
// Re-enabling after a completed taught gesture requires a new full hold and can fire again.
check(() => {
  const e = new GestureActions(), pts = fingers(fingerPose);
  e.setPoses(poses.makeMatcher([mk("a", "Close", pts, { kind: "close" })]));
  e.update(pts, 0); same(e.update(pts, 700).action, { kind: "close" });
  e.reset();
  assert.equal(e.update(pts, 2000).action, null);
  same(e.update(pts, 2700).action, { kind: "close" });
});
// No hand also cancels the taught hold instead of accumulating time while tracking is lost.
check(() => {
  const e = new GestureActions(), pts = fingers(fingerPose);
  e.setPoses(poses.makeMatcher([mk("a", "Close", pts, { kind: "close" })]));
  e.update(pts, 0); e.update(pts, 500); e.update(null, 550);
  assert.equal(e.update(pts, 1000).action, null);
  assert.equal(e.update(pts, 1699).action, null);
  same(e.update(pts, 1700).action, { kind: "close" });
});
console.log(`${count} custom shortcut checks passed.`);
