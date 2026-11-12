// Quick-add parsing for Tasks & Calendar (core/quickTask.ts): pure, no browser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/quickTask.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject, Date });
const { parseQuickTask } = exportsObject;
const now = new Date('2026-10-28T09:00:00'); // a Wednesday
let n = 0; const check = fn => { fn(); n++; };
check(() => { const t = parseQuickTask('call bank fri 3pm !high', now); assert.equal(t.title, 'call bank'); assert.equal(t.priority, 'High'); const d = new Date(t.deadline); assert.equal(d.getDay(), 5); assert.equal(d.getHours(), 15); });
check(() => { const t = parseQuickTask('fix the monitor stand', now); assert.equal(t.title, 'fix the monitor stand'); assert.equal(t.deadline, null); assert.equal(t.priority, 'Normal'); });
check(() => { const t = parseQuickTask('pay bill tomorrow !critical', now); assert.equal(t.title, 'pay bill'); assert.equal(t.priority, 'Critical'); assert.equal(new Date(t.deadline).getDate(), 29); assert.equal(new Date(t.deadline).getHours(), 17); });
check(() => { const t = parseQuickTask('gym at 18:30', now); assert.equal(new Date(t.deadline).getHours(), 18); assert.equal(new Date(t.deadline).getMinutes(), 30); });
check(() => { const t = parseQuickTask('stretch tonight !low', now); assert.equal(new Date(t.deadline).getHours(), 20); assert.equal(t.priority, 'Low'); });
check(() => { const t = parseQuickTask('team call wednesday 10am', now); assert.equal(new Date(t.deadline).getDate(), 4); assert.equal(t.title, 'team call'); });
console.log(`${n} quick-add checks passed.`);
