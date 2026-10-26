// Simulated browser permission, registration and service-worker delivery only.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
const { webcrypto } = require("node:crypto");
const source = fs.readFileSync(path.join(__dirname, "../src/core/phonePush.ts"), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;

async function main() {
  const calls = [];
  let permission = "default", registered = true, failSave = false, cancelled = 0, subscription = null;
  const key = new Uint8Array([4, ...Array(64).fill(7)]);
  const keyText = Buffer.from(key).toString("base64url");
  const registration = { active: {}, pushManager: {
    getSubscription: async () => subscription,
    subscribe: async options => {
      calls.push("subscribe");
      subscription = { endpoint: "https://web.push.apple.com/test", options,
        toJSON: () => ({ endpoint: "https://web.push.apple.com/test", keys: {} }),
        unsubscribe: async () => { cancelled++; subscription = null; return true; } };
      return subscription;
    },
  } };
  const nav = { userAgent: "iPhone", maxTouchPoints: 1, serviceWorker: {
    getRegistration: async scope => { assert.equal(scope, "/app/"); return registration; },
    register: async (url, options) => { assert.equal(url, "/app/sw.js"); assert.equal(options.scope, "/app/"); assert.equal(options.updateViaCache, "none"); return registration; },
  } };
  const win = { isSecureContext: true, PushManager: {}, Notification: {}, location: { origin: "https://zae.example.test" }, matchMedia: () => ({ matches: false }), setTimeout, clearTimeout };
  const Notification = { get permission() { return permission; }, requestPermission: () => { calls.push("permission"); permission = "granted"; return Promise.resolve(permission); } };
  const api = async (method, url, body) => {
    calls.push(url);
    if (url === "/api/push/key") return { key: keyText };
    if (url === "/api/push/status") {
      const digest = Buffer.from(await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode("https://web.push.apple.com/test"))).toString("hex").slice(0, 32);
      return { devices: registered ? [{ id: digest }] : [] };
    }
    if (url === "/api/push/subscribe") { assert.equal(body.appOrigin, win.location.origin); if (failSave) throw new Error("server save failed"); }
  };
  const exports = {};
  vm.runInNewContext(code, { exports, require: () => ({ api, IN_TAURI: false }), window: win, navigator: nav, Notification,
    crypto: webcrypto, TextEncoder, atob, Uint8Array, Buffer, console });
  assert.match(exports.pushHint(), /Add to Home Screen/);
  nav.userAgent = "Macintosh"; nav.maxTouchPoints = 5;
  assert.match(exports.pushHint(), /iPad/);
  nav.userAgent = "Android";
  assert.equal(await exports.pushState(), "off");
  const enable = exports.enablePush();
  assert.equal(calls[0], "permission"); // No network await before the permission request.
  await enable;
  assert.equal(await exports.pushState(), "on");
  registered = false;
  assert.equal(await exports.pushState(), "unregistered");
  failSave = true;
  await assert.rejects(exports.enablePush(), /server save failed/);
  assert.ok(subscription); assert.equal(cancelled, 0); // Repairable after backend failure.
  failSave = false; registered = true;
  await exports.enablePush();
  await exports.disablePush();
  assert.equal(cancelled, 1);
  assert.equal(await exports.pushState(), "off");
  permission = "denied";
  assert.equal(await exports.pushState(), "blocked");
  win.isSecureContext = false;
  assert.equal(await exports.pushState(), "unsupported");
  assert.match(exports.pushHint(), /HTTPS/);
  assert.match(exports.deliveryMessage("accepted"), /isn't confirmed/);
  assert.match(exports.deliveryMessage("network"), /retry/);

  const handlers = {}, shown = [], opened = [], focused = [];
  let windows = [];
  const self = { registration: { scope: "https://zae.example.test/app/", showNotification: async (title, options) => shown.push({ title, options }) },
    addEventListener: (event, handler) => { handlers[event] = handler; },
    clients: { claim: async () => {}, matchAll: async () => windows, openWindow: async url => opened.push(url) }, skipWaiting: () => {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../public/sw.js"), "utf8"), { self, URL });
  async function push(data) { let work; handlers.push({ data: { json: () => data }, waitUntil: promise => { work = promise; } }); await work; }
  async function tap(url) { let work; handlers.notificationclick({ notification: { close() {}, data: { url } }, waitUntil: promise => { work = promise; } }); await work; }
  await push({ title: "Reminder", body: "Stretch", url: "https://evil.test/phish", tag: "same-notice" });
  assert.equal(shown[0].options.data.url, self.registration.scope);
  assert.equal(shown[0].options.tag, "same-notice");
  assert.equal(shown[0].options.icon, "https://zae.example.test/app/icons/zaenia-192.png");
  await push(null);
  assert.match(shown[1].options.body, /Open ZAE/);
  windows = [{ url: "https://zae.example.test/docs", focus: async () => focused.push("wrong") }];
  await tap("//evil.test");
  assert.equal(opened[0], self.registration.scope); assert.equal(focused.length, 0);
  windows.push({ url: self.registration.scope, focus: async () => focused.push("app") });
  await tap("/app/");
  assert.equal(focused[0], "app");
  console.log("Phone push: browser permission, repair, disable, status, privacy and notification clicks passed.");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
