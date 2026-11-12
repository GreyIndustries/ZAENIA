const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
const cache=new Map();
function load(file){file=path.resolve(__dirname,'../src',file);if(!file.endsWith('.ts'))file+='.ts';if(cache.has(file))return cache.get(file);const exports={};cache.set(file,exports);vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports,localStorage:{getItem:()=>null},require:p=>load(path.relative(path.join(__dirname,'../src'),path.resolve(path.dirname(file),p)))});return exports;}
const voice=load('core/voiceUi'),catalog=load('core/pageCatalog');
for(const [phrase,app,page] of [['open mail','tasks','mail'],['open email','tasks','mail'],['open inbox','tasks','mail'],['open schedule board','tasks','plan'],['open llm training','arena',undefined],['open war room','warroom',undefined],['open analysis workshop','research','workshop'],['open learning explorer','research','reference'],['open study cards','research','cards']]){const result=voice.parseUiCommand(phrase);assert.equal(result?.kind,'navigate',phrase);assert.equal(result.route.app,app,phrase);if(page)assert.equal(result.route.path[0],page,phrase);}
assert.equal(catalog.categoryForRoute('workbench'),'build');
assert.equal(catalog.CATEGORY_MODULES.health,undefined);
assert.equal(catalog.PAGE_CATALOG.find(x=>x.id==='assistant').pages.some(x=>x.id==='mail'),false);
assert.equal(catalog.PAGE_CATALOG.find(x=>x.id==='tasks').pages.find(x=>x.id==='plan').label,'Schedule Board');
assert.equal(voice.parseUiCommand('show nodes').kind,'tabs');
assert.equal(voice.parseUiCommand('close this node').kind,'close-tab');
console.log('PASS 15 node destination, category, naming and voice-routing checks.');
