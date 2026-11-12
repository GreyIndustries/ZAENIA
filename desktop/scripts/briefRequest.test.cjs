// "Brief me" and "on the road brief" by words (core/briefRequest.ts).
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), assert = require("node:assert/strict"), ts = require("typescript");
const mod = {};
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core/briefRequest.ts"), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
vm.runInNewContext(code, { exports: mod, String, RegExp });
const { isBriefRequest } = mod;
let count = 0;
for (const yes of ["on the road brief", "On the road brief", "give me the on the road brief", "give me my on the road brief please", "brief on the road",
  "brief me on the road", "Zae, brief me on the road", "road brief", "the road briefing", "drive briefing", "driving brief", "carplay brief",
  "brief me", "Brief me", "hey zae brief me please", "give me my brief", "give me the briefing", "morning brief", "can you give me the daily briefing",
  "pull up the commute brief", "brief me for the road."]) { assert.ok(isBriefRequest(yes), yes); count++; }
for (const no of ["write a brief summary of this file", "brief me on the Python release", "what is a brief", "keep it brief", "give me a brief overview of thunderstorms",
  "briefly explain the plan", "the brief is due Friday", "", "   ", "brief on the road conditions in Seattle tomorrow morning please check"]) { assert.ok(!isBriefRequest(no), no); count++; }
console.log(`${count} brief request checks passed.`);
