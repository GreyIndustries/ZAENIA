// ZAE's own barcode reader (core/barcode.ts): synthetic EAN-13, UPC-A, EAN-8 and UPC-E lines and images.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/barcode.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject, globalThis: {}, Uint8Array, Uint8ClampedArray, Map, Math, Number, Array, String, Infinity });
const { decodeLine, decodeGray, checkDigitOk, expandUpcE } = exportsObject;
let n = 0; const check = fn => { fn(); n++; };

const L = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011'];
const R = L.map(bits => bits.replace(/./g, b => b === '0' ? '1' : '0'));
const G = R.map(bits => bits.split('').reverse().join(''));
const FIRST = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL'];
const UPCE = ['GGGLLL', 'GGLGLL', 'GGLLGL', 'GGLLLG', 'GLGGLL', 'GLLGGL', 'GLLLGG', 'GLGLGL', 'GLGLLG', 'GLLGLG'];
const ean13 = digits => { const d = digits.split('').map(Number); const p = FIRST[d[0]];
  return '101' + d.slice(1, 7).map((x, i) => (p[i] === 'L' ? L : G)[x]).join('') + '01010' + d.slice(7).map(x => R[x]).join('') + '101'; };
const ean8 = digits => { const d = digits.split('').map(Number); return '101' + d.slice(0, 4).map(x => L[x]).join('') + '01010' + d.slice(4).map(x => R[x]).join('') + '101'; };
const upce = (six, checkDigit) => { const p = UPCE[checkDigit]; return '101' + six.split('').map((x, i) => (p[i] === 'L' ? L : G)[Number(x)]).join('') + '010101'; };
// Render modules to brightness: quiet zones, a module width in pixels, blur-ish edges and noise.
const line = (bits, width = 3, noise = 0) => {
  const out = []; const push = v => { for (let i = 0; i < width; i++) out.push(Math.max(0, Math.min(255, v + (Math.random() - 0.5) * noise))); };
  for (let i = 0; i < 12; i++) push(230);
  for (const b of bits) push(b === '1' ? 30 : 230);
  for (let i = 0; i < 12; i++) push(230);
  return out;
};

check(() => assert.ok(checkDigitOk('5901234123457')));
check(() => assert.ok(!checkDigitOk('5901234123458')));
check(() => assert.equal(expandUpcE('425261', 0, 4), '042100005264'));
check(() => assert.equal(decodeLine(line(ean13('5901234123457'))), '5901234123457'));
check(() => assert.equal(decodeLine(line(ean13('0041196910759'), 2)), '0041196910759')); // a UPC-A as EAN-13
check(() => assert.equal(decodeLine(line(ean13('5901234123457')).reverse()), '5901234123457')); // upside down
check(() => assert.equal(decodeLine(line(ean13('5901234123457'), 4, 60)), '5901234123457')); // noisy
check(() => assert.equal(decodeLine(line(ean8('96385074'))), '96385074'));
check(() => assert.equal(decodeLine(line(upce('425261', 4))), '042100005264'));
check(() => assert.equal(decodeLine(line('1010101010101010101010')), null));
check(() => { // a whole picture: the code across the middle rows, blank paper above and below
  const row = line(ean13('5901234123457'), 3, 20); const width = row.length, height = 120; const data = new Uint8Array(width * height).fill(230);
  for (let y = 40; y < 80; y++) row.forEach((v, x) => { data[y * width + x] = v; });
  assert.equal(decodeGray({ width, height, data }), '5901234123457');
});
check(() => { // held sideways: the code runs down the picture
  const col = line(ean13('5901234123457'), 3); const height = col.length, width = 120; const data = new Uint8Array(width * height).fill(230);
  for (let x = 40; x < 80; x++) col.forEach((v, y) => { data[y * width + x] = v; });
  assert.equal(decodeGray({ width, height, data }), '5901234123457');
});
console.log(`${n} barcode checks passed.`);
