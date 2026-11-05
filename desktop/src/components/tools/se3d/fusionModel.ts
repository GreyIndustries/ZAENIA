/**
 * ZÆNIA's Constellation Fusion, built entirely from portable Three.js geometry.
 * This is a visual instrument: the caller supplies activity, labels and policy.
 * No scene node loads a model, fetches data or grants execution authority.
 */
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

export type FusionBrainId = "talk" | "seek" | "study" | "keep";
type V3 = readonly [number, number, number];

export const FUSION_BRAINS = [
  { id: "talk", name: "Talk", model: "qwen3.5:4b", color: "#ffb347", position: [2.05, 1.22, 0.24] },
  { id: "seek", name: "Seek", model: "qwen3.5:9b", color: "#40e0e8", position: [2.05, -1.02, 0.28] },
  { id: "study", name: "Study", model: "qwen3:14b", color: "#b47cff", position: [-2.02, 1.25, 0.12] },
  { id: "keep", name: "Keep", model: "qwen3:1.7b", color: "#ef9a63", position: [-2.12, -1.10, 0.20] },
] as const satisfies readonly { id: FusionBrainId; name: string; model: string; color: string; position: V3 }[];

export type FusionModel = {
  root: THREE.Group;
  clusters: Record<FusionBrainId, THREE.Group>;
  pickables: THREE.Object3D[];
  update: (timeSeconds: number, levels: Partial<Record<FusionBrainId, number>>, animate?: boolean) => void;
  dispose: () => void;
};

const ROLES: Record<FusionBrainId, string> = {
  talk: "Conversation", seek: "Evidence", study: "Deep research", keep: "Background memory",
};
const UP = new THREE.Vector3(0, 1, 0);
const TAU = Math.PI * 2;
const at = (p: V3) => new THREE.Vector3(...p);

function randomSource(seed: number) {
  let state = seed >>> 0;
  return () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
}

