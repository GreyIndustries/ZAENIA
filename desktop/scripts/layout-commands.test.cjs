// Layout command parsing: pure, no browser or API.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/layoutCommands.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject });
const { parseLayoutCommand } = exportsObject;
let checks = 0;
const expect = (text, expected) => { assert.deepEqual(JSON.parse(JSON.stringify(parseLayoutCommand(text))), expected, text); checks++; };

expect('shrink and put in left corner', [{ kind: 'place', target: 'focused', spot: 'top-left', small: true }]);
expect('Zae, move the calendar to the right', [{ kind: 'place', target: 'calendar', spot: 'right', small: false }]);
expect('put the core in the bottom right corner', [{ kind: 'place', target: 'core', spot: 'bottom-right', small: true }]);
expect('open my calendar', [{ kind: 'open', target: 'calendar' }]);
expect('can you pull up my tasks please', [{ kind: 'open', target: 'tasks' }]);
expect('show system status', [{ kind: 'open', target: 'status' }]);
expect('clear the workspace', [{ kind: 'clear' }]);
expect('close all windows', [{ kind: 'close', target: 'all' }]);
expect('close all', [{ kind: 'close', target: 'all' }]);
expect('minimize all', [{ kind: 'minimize', target: 'all' }]);
expect('minimise all the tabs', [{ kind: 'minimize', target: 'all' }]);
expect('close it', [{ kind: 'close', target: 'focused' }]);
expect('please close this tab', [{ kind: 'close', target: 'focused' }]);
expect('minimize', [{ kind: 'minimize', target: 'focused' }]);
expect('put in right top corner', [{ kind: 'place', target: 'focused', spot: 'top-right', small: true }]);
expect('put it in the left bottom corner', [{ kind: 'place', target: 'focused', spot: 'bottom-left', small: true }]);
expect('Zae, put this tab in the upper right corner', [{ kind: 'place', target: 'focused', spot: 'top-right', small: true }]);
expect('close all tabs except calendar', null);
expect('minimize all but tasks', null);
expect('minimize files', [{ kind: 'minimize', target: 'files' }]);
expect('make it bigger', [{ kind: 'size', target: 'focused', grow: true }]);
expect('hide the sidebar', [{ kind: 'sidebar', show: false }]);
expect('full screen calendar', [{ kind: 'maximize', target: 'calendar' }]);
// Ordinary conversation is not a command.
expect('open my notes', [{ kind: 'open', target: 'notes' }]);
expect('move notes to the left', [{ kind: 'place', target: 'notes', spot: 'left', small: false }]);
for (const text of ["what's on my calendar today", 'hello', 'I need to move my dentist appointment', 'the right answer is four',
  'tell me about the files you changed', 'add a task to clean the garage', 'shut down the computer', 'get rid of my old tasks', 'hide all my files']) {
  assert.equal(parseLayoutCommand(text), null, text); checks++;
}
const phraseExports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/layoutPhrases.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText, { exports: phraseExports });
let variations = 0;
phraseExports.LAYOUT_PHRASES.forEach((group, index) => {
  for (const phrase of group.examples) {
    const parsed = parseLayoutCommand(phrase);
    assert.equal(parsed?.[0]?.kind, group.intent, phrase);
    assert.equal(parsed?.[0]?.target, [0, 1, 7].includes(index) ? 'all' : 'focused', phrase);
    variations++; checks++;
  }
});
expect('make it wider', [{ kind: 'size', target: 'focused', grow: true, axis: 'width' }]);
expect('make it shorter', [{ kind: 'size', target: 'focused', grow: false, axis: 'height' }]);
console.log(`${variations} natural phrase variations match their intended tab and action.`);
console.log(`${checks} layout command checks passed.`);
