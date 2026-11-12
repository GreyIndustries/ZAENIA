// The four groups of the 3D security model (components/security/securityGroups.ts).
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
const mod = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/components/security/securityGroups.ts"), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
vm.runInNewContext(code, { exports: mod, Number, Math, Set });
const { groupAreas, worst, alertCount, trailSpeed } = mod;
let count = 0;
const check = (fn) => { fn(); count++; };
// objects built inside the sandbox have their own prototypes, so compare their JSON form
const same = (a, b) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), b);
const IDS = ["network", "signin", "secrets", "clients", "voice", "mode", "tests", "git", "audit", "signals", "packages"];
const area = (id, level) => ({ id, title: id, level });

check(() => {  // always four groups, in a fixed order, and every real reading lands in exactly one
  const groups = groupAreas(IDS.map(id => area(id, "strong")));
  same(groups.map(g => g.id), ["identity", "access", "secrets", "watch"]);
  same(groups.map(g => g.areas.length), [3, 2, 2, 4]);
  assert.equal(groups.reduce((n, g) => n + g.areas.length, 0), IDS.length);
});
check(() => {  // a group is as strong as its weakest measured reading
  const groups = groupAreas([area("signin", "strong"), area("voice", "fair"), area("clients", "strong"), area("network", "weak"), area("mode", "strong")]);
  assert.equal(groups[0].level, "fair");
  assert.equal(groups[1].level, "weak");
  assert.equal(groups[2].level, "unknown");   // nothing measured in Secrets
});
check(() => {  // "not measured" never drags a group down, and only wins when nothing was measured
  assert.equal(worst(["unknown", "strong"]), "strong");
  assert.equal(worst(["unknown", "unknown"]), "unknown");
  assert.equal(worst([]), "unknown");
  assert.equal(worst(["strong", "weak", "fair"]), "weak");
  assert.equal(worst(["fair", "strong"]), "fair");
});
check(() => {  // a reading with an id we don't know is kept, in Watch
  const groups = groupAreas([area("error", "unknown"), area("audit", "strong"), area("mystery", "weak")]);
  same(groups[3].areas.map(a => a.id), ["error", "audit", "mystery"]);
  assert.equal(groups[3].level, "weak");
});
check(() => {  // the gate's ring: attempts add up, bad numbers count as nothing, speed stays between .2 and 1
  assert.equal(alertCount(undefined), 0);
  assert.equal(alertCount({}), 0);
  assert.equal(alertCount({ failedSignins: 2, denied: 3, voiceRejected: 1, unlockFailed: 4 }), 10);
  assert.equal(alertCount({ failedSignins: -5, denied: NaN, voiceRejected: 2 }), 2);
  assert.equal(trailSpeed(0), 0.2);
  assert.ok(trailSpeed(10) > 0.2 && trailSpeed(10) < 1);
  assert.equal(trailSpeed(500), 1);
});
console.log(`${count} security group checks passed.`);
