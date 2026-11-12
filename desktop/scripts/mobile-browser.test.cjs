// Browser credentials and recording lifecycle, with simulated audio only.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
function compile(file, modules, globals) {
  const exports = {};
  const source = fs.readFileSync(path.join(__dirname, "../src/core", file), "utf8").replaceAll("import.meta.env.MODE", '"web"');
  const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
  vm.runInNewContext(code, { exports, require: name => { if (!(name in modules)) throw new Error(name); return modules[name]; }, ...globals });
  return exports;
}
async function main() {
  const storage = new Map(), calls = [], lifecycleEvents = [];
  let status = 200, detail = null;
  const browser = { dispatchEvent: event => { lifecycleEvents.push(event.type); return true; }, localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }, setTimeout, clearTimeout };
  const bridge = compile("bridge.ts", { "@tauri-apps/api/core": {}, "./coreTelemetry": { localStatusEndpoint: () => null } }, {
    window: browser, Event, AbortController, fetch: async (url, options) => { calls.push({ url, options }); return { status, ok: status === 200, json: async () => detail ?? { success: true }, blob: async () => new Blob(["audio"]) }; }, console,
  });
  assert.equal(bridge.savedToken(), null);
  await bridge.checkPhoneConnection();
  assert.equal(calls.at(-1).options.credentials, "same-origin");
  assert.equal(calls.at(-1).options.headers["X-ZAENIA-APP"], "1");
  await bridge.api("POST", "/api/briefing", {});
  assert.equal(calls.at(-1).options.headers["X-ZAENIA-API-TOKEN"], "");
  bridge.saveToken("local-test-token");
  await bridge.readStatus();
  assert.equal(calls.at(-1).options.headers["X-ZAENIA-API-TOKEN"], "local-test-token");
  await bridge.completeVoiceLogin("one-use-id", "pcm");
  assert.equal(bridge.savedToken(), null);
  assert.equal(calls.at(-1).url, "/api/auth/voice/verify");
  assert.equal(calls.at(-1).options.credentials, "same-origin");
  await bridge.briefingAudio("session?unsafe=value");
  assert.equal(calls.at(-1).url, "/api/briefing/audio?session_id=session%3Funsafe%3Dvalue");
  assert.equal(calls.at(-1).options.credentials, "same-origin");
  bridge.saveToken("token-to-forget");
  await bridge.disconnectPhone();
  assert.deepEqual(lifecycleEvents, ["zae:trip-session-end"]);
  assert.equal(calls.at(-1).url, "/api/auth/logout");
  assert.equal(bridge.savedToken(), null);
  const nativeCalls = [];
  const nativeBridge = compile("bridge.ts", {
    "@tauri-apps/api/core": { invoke: async (name, args) => { nativeCalls.push({ name, args }); return [82, 73, 70, 70]; } },
    "./coreTelemetry": { localStatusEndpoint: () => null },
  }, { window: { ...browser, __TAURI_INTERNALS__: {} }, Blob, AbortController });
  const nativeAudio = await nativeBridge.briefingAudio("desktop-session");
  assert.equal(nativeCalls[0].name, "zaenia_briefing_audio");
  assert.equal(nativeCalls[0].args.sessionId, "desktop-session");
  assert.equal(nativeAudio.type, "audio/wav");
  assert.equal(nativeAudio.size, 4);
  status = 401; detail = { detail: "Voice did not match." };
  await assert.rejects(bridge.completeVoiceLogin("id", "pcm"), error => error.kind === "auth" && error.message === "Voice did not match.");
  let stops = 0, closes = 0, processor, pendingMic;
  class Context {
    sampleRate = 48000; state = "running";
    resume() { return Promise.resolve(); }
    close() { closes++; return Promise.resolve(); }
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    createScriptProcessor() { processor = { connect() {}, disconnect() {}, onaudioprocess: null }; return processor; }
  }
  const microphone = { getUserMedia: async () => ({ getTracks: () => [{ stop() { stops++; } }] }) };
  const voice = compile("voiceLogin.ts", { "./voiceInput": { encodeClip: chunks => `encoded-${chunks.length}` } }, {
    window: { isSecureContext: true, AudioContext: Context }, navigator: { mediaDevices: microphone }, Float32Array,
  });
  let controller = new AbortController();
  const recording = await voice.recordLoginVoice(controller.signal);
  for (let i = 0; i < 25; i++) processor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(4096) } });
  assert.equal(recording.finish(), "encoded-25");
  assert.equal(stops, 1); assert.equal(closes, 1);
  assert.throws(() => recording.finish(), /cancelled/);
  controller = new AbortController();
  const short = await voice.recordLoginVoice(controller.signal);
  assert.throws(() => short.finish(), /all six words/);
  assert.equal(stops, 2); assert.equal(closes, 2);
  controller = new AbortController();
  await voice.recordLoginVoice(controller.signal);
  controller.abort();
  assert.equal(stops, 3); assert.equal(closes, 3);
  microphone.getUserMedia = () => new Promise(resolve => { pendingMic = resolve; });
  controller = new AbortController();
  const pending = voice.recordLoginVoice(controller.signal);
  await new Promise(setImmediate); controller.abort();
  pendingMic({ getTracks: () => [{ stop() { stops++; } }] });
  await assert.rejects(pending, /cancelled/);
  assert.equal(stops, 4); assert.equal(closes, 4);
  console.log("PASS: cookie-based browser calls, token compatibility, logout, auth errors, protected audio, and microphone cleanup on success, short clips, cancellation, and delayed permission.");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
