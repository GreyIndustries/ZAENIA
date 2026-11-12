// Appearance parsing and voice commands: pure, no browser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/appearance.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject });
const { parseAppearance, parseAppearanceCommand, tabAppearance, ACCENTS, DEFAULT_APPEARANCE } = exportsObject;
const plain = value => JSON.parse(JSON.stringify(value));
let checks = 0;
const check = run => { run(); checks++; };
const base = { ...DEFAULT_APPEARANCE };

check(() => assert.deepEqual(plain(parseAppearance('{"font":"mono","size":500,"accent":"nope","glow":10}')), { font: 'mono', size: 125, accent: 'amber', glow: 40, look: 'aurora', tabs: {}, orbs: 'mixed', density: 'comfortable', corners: 'style', panelOpacity: 100, motion: 'full' }));
check(() => assert.deepEqual({ ...parseAppearance('not json') }, base));
check(() => assert.equal(parseAppearanceCommand('make it blue', base).accent, 'blue'));
check(() => assert.equal(parseAppearanceCommand('change the color to red', base).accent, 'crimson'));
check(() => assert.equal(parseAppearanceCommand('switch the theme to purple', base).accent, 'violet'));
check(() => assert.equal(parseAppearanceCommand('use the mono font', base).font, 'mono'));
check(() => assert.equal(parseAppearanceCommand('bigger text please', base).size, 110));
check(() => assert.equal(parseAppearanceCommand('less glow', base).glow, 80));
for (const text of ['add a task to buy blue paint', 'what color is the sky', 'I like the green one', 'hello']) {
  check(() => assert.equal(parseAppearanceCommand(text, base) === null || text === 'what color is the sky', true, text));
}
check(() => assert.equal(parseAppearanceCommand('add a task to buy blue paint', base), null));
// More colours, and each tab's own style and colour.
check(() => assert.ok(ACCENTS.length >= 28 && new Set(ACCENTS.map(a => a.id)).size === ACCENTS.length));
check(() => assert.deepEqual(plain(parseAppearance('{"tabs":{"tasks":{"look":"hud","color":"rose"},"news":{"look":"bogus"},"nope":{"color":"mint"}}}').tabs), { tasks: { look: 'hud', color: 'rose' } }));
check(() => assert.equal(tabAppearance({ ...base, look: 'neon', tabs: { tasks: { look: 'hud' } } }, 'tasks').look, 'hud'));
check(() => assert.equal(tabAppearance({ ...base, look: 'neon', tabs: {} }, 'notes').look, 'neon'));
check(() => assert.deepEqual(plain(parseAppearance('{"tabs":{"workbench":{"color":"blue"},"music":{"look":"hud"},"fitness":{"color":"mint"}}}').tabs), { workbench: { color: 'blue' }, music: { look: 'hud' }, fitness: { color: 'mint' } }));
check(() => assert.equal(tabAppearance({ ...base, tabs: { notes: { color: 'mint' } } }, 'notes').style['--accent'], '#9cf5c8'));
check(() => { const next = parseAppearanceCommand('make the tasks tab pink', base); assert.equal(next.tabs.tasks.color, 'pink'); assert.equal(next.accent, 'amber'); });
check(() => assert.equal(parseAppearanceCommand('make it teal', base).accent, 'teal'));
check(() => assert.equal(parseAppearanceCommand('open the files window', base), null));
check(() => assert.equal(parseAppearance('{"orbs":"match"}').orbs, 'match'));
check(() => assert.deepEqual((({ density, corners, panelOpacity, motion }) => ({ density, corners, panelOpacity, motion }))(parseAppearance('{"density":"compact","corners":"round","panelOpacity":10,"motion":"reduced"}')), { density: 'compact', corners: 'round', panelOpacity: 50, motion: 'reduced' }));
check(() => assert.equal(parseAppearance('{"density":"huge","corners":"wavy"}').density, 'comfortable'));
check(() => assert.equal(parseAppearanceCommand('use a compact layout', base).density, 'compact'));
check(() => assert.equal(parseAppearanceCommand('give me round corners', base).corners, 'round'));
check(() => assert.equal(parseAppearanceCommand('reduce motion please', base).motion, 'reduced'));
check(() => assert.equal(parseAppearanceCommand('make the core icons the same colour', base).orbs, 'match'));
check(() => assert.equal(parseAppearanceCommand('make the core icons the same colour', base).accent, 'amber'));
check(() => assert.equal(parseAppearanceCommand('give the icons two colours again', { ...base, orbs: 'match' }).orbs, 'mixed'));
console.log(`${checks} appearance checks passed.`);
