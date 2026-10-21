// Pure client routing checks: no microphone, stored data, browser, or live API.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const exportsObject = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/core/voiceAttention.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { exports: exportsObject });
const { acceptsVoiceTurn, FOLLOW_UP_MS, isQuietVoiceAcknowledgement } = exportsObject;
let checks = 0;
function check(run) { run(); checks++; }
check(() => assert.equal(FOLLOW_UP_MS, 30_000));
for (const active of [false, true]) {
  check(() => assert.equal(acceptsVoiceTurn({ addressed: true }, active), true));
  check(() => assert.equal(acceptsVoiceTurn({ addressed: false, conversational: false }, active), false));
  check(() => assert.equal(acceptsVoiceTurn({ addressed: false }, active), false));
}
check(() => assert.equal(acceptsVoiceTurn({ addressed: false, conversational: true }, true), true));
check(() => assert.equal(acceptsVoiceTurn({ addressed: false, conversational: true }, false), false));
check(() => assert.equal(acceptsVoiceTurn({ addressed: false, conversational: 'true' }, true), false));
check(() => assert.equal(acceptsVoiceTurn({ addressed: false, forZae: true }, false), true));
check(() => assert.equal(acceptsVoiceTurn({ addressed: false, forZae: 'true' }, false), false));
check(() => assert.equal(acceptsVoiceTurn({ addressed: false, forZae: false, conversational: true }, false), false));
check(() => assert.equal(isQuietVoiceAcknowledgement({ addressed: false, acknowledgement: true }, true), true));
check(() => assert.equal(isQuietVoiceAcknowledgement({ addressed: false, acknowledgement: true }, false), false));
check(() => assert.equal(isQuietVoiceAcknowledgement({ addressed: true }, true), false));
check(() => assert.equal(isQuietVoiceAcknowledgement({ addressed: true, acknowledgement: false }, true), false));
check(() => assert.equal(isQuietVoiceAcknowledgement({ addressed: false, acknowledgement: 'true' }, true), false));
console.log(`${checks} voice attention routing checks passed.`);
