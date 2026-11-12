const assert=require('node:assert/strict'),path=require('node:path');
const {launch}=require('./lib/cdp.cjs');
(async()=>{
 const b=await launch({width:1440,height:1000});
 const checks=[];
 try{
  await b.call('Page.navigate',{url:process.env.NODES_URL||'http://127.0.0.1:1539/'});
  await b.until('!!window.__ZAE_DEV__');
  const open=async(id,page,heading)=>{await b.evaluate(`window.dispatchEvent(new CustomEvent('zae:open-section',{detail:${JSON.stringify(id)}}))`);await b.delay(450);if(page)await b.evaluate(`window.dispatchEvent(new CustomEvent('zae:page-tab',{detail:{page:${JSON.stringify(id)},tab:${JSON.stringify(page)}}}))`);await b.until(`document.body.innerText.includes(${JSON.stringify(heading)})`);};
  await open('arena','training','LLM Training');
  assert(await b.evaluate(`!!document.querySelector('input[aria-label="Lesson title"]')`));checks.push('Training editor mounts');
  await b.screenshot(path.resolve(__dirname,'../../docs/previews/nodes/desktop-training.png'));
  await open('warroom','business','Business planning');
  assert(await b.evaluate(`!!document.querySelector('textarea[aria-label="Section content"]')`));checks.push('Business plan editor mounts');
  await b.screenshot(path.resolve(__dirname,'../../docs/previews/nodes/desktop-warroom.png'));
  await open('warroom','cameras','Camera registry');checks.push('Camera registry is explicit about connection limits');
  await open('research','workshop','Follow the evidence further');checks.push('Evidence workshop mounts');
  await open('research','cards','Learn and review');checks.push('Study card editor mounts');
  await b.viewport(390,844,true);
  await open('warroom','defense','Defense planning');
  assert(await b.evaluate(`(()=>{const el=[...document.querySelectorAll('.node-workspace')].find(e=>e.getBoundingClientRect().width>0&&e.innerText.includes('Defense planning'));return !!el&&el.scrollWidth<=el.clientWidth+2})()`));checks.push('Phone defense editor has no internal horizontal overflow');
  await b.screenshot(path.resolve(__dirname,'../../docs/previews/nodes/phone-warroom.png'));
  assert.equal(b.errors.filter(e=>!e.includes('WebGL')).length,0,b.errors.join('\n'));
  console.log('PASS',checks.length,'rendered checks:',checks.join('; '));
 }finally{await b.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
