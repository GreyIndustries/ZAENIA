// Recipe ingredient scaling (RecipeIngredient.tsx gramsFor/scaled): pure maths, no browser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/components/personal/RecipeIngredient.tsx'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject, require: () => ({}), Number, Math, Object, String, Set });
const { gramsFor, scaled, emptyNutrients, servingGramsOf, servingText } = exportsObject;
let n = 0; const check = fn => { fn(); n++; };
const per100 = { ...emptyNutrients(), calories: 59, protein: 10.3, fiber: 0, fat: 0.4 };
check(() => assert.equal(gramsFor('150', 'g'), 150));
check(() => assert.equal(Math.round(gramsFor('2', 'oz') * 100) / 100, 56.7));
check(() => assert.equal(gramsFor('1.5', 'serving', 170), 255));
check(() => assert.equal(gramsFor('1', 'serving', null), null));
check(() => assert.equal(gramsFor('abc', 'g'), null));
check(() => { const out = scaled(per100, 200, emptyNutrients()); assert.equal(out.calories, 118); assert.equal(out.protein, 20.6); assert.equal(out.carbs, null); });
check(() => { const current = { ...emptyNutrients(), calories: 150 }; const out = scaled(per100, 200, current, ['calories']); assert.equal(out.calories, 150); assert.equal(out.protein, 20.6); });
check(() => assert.equal(servingGramsOf({ servingSize: 50, servingSizeUnit: 'g' }), 50));
check(() => assert.equal(servingGramsOf({ servingSize: '1 cup (240 ml)' }), 240));
check(() => assert.equal(servingGramsOf({ servingSize: '170 g' }), 170));
check(() => assert.equal(servingGramsOf({ servingSize: '2 slices' }), null));
check(() => assert.equal(servingText('1 large egg', 50), '1 large egg (50 g)'));
check(() => assert.equal(servingText('', 30, 30), '1 serving (30 g)'));
check(() => assert.equal(servingText('', 240, '1 cup (240 ml)'), '1 cup (240 ml)'));
console.log(`${n} recipe ingredient checks passed.`);
