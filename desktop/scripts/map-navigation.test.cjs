const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const { test } = require('node:test');
const dir = path.join(__dirname, '../src/components/map');
function load(name) {
  const source = fs.readFileSync(path.join(dir, name + '.ts'), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => load(name.replace('./', '')), console });
  return exports;
}
const math = load('mapMath');
const state = load('mapRequests');
const stops = [0, 1, 2].map(key => ({ key, query: 'Place ' + key, label: 'Place ' + key, lat: 47 + key / 100, lon: -122 }));
const route = () => ({ distance: 1000, duration: 120, line: [[47, -122], [47.01, -122]],
  legs: [{ distance: 1000, duration: 120, steps: [{ text: 'Continue', distance: 1000, duration: 120, lat: 47, lon: -122 }] }], order: [0, 1], engine: 'local' });

test('an unresolved middle stop cannot silently disappear from a route', () => {
  assert.equal(state.completeStops(stops), true);
  assert.equal(state.completeStops(stops.map((s, i) => i === 1 ? { ...s, lat: null, lon: null } : s)), false);
  assert.equal(state.completeStops([stops[0]]), false);
  assert.equal(state.completeStops(stops.map(s => ({ ...s, lat: NaN }))), false);
});
test('editing, clearing, and replacing route requests rejects their late results', () => {
  const gate = new state.RequestGate();
  const key = state.stopFingerprint(stops, false);
  const old = gate.issue(key);
  gate.invalidate();
  assert.equal(gate.accepts(old, key), false);
  const next = gate.issue(key);
  assert.equal(gate.accepts(next, key), true);
  assert.equal(gate.accepts(next, state.stopFingerprint([...stops].reverse(), false)), false);
  assert.equal(gate.accepts(next, state.stopFingerprint(stops, true)), false);
});
test('a late search cannot target a different or edited stop', () => {
  const gate = new state.RequestGate();
  const ticket = gate.issue('10:Airport');
  assert.equal(gate.accepts(ticket, '11:Airport'), false);
  assert.equal(gate.accepts(ticket, '10:Airport hotel'), false);
  gate.issue('11:Airport');
  assert.equal(gate.isCurrent(ticket), false);
});
test('routing replies must contain finite geometry and an exact endpoint-preserving stop permutation', () => {
  assert.equal(state.checkedRoute(route(), 2).engine, 'local');
  for (const changed of [
    { ...route(), order: [0, 0] }, { ...route(), order: [1, 0] },
    { ...route(), duration: NaN }, { ...route(), line: [[47, -122], [91, -122]] },
    { ...route(), legs: [] }, { ...route(), engine: 'invented' },
    { ...route(), legs: [{ ...route().legs[0], steps: [{ text: 'Turn', lat: Infinity, lon: 0, distance: 1, duration: 1 }] }] },
  ]) assert.throws(() => state.checkedRoute(changed, 2));
});
test('traffic near the middle of a sparse road segment is matched', () => {
  assert.ok(math.kmToLine({ lat: 0.001, lon: 0.05 }, [[0, 0], [0, 0.1]]) < 0.12);
  assert.ok(math.kmToLine({ lat: 0.01, lon: 0.05 }, [[0, 0], [0, 0.1]]) > 1);
  assert.equal(math.kmToLine({ lat: 0, lon: 0 }, []), Infinity);
});
test('route proximity handles zero-length segments and the date line', () => {
  assert.equal(math.kmToLine({ lat: 0, lon: 0 }, [[0, 0], [0, 0]]), 0);
  assert.ok(math.kmToLine({ lat: 0.001, lon: 180 }, [[0, 179.9], [0, -179.9]]) < 0.12);
});
test('map projection stays finite and within the Mercator world at the poles', () => {
  for (const lat of [-90, 90]) { const p = math.project(lat, 0, 10); assert.ok(Number.isFinite(p.y)); assert.ok(p.y >= -0.001 && p.y <= math.world(10) + 0.001); }
});
test('satellite has no key-gated label overlay and dark filtering leaves traffic overlays untouched', () => {
  const source = fs.readFileSync(path.join(dir, 'MapPanel.tsx'), 'utf8');
  const file = ts.createSourceFile('MapPanel.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let declaration;
  function visit(node) { if (ts.isVariableDeclaration(node) && node.name.getText(file) === 'STYLE_LAYERS') declaration = node; ts.forEachChild(node, visit); }
  visit(file);
  const layers = vm.runInNewContext('(' + declaration.initializer.getText(file) + ')');
  assert.equal(layers.satellite.length, 1);
  assert.equal(layers.satellite[0][0], 'satellite');
  const css = fs.readFileSync(path.join(dir, 'MapPanel.css'), 'utf8');
  assert.match(css, /\.zmap--dark \.zmap__tiles--dark\s*\{\s*filter:/);
  assert.doesNotMatch(css, /\.zmap__overlay\s*\{[^}]*filter:\s*invert/);
});


const traffic = load('routeTraffic');
test('route traffic uses blue/orange/red and never labels unavailable coverage clear', () => {
  const line = [[47, -122], [47.001, -122]];
  const roads = [{ from: 'a', to: 'b', line }];
  for (const level of [1, 2, 3, 4]) assert.equal(traffic.routeTraffic(line, roads, [{ id: 'a', level }], true)[0].level, level);
  assert.equal(traffic.ROUTE_COLORS[1], '#4285f4');
  assert.equal(traffic.routeTraffic(line, roads, [{ id: 'a', level: 1 }], false)[0].level, null);
  assert.equal(traffic.routeTraffic(line, roads, [], true)[0].level, null);
  assert.equal(traffic.routeTraffic([[48, -122], [48.001, -122]], roads, [{ id: 'a', level: 1 }], true)[0].level, null);
});
test('crossing roads and unobserved gaps cannot colour a route from one nearby sensor', () => {
  const route = [[47, -122], [47.001, -122]];
  const crossing = [{ from: 'a', to: 'b', line: [[47.0005, -122.001], [47.0005, -121.999]] }];
  assert.equal(traffic.routeTraffic(route, crossing, [{ id: 'a', level: 3 }], true)[0].level, null);
  const far = [{ from: 'a', to: 'b', line: [[40, -122], [50, -122]] }];
  assert.equal(traffic.routeTraffic(route, far, [{ id: 'a', level: 3 }], true)[0].level, null);
});
