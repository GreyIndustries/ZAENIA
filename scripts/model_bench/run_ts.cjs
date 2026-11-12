// Explicit opt-in only: Node vm is not a security sandbox and code can have this account's permissions.
// usage: node run_ts.cjs --allow-unsafe-local-execution <code.ts> <tests.js>
// Gate before loading modules or reading either input file, including when invoked without bench.py.
const args = process.argv.slice(2);
if (args[0] !== "--allow-unsafe-local-execution") {
  console.error("Code execution is disabled; explicit --allow-unsafe-local-execution is required. This runner is not a security sandbox.");
  process.exit(2);
}
if (args.length !== 3) {
  console.error("usage: node run_ts.cjs --allow-unsafe-local-execution <code.ts> <tests.js>");
  process.exit(2);
}
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");
const ts = require(path.resolve(__dirname, "../../desktop/node_modules/typescript"));   // the app's own compiler

const code = fs.readFileSync(args[1], "utf8");
const tests = fs.readFileSync(args[2], "utf8");
const out = ts.transpileModule(code, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None, removeComments: true },
  reportDiagnostics: false,
});
try {
  vm.runInNewContext(out.outputText + "\n;\n" + tests, { assert }, { timeout: 5000, filename: "answer.js" });
} catch (e) {
  console.error(String(e && e.message ? e.message : e).split("\n")[0].slice(0, 160));
  process.exit(1);
}
