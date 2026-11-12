// Minimal headless-Chrome driver over the DevTools protocol (no new dependency).
// Used by the nav/split rendered-behaviour checks; not shipped in the app.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const CHROME = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/opt/pw-browsers/chromium',
].find(file => fs.existsSync(file));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function launch({ width = 1440, height = 900, mobile = false } = {}) {
  if (!CHROME) throw new Error('No Chrome/Edge executable found');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'zae-cdp-'));
  const proc = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  // Always close this run's own browser, even when a check throws.
  process.once('exit', () => { try { proc.kill(); } catch { /* already closed */ } });
  for (let n = 0; n < 200 && !fs.existsSync(path.join(profile, 'DevToolsActivePort')); n++) await delay(100);
  const port = fs.readFileSync(path.join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0];
  const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const ws = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
  const pending = new Map(); const errors = []; const dialogs = []; let sequence = 0;
  ws.addEventListener('message', event => {
    const data = JSON.parse(event.data);
    if (data.method === 'Runtime.exceptionThrown') errors.push(data.params.exceptionDetails.exception?.description || data.params.exceptionDetails.text);
    // Record and accept page dialogs (e.g. the unsaved-draft "leave?" prompt on reload) so a run never blocks.
    if (data.method === 'Page.javascriptDialogOpening') { dialogs.push(data.params.type); ws.send(JSON.stringify({ id: ++sequence, method: 'Page.handleJavaScriptDialog', params: { accept: true } })); }
    const entry = pending.get(data.id);
    if (entry) { clearTimeout(entry.timer); pending.delete(data.id); data.error ? entry.reject(new Error(data.error.message)) : entry.resolve(data.result); }
  });
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout ${method}`)); }, 30000);
    pending.set(id, { resolve, reject, timer }); ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  };
  const until = async (expression, tries = 150) => {
    for (let n = 0; n < tries; n++) { if (await evaluate(expression)) return; await delay(100); }
    throw new Error(`Condition timed out: ${expression}`);
  };
  const viewport = async (w, h, isMobile) => call('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: isMobile ? 2 : 1, mobile: !!isMobile });
  const screenshot = async file => {
    const shot = await call('Page.captureScreenshot', { format: 'png' });
    fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
  };
  const mouse = async (type, x, y, button = 'left', buttons = 1) => call('Input.dispatchMouseEvent', { type, x, y, button, buttons, clickCount: 1 });
  const click = async (x, y) => { await mouse('mouseMoved', x, y, 'none', 0); await mouse('mousePressed', x, y); await mouse('mouseReleased', x, y, 'left', 0); };
  const type = async text => call('Input.insertText', { text });
  // A freshly started browser sometimes ignores its first commands; retry the setup a few times.
  for (let attempt = 1; ; attempt++) {
    try { await Promise.race([(async () => { await call('Page.enable'); await call('Runtime.enable'); await viewport(width, height, mobile); })(), delay(8000).then(() => { throw new Error('setup timeout'); })]); break; }
    catch (error) { if (attempt >= 4) throw error; await delay(1000); }
  }
  const close = async () => { try { await call('Browser.close'); } catch { /* closing */ } proc.kill(); };
  return { call, evaluate, until, viewport, screenshot, mouse, click, type, close, errors, dialogs, delay };
}

module.exports = { launch, delay };
