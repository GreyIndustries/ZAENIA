// Wake-up calls and sleep phrases (core/calmPhrases.ts): small wording changes match, ordinary sentences don't.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/calmPhrases.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject, Set });
const { matchCalmPhrase } = exportsObject;
let n = 0; const check = fn => { fn(); n++; };
const is = (text, kind, id) => check(() => { const m = matchCalmPhrase(text); assert.ok(m, `no match for "${text}"`); assert.equal(m.kind, kind, text); assert.equal(m.id, id, text); });
const none = text => check(() => assert.equal(matchCalmPhrase(text), null, text));

is('Wake up sleepy, we have work to do!', 'wake', 1);
is('wake up sleepy we got work to do', 'wake', 1);
is('Sleeping on the job?', 'wake', 2);
is('Zae, sleeping on the job?', 'wake', 2);
is('The boss is here.', 'wake', 3);
is("Zae, you're still there?", 'wake', 4);
is('Zay are you still there', 'wake', 4);
is('The day is not yet over', 'wake', 5);
is('the night is still young', 'wake', 5);
is('Take everything to the background.', 'sleep', 1);
is("I'm going to sleep", 'sleep', 2);
is('I am going to sleep', 'sleep', 2);
is("Let's put a pin in this and continue tomorrow", 'sleep', 3);
is('Calm view', 'sleep', 4);
none('I think the boss is here to talk about the budget and the quarterly numbers today');
none('What time am I going to sleep tonight if I work out at nine and eat dinner late');
none('Add a calendar event');
none('');
console.log(`${n} calm phrase checks passed.`);
