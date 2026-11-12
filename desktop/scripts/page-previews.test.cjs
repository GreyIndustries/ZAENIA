const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),ts=require('typescript');
const result={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/core/pageCatalog.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:result});
const {PAGE_CATALOG,flattenPages,lastAppView}=result;
assert.equal(new Set(PAGE_CATALOG.map(a=>a.id)).size,PAGE_CATALOG.length);
for(const app of PAGE_CATALOG){const flattened=flattenPages(app);assert.ok(flattened.length);assert.equal(new Set(flattened.map(p=>p.id)).size,flattened.length);assert.ok(flattened.every(p=>p.path.length&&p.label.length));}
assert.equal(lastAppView('notes',key=>key==='zaenia.pageTab.notes'?'editor':null),'All notes');
assert.equal(lastAppView('research',key=>key==='zaenia.researchTab'?'library':null),'The Library');
const fitness={'zaenia.pageTab.life':'fitness','zaenia.fitness.section':'food','zaenia.fitness.food':'cookbook'};
assert.equal(lastAppView('tasks',key=>fitness[key]??null),'Fitness & Health / Food / Cookbook');
assert.equal(lastAppView('system',key=>({'zaenia.pageTab.settingshub':'security','zaenia.pageTab.security':'activity'}[key]??null)),'Security / Activity');
assert.equal(lastAppView('notes',()=>'../../credentials'),null);
const keys=[];assert.equal(lastAppView('private-record',key=>{keys.push(key);return null}),null);assert.equal(keys.length,0);
lastAppView('tasks',key=>{keys.push(key);return null});assert.ok(keys.every(k=>k.startsWith('zaenia.pageTab.')||k.startsWith('zaenia.fitness.')||k==='zaenia.plan.tab'));
console.log(`PASS: ${PAGE_CATALOG.length} app inventories, ${PAGE_CATALOG.flatMap(flattenPages).length} unique page destinations, saved-view aliases, malformed values and allowlisted presentation storage.`);
