// Rendered behaviour of page navigation and split panes in real headless Chrome (Claude, 2026-11-11).
// Needs a running dev or served build: NAV_URL=http://127.0.0.1:1531/ node scripts/nav-split-browser.test.cjs
// Uses preview mode (no Core, no owner data). Typed chat commands use the same deterministic parser as
// recognised voice; real microphone recognition is not exercised here.
const assert = require('node:assert/strict');
const path = require('node:path');
const { launch } = require('./lib/cdp.cjs');
const URL = process.env.NAV_URL || 'http://127.0.0.1:1531/';
const SHOTS = process.env.NAV_SHOTS || path.resolve(__dirname, '../../docs/previews/nav-split');
const results = [];
const only = process.env.NAV_ONLY ? new RegExp(process.env.NAV_ONLY, 'i') : null;
const step = async (name, fn) => { if (only && !only.test(name)) return; try { await fn(); results.push(['PASS', name]); } catch (error) { results.push(['FAIL', name, error.message.split('\n')[0]]); } if (process.env.NAV_VERBOSE) console.log(...results.at(-1)); };

(async () => {
  try { await fetch(URL); } catch { console.log(`SKIP nav-split browser checks: nothing is serving ${URL}`); return; }
  const b = await launch({ width: 1440, height: 900 });
  const js = expression => b.evaluate(expression);
  const devReady = async () => { for (let i = 0; i < 40 && !(await js('!!window.__ZAE_DEV__')); i++) await b.delay(250); };
  const open = id => js(`window.dispatchEvent(new CustomEvent('zae:open-section',{detail:'${id}'}))`);
  const pageTab = (page, tab) => js(`window.dispatchEvent(new CustomEvent('zae:page-tab',{detail:{page:'${page}',tab:'${tab}'}}))`);
  const panes = () => js(`JSON.stringify([...document.querySelectorAll('.os-window:not([hidden])')].map(w=>{const r=w.getBoundingClientRect();return {id:w.dataset.windowId,x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}}))`).then(JSON.parse);
  const current = (win, nav) => js(`document.querySelector('[data-window-id="${win}"] [data-page-navigator="${nav}"]')?.dataset.pageCurrent ?? null`);
  const center = selector => js(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()`);
  const mouseButton = async (selector, button) => { const [x, y] = await center(selector); await b.mouse('mousePressed', x, y, button, button === 'back' ? 8 : 16); await b.mouse('mouseReleased', x, y, button, 0); await b.delay(400); };
  const chat = async text => { if (process.env.NAV_VERBOSE) console.log("  chat:", text);
    await js(`(()=>{const f=[...document.querySelectorAll('textarea,input')].find(x=>/Ask Z/i.test(x.placeholder||''));f.focus();})()`);
    await b.type(text); await b.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 }); await b.call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 }); await b.delay(700);
  };
  const choose = async n => {
    if (await js(`document.querySelector('.zt-manage').getAttribute('aria-expanded')!=='true'`)) await js(`document.querySelector('.zt-manage').click()`);
    await b.delay(150); await js(`document.querySelector('.zt-manager .os-snap-trigger').click()`); await b.delay(150);
    await js(`document.querySelector('.os-snap-picker button[aria-label="${n} windows"]').click()`); await b.delay(700);
    await js(`document.querySelector('.zt-manage')?.getAttribute('aria-expanded')==='true'&&document.querySelector('.zt-manage').click()`); await b.delay(200);
  };
  /** Breadcrumb of the visible leaf/record screen in a window: "Life > LIFE > … > here". */
  const crumbsIn = (scope, which = '.page-nav--leaf') => js(`[...document.querySelectorAll('${scope} ${which}:not([hidden]) .bx-crumbs')].filter(n=>n.getClientRects().length).map(n=>[...n.querySelectorAll('button,.here')].map(x=>x.textContent).join(' > ')).pop()||''`);

  await b.call('Page.navigate', { url: URL }); await b.delay(2500);
  await js(`localStorage.clear();sessionStorage.clear();localStorage.setItem('zaenia.navigation.recentApps.v1',JSON.stringify([{id:'research',at:Date.now()-1000}]))`);
  await b.call('Page.navigate', { url: URL }); await b.delay(3500);

  await step('picker stays open on hover then click', async () => {
    await open('notes'); await b.delay(900);
    const [x, y] = await center('[data-window-id="notes"] .bx-ctl .os-snap-trigger');
    await b.mouse('mouseMoved', x, y, 'none', 0); await b.delay(450);
    await b.mouse('mousePressed', x, y); await b.mouse('mouseReleased', x, y, 'left', 0); await b.delay(200);
    assert.equal(await js(`!!document.querySelector('.os-snap-picker')`), true);
  });
  await step('2 panes with only one window open fills from recent apps', async () => {
    await js(`document.querySelector('.os-snap-picker button[aria-label="2 windows"]').click()`); await b.delay(800);
    const list = await panes();
    assert.deepEqual(list.map(p => p.id), ['notes', 'research']);
    assert.ok(list[0].w > 600 && list[1].x > 700, JSON.stringify(list));
    assert.match(await js(`document.querySelector('.os-arrange-toast')?.textContent||''`), /Arranged 2 windows: Notes, Research/);
    await b.screenshot(path.join(SHOTS, '01-two-panes-from-one-window.png'));
  });
  await step('panes navigate independently with their own Back (button, mouse, typed command)', async () => {
    await pageTab('research', 'library'); await b.delay(300); await pageTab('research', 'news'); await b.delay(300);
    await pageTab('notes', 'map'); await b.delay(300);
    assert.equal(await current('research', 'research'), 'news');
    await mouseButton('[data-window-id="research"] .os-window__body', 'back');
    assert.equal(await current('research', 'research'), 'library', 'mouse back');
    assert.equal(await current('notes', 'notes'), 'map', 'other pane untouched');
    await js(`document.querySelector('[data-window-id="research"] [data-pane-back]').click()`); await b.delay(300);
    { const now = await current('research', 'research'); assert.equal(now, 'home-view', 'Back button returns to the module home it opened on: ' + now + ' ' + await js(`JSON.stringify([...document.querySelectorAll('[data-window-id="research"] [data-pane-back]')].map(x=>x.className+':'+!!x.getClientRects().length))`)); }
    await mouseButton('[data-window-id="research"] .os-window__body', 'forward');
    assert.equal(await current('research', 'research'), 'library', 'mouse forward');
    await js(`document.querySelector('[data-window-id="notes"] .os-window__body').dispatchEvent(new PointerEvent('pointerenter'))`);
    await js(`document.querySelector('[data-window-id="notes"] .os-window__body').focus()`);
    await js(`document.querySelector('[data-window-id="notes"]').dispatchEvent(new FocusEvent('focusin',{bubbles:true}))`);
    await chat('go back'); assert.equal(await current('notes', 'notes'), 'home-view', 'typed "go back" acts on the attended pane (Notes opened on its home)');
    assert.equal(await current('research', 'research'), 'library');
  });
  await step('3 then 4 panes work after an earlier arrangement (minimized windows count)', async () => {
    await open('tasks'); await b.delay(900); await open('assistant'); await b.delay(900);
    await choose(2); assert.equal((await panes()).length, 2);
    await choose(3); let list = await panes(); assert.equal(list.length, 3, JSON.stringify(list));
    assert.ok(list[0].h > 600 && list[1].h < 340 && list[2].h < 340, 'one large, two small');
    await b.screenshot(path.join(SHOTS, '02-three-panes.png'));
    await choose(4); list = await panes(); assert.equal(list.length, 4);
    assert.equal(new Set(list.map(p => `${p.x > 700}-${p.y > 400}`)).size, 4, 'grid');
    await b.screenshot(path.join(SHOTS, '03-four-panes.png'));
  });
  await step('no background/core overlay intercepts pane clicks', async () => {
    // The floating chat transcript (existing design) may sit over a pane until it folds; anything else is a failure.
    const misses = await js(`[...document.querySelectorAll('.os-window:not([hidden])')].map(w=>{const r=w.getBoundingClientRect();const e=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return w.contains(e)||e?.closest('.home-chat')?null:(e?.className||e?.tagName||'none').toString()}).filter(Boolean)`);
    assert.deepEqual(misses, []);
  });
  await step('nested LIFE screens show a breadcrumb and one header', async () => {
    await pageTab('life', 'fitness'); await b.delay(500); await pageTab('fitness', 'food'); await b.delay(500); await pageTab('fitness-food', 'cookbook'); await b.delay(500);
    const crumbs = await crumbsIn('[data-window-id="tasks"]');
    assert.match(crumbs, /Life > LIFE > Fitness & Health > Food > Cookbook$/, crumbs);
    assert.equal(await js(`document.querySelector('[data-window-id="tasks"] .page-nav--leaf:not([hidden]) h2').textContent`), 'Cookbook');
    assert.equal(await js(`document.querySelectorAll('[data-window-id="tasks"] .page-nav--leaf:not([hidden])').length`), 1);
  });
  await step('maximize then restore returns the pane to its slot', async () => {
    const before = (await panes()).find(p => p.id === 'tasks');
    await js(`document.querySelector('[data-window-id="tasks"] [aria-label^="Maximize"]').click()`); await b.delay(500);
    const big = (await panes()).find(p => p.id === 'tasks'); assert.ok(big.w > 1400, 'maximized');
    await js(`document.querySelector('[data-window-id="tasks"] [aria-label^="Restore size"]').click()`); await b.delay(500);
    assert.deepEqual((await panes()).find(p => p.id === 'tasks'), before);
  });
  await step('drafts survive being minimized by an arrangement', async () => {
    await pageTab('life', 'plan'); await b.delay(500);
    const ok = await js(`(()=>{const f=[...document.querySelectorAll('[data-window-id="tasks"] input,[data-window-id="tasks"] textarea')].find(x=>x.getClientRects().length&&!['checkbox','radio','range','file','password'].includes(x.type));if(!f)return false;f.focus();return true})()`);
    if (!ok) { await pageTab('life', 'plan'); await b.delay(500); await js(`(()=>{const f=[...document.querySelectorAll('[data-window-id="tasks"] input,[data-window-id="tasks"] textarea')].find(x=>x.getClientRects().length&&!['checkbox','radio','range','file','password'].includes(x.type));f.focus()})()`); }
    await b.type('unsaved draft 42');
    await chat('put notes and research side by side'); // LIFE is not named, so the arrangement minimizes it
    const minimized = await js(`document.querySelector('[data-window-id="tasks"]').hidden`);
    await open('tasks'); await b.delay(500);
    const kept = await js(`[...document.querySelectorAll('[data-window-id="tasks"] input,[data-window-id="tasks"] textarea')].some(x=>x.value==='unsaved draft 42')`);
    assert.equal(minimized && kept, true, `minimized=${minimized} kept=${kept}`);
  });
  await step('Undo restores the previous arrangement', async () => {
    await choose(4); const four = await panes();
    await choose(2); assert.equal((await panes()).length, 2);
    await js(`[...document.querySelectorAll('.os-arrange-toast button')].find(x=>x.textContent==='Undo').click()`); await b.delay(500);
    assert.deepEqual((await panes()).map(p => p.id).sort(), four.map(p => p.id).sort());
  });
  await step('resizing a pane moves the shared edge of its neighbour', async () => {
    await choose(2); const [left, right] = await panes();
    const [x, y] = await center(`[data-window-id="${left.id}"] .os-window__resize--e`);
    await b.mouse('mouseMoved', x, y, 'none', 0); await b.mouse('mousePressed', x, y);
    for (let dx = 20; dx <= 140; dx += 20) await b.mouse('mouseMoved', x + dx, y, 'left', 1);
    await b.mouse('mouseReleased', x + 140, y, 'left', 0); await b.delay(300);
    const [l2, r2] = await panes();
    assert.ok(l2.w > left.w + 100 && r2.x > right.x + 100 && Math.abs(r2.x + r2.w - (right.x + right.w)) < 3, JSON.stringify([left, right, l2, r2]));
    await b.screenshot(path.join(SHOTS, '04-two-panes-resized.png'));
  });
  await step('scroll position is kept per page', async () => {
    const id = (await panes())[0].id;
    await pageTab({ notes: 'notes', research: 'research', tasks: 'life' }[id] ?? id, { notes: 'board', research: 'desk', tasks: 'plan' }[id] ?? ''); await b.delay(500);
    const nav = await js(`document.querySelector('[data-window-id="${id}"] .page-nav--leaf').dataset.pageNavigator`);
    const first = await current(id, nav);
    const other = await js(`[...document.querySelectorAll('[data-window-id="${id}"] .page-nav--leaf .page-nav__siblings button:not(.on)')][0].textContent`);
    await js(`(()=>{const b=document.querySelector('[data-window-id="${id}"] .os-window__body');const s=document.createElement('div');s.className='test-spacer';s.style.height='2400px';b.querySelector('.glass-module').appendChild(s);b.scrollTop=420;b.dispatchEvent(new Event('scroll'))})()`); await b.delay(250);
    await js(`[...document.querySelectorAll('[data-window-id="${id}"] .page-nav--leaf .page-nav__siblings button')].find(x=>x.textContent===${JSON.stringify(other)}).click()`); await b.delay(300);
    const away = await js(`document.querySelector('[data-window-id="${id}"] .os-window__body').scrollTop`);
    await js(`document.querySelector('[data-window-id="${id}"] [data-pane-back]').click()`); await b.delay(300);
    assert.equal(await current(id, nav), first);
    const back = await js(`document.querySelector('[data-window-id="${id}"] .os-window__body').scrollTop`);
    assert.ok(away < 50 && Math.abs(back - 420) < 5, `away=${away} back=${back}`);
    await js(`document.querySelector('[data-window-id="${id}"] .test-spacer')?.remove()`);
  });
  await step('typed layout and pane commands use the shared parser', async () => {
    await chat('arrange four windows'); assert.equal((await panes()).length, 4, 'four: ' + JSON.stringify(await panes()));
    await chat('undo window arrangement'); assert.equal((await panes()).length, 2, 'undo: ' + JSON.stringify(await panes()));
    await chat('next pane'); assert.match(await js(`document.body.innerText`), /pane, sir\./);
  });
  await step('reload restores panes, sub-pages and Back history', async () => {
    const before = await panes(); const page = await current('research', 'research');
    await b.call('Page.reload'); await b.delay(4000);
    assert.deepEqual((await panes()).map(p => p.id), before.map(p => p.id));
    assert.equal(await current('research', 'research'), page);
    assert.equal(await js(`!document.querySelector('[data-window-id="research"] [data-pane-back]').disabled`), true, 'Back history survives reload');
  });

  await step('screen tabs: Build requests | Suggestions side by side, tab manager, close and reopen', async () => {
    await js(`localStorage.removeItem('zaenia.shellWindows')`); await b.call('Page.reload'); await b.delay(3500);
    await js(`window.dispatchEvent(new CustomEvent('zae:open-route',{detail:{app:'codedoctor',path:['build'],label:'Build requests'}}))`); await b.delay(2500);
    await js(`document.querySelector('[data-window-id="codedoctor"] [data-open-new-tab]').click()`); await b.delay(2500);
    let tabs = JSON.parse(await js(`JSON.stringify([...document.querySelectorAll('.zt-strip .zt-tab')].map(t=>t.dataset.tabId))`));
    assert.equal(tabs.length, 2, 'Open in new tab adds a second Code Doctor tab'); assert.ok(tabs[1].startsWith('codedoctor~'), tabs.join());
    await chat('split build requests and suggestions'); await b.delay(2500);
    const list = await panes(); assert.equal(list.length, 2, JSON.stringify(list));
    assert.ok(list.every(p => p.id.startsWith('codedoctor')) && Math.abs(list[0].x - list[1].x) > 600, JSON.stringify(list));
    const pages = await js(`[...document.querySelectorAll('.os-window:not([hidden])')].sort((a,b)=>a.getBoundingClientRect().x-b.getBoundingClientRect().x).map(w=>w.querySelector('[data-page-navigator="codedoctor"]')?.dataset.pageCurrent).join('|')`);
    assert.equal(pages, 'build|suggestions', 'each tab keeps its own page');
    assert.match(await js(`[...document.querySelectorAll('.zt-tab .zt-t')].map(x=>x.textContent).join('|')`), /Build requests\|Suggestions/, 'tab titles follow the page');
    await b.screenshot(path.join(SHOTS, 'v2', '20-tabs-split-build-suggestions.png'));
    // Each tab has its own history: Back in the right tab does not move the left one.
    const right = list.sort((a, c) => a.x - c.x)[1].id;
    await js(`window.dispatchEvent(new CustomEvent('zae:page-tab',{detail:{page:'codedoctor',tab:'files',pane:'${right}'}}))`); await b.delay(400);
    assert.equal(await js(`document.querySelector('[data-window-id="${right}"] [data-page-navigator="codedoctor"]').dataset.pageCurrent`), 'files');
    assert.equal(await js(`document.querySelector('[data-window-id="codedoctor"] [data-page-navigator="codedoctor"]').dataset.pageCurrent`), 'build', 'a pane-addressed page change stays in its pane');
    await chat('show tabs'); await b.delay(500);
    assert.equal(await js(`document.querySelectorAll('.zt-manager .zt-list li').length`), 2, 'manager lists every tab');
    assert.match(await js(`document.querySelector('.zt-manager').innerText`), /Code Doctor/, 'manager shows where each tab is');
    await b.screenshot(path.join(SHOTS, 'v2', '21-tab-manager.png'));
    await js(`document.querySelector('.zt-manager [aria-label^="Pin"]').click()`); await b.delay(300);
    assert.equal(await js(`document.querySelectorAll('.zt-tab.pinned').length`), 1, 'pin');
    await js(`[...document.querySelectorAll('.zt-manager [aria-label^="Move"][aria-label$="down"]')].find(x=>!x.disabled)?.click()`); await b.delay(300);
    await js(`document.querySelector('.zt-manager [aria-label="Close node manager"]').click()`); await b.delay(200);
    await js(`window.dispatchEvent(new CustomEvent('zae:open-tab',{detail:{app:'research',path:['library'],label:'Research / The Library'}}))`); await b.delay(2500);
    assert.equal(await js(`document.querySelectorAll('.zt-tab').length`), 3, 'zae:open-tab (Ctrl/middle-click, voice) opens a third tab');
    await chat('close this tab'); await b.delay(500);
    assert.equal(await js(`document.querySelectorAll('.zt-tab').length`), 2, 'close this tab');
    await chat('reopen closed tab'); await b.delay(800);
    assert.equal(await js(`document.querySelectorAll('.zt-tab').length`), 3, 'reopen closed tab');
    const opaque = await js(`[...document.querySelectorAll('.os-window:not([hidden])')].every(w=>{const s=getComputedStyle(w);const alphas=[...s.backgroundImage.matchAll(/rgba\(([^)]*)\)/g)].map(m=>Number(m[1].split(',').pop()));return s.backgroundImage!=='none'&&alphas.every(a=>a>=0.999)})`);
    assert.equal(opaque, true, 'pane backgrounds are opaque');
    assert.equal(await js(`[...document.querySelectorAll('.os-arrange-toast,.voice-note,[role=status]')].some(x=>/Nothing to go forward to/.test(x.textContent))`), false, 'no stuck forward toast');
  });
  const V2 = path.join(SHOTS, 'v2');
  const workspace = async id => { await js(`window.dispatchEvent(new CustomEvent('zae:workspace',{detail:'${id}'}))`); await b.delay(900); };
  const closeHub = async () => { await js(`document.querySelector('.navhub__close')?.click()`); await b.delay(300); };
  await step('category pages show every module as a bento tile with every screen inside', async () => {
    const expected = { plan: { LIFE: ['Schedule Board', 'Fitness & Health', 'Mail', 'GODSPEED'], Notes: ['Board', 'Notebook', 'Map', 'All notes'] },
      know: { Research: 13, Assistant: 4 }, create: { Music: 4 }, build: { Workbench: 6, 'Code Doctor & Files': 11, 'LLM Training': 7 },
      warroom: { 'War Room': ['Defense planning', 'Business plans', 'Cameras'] }, system: { Settings: 9, Status: 8, Security: 5 } };
    for (const [id, modules] of Object.entries(expected)) {
      await workspace(id);
      const tiles = JSON.parse(await js(`JSON.stringify(Object.fromEntries([...document.querySelectorAll('.navhub .bx-bt')].map(t=>[t.querySelector('.bx-n').textContent,[...t.querySelectorAll('.bx-mini button')].map(x=>x.firstChild.textContent)])))`));
      for (const [name, want] of Object.entries(modules)) {
        assert.ok(tiles[name], `${id}: ${name} tile missing (${Object.keys(tiles)})`);
        if (Array.isArray(want)) assert.deepEqual(tiles[name], want, `${id}/${name}`); else assert.equal(tiles[name].length, want, `${id}/${name}`);
      }
      assert.equal(await js(`[...document.querySelectorAll('.navhub .bx-bt.wide')].every(t=>t.querySelectorAll('.bx-mini button').length>6||document.querySelectorAll('.navhub .bx-bt').length===1)`), true, 'only a lone module or one with more than 6 screens spans full width');
      assert.equal(await js(`!!document.querySelector('.navhub .bx-seg [aria-selected=true]')&&!!document.querySelector('.navhub [data-page-search]')`), true, 'category switcher and search on every category page');
      await b.screenshot(path.join(V2, `0${Object.keys(expected).indexOf(id) + 1}-category-${id}.png`));
    }
    await closeHub();
  });
  await step('a screen tile opens that exact page', async () => {
    await workspace('know');
    await js(`[...([...document.querySelectorAll('.navhub .bx-bt')].find(t=>t.querySelector('.bx-n').textContent==='Research').querySelectorAll('.bx-mini button'))].find(x=>x.firstChild.textContent==='The Library').click()`); await b.delay(2500);
    assert.equal(await current('research', 'research'), 'library');
    assert.equal(await js(`!document.querySelector('.navhub')`), true, 'the sheet closes');
  });
  await step('search (Ctrl+K) finds any page and Enter opens the same page as voice', async () => {
    await b.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'k', code: 'KeyK', modifiers: 2, windowsVirtualKeyCode: 75 }); await b.delay(600);
    assert.equal(await js(`document.activeElement?.matches('[data-page-search]')`), true, 'Ctrl+K focuses search');
    await b.type('cookbook'); await b.delay(300);
    assert.match(await js(`document.querySelector('.bx-res.first')?.innerText||''`), /Cookbook[\s\S]*Life › LIFE › Fitness & Health › Food/);
    await b.screenshot(path.join(V2, '07-search-cookbook.png'));
    await b.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 }); await b.delay(3000);
    assert.equal(await js(`document.querySelector('[data-window-id="tasks"] [data-page-navigator="fitness-food"]')?.dataset.pageCurrent`), 'cookbook', 'Enter opened Cookbook: ' + await js(`JSON.stringify([...document.querySelectorAll('.os-window')].map(w=>w.dataset.windowId+(w.hidden?'(min)':'')))`));
    await b.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'k', code: 'KeyK', modifiers: 2, windowsVirtualKeyCode: 75 }); await b.delay(600);
    await b.type('traffic'); await b.delay(300);
    assert.match(await js(`document.querySelector('.bx-res.first')?.innerText||''`), /Traffic[\s\S]*GODSPEED/);
    await b.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 }); await b.delay(3000);
    assert.equal(await js(`document.querySelector('[data-window-id="tasks"] [data-page-navigator="godspeed"]')?.dataset.pageCurrent`), 'traffic', 'GODSPEED Traffic page');
    await pageTab('godspeed', 'weather'); await b.delay(500);
    await mouseButton('[data-window-id="tasks"] .os-window__body', 'back');
    assert.equal(await js(`document.querySelector('[data-window-id="tasks"] [data-page-navigator="godspeed"]')?.dataset.pageCurrent`), 'traffic', 'map screens are Back steps');
    await b.screenshot(path.join(V2, '11-godspeed-traffic-page.png'));
    await b.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'k', code: 'KeyK', modifiers: 2, windowsVirtualKeyCode: 75 }); await b.delay(600);
    await b.type('zzqx'); await b.delay(300);
    assert.match(await js(`[...document.querySelectorAll('.bx-nores')].map(x=>x.innerText).join()`), /No page called/);
    await closeHub();
  });
  await step('module page children use the bento treatment with counts', async () => {
    await js(`window.dispatchEvent(new CustomEvent('zae:open-route',{detail:{app:'tasks',path:[],label:'LIFE'}}))`); await b.delay(2500);
    const tiles = await js(`[...document.querySelectorAll('[data-window-id="tasks"] .bx-bento .bx-bt')].filter(t=>t.getClientRects().length).map(t=>t.querySelector('.bx-n').textContent+' '+t.querySelectorAll('.bx-mini button').length).join(' | ')`);
    assert.match(tiles, /Schedule Board \d+ \| Fitness & Health \d+ \| Mail \d+ \| GODSPEED \d+/, tiles);
    assert.equal(await crumbsIn('[data-window-id="tasks"]'), 'Life > LIFE');
    await b.screenshot(path.join(V2, '08-module-page-children.png'));
  });
  // Dev server only: the __ZAE_DEV__ bridge (stripped from production) injects a recognised-voice turn through the
  // same submit path as the microphone, and a local unsaved draft, so detail screens and the resume offer can be
  // checked without a Core or owner data.
  const dev = await js(`typeof window.__ZAE_DEV__?.voice === 'function'`);
  if (!dev) results.push(['SKIP', 'detail screens and voice resume offer (production build has no dev bridge; run against the dev server)']);
  if (dev) {
    const say = async text => { if (process.env.NAV_VERBOSE) console.log("  say:", text); await js(`window.__ZAE_DEV__.voice(${JSON.stringify(text)})`); await b.delay(900); };
    const lastReply = () => js(`[...document.querySelectorAll('.message')].map(m=>m.textContent).filter(Boolean).slice(-1)[0]||''`);
    const leafState = win => js(`JSON.stringify({leaf:[...document.querySelectorAll('[data-window-id="${win}"] .page-nav--leaf')].filter(n=>!n.closest('[hidden]')).map(n=>n.dataset.pageNavigator+':'+n.querySelector('h2')?.textContent),win:[...document.querySelectorAll('.os-window')].map(w=>w.dataset.windowId+(w.hidden?'(min)':'')),hub:!!document.querySelector('.navhub')})`);
    const leafTitle = win => js(`[...document.querySelectorAll('[data-window-id="${win}"] .page-nav--leaf')].filter(n=>!n.closest('[hidden]')).map(n=>n.querySelector('h2').textContent).join('|')`);
    await step('recipe opens as its own screen with breadcrumb; Back keeps the draft', async () => {
      await js(`localStorage.clear();sessionStorage.clear()`); await b.call('Page.reload'); await b.delay(3500);
      await devReady(); await js(`window.__ZAE_DEV__.seedDraft('recipes',{title:'Protein pancakes',archived:false,category:'Breakfast',mealTypes:['Breakfast'],servings:2,ingredients:[],instructions:'Whisk and cook.',source:'Owner recipe',weekOf:''})`);
      await open('tasks'); await b.delay(1200);
      await pageTab('life', 'fitness'); await b.delay(500); await pageTab('fitness', 'food'); await b.delay(500); await pageTab('fitness-food', 'cookbook'); await b.delay(700);
      await js(`[...document.querySelectorAll('[data-window-id="tasks"] .personal-resume')].find(x=>x.getClientRects().length).click()`); await b.delay(600);
      assert.equal(await leafTitle('tasks'), 'Protein pancakes', ('leaf') + ' ' + await leafState('tasks'));
      const crumbs = await crumbsIn('[data-window-id="tasks"]', '.page-nav--detail');
      assert.match(crumbs, /Food > Cookbook > Protein pancakes$/, crumbs);
      assert.equal(await js(`!!document.querySelector('[data-window-id="tasks"] .personal-editor input[value="Protein pancakes"], [data-window-id="tasks"] input')`), true);
      await b.screenshot(path.join(SHOTS, '08-recipe-detail-screen.png'));
      await mouseButton('[data-window-id="tasks"] .os-window__body', 'back');
      assert.equal(await leafTitle('tasks'), 'Cookbook', ('mouse Back returns to the Cookbook list') + ' ' + await leafState('tasks'));
      assert.match(await js(`[...document.querySelectorAll('[data-window-id="tasks"] .personal-resume')].find(x=>x.getClientRects().length)?.textContent||''`), /Protein pancakes · unsaved draft/);
      await mouseButton('[data-window-id="tasks"] .os-window__body', 'forward');
      assert.equal(await leafTitle('tasks'), 'Protein pancakes', ('Forward reopens the recipe') + ' ' + await leafState('tasks'));
    });
    await step('Fitness: training plan, targets, food and exercise entries open as their own screens', async () => {
      await js(`localStorage.removeItem('zaenia.shellWindows')`); await b.call('Page.reload'); await b.delay(3500);
      await devReady(); await js(`window.__ZAE_DEV__.seedDraft('plans',{title:'Push pull legs',archived:false,sourceUrl:'',sourceName:'Owner-created plan',sourceText:'',schedule:'Mon / Wed / Fri',steps:[],sessions:[]})`);
      await devReady(); await js(`window.__ZAE_DEV__.seedDraft('food',{title:'Greek yogurt bowl',archived:false,date:'2026-11-11',calories:320,protein:28,fiber:6,source:'Food label / manual entry'})`);
      await devReady(); await js(`window.__ZAE_DEV__.seedDraft('fitness-settings',{title:'My targets',archived:false,proteinTarget:180,fiberTarget:35,baselineCalories:null})`);
      await js(`document.querySelector('[data-window-id="tasks"] [aria-label^="Restore size"]')?.click()`);
      await open('tasks'); await b.delay(1200);
      await pageTab('life', 'fitness'); await b.delay(500); await pageTab('fitness', 'training'); await b.delay(500); await pageTab('fitness-training', 'plans'); await b.delay(800);
      const resume = label => js(`[...document.querySelectorAll('[data-window-id="tasks"] .personal-resume')].find(x=>x.getClientRects().length&&x.textContent.includes(${JSON.stringify(label)}))?.click()`);
      await resume('Push pull legs'); await b.delay(600);
      assert.equal(await leafTitle('tasks'), 'Push pull legs', ('leaf') + ' ' + await leafState('tasks'));
      assert.match(await crumbsIn('[data-window-id="tasks"]', '.page-nav--detail'), /Training > Plans & targets > Push pull legs$/);
      await b.screenshot(path.join(V2, '09-training-plan-screen.png'));
      await mouseButton('[data-window-id="tasks"] .os-window__body', 'back');
      assert.equal(await leafTitle('tasks'), 'Plans & targets', ('leaf') + ' ' + await leafState('tasks'));
      await resume('My targets'); await b.delay(600);
      assert.equal(await leafTitle('tasks'), 'My targets', ('leaf') + ' ' + await leafState('tasks'));
      await mouseButton('[data-window-id="tasks"] .os-window__body', 'back');
      await pageTab('fitness-training', 'log'); await b.delay(800);
      await resume('Greek yogurt bowl'); await b.delay(600);
      assert.equal(await leafTitle('tasks'), 'Greek yogurt bowl', ('leaf') + ' ' + await leafState('tasks'));
      assert.equal(await js(`[...document.querySelectorAll('[data-window-id="tasks"] .personal-log[data-detail="food"]')].some(x=>x.getClientRects().length)`), true, 'the rest of the Log page steps aside');
      assert.equal(await js(`[...document.querySelectorAll('[data-window-id="tasks"] h3')].some(x=>x.textContent==='Exercise log'&&x.getClientRects().length)`), false);
      await b.screenshot(path.join(V2, '10-food-entry-screen.png'));
      await say('go back');
      assert.equal(await leafTitle('tasks'), 'Food & exercise', ('leaf') + ' ' + await leafState('tasks'));
    });
    await step('Notes: the note editor is its own screen; Back returns to the wall with the draft kept', async () => {
      await js(`localStorage.removeItem('zaenia.shellWindows')`); await b.call('Page.reload'); await b.delay(3500);
      await devReady(); await js(`window.__ZAE_DEV__.seedNote({title:'Greenhouse pump wiring',body:'Relay on GPIO 17',pinned:false,reference:false,archived:false})`);
      await open('notes'); await b.delay(1000); await pageTab('notes', 'editor'); await b.delay(800);
      await js(`[...document.querySelectorAll('[data-window-id="notes"] .personal-resume')].find(x=>x.getClientRects().length&&x.textContent.includes('Greenhouse pump wiring')).click()`); await b.delay(600);
      assert.equal(await leafTitle('notes'), 'Greenhouse pump wiring', 'leaf ' + await leafState('notes'));
      assert.equal(await js(`[...document.querySelectorAll('[data-window-id="notes"] .notes-wall')].some(x=>x.getClientRects().length)`), false, 'wall steps aside');
      assert.equal(await js(`[...document.querySelectorAll('[data-window-id="notes"] textarea')].some(x=>x.value==='Relay on GPIO 17'&&x.getClientRects().length)`), true, 'editor shows the draft');
      await b.screenshot(path.join(V2, '12-note-editor-screen.png'));
      await mouseButton('[data-window-id="notes"] .os-window__body', 'back');
      assert.equal(await leafTitle('notes'), 'All notes', 'leaf ' + await leafState('notes'));
      assert.match(await js(`[...document.querySelectorAll('[data-window-id="notes"] .personal-resume')].find(x=>x.getClientRects().length)?.textContent||''`), /Greenhouse pump wiring · unsaved draft/);
    });
    await step('Workbench project opens as its own screen; voice "go back" returns to the list', async () => {
      await devReady(); await js(`window.__ZAE_DEV__.seedDraft('workbench',{title:'Hydroponic tower',archived:false,category:'Tech',tags:[],color:'amber',size:'medium',status:'Idea',body:'NFT channels',blueprint:'',scenarios:'',unit:'mm',boardWidth:100,strokes:[],referenceImage:''})`);
      await open('workbench'); await b.delay(1200); await pageTab('workbench', 'projects'); await b.delay(800);
      await js(`[...document.querySelectorAll('[data-window-id="workbench"] .personal-resume')].find(x=>x.getClientRects().length).click()`); await b.delay(600);
      assert.equal(await leafTitle('workbench'), 'Hydroponic tower', ('leaf') + ' ' + await leafState('workbench'));
      assert.match(await crumbsIn('[data-window-id="workbench"]', '.page-nav--detail'), /Workbench > Projects > Hydroponic tower$/);
      await b.screenshot(path.join(SHOTS, '09-project-detail-screen.png'));
      const [wx, wy] = await center('[data-window-id="workbench"] .os-window__body'); await b.mouse('mouseMoved', wx, wy, 'none', 0); await b.delay(200);
      await say('go back');
      assert.equal(await leafTitle('workbench'), 'Projects', ('leaf') + ' ' + await leafState('workbench'));
    });
    await step('voice resume offer: relevant, once per context, later / not now / don\'t ask again respected', async () => {
      const seed = subject => js(`localStorage.setItem('zaenia.pageActivity.v1',JSON.stringify([{key:'notes/notes/editor',app:'notes',navigator:'notes',page:'editor',label:'All notes',subject:${JSON.stringify(subject)},action:'edited',at:Date.now()-60000}]))`);
      await js(`localStorage.removeItem('zaenia.resumeOffers.v1')`); await seed('your engine concept note');
      await say('open notes board'); await say('open notes all notes');
      assert.match(await lastReply(), /You were recently working on your engine concept note, sir\. Would you want to continue\?/);
      await b.screenshot(path.join(SHOTS, '10-voice-resume-offer.png'));
      await say("not now"); assert.match(await lastReply(), /leave that for later/);
      await say('open notes board'); await say('open notes all notes');
      assert.doesNotMatch(await lastReply(), /Would you want to continue/, 'deferred: no repeat on the next visit');
      await seed('the greenhouse wiring note'); await say('open notes board'); await say('open notes all notes');
      assert.match(await lastReply(), /greenhouse wiring note.*Would you want to continue/, 'a different context qualifies');
      await say("I'm doing something else"); assert.match(await lastReply(), /leave that for later/);
      await seed('the pump schedule note'); await say('open notes board'); await say('open notes all notes');
      await say("don't ask again"); assert.match(await lastReply(), /won't|will not|Understood/i);
      const prompts = b.dialogs.length;
      await b.call('Page.reload'); await b.delay(3500);
      assert.ok(b.dialogs.length > prompts && b.dialogs.at(-1) === 'beforeunload', 'an unsaved note draft asks before leaving the page');
      await say('open notes board'); await say('open notes all notes');
      assert.doesNotMatch(await lastReply(), /Would you want to continue/, "don't ask again survives reload");
      await chat('open notes board'); await seed('a typed-only note'); await chat('open notes all notes');
      assert.doesNotMatch(await lastReply(), /Would you want to continue/, 'typed navigation never speaks an offer');
      assert.equal(await js(`Object.keys(localStorage).some(k=>/reminder/i.test(k))||/reminder set/i.test(document.body.innerText)`), false, 'no reminder created');
    });
  }

  // Phone: one screen at a time, native page picker, Back and reload.
  await b.viewport(390, 844, true); await js(`localStorage.removeItem('zaenia.phone.section');localStorage.setItem('zaenia.pageTab.life','plan');localStorage.setItem('zaenia.fitness.section','today');sessionStorage.clear()`); await b.call('Page.navigate', { url: URL }); await b.delay(3500);
  await step('phone shows one screen with a visible page picker and breadcrumb', async () => {
    await open('research'); await b.delay(900);
    assert.equal(await js(`document.querySelectorAll('.os-window').length`), 0);
    assert.equal(await js(`!!document.querySelector('[data-pane-root=phone] select.page-nav__picker')`), true);
    const overflow = await js(`document.documentElement.scrollWidth>window.innerWidth+1`);
    assert.equal(overflow, false, 'no horizontal page scroll');
    await b.screenshot(path.join(SHOTS, '05-phone-research.png'));
  });
  await step('phone Back covers sub-pages and apps; reload keeps the screen', async () => {
    await pageTab('research', 'desk'); await b.delay(500);
    await js(`(()=>{const s=document.querySelector('[data-pane-root=phone] select.page-nav__picker');const set=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;set.call(s,'library');s.dispatchEvent(new Event('change',{bubbles:true}))})()`); await b.delay(400);
    assert.equal(await js(`document.querySelector('[data-page-navigator=research]').dataset.pageCurrent`), 'library', 'picker');
    await open('tasks'); await b.delay(900); await pageTab('life', 'fitness'); await b.delay(400); await pageTab('fitness', 'food'); await b.delay(400);
    await b.screenshot(path.join(SHOTS, '06-phone-life-food.png'));
    await js(`document.querySelector('[data-pane-root=phone] [data-pane-back]').click()`); await b.delay(400);
    assert.notEqual(await js(`document.querySelector('[data-pane-root=phone] [data-page-navigator=fitness]').dataset.pageCurrent`), 'food', 'Back leaves Food');
    for (let n = 0; n < 4 && !(await js(`!!document.querySelector('[data-pane-root=phone] [data-page-navigator=research]')`)); n++) { await js(`document.querySelector('[data-pane-root=phone] [data-pane-back]').click()`); await b.delay(700); }
    assert.equal(await js(`document.querySelector('[data-page-navigator=research]')?.dataset.pageCurrent`), 'library', 'back to Research Library');
    await b.call('Page.reload'); await b.delay(4000);
    assert.equal(await js(`document.querySelector('[data-page-navigator=research]')?.dataset.pageCurrent`), 'library', 'reload keeps the screen');
    await b.screenshot(path.join(SHOTS, '07-phone-after-reload.png'));
  });
  await step('phone layout command is labelled as a PC request', async () => {
    await chat('arrange three windows');
    assert.match(await js(`document.body.innerText`), /this phone stays on one screen|This phone shows one screen/i);
  });

  // Phone M5 "voice-first accordion" at two phone widths.
  for (const [pw, ph] of [[390, 844], [360, 780]]) {
    await b.viewport(pw, ph, true);
    await js(`localStorage.removeItem('zaenia.phone.section');sessionStorage.clear()`); await b.call('Page.navigate', { url: URL }); await b.delay(3500);
    const tag = `${pw}x${ph}`;
    await step(`phone ${tag}: category root is an accordion, one module open at a time`, async () => {
      await js(`window.dispatchEvent(new CustomEvent('zae:workspace',{detail:'plan'}))`); await b.delay(900);
      const heads = () => js(`JSON.stringify([...document.querySelectorAll('.navhub .bx-acc>.bx-bh')].map(x=>x.getAttribute('aria-expanded')))`).then(JSON.parse);
      assert.deepEqual(await heads(), ['true', 'false'], 'first module open by default');
      assert.match(await js(`document.querySelector('.navhub .bx-acc.open .bx-rows')?.innerText||''`), /Open LIFE home[\s\S]*Schedule Board[\s\S]*Fitness & Health[\s\S]*GODSPEED/);
      assert.equal(await js(`[...document.querySelectorAll('.navhub .bx-vbar,.navhub .bx-mic,.navhub .bx-pseg')].length`), 3, 'say-or-type bar, mic and category chips');
      assert.ok(await js(`document.querySelector('.navhub .bx-vbar').getBoundingClientRect().height>=56&&document.querySelector('.navhub .bx-mic').getBoundingClientRect().width>=42`), 'bar 56px, mic 42px');
      assert.equal(await js(`!!document.querySelector('.navhub .bx-recent')`), true, 'Continue card');
      assert.equal(await js(`document.documentElement.scrollWidth>window.innerWidth+1`), false, 'no horizontal page scroll');
      assert.equal(await js(`[...document.querySelectorAll('.navhub .bx-rows button,.navhub .bx-acc>.bx-bh')].every(x=>x.getBoundingClientRect().height>=44)`), true, 'touch targets at least 44px');
      await b.screenshot(path.join(V2, `phone-${tag}-01-category-accordion.png`));
      await js(`document.querySelectorAll('.navhub .bx-acc>.bx-bh')[1].click()`); await b.delay(300);
      assert.deepEqual(await heads(), ['false', 'true'], 'opening Notes closes LIFE');
      await js(`document.querySelectorAll('.navhub .bx-acc>.bx-bh')[1].click()`); await b.delay(300);
      assert.deepEqual(await heads(), ['false', 'false'], 'tapping the open header closes it');
      await js(`document.querySelector('.navhub .bx-mic').click()`); await b.delay(300);
      assert.match(await js(`document.querySelector('.navhub .bx-note')?.textContent||''`), /isn't available|Listening|microphone/i, 'mic explains itself in place');
    });
    await step(`phone ${tag}: typed search + Enter opens the page (same matcher as voice)`, async () => {
      await js(`document.querySelector('.navhub .bx-vbar input').focus()`); await b.type('cookbook'); await b.delay(300);
      assert.match(await js(`document.querySelector('.bx-res.first')?.innerText||''`), /Cookbook[\s\S]*Fitness & Health › Food/);
      await b.screenshot(path.join(V2, `phone-${tag}-02-search.png`));
      await b.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 }); await b.delay(2500);
      assert.equal(await js(`document.querySelector('[data-pane-root=phone] [data-page-navigator=fitness-food]')?.dataset.pageCurrent`), 'cookbook');
      assert.equal(await js(`document.querySelectorAll('.os-window').length`), 0, 'one screen at a time');
    });
    if (dev) await step(`phone ${tag}: a recipe is its own screen; Back returns; reload restores the page`, async () => {
      await devReady(); await js(`window.__ZAE_DEV__.seedDraft('recipes',{title:'Overnight oats',archived:false,category:'Breakfast',mealTypes:['Breakfast'],servings:1,ingredients:[],instructions:'',source:'Owner recipe',weekOf:''})`);
      await js(`window.dispatchEvent(new CustomEvent('zae:open-section',{detail:'overview'}))`); await b.delay(600);
      await js(`window.dispatchEvent(new CustomEvent('zae:open-section',{detail:'tasks'}))`); await b.delay(1200);
      await pageTab('life', 'fitness'); await b.delay(400); await pageTab('fitness', 'food'); await b.delay(400); await pageTab('fitness-food', 'cookbook'); await b.delay(700);
      await js(`[...document.querySelectorAll('[data-pane-root=phone] .personal-resume')].find(x=>x.getClientRects().length&&x.textContent.includes('Overnight oats')).click()`); await b.delay(600);
      assert.equal(await js(`[...document.querySelectorAll('[data-pane-root=phone] .page-nav--leaf')].filter(n=>!n.closest('[hidden]')).map(n=>n.querySelector('h2').textContent).join()`), 'Overnight oats');
      await b.screenshot(path.join(V2, `phone-${tag}-03-recipe-screen.png`));
      await js(`[...document.querySelectorAll('[data-pane-root=phone] [data-pane-back]')].find(x=>x.getClientRects().length).click()`); await b.delay(500);
      assert.equal(await js(`[...document.querySelectorAll('[data-pane-root=phone] .page-nav--leaf')].filter(n=>!n.closest('[hidden]')).map(n=>n.querySelector('h2').textContent).join()`), 'Cookbook');
      await b.call('Page.reload'); await b.delay(3500);
      assert.equal(await js(`document.querySelector('[data-pane-root=phone] [data-page-navigator=fitness-food]')?.dataset.pageCurrent`), 'cookbook', 'reload restores the screen');
      assert.equal(await js(`document.documentElement.scrollWidth>window.innerWidth+1`), false, 'no horizontal page scroll');
      await b.screenshot(path.join(V2, `phone-${tag}-04-after-reload.png`));
    });
  }
  await b.viewport(1440, 900, false);
  await step('desktop unchanged after phone checks (bento category page still shown)', async () => {
    await b.call('Page.navigate', { url: URL }); await b.delay(3500);
    await js(`window.dispatchEvent(new CustomEvent('zae:workspace',{detail:'plan'}))`); await b.delay(900);
    assert.ok(await js(`document.querySelectorAll('.navhub .bx-bt').length===2&&!document.querySelector('.navhub .bx-acc')`));
    await closeHub();
  });
  if (b.errors.length) results.push(['FAIL', 'no uncaught page errors', b.errors.slice(0, 3).join(' | ')]);
  await b.close();
  for (const row of results) console.log(row.join('  '));
  const failed = results.filter(row => row[0] === 'FAIL').length;
  console.log(`${results.length - failed}/${results.length} rendered nav/split checks passed`);
  if (failed) process.exitCode = 1;
})().catch(error => { console.error(error); process.exit(1); });
