// Workbench science helpers: calculator, units, molar mass. Pure, no browser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/science.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject, Math, Number, Map, Error, String });
const { calculate, convert, molarMass, ELEMENTS } = exportsObject;
let checks = 0;
const near = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${a} != ${b}`);
const check = run => { run(); checks++; };
check(() => near(calculate('2+3*4'), 14));
check(() => near(calculate('2^3^2'), 512));
check(() => near(calculate('-(3+2)*2'), -10));
check(() => near(calculate('sin(30)', true), 0.5));
check(() => near(calculate('2pi'), 2 * Math.PI));
check(() => near(calculate('5!'), 120));
check(() => near(calculate('sqrt(16)+log(100)'), 6));
check(() => near(calculate('1.5e3/3'), 500));
check(() => assert.throws(() => calculate('alert(1)')));
check(() => assert.throws(() => calculate('2+')));
check(() => near(convert(100, 'Temperature', '°C', '°F'), 212));
check(() => near(convert(1, 'Length', 'mi', 'km'), 1.609344));
check(() => near(convert(1, 'Data', 'GiB', 'MB'), 1073.741824));
check(() => near(molarMass('H2O').mass, 18.015, 1e-3));
check(() => near(molarMass('Ca(OH)2').mass, 74.092, 1e-3));
check(() => near(molarMass('CuSO4·5H2O').mass, 249.677, 1e-3));
check(() => assert.throws(() => molarMass('Xx2')));
check(() => assert.equal(ELEMENTS.length, 118));
console.log(`${checks} science checks passed.`);
