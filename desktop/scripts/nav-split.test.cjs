// Pure-state checks for per-screen navigation, split layouts and the new voice phrases (Claude, 2026-11-11).
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript'), assert = require('node:assert/strict');
const store = new Map();
const env = { Date, Number, Math, JSON, Object, Array, Set, Map, RegExp, Event: class { constructor(type) { this.type = type; } }, CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init?.detail; } }, localStorage: { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) }, window: { dispatchEvent() {} } };
const cache = new Map();
function load(file) {
  file = path.resolve(__dirname, '../src', file); if (!file.endsWith('.ts')) file += '.ts';
  if (cache.has(file)) return cache.get(file);
  const output = {}; cache.set(file, output);
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText,
    { ...env, exports: output, require: p => load(path.relative(path.join(__dirname, '../src'), path.resolve(path.dirname(file), p))) });
  return output;
}
const nav = load('core/paneNav'), layout = load('core/windowLayout'), voice = load('core/voiceUi');
let passed = 0; const check = (name, fn) => { fn(); passed++; };

check('history push/back/forward', () => {
  let h = nav.emptyHistory();
  h = nav.pushStep(h, { kind: 'page', navigator: 'research', from: 'desk', to: 'library' });
  h = nav.pushStep(h, { kind: 'page', navigator: 'research', from: 'library', to: 'news' });
  h = nav.pushStep(h, { kind: 'page', navigator: 'research', from: 'news', to: 'news' }); // no-op ignored
  assert.equal(h.back.length, 2);
  const back = nav.takeBack(h); assert.equal(back.step.from, 'library'); h = back.history;
  assert.equal(h.forward.length, 1);
  const forward = nav.takeForward(h); assert.equal(forward.step.to, 'news'); h = forward.history;
  assert.equal(h.back.length, 2); assert.equal(h.forward.length, 0);
  h = nav.takeBack(h).history; h = nav.pushStep(h, { kind: 'app', from: 'research', to: 'notes' });
  assert.equal(h.forward.length, 0, 'a new step clears Forward');
  assert.equal(nav.takeBack(nav.emptyHistory()), null);
});
check('history is bounded and validated', () => {
  let h = nav.emptyHistory();
  for (let i = 0; i < 100; i++) h = nav.pushStep(h, { kind: 'page', navigator: 'n', from: `a${i}`, to: `a${i + 1}` });
  assert.equal(h.back.length, nav.HISTORY_LIMIT);
  assert.equal(nav.pushStep(nav.emptyHistory(), { kind: 'page', navigator: '<script>', from: 'a', to: 'b' }).back.length, 0);
  assert.equal(nav.pushStep(nav.emptyHistory(), { kind: 'other', from: 'a', to: 'b' }).back.length, 0);
});
check('history persistence round trip drops junk', () => {
  const saved = new Map();
  nav.writeHistories({ notes: { back: [{ kind: 'page', navigator: 'notes', from: 'board', to: 'map' }], forward: [] } }, (k, v) => saved.set(k, v));
  const raw = JSON.parse(saved.get('zaenia.paneNav.v1')); raw['bad id!'] = raw.notes; raw.junk = { back: [{ kind: 'page', navigator: 'x', from: 1, to: 2 }], forward: 'no' };
  const read = nav.readHistories(() => JSON.stringify(raw));
  assert.deepEqual(Object.keys(read), ['notes']); assert.equal(read.notes.back[0].to, 'map');
  assert.equal(JSON.stringify(nav.readHistories(() => '{not json')), '{}');
});
check('breadcrumb and scroll memory', () => {
  assert.deepEqual([...nav.breadcrumb('LIFE', [{ label: 'Fitness & Health' }, { label: 'Food' }])], ['LIFE', 'Fitness & Health', 'Food']);
  assert.deepEqual([...nav.breadcrumb('Research', [{ label: 'Research' }])], ['Research']);
  const memory = new Map(); for (let i = 0; i < 5; i++) nav.rememberScroll(memory, `k${i}`, i * 10, 3);
  assert.deepEqual([...memory.keys()], ['k2', 'k3', 'k4']); nav.rememberScroll(memory, 'k2', NaN, 3); assert.equal(memory.get('k2'), 20);
});

