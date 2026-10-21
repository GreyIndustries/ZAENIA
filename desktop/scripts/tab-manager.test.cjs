// Geometry and attended-tab behavior without credentials, mic, or live API calls.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict'), ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/windowLayout.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject });
const { boundedWindow, resizeWindow, attendedWindow } = exportsObject;
let count = 0;
function check(run) { run(); count++; }
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-10, `${a} != ${b}`);
const rect = { x: .3, y: .2, w: .5, h: .6 };
for (const edge of ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']) {
  for (const delta of [-10, -.1, 0, .1, 10]) check(() => {
    const changed = resizeWindow(rect, edge, delta, delta);
    assert.ok(changed.w >= .26 && changed.h >= .3);
    assert.ok(changed.x >= 0 && changed.y >= 0);
    assert.ok(changed.x + changed.w <= 1 + 1e-10 && changed.y + changed.h <= 1 + 1e-10);
    if (edge.includes('w')) near(changed.x + changed.w, rect.x + rect.w);
    if (edge.includes('n')) near(changed.y + changed.h, rect.y + rect.h);
    if (edge.includes('e')) near(changed.x, rect.x);
    if (edge.includes('s')) near(changed.y, rect.y);
  });
}
check(() => { const changed = boundedWindow({ x: .9, y: .9, w: .8, h: .8 }); near(changed.x, .2); near(changed.y, .2); });
check(() => { const changed = boundedWindow({ x: NaN, y: Infinity, w: NaN, h: -5 }); assert.ok(Object.values(changed).every(Number.isFinite)); near(changed.h, .3); });
const tabs = [{ id: 'calendar', minimized: false }, { id: 'tasks', minimized: false }, { id: 'notes', minimized: true }];
check(() => assert.equal(attendedWindow(tabs, 'calendar', 'tasks'), 'calendar', 'Last pointed-to tab wins over frontmost tab'));
check(() => assert.equal(attendedWindow(tabs, 'notes', 'tasks'), 'tasks', 'Minimized targets do not steal the next command'));
check(() => assert.equal(attendedWindow(tabs, 'closed', 'tasks'), 'tasks', 'Closed targets fall back to active tab'));
check(() => assert.equal(attendedWindow(tabs, null, 'calendar'), 'calendar'));
check(() => assert.equal(attendedWindow([], 'calendar', null), null));
console.log(`${count} tab resizing, screen-boundary, and attended-tab checks passed.`);
