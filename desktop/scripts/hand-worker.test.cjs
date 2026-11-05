// Execute the actual worker with a mocked local MediaPipe runtime; no camera or network.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict");
const source = fs.readFileSync(path.join(__dirname, "../public/handtracking/worker.js"), "utf8");
const plain = value => JSON.parse(JSON.stringify(value));
let count = 0;
async function check(name, run) { await run(); count++; console.log(`  OK ${name}`); }
function probe() {
  const state = { imports: [], filesets: [], options: null, detectCalls: [], messages: [], closed: 0, trackerClosed: 0, result: null, detectError: false, initError: false };
  const tracker = { detectForVideo(frame, at) { state.detectCalls.push({ frame, at }); if (state.detectError) throw new Error("fixture detection failure"); return state.result; }, close() { state.trackerClosed++; } };
  const self = { location: { href: "http://127.0.0.1:1420/app/handtracking/worker.js" }, postMessage(message) { state.messages.push(message); }, close() { state.closed++; } };
  const context = { self, URL, Number, importScripts(url) { state.imports.push(url); }, Vision: {
    FilesetResolver: { async forVisionTasks(url) { state.filesets.push(url); return { local: true }; } },
    HandLandmarker: { async createFromOptions(fileset, options) { state.options = options; assert.equal(fileset.local, true); if (state.initError) throw new Error("fixture init failure"); return tracker; } },
  } };
  vm.runInNewContext(source, context);
  return { state, send: data => self.onmessage({ data }), frame: () => { const frame = { closed: 0, close() { this.closed++; } }; return frame; } };
}
async function main() {
  await check("initializes two-hand VIDEO tracking using only local CPU assets", async () => {
    const p = probe(); await p.send({ type: "init" });
    assert.deepEqual(p.state.imports, ["vision_bundle.js"]);
    assert.deepEqual(p.state.filesets, ["http://127.0.0.1:1420/app/handtracking/wasm"]);
    assert.equal(p.state.options.baseOptions.modelAssetPath, "http://127.0.0.1:1420/app/handtracking/hand_landmarker.task");
    assert.equal(p.state.options.baseOptions.delegate, "CPU"); assert.equal(p.state.options.runningMode, "VIDEO"); assert.equal(p.state.options.numHands, 2);
    assert.equal(p.state.options.minHandDetectionConfidence, .65); assert.equal(p.state.options.minHandPresenceConfidence, .65); assert.equal(p.state.options.minTrackingConfidence, .65);
    assert.equal(p.state.messages.at(-1).type, "ready");
  });
  await check("returns both hands with their own landmarks, handedness and score", async () => {
    const p = probe(); await p.send({ type: "init" });
    const left = [{ x: .2, y: .3, z: -.1 }], right = [{ x: .7, y: .4, z: -.2 }];
    p.state.result = { landmarks: [left, right], handedness: [[{ categoryName: "Left", score: .97 }], [{ categoryName: "Right", score: .92 }]] };
    const frame = p.frame(); await p.send({ type: "frame", frame, at: 100 });
    const answer = p.state.messages.at(-1);
    assert.deepEqual(plain(answer), { type: "landmarks", hands: [{ points: left, handedness: "Left", score: .97 }, { points: right, handedness: "Right", score: .92 }], at: 100 });
    assert.equal(p.state.detectCalls[0].frame, frame); assert.equal(frame.closed, 1);
  });
  await check("supports the older handedness alias and caps output to two hands", async () => {
    const p = probe(); await p.send({ type: "init" });
    p.state.result = { landmarks: [[{ x: 1, y: 0 }], [{ x: 2, y: 0 }], [{ x: 3, y: 0 }]], handednesses: [[{ categoryName: "Right", score: .9 }], [{ categoryName: "Left", score: .8 }]] };
    await p.send({ type: "frame", frame: p.frame(), at: 100 }); const out = p.state.messages.at(-1);
    assert.equal(out.hands.length, 2); assert.equal(out.hands[0].handedness, "Right"); assert.equal(out.hands[1].handedness, "Left");
  });
  await check("missing classification stays unknown with zero confidence", async () => {
    const p = probe(); await p.send({ type: "init" }); p.state.result = { landmarks: [[{ x: .2, y: .3 }]] };
    await p.send({ type: "frame", frame: p.frame(), at: 100 }); const hand = p.state.messages.at(-1).hands[0];
    assert.equal(hand.handedness, "Unknown"); assert.equal(hand.score, 0);
  });
  await check("rejects duplicate, backwards and non-finite timestamps and closes every frame", async () => {
    const p = probe(); await p.send({ type: "init" }); await p.send({ type: "frame", frame: p.frame(), at: 100 });
    for (const at of [100, 99, NaN, Infinity, -Infinity]) {
      const frame = p.frame(); await p.send({ type: "frame", frame, at });
      assert.equal(frame.closed, 1); assert.equal(p.state.detectCalls.length, 1); assert.deepEqual(plain(p.state.messages.at(-1).hands), []);
    }
    const fresh = p.frame(); await p.send({ type: "frame", frame: fresh, at: 101 }); assert.equal(fresh.closed, 1); assert.equal(p.state.detectCalls.length, 2);
  });
  await check("detection exceptions report failure and close the transferred frame", async () => {
    const p = probe(); await p.send({ type: "init" }); p.state.detectError = true;
    const frame = p.frame(); await p.send({ type: "frame", frame, at: 100 });
    assert.equal(frame.closed, 1); assert.equal(p.state.messages.at(-1).type, "error"); assert.match(p.state.messages.at(-1).detail, /fixture detection failure/);
  });
  await check("initialization errors are reported and a blank result returns no hands", async () => {
    let p = probe(); p.state.initError = true; await p.send({ type: "init" }); assert.equal(p.state.messages.at(-1).type, "error");
    p = probe(); await p.send({ type: "init" }); await p.send({ type: "frame", frame: p.frame(), at: 100 }); assert.deepEqual(plain(p.state.messages.at(-1).hands), []);
  });
  await check("close releases the tracker and closes the worker", async () => {
    const p = probe(); await p.send({ type: "init" }); await p.send({ type: "close" });
    assert.equal(p.state.trackerClosed, 1); assert.equal(p.state.closed, 1);
  });
  console.log(`${count} hand worker checks passed.`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