const known = ['notes', 'research', 'tasks', 'assistant', 'music', 'workbench'];
const win = (id, x, y, z, minimized = false) => ({ id, x, y, w: .494, h: .494, z, minimized });
check('snap order fills from visible, minimized, recent, known', () => {
  assert.deepEqual([...layout.snapOrder(2, [win('notes', 0, 0, 1)], { known, recent: ['research'] })], ['notes', 'research']);
  assert.deepEqual([...layout.snapOrder(3, [win('notes', 0, 0, 5), win('research', .506, 0, 9), win('tasks', 0, 0, 3, true), win('assistant', 0, 0, 7, true)], { known })],
    ['notes', 'research', 'assistant'], 'visible in slot order, then newest minimized');
  assert.deepEqual([...layout.snapOrder(2, [win('notes', 0, 0, 5), win('research', .506, 0, 9)], { known, anchor: 'research' })], ['research', 'notes']);
  assert.deepEqual([...layout.snapOrder(2, [], { known, ids: ['music', 'notes'] })], ['music', 'notes']);
  assert.equal(layout.snapOrder(4, [], { known: ['notes', 'research'] }), null);
});
check('slot order is stable regardless of focus', () => {
  const panes = [win('a', 0, 0, 20), win('b', .506, 0, 3), win('c', 0, .506, 1), win('d', .506, .506, 50)];
  assert.deepEqual([...layout.snapOrder(4, panes, { known: ['a', 'b', 'c', 'd'] })], ['a', 'b', 'c', 'd']);
});
check('tiled resize moves shared edges and respects minimums', () => {
  const rects = layout.snapRectangles(2).map((r, i) => ({ id: ['l', 'r'][i], ...r }));
  const moved = layout.resizeTiled(rects, 'l', { ...rects[0], w: .65 });
  assert.ok(Math.abs(moved[0].w - .65) < 1e-9); assert.ok(Math.abs(moved[1].x - .662) < 1e-9); assert.ok(Math.abs(moved[1].x + moved[1].w - 1) < 1e-9);
  const extreme = layout.resizeTiled(rects, 'l', { ...rects[0], w: .95 });
  assert.ok(extreme[1].w >= layout.MIN_WINDOW_WIDTH - 1e-9, 'neighbour keeps its minimum');
  const grid = layout.snapRectangles(3).map((r, i) => ({ id: ['big', 'top', 'bottom'][i], ...r }));
  const g = layout.resizeTiled(grid, 'top', { ...grid[1], h: .6 });
  assert.ok(Math.abs(g[2].y - .612) < 1e-9, 'lower pane follows'); assert.equal(JSON.stringify(g[0]), JSON.stringify(grid[0]), 'non-adjacent pane untouched');
});
check('pane focus directions', () => {
  const panes = layout.snapRectangles(4).map((r, i) => ({ id: ['tl', 'tr', 'bl', 'br'][i], ...r }));
  assert.equal(layout.paneInDirection(panes, 'tl', 'next'), 'tr'); assert.equal(layout.paneInDirection(panes, 'tl', 'previous'), 'br');
  assert.equal(layout.paneInDirection(panes, 'tl', 'right'), 'tr'); assert.equal(layout.paneInDirection(panes, 'tl', 'down'), 'bl');
  assert.equal(layout.paneInDirection(panes, 'tl', 'left'), null); assert.ok(layout.isMaximized({ x: 0, y: 0, w: 1, h: 1 }));
});
check('voice phrases', () => {
  const kind = text => voice.parseUiCommand(text)?.kind;
  for (const text of ['go back', 'back', 'Zae, go back', 'go back a page', 'back to the previous screen', 'previous screen']) assert.equal(kind(text), 'back', text);
  for (const text of ['go forward', 'forward', 'next screen']) assert.equal(kind(text), 'forward', text);
  for (const text of ['restore size', 'restore the normal size', 'exit full screen', 'unmaximize', 'un-maximize this window']) assert.equal(kind(text), 'restore-size', text);
  assert.deepEqual({ ...voice.parseUiCommand('focus the right pane') }, { kind: 'focus-pane', direction: 'right' });
  assert.deepEqual({ ...voice.parseUiCommand('next pane') }, { kind: 'focus-pane', direction: 'next' });
  assert.deepEqual({ ...voice.parseUiCommand('switch to the bottom window') }, { kind: 'focus-pane', direction: 'down' });
  assert.equal(kind('next page'), 'next'); assert.equal(kind('previous page'), 'previous');
  assert.equal(kind('arrange three windows'), 'arrange'); assert.equal(kind('undo window arrangement'), 'undo-arrange');
  assert.equal(voice.parseUiCommand('I went back to the store yesterday'), null, 'ordinary conversation is not a command');
  assert.equal(voice.parseUiCommand('tell me about the back pane of the car'), null);
  const recipes = voice.parseUiCommand('open recipes'); assert.equal(recipes.kind, 'navigate'); assert.deepEqual([...recipes.route.path], ['fitness', 'food', 'cookbook']);
  assert.deepEqual([...voice.parseUiCommand('open research library').route.path], ['library']);
});
check('resume offer answers and cooldown', () => {
  const activity = load('core/pageActivity');
  for (const [text, answer] of [['later', 'later'], ['not now', 'later'], ["I'm doing something else", 'later'], ["don't ask again", 'dismiss'], ['never ask me about that again', 'dismiss']]) assert.equal(activity.parseResumeAnswer(text), answer, text);
  assert.equal(activity.parseResumeAnswer('remind me later to water the plants'), null, 'reminder requests keep their own handling');
  const now = Date.now(), work = { key: 'notes/notes/editor', app: 'notes', navigator: 'notes', page: 'editor', label: 'All notes', subject: 'pump schedule', action: 'edited', at: now - 1000 };
  activity.recordPageActivity(work); const offers = new activity.ResumeOffers();
  assert.match(offers.offer(work), /pump schedule, sir\. Would you want to continue\?/); assert.equal(offers.offer(work), null, 'not on every visit');
  assert.equal(offers.answer("don't ask again").answer, 'dismiss'); assert.equal(new activity.ResumeOffers().offer(work, now + 3 * 864e5), null, 'persisted');
});
check('typed search and voice resolve to the same page; catalogue matches GODSPEED tabs', () => {
  const catalog = load('core/pageCatalog');
  const map = catalog.catalogNode('tasks', ['map']);
  assert.equal(map.children.map(item => item.label).join(), 'Directions,Traffic,Weather,Air,Sea');
  assert.equal(catalog.screensInside(catalog.catalogNode('tasks', ['fitness'])), 10);
  for (const phrase of ['cookbook', 'the library', 'research library', 'traffic', 'updates', 'meal planner', 'godspeed weather']) {
    const spoken = voice.parseUiCommand(`open ${phrase}`), typed = voice.searchPages(phrase)[0];
    assert.equal(spoken?.kind, 'navigate', phrase);
    assert.equal(`${typed.app}/${typed.path.join('/')}`, `${spoken.route.app}/${spoken.route.path.join('/')}`, phrase);
  }
  assert.equal(voice.searchPages('cook')[0].label, 'LIFE / Fitness & Health / Food / Cookbook', 'prefix match');
  assert.ok(voice.searchPages('library').some(route => route.label.endsWith('The Library')));
  assert.equal(voice.searchPages('zzqx').length, 0);
  assert.equal(voice.searchPages('').length, 0);
  for (const [id, modules] of Object.entries(catalog.CATEGORY_MODULES)) for (const module of modules)
    assert.ok(catalog.PAGE_CATALOG.some(app => app.id === module.app), `${id}: ${module.app}`);
});
check('build requests show only the final answer and real changed files', () => {
  const text = load('core/buildText');
  const raw = "Wait, the user also mentioned the clock.\nLet me draft the changes.\n----\n**ANSWER**\nFixed the time reference so 'tomorrow' means the next calendar day.";
  assert.equal(text.finalAnswer(raw), "Fixed the time reference so 'tomorrow' means the next calendar day.");
  assert.equal(text.finalAnswer('<think>private plan</think>Done: renamed the setting.'), 'Done: renamed the setting.');
  assert.equal(text.finalAnswer('Plain summary with no marker.'), 'Plain summary with no marker.');
  assert.equal(text.finalAnswer(undefined), '');
  assert.equal(text.displayFiles(['.aider.chat.history.md', '.aider.input.history', '.aider.tags.cache.v4/05/77/x.val', 'core/brain/conductor.py', 'desktop/src/App.tsx']).join(), 'core/brain/conductor.py,desktop/src/App.tsx');
});
check('preview metadata covers every category module', () => {
  const catalog = load('core/pageCatalog');
  for (const [id, modules] of Object.entries(catalog.CATEGORY_MODULES)) {
    assert.ok(catalog.CATEGORY_META[id], id);
    for (const module of modules) assert.ok(catalog.moduleMeta(module.app, module.path ?? []).accent, module.app);
  }
  assert.equal(catalog.navigatorFor('tasks', ['fitness', 'food']), 'fitness-food');
  assert.equal(catalog.navigatorFor('notes', []), 'notes');
  assert.equal(catalog.categoryForRoute('research'), 'know');
});
console.log(`nav-split: ${passed} checks passed`);
