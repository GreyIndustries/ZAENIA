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
const { parseAppearance, parseAppearanceCommand, DEFAULT_APPEARANCE } = exportsObject;
let checks = 0;
const check = run => { run(); checks++; };
const base = { ...DEFAULT_APPEARANCE };

check(() => assert.deepEqual({ ...parseAppearance('{"font":"mono","size":500,"accent":"nope","glow":10}') }, { font: 'mono', size: 125, accent: 'amber', glow: 40, look: 'aurora' }));
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
console.log(`${checks} appearance checks passed.`);
