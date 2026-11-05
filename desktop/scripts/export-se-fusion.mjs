// Regenerate the portable model with the project's installed Three.js exporter.
// No network, API keys, runtime data or external model-generation service is used.
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";
import { GLTFExporter } from "three/addons/exporters/GLTFExporter.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.join(desktop, "src/components/tools/se3d/fusionModel.ts");
const cache = path.join(desktop, "node_modules/.cache/zaenia-se-export");
await fs.mkdir(cache, { recursive: true });
const compiled = path.join(cache, "fusionModel.mjs");
await fs.writeFile(compiled, ts.transpileModule(await fs.readFile(source, "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
}).outputText);

// GLTFExporter's texture-free binary path needs only this browser FileReader operation.
if (!globalThis.FileReader) {
  globalThis.FileReader = class {
    result = null;
    onloadend = null;
    onerror = null;
    readAsArrayBuffer(blob) {
      blob.arrayBuffer().then(result => { this.result = result; this.onloadend?.(); }, error => this.onerror?.(error));
    }
  };
}
const { createFusionModel, FUSION_BRAINS } = await import(pathToFileURL(compiled).href);
const model = createFusionModel();
try {
  model.update(0, { talk: 0.45, seek: 0.45, study: 0.45, keep: 0.45 }, false);
  const bytes = await new GLTFExporter().parseAsync(model.root, { binary: true, onlyVisible: true });
  if (!(bytes instanceof ArrayBuffer)) throw new Error("The exporter did not return a binary model.");
  const header = new DataView(bytes);
  if (header.getUint32(0, true) !== 0x46546c67 || header.getUint32(4, true) !== 2 || header.getUint32(8, true) !== bytes.byteLength) {
    throw new Error("Invalid glTF binary header.");
  }
  const loaded = await new GLTFLoader().parseAsync(bytes, "");
  for (const spec of FUSION_BRAINS) {
    if (!loaded.scene.getObjectByName(`${spec.name}_Constellation`)) throw new Error(`Missing ${spec.name} after model round-trip.`);
  }
  if (!loaded.scene.getObjectByName("Central_Conductor") || !loaded.scene.getObjectByName("Execution_Security_Gate")) {
    throw new Error("The coordinator or separate execution gate was lost during export.");
  }
  const folder = path.join(desktop, "public/models");
  await fs.mkdir(folder, { recursive: true });
  const target = path.join(folder, "zaenia-se-fusion.glb");
  await fs.writeFile(target, new Uint8Array(bytes));
  const geometries = new Set(), materials = new Set();
  loaded.scene.traverse(object => {
    if (object.geometry) geometries.add(object.geometry);
    if (object.material) for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material);
  });
  geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose());
  console.log(`Exported and reloaded ${path.relative(desktop, target)} (${(bytes.byteLength / 1024).toFixed(0)} KiB). Four brain clusters, Conductor and gate verified.`);
} finally {
  model.dispose();
}
