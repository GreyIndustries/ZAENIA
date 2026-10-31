// Hand-gesture actions (core/gestureActions.ts): synthetic hand landmarks, no camera.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
const mod = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core/gestureActions.ts"), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
vm.runInNewContext(code, { exports: mod, Math });
const { shapeOf, GestureActions } = mod;
let count = 0; const check = run => { run(); count++; };

/** A right hand facing the camera. fingers = [index, middle, ring, pinky] up?; thumb: "in" | "out" | "up" | "down" | "pinch". */
function hand({ fingers = [false, false, false, false], thumb = "in", spread = false, at = { x: 0.5, y: 0.75 } } = {}) {
  const p = Array.from({ length: 21 }, () => ({ x: 0, y: 0 }));
  const wx = at.x, wy = at.y;
  p[0] = { x: wx, y: wy };
  const bases = [-0.06, -0.02, 0.02, 0.06];
  [5, 9, 13, 17].forEach((k, i) => {
    const bx = wx + bases[i] * (spread && i < 2 ? 2.2 : 1), by = wy - 0.2;
    p[k] = { x: bx, y: by };
    if (fingers[i]) { p[k + 1] = { x: bx, y: by - 0.06 }; p[k + 2] = { x: bx, y: by - 0.11 }; p[k + 3] = { x: bx * (spread && i < 2 ? 1 : 1), y: by - 0.16 }; }
    else { p[k + 1] = { x: bx, y: by - 0.04 }; p[k + 2] = { x: bx, y: by + 0.01 }; p[k + 3] = { x: bx, y: by + 0.05 }; }
  });
  if (spread) { p[8] = { x: wx - 0.17, y: wy - 0.34 }; p[12] = { x: wx + 0.05, y: wy - 0.36 }; }
  p[1] = { x: wx - 0.05, y: wy - 0.04 }; p[2] = { x: wx - 0.09, y: wy - 0.08 };
  const thumbs = { in: [[wx - 0.06, wy - 0.12], [wx - 0.05, wy - 0.17]], out: [[wx - 0.15, wy - 0.12], [wx - 0.21, wy - 0.15]],
    up: [[wx - 0.1, wy - 0.17], [wx - 0.1, wy - 0.27]], down: [[wx - 0.1, wy + 0.02], [wx - 0.1, wy + 0.12]], pinch: [[wx - 0.07, wy - 0.25], [p[8].x - 0.005, p[8].y + 0.005]] };
  const [[x3, y3], [x4, y4]] = thumbs[thumb];
  p[3] = { x: x3, y: y3 }; p[4] = { x: x4, y: y4 };
  return p;
}
const up4 = [true, true, true, true];

check(() => assert.equal(shapeOf(hand({ fingers: [true, false, false, false] })), "one"));
check(() => assert.equal(shapeOf(hand({ fingers: [true, true, false, false] })), "two"));
check(() => assert.equal(shapeOf(hand({ fingers: [true, true, false, false], spread: true })), "peace"));
check(() => assert.equal(shapeOf(hand({ fingers: [true, true, true, false] })), "three"));
check(() => assert.equal(shapeOf(hand({ fingers: up4 })), "four"));
check(() => assert.equal(shapeOf(hand({ fingers: up4, thumb: "out" })), "five"));
check(() => assert.equal(shapeOf(hand({ fingers: [true, false, false, true] })), "rock"));
check(() => assert.equal(shapeOf(hand()), "fist"));
check(() => assert.equal(shapeOf(hand({ thumb: "up" })), "thumbsUp"));
check(() => assert.equal(shapeOf(hand({ thumb: "down" })), "thumbsDown"));
check(() => assert.equal(shapeOf(hand({ fingers: [true, false, false, false], thumb: "pinch" })), "pinch"));
check(() => assert.equal(shapeOf([{ x: 0, y: 0 }]), null));

const run = (frames, speaking = false) => {
  const engine = new GestureActions(); const actions = []; let holding = null;
  frames.forEach(([points, at]) => { const out = engine.update(points, at, speaking); if (out.action) actions.push(JSON.parse(JSON.stringify(out.action))); if (out.holding) holding = out.holding; });
  return { actions, holding };
};
const hold = (points, ms) => Array.from({ length: Math.ceil(ms / 40) + 1 }, (_, i) => [points, 1000 + i * 40]);
// Holding up fingers opens a category once, after the hold time, and shows progress meanwhile.
check(() => { const r = run(hold(hand({ fingers: [true, true, true, false] }), 1200)); assert.deepEqual(r.actions, [{ kind: "category", index: 2 }]); assert.equal(r.holding.label, "3 · Know"); });
check(() => assert.deepEqual(run(hold(hand({ fingers: [true, false, false, false] }), 500)).actions, []));   // too short
check(() => assert.deepEqual(run(hold(hand({ fingers: [true, false, false, true] }), 1000)).actions, [{ kind: "system" }]));
check(() => assert.deepEqual(run(hold(hand(), 1100)).actions, [{ kind: "calm" }]));
check(() => assert.deepEqual(run(hold(hand({ fingers: [true, true, false, false], spread: true }), 900)).actions, [{ kind: "mic" }]));
check(() => assert.deepEqual(run(hold(hand({ thumb: "up" }), 800)).actions, [{ kind: "confirm" }]));
check(() => assert.deepEqual(run(hold(hand({ thumb: "down" }), 800)).actions, [{ kind: "dismiss" }]));
check(() => assert.deepEqual(run(hold(hand({ fingers: [true, false, false, false], thumb: "pinch" }), 800)).actions, [{ kind: "close" }]));
// Open palm: stop while she talks; otherwise it is "5", Build.
check(() => assert.deepEqual(run(hold(hand({ fingers: up4, thumb: "out" }), 700), true).actions, [{ kind: "stop" }]));
check(() => assert.deepEqual(run(hold(hand({ fingers: up4, thumb: "out" }), 1200)).actions, [{ kind: "category", index: 4 }]));
// Swipes with an open hand. The camera is mirrored: moving the hand to the camera's left is "right" on screen.
const swipe = (dx, dy) => Array.from({ length: 9 }, (_, i) => [hand({ fingers: up4, at: { x: 0.5 - dx * i / 8, y: 0.75 + dy * i / 8 } }), 1000 + i * 40]);
check(() => assert.deepEqual(run(swipe(0.3, 0)).actions, [{ kind: "next" }]));
check(() => assert.deepEqual(run(swipe(-0.3, 0)).actions, [{ kind: "previous" }]));
check(() => assert.deepEqual(run(swipe(0, -0.3)).actions, [{ kind: "home" }]));
check(() => assert.deepEqual(run(swipe(0, 0.3)).actions, [{ kind: "minimize" }]));
// A slow drift is not a swipe, and one hold fires once.
check(() => assert.deepEqual(run(Array.from({ length: 30 }, (_, i) => [hand({ fingers: up4, at: { x: 0.5 - 0.3 * i / 29, y: 0.75 } }), 1000 + i * 40])).actions.filter(a => a.kind !== "category"), []));
check(() => assert.equal(run(hold(hand(), 3000)).actions.length, 1));
check(() => assert.deepEqual(run([[null, 1000], [null, 1040]]).actions, []));
console.log(`gestures: ${count} checks passed`);
