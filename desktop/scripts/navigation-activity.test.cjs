const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const assert = require('node:assert/strict');
const storage = new Map(); let events = 0;
const output = {};
const context = { exports: output, Date, Set, Number, JSON, Event: class {},
  window: { dispatchEvent: () => events++ },
  localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key,value) => storage.set(key,value), removeItem: key => storage.delete(key) } };
vm.runInNewContext(ts.transpileModule(readFileSync(join(__dirname,'../src/core/navigationActivity.ts'),'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
}).outputText, context);
const { normalizeVisits, recordAppVisit, readAppVisits, clearAppVisits, VISITS_KEY } = output;
const plain = value => JSON.parse(JSON.stringify(value));
assert.deepEqual(plain(normalizeVisits(null)), []);
assert.deepEqual(plain(normalizeVisits([null, 2, {id:'../../secrets',at:20}, {id:'notes',at:'20'}, {id:'notes',at:Infinity}, {id:'notes',at:101}],100)), []);
assert.deepEqual(plain(normalizeVisits([{id:'notes',at:10,document:'private'}, {id:'music',at:30}, {id:'notes',at:20}],100)), [{id:'music',at:30},{id:'notes',at:20}]);
const ids=['tasks','fitness','notes','research','news','assistant','music','workbench','codedoctor','files','arena','system','status','security'];
assert.equal(normalizeVisits(ids.map((id,i)=>({id,at:i+1})),100).length,10);
storage.set(VISITS_KEY, '{broken'); assert.deepEqual(plain(readAppVisits()), []);
recordAppVisit('notes');recordAppVisit('notes');recordAppVisit('music');recordAppVisit('untrusted');
assert.equal(readAppVisits().length,2);assert.equal(events,3);
assert.ok(readAppVisits().every(item=>Object.keys(item).sort().join(',')==='at,id'));
clearAppVisits();assert.equal(storage.has(VISITS_KEY),false);assert.deepEqual(plain(readAppVisits()),[]);
context.localStorage.getItem=()=>{throw Error('disabled')};context.localStorage.setItem=()=>{throw Error('disabled')};context.localStorage.removeItem=()=>{throw Error('disabled')};
assert.doesNotThrow(()=>{readAppVisits();recordAppVisit('notes');clearAppVisits()});
console.log('PASS navigation history: malformed/unknown/future records, deduplication, ordering, 10-app cap, content stripping, clear and disabled storage.');
