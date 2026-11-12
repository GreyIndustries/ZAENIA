// App-style swiping (core/swipe.ts): what counts as a swipe, and where it goes.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/swipe.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject, require: () => ({ useEffect() {}, useRef: v => ({ current: v }) }), Math });
const { swipeDirection, swipeTarget } = exportsObject;
let n = 0; const check = fn => { fn(); n++; };

check(() => assert.equal(swipeDirection(-120, 10, 250), 'next'));
check(() => assert.equal(swipeDirection(140, -20, 300), 'previous'));
check(() => assert.equal(swipeDirection(-40, 0, 200), null));      // too short
check(() => assert.equal(swipeDirection(-100, 90, 200), null));    // mostly vertical (a scroll)
check(() => assert.equal(swipeDirection(-200, 0, 1200), null));    // too slow (a drag)
check(() => assert.deepEqual({ ...swipeTarget('next', 0, 3, 1, 5) }, { kind: 'subtab', index: 1 }));
check(() => assert.deepEqual({ ...swipeTarget('next', 2, 3, 1, 5) }, { kind: 'page', index: 2 }));   // last sub-tab: next page
check(() => assert.deepEqual({ ...swipeTarget('previous', 0, 3, 1, 5) }, { kind: 'page', index: 0 }));
check(() => assert.deepEqual({ ...swipeTarget('next', 0, 0, 0, 5) }, { kind: 'page', index: 1 }));   // no sub-tabs (dashboard)
check(() => assert.equal(swipeTarget('previous', 0, 0, 0, 5), null));                                // nothing before the first page
console.log(`${n} swipe checks passed.`);
