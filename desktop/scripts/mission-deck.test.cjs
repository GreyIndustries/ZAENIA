const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript'),assert=require('node:assert/strict');
const store=new Map(),listeners=new Map();
const env={Date,Number,Math,JSON,Object,Array,Set,Map,Event:class{},localStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},window:{dispatchEvent:e=>{for(const fn of listeners.get(e.type)??[])fn(e)}}};
const cache=new Map();function load(file){file=path.resolve(__dirname,'../src',file);if(!file.endsWith('.ts'))file+='.ts';if(cache.has(file))return cache.get(file);const output={};cache.set(file,output);vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText,{...env,exports:output,require:p=>load(path.relative(path.join(__dirname,'../src'),path.resolve(path.dirname(file),p)))});return output;}
const activity=load('core/pageActivity'),voice=load('core/voiceUi'),layout=load('core/windowLayout'),catalog=load('core/pageCatalog');
const now=Date.now(),work={key:'tasks/fitness-food/cookbook',app:'tasks',navigator:'fitness-food',page:'cookbook',label:'Cookbook',subject:'Protein pancakes',action:'edited',at:now};
assert.equal(activity.normalizeActivities([{...work,body:'private input',token:'not retained'}])[0].body,undefined);
assert.equal(activity.normalizeActivities([{...work,at:now+1000}]).length,0);
assert.equal(activity.normalizeActivities([{...work,key:'wrong'}]).length,0);
activity.recordPageActivity(work);let manager=new activity.ResumeOffers();
assert.match(manager.offer(work),/Protein pancakes, sir\. Would you want to continue\?/);
assert.equal(manager.offer(work),null);
assert.equal(manager.answer("I'll do it later").answer,'later');
assert.equal(new activity.ResumeOffers().offer(work,now+60000),null);
assert.ok(new activity.ResumeOffers().offer(work,now+864e5+1000));
activity.clearPageActivities();manager=new activity.ResumeOffers();manager.offer(work);assert.equal(manager.answer("don't ask me again").answer,'dismiss');assert.equal(new activity.ResumeOffers().offer(work),null);
const sameWork={...work,at:now+1};assert.equal(new activity.ResumeOffers().offer(sameWork,now+2),null);
const newWork={...work,at:now+1,subject:"A different recipe"};assert.ok(new activity.ResumeOffers().offer(newWork,now+2));
for(const phrase of ['later','not now','no thanks',"I'm doing something else","I'll get to it later","I will do that tomorrow"]){assert.equal(activity.parseResumeAnswer(phrase),'later',phrase)}
assert.equal(activity.parseResumeAnswer('yes delete all files'),null);
assert.equal(activity.parseResumeAnswer('remind me tomorrow'),null);
activity.clearPageActivities();manager=new activity.ResumeOffers();manager.offer(work);assert.equal(manager.answer('yes').answer,'continue');assert.equal(new activity.ResumeOffers().offer(work),null);
for(const count of [2,3,4]){const rects=layout.snapRectangles(count);assert.equal(rects.length,count);for(const r of rects)assert.ok(r.x>=0&&r.y>=0&&r.x+r.w<=1&&r.y+r.h<=1);for(let i=0;i<count;i++)for(let j=i+1;j<count;j++){const a=rects[i],b=rects[j];assert.ok(a.x+a.w<=b.x||b.x+b.w<=a.x||a.y+a.h<=b.y||b.y+b.h<=a.y);}}
for(const [phrase,count] of [['split into two',2],['arrange three windows',3],['tile four windows',4],['split the screen into 2 windows',2]])assert.equal(voice.parseUiCommand(phrase).count,count,phrase);
assert.deepEqual(JSON.parse(JSON.stringify(voice.parseUiCommand('put notes and research side by side').apps)),['notes','research']);
assert.equal(voice.parseUiCommand('split my protein into two meals'),null);
assert.equal(voice.parseUiCommand('Set Search to Comets').value,'Comets');
assert.equal(voice.parseUiCommand('open notebook').kind,'ambiguous');
assert.equal(voice.parseUiCommand('open notebook','research').route.app,'research');
assert.deepEqual(JSON.parse(JSON.stringify(voice.parseUiCommand('open recipes').route.path)),['fitness','food','cookbook']);
assert.equal(voice.routeForActivity(work).path.join('/'),'fitness/food/cookbook');
let count=0;for(const app of catalog.PAGE_CATALOG)for(const page of catalog.flattenPages(app)){const command=voice.parseUiCommand('open '+app.label+' '+page.label.replaceAll(' / ',' '));assert.equal(command?.kind,'navigate',app.label+'/'+page.label);assert.equal(command.route.app,app.id);assert.equal(command.route.path.join('/'),page.path.join('/'));count++;}
assert.equal(count,112); // Includes approved War Room, learning and Research destinations.
console.log('PASS Mission Deck: resume/defer/dismiss persistence and new context, metadata filtering, 2/3/4 geometry, natural layout phrases and all 112 page voice destinations.');
