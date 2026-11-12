// Phone confirms: a QR code drawn the way the PC draws it is read back by the phone's reader (qrcode -> jsQR).
const assert = require('node:assert/strict');
const QRCode = require('qrcode');
const jsQR = require('jsqr');

function raster(value, scale = 6, margin = 2) {
  const { modules } = QRCode.create(value, { errorCorrectionLevel: 'M' });
  const size = (modules.size + margin * 2) * scale;
  const data = new Uint8ClampedArray(size * size * 4).fill(255);
  for (let y = 0; y < modules.size; y++) for (let x = 0; x < modules.size; x++) {
    if (!modules.get(x, y)) continue;
    for (let dy = 0; dy < scale; dy++) for (let dx = 0; dx < scale; dx++) {
      const i = (((y + margin) * scale + dy) * size + (x + margin) * scale + dx) * 4;
      data[i] = data[i + 1] = data[i + 2] = 10;
    }
  }
  return { data, size };
}

let n = 0;
for (const value of ['zae-near:' + 'A'.repeat(32), 'zae-near:Qm9vLV8tYmFyX2tleV8xMjM0NTY3ODkw', 'zae-near:_-xyz09' + 'k'.repeat(26)]) {
  const { data, size } = raster(value);
  assert.equal(jsQR(data, size, size)?.data, value); n++;
}
console.log(`${n} QR round trips passed.`);
