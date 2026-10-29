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
const { gramsFor, scaled, emptyNutrients } = exportsObject;
let n = 0; const check = fn => { fn(); n++; };
const per100 = { ...emptyNutrients(), calories: 59, protein: 10.3, fiber: 0, fat: 0.4 };
check(() => assert.equal(gramsFor('150', 'g'), 150));
check(() => assert.equal(Math.round(gramsFor('2', 'oz') * 100) / 100, 56.7));
check(() => assert.equal(gramsFor('1.5', 'serving', 170), 255));
check(() => assert.equal(gramsFor('1', 'serving', null), null));
check(() => assert.equal(gramsFor('abc', 'g'), null));
check(() => { const out = scaled(per100, 200, emptyNutrients()); assert.equal(out.calories, 118); assert.equal(out.protein, 20.6); assert.equal(out.carbs, null); });
check(() => { const current = { ...emptyNutrients(), calories: 150 }; const out = scaled(per100, 200, current, ['calories']); assert.equal(out.calories, 150); assert.equal(out.protein, 20.6); });
console.log(`${n} recipe ingredient checks passed.`);