/** A faceted strip follows the silhouette, leaving the four working organs open. */
function quartzRibbon(points: V3[], width: number, seed: number): THREE.BufferGeometry {
  const curve = new THREE.CatmullRomCurve3(points.map(at));
  const random = randomSource(seed), vertices: number[] = [], indices: number[] = [];
  const rows = 30, columns = 5;
  for (let i = 0; i <= rows; i++) {
    const t = i / rows, center = curve.getPoint(t), tangent = curve.getTangent(t);
    const side = new THREE.Vector3(-tangent.y, tangent.x, 0).normalize()
      .applyAxisAngle(tangent, Math.sin(t * Math.PI * 1.8 + seed) * 0.64);
    const taper = 0.14 + 0.86 * Math.sin(Math.PI * t) ** 0.65;
    for (let j = 0; j <= columns; j++) {
      const q = center.clone().addScaledVector(side, (j / columns - 0.5) * width * taper);
      q.z += Math.sin(j / columns * Math.PI) * width * 0.42 + (random() - 0.5) * 0.075;
      vertices.push(q.x, q.y, q.z);
      if (i && j) {
        const a = (i - 1) * (columns + 1) + j - 1, b = i * (columns + 1) + j - 1;
        if ((i + j) % 2) indices.push(a, b, b + 1, a, b + 1, a + 1);
        else indices.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setIndex(indices); geometry.computeVertexNormals();
  return geometry;
}

export function createFusionModel(): FusionModel {
  const root = new THREE.Group();
  root.name = "ZAENIA_Constellation_Fusion";
  root.userData = { part: "constellation-fusion", role: "Read-only visualization; security remains outside the SE", version: 1 };
  const clusters = {} as Record<FusionBrainId, THREE.Group>;
  const pickables: THREE.Object3D[] = [];
  const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>();
  const remember = <T extends THREE.BufferGeometry>(geometry: T): T => { geometries.add(geometry); return geometry; };
  const release = (geometry: THREE.BufferGeometry) => { if (geometries.delete(geometry)) geometry.dispose(); };
  const material = (options: THREE.MeshStandardMaterialParameters) => {
    const value = new THREE.MeshStandardMaterial(options); materials.add(value); return value;
  };
  const steel = material({ color: "#887665", metalness: 0.72, roughness: 0.26 });
  const darkSteel = material({ color: "#292a30", metalness: 0.72, roughness: 0.36 });
  const copper = material({ color: "#b97538", metalness: 0.79, roughness: 0.27, emissive: "#aa480c", emissiveIntensity: 0.14 });
  const gold = material({ color: "#ffb84a", metalness: 0.55, roughness: 0.27, emissive: "#ff8b16", emissiveIntensity: 0.55 });
  const ivory = material({ color: "#fff1ce", metalness: 0.12, roughness: 0.30, emissive: "#ffe1a2", emissiveIntensity: 1.65 });
  const mint = material({ color: "#8cf1d0", metalness: 0.18, roughness: 0.26, emissive: "#54c9ad", emissiveIntensity: 0.45 });
  const quartz = material({ color: "#f4ad55", metalness: 0.14, roughness: 0.16, transparent: true, opacity: 0.32, side: THREE.DoubleSide, depthWrite: false, flatShading: true, emissive: "#f39230", emissiveIntensity: 0.25 });
  const quartzHighlight = material({ color: "#ffe2b4", metalness: 0.22, roughness: 0.14, transparent: true, opacity: 0.24, side: THREE.DoubleSide, depthWrite: false, flatShading: true, emissive: "#f4a04a", emissiveIntensity: 0.12 });
  const sphere = remember(new THREE.IcosahedronGeometry(1, 1));
  const cube = remember(new THREE.BoxGeometry(1, 1, 1));
  const rod = remember(new THREE.CylinderGeometry(1, 1, 1, 5, 1));
  const diamond = remember(new THREE.OctahedronGeometry(1));

  // Geometry is merged by material in each semantic group. Ordinary meshes keep
  // the complete shape portable to glTF without an instancing/shader extension.
  function batch(parent: THREE.Group, name: string) {
    const pieces = new Map<THREE.MeshStandardMaterial, THREE.BufferGeometry[]>();
    const add = (base: THREE.BufferGeometry, mat: THREE.MeshStandardMaterial, position: V3 = [0, 0, 0], scale: V3 = [1, 1, 1], rotation: V3 = [0, 0, 0]) => {
      const geometry = remember(base.index ? base.toNonIndexed() : base.clone()); geometry.deleteAttribute("uv");
      geometry.applyMatrix4(new THREE.Matrix4().compose(at(position), new THREE.Quaternion().setFromEuler(new THREE.Euler(...rotation)), at(scale)));
      const list = pieces.get(mat) ?? []; list.push(geometry); pieces.set(mat, list);
    };
    const beam = (a: THREE.Vector3, b: THREE.Vector3, radius: number, mat: THREE.MeshStandardMaterial) => {
      const distance = a.distanceTo(b); if (distance < 0.0001) return;
      const geometry = remember(rod.toNonIndexed()); geometry.deleteAttribute("uv");
      geometry.applyMatrix4(new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), new THREE.Quaternion().setFromUnitVectors(UP, b.clone().sub(a).normalize()), new THREE.Vector3(radius, distance, radius)));
      const list = pieces.get(mat) ?? []; list.push(geometry); pieces.set(mat, list);
    };
    const tube = (points: V3[], radius: number, mat: THREE.MeshStandardMaterial, segments = 36, closed = false) => {
      const geometry = remember(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(at), closed), segments, radius, 5, closed));
      add(geometry, mat); release(geometry);
    };
    const finish = () => {
      const meshes: THREE.Mesh[] = [];
      for (const [mat, list] of pieces) {
        const merged = mergeGeometries(list, false);
        if (!merged) throw new Error(`Cannot assemble ${name}`);
        remember(merged); list.forEach(release);
        const mesh = new THREE.Mesh(merged, mat); mesh.name = `${name}_${mat.name || mat.color.getHexString()}`;
        mesh.userData = { part: name }; parent.add(mesh); meshes.push(mesh);
      }
      return meshes;
    };
    return { add, beam, tube, finish };
  }
  const group = (name: string, part: string, parent = root) => {
    const value = new THREE.Group(); value.name = name; value.userData = { part }; parent.add(value); return value;
  };
  const select = (objects: THREE.Object3D[], id: FusionBrainId | "conductor" | "gate") => {
    objects.forEach(object => { object.userData.pick = id; pickables.push(object); });
  };

  const shell = group("Smoky_Quartz_Folds", "protective-visual-shell");
  const folds = batch(shell, "Faceted_Quartz");
  const ribbons: { points: V3[]; width: number }[] = [
    { points: [[0.72, 2.54, -0.76], [-0.95, 2.96, -0.62], [-2.42, 2.70, -0.15], [-3.16, 1.88, 0.34], [-3.52, 0.65, 0.52], [-3.25, -0.20, 0.18]], width: 0.91 },
    { points: [[-3.42, 0.22, -0.34], [-3.50, -0.81, 0.27], [-2.87, -1.84, 0.54], [-1.88, -2.20, 0.28], [-0.70, -2.87, 0.52], [0.52, -2.91, 0.24]], width: 0.82 },
    { points: [[-0.44, 2.62, -0.94], [1.23, 2.68, -0.76], [2.67, 2.18, -0.44], [3.30, 1.10, -0.15], [3.31, 0.25, -0.30]], width: 0.69 },
    { points: [[2.97, 0.02, -0.56], [3.60, -0.68, 0.20], [3.36, -1.72, 0.44], [2.42, -2.13, 0.70], [1.43, -2.53, 0.34], [0.64, -2.91, 0.14]], width: 0.93 },
    { points: [[-2.58, 0.43, -0.93], [-1.53, 0.50, -0.85], [-0.78, 0.97, -0.77], [0.07, 0.92, -0.72], [0.85, 0.30, -0.94]], width: 0.39 },
    { points: [[-1.14, -2.44, -0.82], [-0.42, -2.86, -0.50], [0.62, -2.84, -0.36], [1.55, -2.25, -0.44], [2.66, -1.89, -0.76]], width: 0.55 },
  ];
  ribbons.forEach((ribbon, i) => {
    const geometry = remember(quartzRibbon(ribbon.points, ribbon.width, 940 + i));
    folds.add(geometry, i % 3 === 1 ? quartzHighlight : quartz); release(geometry);
    if (i < 4) folds.tube(ribbon.points.map(p => [p[0], p[1], p[2] - 0.04] as V3), 0.006, gold, 36);
  });
  folds.finish();

  // Curved ribs form genuine open cells. Their holes remain empty from every
  // viewing angle rather than being a pattern painted on an opaque surface.
  const frame = group("Porous_Organic_Metal_Ribs", "structural-ribs");
  const ribs = batch(frame, "Open_Cell_Metal");
  // Two irregular pierced lobes, rather than a rectilinear cage behind every
  // organ. Beveled openings curve in depth and remain actual geometric holes.
  for (const [cx, cy, angle] of [[2.10, 1.14, -0.25], [-2.11, -1.08, 0.32]]) {
    const shape = new THREE.Shape();
    shape.moveTo(-0.90, -0.56);
    shape.bezierCurveTo(-1.19, 0.12, -0.92, 1.00, -0.27, 1.13);
    shape.bezierCurveTo(0.31, 1.39, 1.01, 0.66, 1.03, 0.02);
    shape.bezierCurveTo(1.17, -0.64, 0.64, -1.08, 0.03, -1.00);
    shape.bezierCurveTo(-0.46, -1.13, -0.69, -0.92, -0.90, -0.56);
    const holes = [[0.02, 0.09, 0.36, 0.34, -0.26], [-0.55, 0.30, 0.20, 0.30, -0.24], [0.57, 0.17, 0.22, 0.33, 0.10], [-0.17, 0.78, 0.31, 0.16, 0.10], [-0.22, -0.61, 0.32, 0.19, -0.26], [0.55, -0.55, 0.20, 0.23, -0.30]];
    holes.forEach(([x, y, rx, ry, turn]) => {
      const hole = new THREE.Path(); hole.absellipse(x, y, rx, ry, 0, TAU, true, turn); shape.holes.push(hole);
    });
    const geometry = remember(new THREE.ExtrudeGeometry(shape, { depth: 0.055, bevelEnabled: true, bevelSegments: 2, bevelSize: 0.025, bevelThickness: 0.025, steps: 1, curveSegments: 12 }));
    const points = geometry.getAttribute("position");
    for (let i = 0; i < points.count; i++) {
      const x = points.getX(i), y = points.getY(i);
      points.setZ(i, points.getZ(i) + 0.21 * (x * x + y * y) + Math.sin(y * 2.5) * 0.14);
    }
    geometry.computeVertexNormals();
    ribs.add(geometry, steel, [cx, cy, -0.88], [1.06, 1.06, 1], [0.06, -0.08, angle]); release(geometry);
  }
  const branches: V3[][] = [
    [[-0.62, -2.69, -0.36], [-1.63, -2.31, -0.67], [-2.96, -1.36, -0.52], [-3.13, 0.21, -0.71], [-2.73, 1.80, -0.72], [-1.72, 2.60, -0.69]],
    [[0.64, -2.69, -0.42], [1.80, -2.25, -0.63], [3.02, -1.38, -0.60], [3.11, 0.30, -0.77], [2.67, 1.90, -0.80], [1.70, 2.52, -0.77]],
    [[-3.15, -0.01, -0.74], [-2.67, 0.31, -0.85], [-1.87, 0.33, -0.99], [-1.02, -0.17, -0.76]],
    [[3.14, 0.03, -0.76], [2.65, -0.31, -0.88], [1.90, -0.34, -0.99], [0.99, 0.12, -0.78]],
  ];
  branches.forEach((path, i) => ribs.tube(path, i < 2 ? 0.054 : 0.034, i % 2 ? copper : steel, 48));
  ribs.finish();

  const orbits = group("Inclined_Gimbal_Orbits", "orbital-support");
  const orbitBatch = batch(orbits, "Gimbal_Tracks");
  for (let ring = 0; ring < 3; ring++) {
    const path: V3[] = [];
    const tilt = [-0.11, 0.13, -0.23][ring], cy = [0.12, -0.10, -0.07][ring];
    const radiusX = [4.30, 4.08, 4.12][ring], radiusY = [2.47, 2.55, 1.73][ring];
    const start = [-0.04, 0.96, 0.52][ring] * Math.PI;
    const span = [1.08, 1.08, 0.86][ring] * Math.PI;
    for (let step = 0; step <= 72; step++) {
      const angle = start + step / 72 * span, x = Math.cos(angle) * radiusX, y = Math.sin(angle) * radiusY;
      path.push([x * Math.cos(tilt) - y * Math.sin(tilt), cy + x * Math.sin(tilt) + y * Math.cos(tilt), Math.sin(angle * 2) * 1.40 - 0.55]);
    }
    orbitBatch.tube(path, ring === 0 ? 0.033 : 0.023, ring === 0 ? steel : copper, 108);
    for (let tick = 0; tick < 25; tick++) {
      const point = path[Math.floor(tick / 25 * path.length)];
      orbitBatch.add(sphere, tick % 4 === 0 ? mint : gold, point, [0.027, 0.027, 0.027]);
    }
  }
  orbitBatch.finish();

  const dynamic: { id: FusionBrainId; lights: THREE.MeshStandardMaterial[]; pulse: THREE.Mesh; curve: THREE.CatmullRomCurve3 }[] = [];
  FUSION_BRAINS.forEach((spec, brainIndex) => {
    const cluster = group(`${spec.name}_Constellation`, "brain-cluster");
    const [x, y, z] = spec.position;
    cluster.position.set(x, y, z);
    cluster.userData = { part: "brain-cluster", id: spec.id, model: spec.model, role: ROLES[spec.id], pick: spec.id };
    clusters[spec.id] = cluster;
    const active = material({ color: spec.color, metalness: 0.20, roughness: 0.25, emissive: spec.color, emissiveIntensity: 0.65 });
    active.name = `${spec.id}_activity`;
    const trace = material({ color: spec.color, metalness: 0.25, roughness: 0.30, emissive: spec.color, emissiveIntensity: 0.36 });
    trace.name = `${spec.id}_nerves`;
    const glass = material({ color: spec.color, metalness: 0.25, roughness: 0.18, transparent: true, opacity: 0.23, depthWrite: false, flatShading: true, side: THREE.DoubleSide, emissive: spec.color, emissiveIntensity: 0.16 });
    const network = batch(cluster, `${spec.name}_Cells_And_Nerves`);
    const random = randomSource(710 + brainIndex * 31);
    const cells: THREE.Vector3[] = [];
    const count = [30, 36, 42, 27][brainIndex];
    for (let i = 0; i < count; i++) {
      const angle = i * 2.3999632297, y = 1 - 2 * (i + 0.5) / count;
      const r = Math.sqrt(1 - y * y), distance = 0.85 + random() * 0.19;
      const p = new THREE.Vector3(Math.cos(angle) * r * distance * 1.04, y * distance * 0.90, Math.sin(angle) * r * distance * 0.63);
      cells.push(p);
      const size = 0.023 + random() * 0.022;
      network.add(sphere, active, [p.x, p.y, p.z], [size, size, size]);
      if (i % 5 === 0) network.add(cube, glass, [p.x * 0.91, p.y * 0.90, p.z + 0.17], [0.14, 0.14, 0.14], [random(), random(), 0]);
    }
    const links = new Set<string>();
    cells.forEach((p, index) => {
      const near = cells.map((q, j) => ({ j, distance: p.distanceToSquared(q) })).filter(item => item.j !== index).sort((a, b) => a.distance - b.distance).slice(0, 3);
      near.forEach(({ j }) => {
        const key = `${Math.min(index, j)}:${Math.max(index, j)}`;
        if (!links.has(key)) { links.add(key); network.beam(p, cells[j], 0.008, trace); }
      });
    });
    network.finish();

    const organ = group(`${spec.name}_Organ`, "role-organ", cluster);
    organ.userData = { part: "role-organ", id: spec.id, model: spec.model, role: ROLES[spec.id], pick: spec.id };
    const body = batch(organ, `${spec.name}_Geometry`);
    if (spec.id === "talk") {
      const capsule = remember(new THREE.CapsuleGeometry(0.36, 0.80, 5, 12));
      body.add(capsule, glass, [0, 0, 0.12], [1, 1, 1], [0, 0, Math.PI / 2]); release(capsule);
      const outline: V3[] = [];
      for (let i = 0; i < 48; i++) {
        const angle = i / 48 * TAU;
        outline.push([Math.cos(angle) * 0.36 + (Math.cos(angle) >= 0 ? 0.40 : -0.40), Math.sin(angle) * 0.36, 0.39]);
      }
      body.tube(outline, 0.035, copper, 60, true);
      for (let layer = 0; layer < 3; layer++) {
        const collar = remember(new THREE.TorusGeometry(0.41, 0.033, 5, 32));
        body.add(collar, layer === 1 ? active : steel, [(layer - 1) * 0.56, 0, 0.12], [1, 1, 1], [0, Math.PI / 2, 0]); release(collar);
      }
      for (let i = 0; i < 25; i++) {
        const x = (i - 12) * 0.049;
        const height = 0.045 + Math.exp(-x * x * 3) * (0.055 + Math.abs(Math.sin(i * 1.65)) * 0.25);
        body.add(cube, active, [x, 0, 0.49], [0.018, height, 0.024]);
      }
      for (let i = 0; i < 8; i++) body.add(cube, glass, [(i % 4 - 1.5) * 0.34, i < 4 ? 0.49 : -0.49, 0.07], [0.25, 0.23, 0.24], [0.1, 0.2, 0.08]);
    } else if (spec.id === "seek") {
      body.add(diamond, glass, [0, 0.02, 0.18], [0.65, 0.85, 0.56], [0, 0.30, -0.20]);
      const edges = remember(new THREE.EdgesGeometry(diamond));
      const positions = edges.getAttribute("position");
      for (let i = 0; i < positions.count; i += 2) {
        const transform = (index: number) => new THREE.Vector3(positions.getX(index) * 0.65, positions.getY(index) * 0.85, positions.getZ(index) * 0.56).applyEuler(new THREE.Euler(0, 0.30, -0.20)).add(new THREE.Vector3(0, 0.02, 0.18));
        body.beam(transform(i), transform(i + 1), 0.013, active);
      }
      release(edges);
      for (const radius of [0.38, 0.64, 0.79]) {
        const ring = remember(new THREE.TorusGeometry(radius, 0.010, 4, 64));
        body.add(ring, trace, [0, -0.11, 0.31], [1, 1, 1], [0.30, 0.15, 0]); release(ring);
      }
      for (let i = 0; i < 24; i++) {
        const a = i / 24 * TAU;
        body.add(cube, active, [Math.cos(a) * 0.65, Math.sin(a) * 0.65 - 0.11, 0.40], [0.010, 0.045, 0.013], [0, 0, a - Math.PI / 2]);
      }
    } else if (spec.id === "study") {
      body.add(cube, glass, [0, 0, 0.16], [0.95, 0.95, 0.81], [0.10, 0.23, -0.12]);
      for (let face = 0; face < 4; face++) {
        const a = face * Math.PI / 2;
        body.add(diamond, glass, [Math.cos(a) * 0.63, Math.sin(a) * 0.58, -0.01], [0.46, 0.32, 0.24], [0.15, a, a * 0.35]);
      }
      for (let z = 0; z < 2; z++) for (let row = 0; row < 3; row++) {
        const y = (row - 1) * 0.22;
        body.tube([[-0.41, y + 0.09, 0.59 - z * 0.13], [-0.15, y + 0.09, 0.59 - z * 0.13], [-0.15, y - 0.06, 0.59 - z * 0.13], [0.15, y - 0.06, 0.59 - z * 0.13], [0.15, y - 0.18, 0.59 - z * 0.13], [0.42, y - 0.18, 0.59 - z * 0.13]], 0.010, z === 0 ? gold : active, 18);
      }
      const wire = remember(new THREE.EdgesGeometry(cube));
      const positions = wire.getAttribute("position");
      for (let i = 0; i < positions.count; i += 2) {
        const a = new THREE.Vector3().fromBufferAttribute(positions, i).multiplyScalar(0.99).add(new THREE.Vector3(0, 0, 0.16));
        const b = new THREE.Vector3().fromBufferAttribute(positions, i + 1).multiplyScalar(0.99).add(new THREE.Vector3(0, 0, 0.16));
        body.beam(a, b, 0.012, active);
      }
      release(wire);
    } else {
      const beads: V3[] = [[0, 0, 0.32], [-0.58, 0.28, 0.18], [0.57, 0.23, 0.12], [-0.31, -0.43, 0.08], [0.36, -0.44, 0.18], [-0.09, 0.62, -0.02], [0.64, -0.18, -0.12], [-0.66, -0.25, -0.17]];
      beads.forEach((p, i) => {
        const size = i === 0 ? 0.25 : 0.12 + (i % 3) * 0.035;
        body.add(sphere, copper, p, [size, size, size]);
        if (i) body.beam(at(p), at(beads[0]), 0.014, mint);
        if (i > 1) body.beam(at(p), at(beads[i - 1]), 0.012, trace);
      });
      for (let i = 0; i < 10; i++) {
        const a = i / 10 * TAU;
        body.add(cube, mint, [Math.cos(a) * 0.73, Math.sin(a) * 0.69, -0.13 + (i % 2) * 0.20], [0.09, 0.09, 0.09]);
      }
    }
    const bodyMeshes = body.finish(); select(bodyMeshes, spec.id);
    // One travelling pearl per brain uses the actual curved nerve geometry.
    const p = spec.position;
    const path: V3[] = [[0, 0.04, 0.60], [p[0] * 0.34, p[1] * 0.10, 0.65], [p[0] * 0.63, p[1] * 0.77, 0.62], [p[0], p[1], p[2] + 0.22]];
    const curve = new THREE.CatmullRomCurve3(path.map(at));
    const nerves = batch(root, `${spec.name}_Conductor_Link`);
    for (let line = 0; line < 3; line++) nerves.tube(path.map(q => [q[0], q[1] + (line - 1) * 0.045, q[2] - Math.abs(line - 1) * 0.035] as V3), line === 1 ? 0.015 : 0.007, line === 1 ? active : trace, 40);
    nerves.finish();
    const pearl = new THREE.Mesh(sphere, active); pearl.name = `${spec.name}_Signal_Pearl`; pearl.scale.setScalar(0.043); pearl.userData = { part: "activity-signal", id: spec.id }; root.add(pearl);
    dynamic.push({ id: spec.id, lights: [active, trace, glass], pulse: pearl, curve });
  });

  const conductor = group("Central_Conductor", "conductor");
  conductor.position.set(0, 0.04, 0.60);
  conductor.userData = { part: "conductor", role: "Routes work between brains; does not grant permissions", pick: "conductor" };
  const hub = batch(conductor, "Conductor_Crystal_And_Cage");
  const hubGlass = material({ color: "#ffc572", emissive: "#ff9b32", emissiveIntensity: 0.25, metalness: 0.20, roughness: 0.22, transparent: true, opacity: 0.16, depthWrite: false, flatShading: true });
  hub.add(diamond, ivory, [0, 0, 0], [0.25, 0.44, 0.25]);
  hub.add(diamond, hubGlass, [0, 0, 0], [0.36, 0.57, 0.35]);
  hub.add(sphere, hubGlass, [0, 0, -0.08], [0.81, 0.83, 0.70]);
  for (let i = 0; i < 3; i++) {
    const ring = remember(new THREE.TorusGeometry(0.77 + i * 0.08, 0.009, 4, 72));
    hub.add(ring, i === 1 ? gold : copper, [0, 0, -0.10], [1, 1, 1], [i * 0.62 + 0.10, i * 0.72, 0.20]); release(ring);
  }
  select(hub.finish(), "conductor");

  // A deliberately separate mechanical gate below the SE. Visual connections
  // carry no authority and never imply the brains may bypass the real gate.
  const gate = group("Execution_Security_Gate", "execution-security-gate");
  gate.position.set(0, -2.14, 0.60);
  gate.userData = { part: "execution-security-gate", role: "Independent authorization boundary; visual indicator only", pick: "gate" };
  const gateBody = batch(gate, "Gate_Housing_And_Jaws");
  const outer = remember(new THREE.TorusGeometry(0.64, 0.135, 8, 48));
  gateBody.add(outer, darkSteel, [0, 0, -0.10]); release(outer);
  const inner = remember(new THREE.TorusGeometry(0.46, 0.045, 6, 48));
  gateBody.add(inner, copper, [0, 0, 0.02]); release(inner);
  for (let sector = 0; sector < 8; sector++) {
    const a = sector / 8 * TAU;
    const jaw = remember(new THREE.TorusGeometry(0.65, 0.105, 5, 7, 0.54));
    gateBody.add(jaw, sector % 2 ? steel : copper, [0, 0, 0.09], [1, 1, 1], [0, 0, a]); release(jaw);
    gateBody.add(cube, steel, [Math.cos(a + 0.28) * 0.63, Math.sin(a + 0.28) * 0.63, 0.22], [0.10, 0.07, 0.07], [0, 0, a]);
    gateBody.add(sphere, darkSteel, [Math.cos(a + 0.28) * 0.71, Math.sin(a + 0.28) * 0.71, 0.25], [0.028, 0.028, 0.018]);
  }
  gateBody.add(cube, gold, [0, 0, -0.01], [0.43, 0.27, 0.28]);
  for (const y of [-0.25, 0.25]) gateBody.add(cube, steel, [0, y, 0.06], [0.48, 0.075, 0.35]);
  for (const x of [-0.31, 0.31]) gateBody.add(cube, copper, [x, 0, 0.10], [0.10, 0.43, 0.21]);
  for (const x of [-0.19, 0, 0.19]) gateBody.add(cube, ivory, [x, 0, 0.17], [0.016, 0.20, 0.018]);
  const pedestal = remember(new THREE.CylinderGeometry(0.56, 0.68, 0.13, 24));
  gateBody.add(pedestal, steel, [0, -0.78, -0.04]); release(pedestal);
  gateBody.add(cube, darkSteel, [0, -0.63, -0.04], [0.60, 0.20, 0.43]);
  select(gateBody.finish(), "gate");
  const gateLinks = batch(root, "Conductor_To_Security_Gate");
  for (const x of [-0.04, 0.04]) gateLinks.tube([[x, -0.42, 0.63], [x, -0.94, 0.59], [-0.15 + x, -1.32, 0.67], [x, -1.50, 0.72]], 0.018, gold, 28);
  gateLinks.finish();

  let disposed = false;
  function update(timeSeconds: number, levels: Partial<Record<FusionBrainId, number>>, animate = true) {
    if (disposed) return;
    const time = animate && Number.isFinite(timeSeconds) ? timeSeconds : 0;
    let peak = 0;
    dynamic.forEach((item, index) => {
      const input = levels[item.id];
      const level = typeof input === "number" && Number.isFinite(input) ? THREE.MathUtils.clamp(input, 0, 1) : 0;
      peak = Math.max(peak, level);
      const shimmer = animate ? Math.sin(time * (1.25 + level * 3) + index * 1.4) * 0.08 * level : 0;
      item.lights[0].emissiveIntensity = 0.28 + level * 1.85 + shimmer;
      item.lights[1].emissiveIntensity = 0.15 + level * 0.75;
      item.lights[2].emissiveIntensity = 0.08 + level * 0.28;
      const progress = ((time * (0.11 + level * 0.26) + index * 0.22 + 0.16) % 1 + 1) % 1;
      item.curve.getPoint(progress, item.pulse.position);
      item.pulse.scale.setScalar(0.024 + level * 0.024);
    });
    ivory.emissiveIntensity = 1.15 + peak * 1.1;
    // Never change root rotation/position: the host owns the camera and drag.
  }
  update(0, {}, false);
  root.updateMatrixWorld(true);
  return {
    root, clusters, pickables, update,
    dispose() {
      if (disposed) return; disposed = true;
      geometries.forEach(geometry => geometry.dispose());
      materials.forEach(value => value.dispose());
      geometries.clear(); materials.clear();
    },
  };
}
