// CPU-only checks for the portable Constellation Fusion geometry. No DOM,
// WebGL context, Ollama, network or production application state is involved.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const ts = require("typescript");
const THREE = require("three");
const source = fs.readFileSync(path.join(__dirname, "../src/components/tools/se3d/fusionModel.ts"), "utf8");
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, strict: true } }).outputText;
const exported = {};
vm.runInNewContext(output, { exports: exported, require, console }, { filename: "fusionModel.ts" });
const { createFusionModel, FUSION_BRAINS } = exported;
const model = createFusionModel();
const ids = ["talk", "seek", "study", "keep"];
let checks = 0;
const check = (name, fn) => { fn(); checks++; console.log(`  OK ${name}`); };
const meshList = [];
model.root.traverse(object => { if (object.isMesh) meshList.push(object); });

check("semantic organs and security boundary are present", () => {
  assert.equal(model.root.name, "ZAENIA_Constellation_Fusion");
  assert.deepEqual(Array.from(FUSION_BRAINS, item => item.id), ids);
  for (const id of ids) {
    assert.equal(model.clusters[id].userData.id, id);
    assert.ok(model.clusters[id].getObjectByName(`${id[0].toUpperCase() + id.slice(1)}_Organ`));
  }
  assert.ok(model.root.getObjectByName("Smoky_Quartz_Folds"));
  assert.ok(model.root.getObjectByName("Porous_Organic_Metal_Ribs"));
  assert.ok(model.root.getObjectByName("Inclined_Gimbal_Orbits"));
  const gate = model.root.getObjectByName("Execution_Security_Gate");
  assert.ok(gate);
  assert.ok(gate.position.y < model.root.getObjectByName("Central_Conductor").position.y - 1.5);
  assert.equal(gate.parent, model.root);
});
check("all six parts have raycastable visible geometry", () => {
  const parts = new Set(model.pickables.map(object => object.userData.pick));
  assert.deepEqual([...parts].sort(), [...ids, "conductor", "gate"].sort());
  assert.ok(model.pickables.every(object => object.isMesh && object.visible && object.geometry.getAttribute("position").count > 0));
});
const triangles = meshList.reduce((sum, mesh) => sum + (mesh.geometry.index?.count ?? mesh.geometry.getAttribute("position").count) / 3, 0);
check("merged geometry stays within the renderer budget", () => {
  assert.ok(meshList.length < 75, `${meshList.length} draw calls`);
  assert.ok(triangles < 100000, `${triangles} triangles`);
  assert.ok(meshList.every(mesh => mesh.material.isMeshStandardMaterial && !mesh.isInstancedMesh));
  assert.ok(meshList.every(mesh => !mesh.material.map && !mesh.material.normalMap));
});
check("every vertex and extent is finite", () => {
  for (const mesh of meshList) {
    const vertices = mesh.geometry.getAttribute("position");
    for (const value of vertices.array) assert.ok(Number.isFinite(value));
  }
  const box = new THREE.Box3().setFromObject(model.root), size = box.getSize(new THREE.Vector3());
  assert.ok(size.x > 8 && size.x < 10, `width ${size.x}`);
  assert.ok(size.y > 5.5 && size.y < 7, `height ${size.y}`);
  assert.ok(size.z > 3 && size.z < 6, `depth ${size.z}`);
});
const signature = value => {
  const hash = crypto.createHash("sha256");
  value.root.traverse(object => {
    hash.update(object.name);
    if (object.isMesh) {
      hash.update(Buffer.from(object.geometry.getAttribute("position").array.buffer));
      if (object.geometry.index) hash.update(Buffer.from(object.geometry.index.array.buffer));
    }
  });
  return hash.digest("hex");
};
check("remounting preserves the exact same geometry", () => {
  const again = createFusionModel();
  assert.equal(signature(model), signature(again));
  again.dispose();
});
check("live levels change brightness while motion-off is stable", () => {
  let active;
  model.root.traverse(object => { if (object.isMesh && object.material.name === "talk_activity") active = object.material; });
  model.update(2, { talk: 0 }, false);
  const low = active.emissiveIntensity;
  model.update(2, { talk: 1 }, false);
  assert.ok(active.emissiveIntensity > low + 1);
  const pearl = model.root.getObjectByName("Talk_Signal_Pearl");
  const position = pearl.position.clone();
  model.update(9999, { talk: 1 }, false);
  assert.ok(pearl.position.equals(position));
  model.root.rotation.set(0.4, -0.3, 0.2);
  model.update(5, { talk: NaN, seek: Infinity, keep: -10, study: 2 });
  assert.deepEqual(model.root.rotation.toArray(), [0.4, -0.3, 0.2, "XYZ"]);
  assert.ok(Number.isFinite(active.emissiveIntensity));
  model.update(10, { talk: 1 });
  assert.ok(!pearl.position.equals(position));
});
check("all exposed resources dispose exactly once", () => {
  const resources = new Set();
  meshList.forEach(mesh => { resources.add(mesh.geometry); resources.add(mesh.material); });
  const disposed = new Map([...resources].map(resource => [resource, 0]));
  resources.forEach(resource => resource.addEventListener("dispose", () => disposed.set(resource, disposed.get(resource) + 1)));
  model.dispose(); model.dispose(); model.update(100, { talk: 1 });
  assert.ok([...disposed.values()].every(count => count === 1));
});
console.log(`${checks} fusion model checks passed; ${meshList.length} mesh draw calls, ${Math.round(triangles).toLocaleString()} triangles.`);
