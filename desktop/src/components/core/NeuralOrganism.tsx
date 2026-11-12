import { Component, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { wakeLevel } from "../../core/coreWake";

type Props = { motion: boolean; processing: boolean; startupProgress: number };
type Strand = { curve: THREE.CatmullRomCurve3; blue: boolean };

// A reproducible organism: remounting never rearranges the network.
function randomGenerator() {
  let seed = 7319;
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}

function makeNetwork() {
  const random = randomGenerator();
  const strands: Strand[] = [];
  const positions: number[] = [];
  const colors: number[] = [];
  const nodes: number[] = [];
  const amber = new THREE.Color("#df8a42");
  const blue = new THREE.Color("#538bc1");
  const add = (points: THREE.Vector3[], isBlue: boolean) => {
    const curve = new THREE.CatmullRomCurve3(points);
    const samples = curve.getPoints(30);
    const color = isBlue ? blue : amber;
    for (let i = 1; i < samples.length; i++) {
      positions.push(...samples[i - 1].toArray(), ...samples[i].toArray());
      colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
    }
    strands.push({ curve, blue: isBlue });
    nodes.push(...points[points.length - 1].toArray());
    return curve;
  };
  // Neurons lie on a common spherical surface. Connections curve around it.
  const neurons = Array.from({ length: 240 }, (_, i) => {
    const y = 1 - 2 * (i + 0.5) / 240;
    const angle = i * Math.PI * (3 - Math.sqrt(5));
    return new THREE.Vector3(Math.cos(angle) * Math.sqrt(1 - y * y), y,
      Math.sin(angle) * Math.sqrt(1 - y * y)).add(new THREE.Vector3((random() - 0.5) * 0.10, (random() - 0.5) * 0.10, (random() - 0.5) * 0.10)).normalize().multiplyScalar(1.03);
  });
  const edges = new Set<string>();
  const connect = (a: THREE.Vector3, b: THREE.Vector3, isBlue: boolean) => {
    const axis = a.clone().cross(b).normalize();
    const bend = (random() - 0.5) * 0.10;
    const points = Array.from({ length: 9 }, (_, step) => {
      const t = step / 8;
      return a.clone().lerp(b, t).normalize().multiplyScalar(1.03)
        .addScaledVector(axis, Math.sin(Math.PI * t) * bend)
        .normalize().multiplyScalar(1.03);
    });
    add(points, isBlue);
  };
  const edge = (i: number, j: number) => {
    const key = `${Math.min(i, j)}:${Math.max(i, j)}`;
    if (edges.has(key)) return;
    edges.add(key);
    connect(neurons[i], neurons[j], (i + j) % 4 === 0);
  };
  neurons.forEach((neuron, i) => {
    const nearest = neurons.map((other, j) => ({ j, d: neuron.distanceToSquared(other) }))
      .filter(candidate => candidate.j !== i).sort((a, b) => a.d - b.d);
    nearest.slice(0, 5).forEach(candidate => edge(i, candidate.j));
    // Each neuron joins the existing graph, ensuring one connected organism.
    if (i > 0) edge(i, nearest.find(candidate => candidate.j < i)!.j);
  });
  nodes.length = 0;
  neurons.forEach(neuron => nodes.push(...neuron.toArray()));
  // These surface junctions match the six existing SVG subsystem nerve roots.
  for (const x of [-160, 160]) {
    for (const y of [-123.2, 0, 129.36]) {
      const px = x * 2.18 / 448;
      const py = -y * 2.18 / 448;
      const junction = new THREE.Vector3(px, py, Math.sqrt(1.03 ** 2 - px ** 2 - py ** 2));
      const nearest = [...neurons].sort((a, b) => a.distanceToSquared(junction) - b.distanceToSquared(junction));
      nearest.slice(0, 3).forEach(neuron => connect(junction, neuron, y === 0));
      nodes.push(...junction.toArray());
    }
  }
  // A restrained inner arbor connects the nucleus to selected surface neurons.
  // Most nerves remain on the sphere so the silhouette stays round.
  for (let i = 0; i < 24; i++) {
    const end = neurons[(i * 37) % neurons.length];
    const bend = new THREE.Vector3(-end.y, end.x, 0).normalize().multiplyScalar(0.12);
    add([end.clone().multiplyScalar(0.09), end.clone().multiplyScalar(0.35).add(bend),
      end.clone().multiplyScalar(0.7).addScaledVector(bend, -0.5), end], i % 3 === 0);
  }
  const tubes = strands.map((strand, i) => {
    const tube = new THREE.TubeGeometry(strand.curve, 20, i % 6 === 0 ? 0.0038 : 0.0018, 4, false);
    const color = i % 29 === 0 ? new THREE.Color("#dddfe4") : i % 7 === 0 ? new THREE.Color(strand.blue ? "#69a4d9" : "#e69a56") : strand.blue ? blue : amber;
    const values = new Float32Array(tube.attributes.position.count * 3);
    for (let j = 0; j < values.length; j += 3) color.toArray(values, j);
    tube.setAttribute("color", new THREE.BufferAttribute(values, 3));
    return tube;
  });
  const filaments = mergeGeometries(tubes)!;
  tubes.forEach(tube => tube.dispose());
  return { strands, filaments, positions: new Float32Array(positions),
    colors: new Float32Array(colors), nodes: new Float32Array(nodes) };
}

const glowVertex = `
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const glowFragment = `
  uniform float uBoot;
  varying vec2 vUv;
  void main() {
    float radius = length(vUv - 0.5) * 2.0;
    float halo = exp(-radius * radius * 9.0);
    float hot = exp(-radius * radius * 80.0);
    gl_FragColor = vec4(mix(vec3(0.88, 0.43, 0.12), vec3(0.96, 0.83, 0.66), hot), (halo * 0.3 + hot * 0.65) * uBoot);
  }
`;
const shellVertex = `
  uniform float uBoot;
  varying vec3 vNormal;
  varying vec3 vEye;
  void main() {
    vec4 view = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vEye = normalize(-view.xyz);
    gl_Position = projectionMatrix * view;
  }
`;
const shellFragment = `
  uniform float uBoot;
  varying vec3 vNormal;
  varying vec3 vEye;
  void main() {
    float facing = max(0.0, dot(normalize(vNormal), normalize(vEye)));
    float rim = pow(1.0 - facing, 3.0);
    float light = max(0.0, dot(normalize(vNormal), normalize(vec3(-0.6, 0.8, 1.0))));
    vec3 color = mix(vec3(0.025, 0.055, 0.095), vec3(0.06, 0.13, 0.23), light);
    color += vec3(0.08, 0.17, 0.30) * rim;
    gl_FragColor = vec4(color, 0.2 * uBoot);
  }
`;
const nerveVertex = `
  varying vec3 vColor;
  varying float vDepth;
  varying float vRadius;
  void main() {
    vColor = color;
    vDepth = position.z;
    vRadius = length(position);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const nerveFragment = `
  uniform float uBoot;
  varying vec3 vColor;
  varying float vDepth;
  varying float vRadius;
  void main() {
    float front = smoothstep(-0.9, 0.9, vDepth);
    float reveal = smoothstep(vRadius - 0.08, vRadius + 0.08, uBoot * 1.2);
    gl_FragColor = vec4(vColor * mix(0.4, 1.2, front), mix(0.08, 0.9, front) * reveal);
  }
`;

const pointVertex = `
  uniform float uSize;
  varying vec3 vColor;
  void main() {
    vColor = color * mix(0.3, 1.0, smoothstep(-0.8, 0.8, position.z));
    vec4 p = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = min(22.0, uSize / max(0.5, -p.z));
    gl_Position = projectionMatrix * p;
  }
`;
const pointFragment = `
  uniform float uBoot;
  varying vec3 vColor;
  void main() {
    float radius = length(gl_PointCoord - 0.5) * 2.0;
    if (radius > 1.0) discard;
    float glow = pow(1.0 - radius, 2.0);
    gl_FragColor = vec4(vColor * (1.0 + glow), glow * uBoot);
  }
`;

function Network({ motion, processing, startupProgress }: Props) {
  const { camera, size, invalidate } = useThree();
  useLayoutEffect(() => {
    const orthographic = camera as THREE.OrthographicCamera;
    orthographic.zoom = Math.min(size.width, size.height) / 2.18;
    orthographic.updateProjectionMatrix();
    invalidate();
  }, [camera, size.width, size.height, invalidate]);
  const network = useMemo(makeNetwork, []);
  const nucleusWake = wakeLevel(startupProgress, 0, 14);
  const nerveWake = wakeLevel(startupProgress, 8, 58);
  useEffect(() => () => network.filaments.dispose(), [network]);
  const signals = useRef<THREE.Points>(null);
  const elapsed = useRef(0);
  const signalPositions = useMemo(() => new Float32Array(80 * 3), []);
  const signalColors = useMemo(() => {
    const buffer = new Float32Array(80 * 3);
    for (let i = 0; i < 80; i++) {
      const strand = network.strands[(i * 17) % network.strands.length];
      new THREE.Color(i % 13 === 0 ? "#e9e7df" : strand.blue ? "#72afe0" : "#eda263").toArray(buffer, i * 3);
    }
    return buffer;
  }, [network]);
  const nodeColors = useMemo(() => {
    const buffer = new Float32Array(network.nodes.length);
    for (let i = 0; i < buffer.length; i += 3) {
      new THREE.Color(i % 19 === 0 ? "#e5e7e9" : i % 7 === 0 ? "#e39955" : i % 12 === 0 ? "#699cd0" : "#d58c4f").toArray(buffer, i);
    }
    return buffer;
  }, [network]);
  const position = useMemo(() => new THREE.Vector3(), []);
  useFrame((_, delta) => {
    if (motion) elapsed.current += Math.min(delta, 0.05) * (processing ? 1.8 : 1);
    const geometry = signals.current?.geometry;
    if (!geometry) return;
    for (let i = 0; i < 80; i++) {
      const strand = network.strands[(i * 17) % network.strands.length];
      const progress = (elapsed.current * (0.1 + (i % 5) * 0.018) + i * 0.618) % 1;
      // Signals travel on actual 3D nerves; the organism never breathes or scales.
      strand.curve.getPoint(progress, position).toArray(signalPositions, i * 3);
    }
    geometry.attributes.position.needsUpdate = true;
  });
  return <group>
    <mesh geometry={network.filaments}><shaderMaterial vertexShader={nerveVertex} fragmentShader={nerveFragment} uniforms={{ uBoot: { value: nerveWake } }} vertexColors transparent depthWrite={false} blending={THREE.AdditiveBlending}/></mesh>
    <mesh position={[0, 0, 1.05]}><planeGeometry args={[0.9, 0.9]}/><shaderMaterial vertexShader={glowVertex} fragmentShader={glowFragment} uniforms={{ uBoot: { value: nucleusWake } }} transparent depthWrite={false} blending={THREE.AdditiveBlending}/></mesh>
    <mesh>
      <sphereGeometry args={[1.025, 64, 48]}/>
      <shaderMaterial vertexShader={shellVertex} fragmentShader={shellFragment} uniforms={{ uBoot: { value: nerveWake } }} transparent depthWrite={false}/>
    </mesh>
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[network.positions, 3]}/>
        <bufferAttribute attach="attributes-color" args={[network.colors, 3]}/>
      </bufferGeometry>
      <shaderMaterial vertexShader={nerveVertex} fragmentShader={nerveFragment} uniforms={{ uBoot: { value: nerveWake } }} vertexColors transparent depthWrite={false} blending={THREE.AdditiveBlending}/>
    </lineSegments>
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[network.nodes, 3]}/>
        <bufferAttribute attach="attributes-color" args={[nodeColors, 3]}/>
      </bufferGeometry>
      <shaderMaterial vertexShader={pointVertex} fragmentShader={pointFragment}
        uniforms={{ uSize: { value: 43 }, uBoot: { value: nerveWake } }} vertexColors transparent depthWrite={false} blending={THREE.AdditiveBlending}/>
    </points>
    <points ref={signals} frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[signalPositions, 3]}/>
        <bufferAttribute attach="attributes-color" args={[signalColors, 3]}/>
      </bufferGeometry>
      <shaderMaterial vertexShader={pointVertex} fragmentShader={pointFragment}
        uniforms={{ uSize: { value: 80 }, uBoot: { value: nerveWake } }} vertexColors transparent depthWrite={false} blending={THREE.AdditiveBlending}/>
    </points>
    <mesh>
      <sphereGeometry args={[0.12, 24, 16]}/>
      <meshBasicMaterial color="#e99b4e" transparent opacity={nucleusWake * 0.95} blending={THREE.AdditiveBlending} depthWrite={false}/>
    </mesh>
  </group>;
}

class RendererBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <div className="neural-core__fallback">3D renderer unavailable. Module navigation remains available.</div> : this.props.children;
  }
}

export function NeuralOrganism({ motion, processing, startupProgress }: Props) {
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReducedMotion(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  const active = motion && !reducedMotion;
  return <RendererBoundary><Canvas
    orthographic camera={{ position: [0, 0, 5], zoom: 1, near: 0.1, far: 20 }}
    dpr={[1, 1.5]} frameloop={active ? "always" : "demand"}
    gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
    onCreated={({ gl }) => {
      gl.setClearColor(0x000000, 0);
    }}
    fallback={<div className="neural-core__fallback">WebGL is unavailable. Module navigation remains available.</div>}
    aria-hidden="true"
  ><Network motion={active} processing={processing} startupProgress={startupProgress}/></Canvas></RendererBoundary>;
}







