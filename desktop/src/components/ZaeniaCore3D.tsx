import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * ZÆNIA planet-atom, Stage 3 reference-matched visual build.
 *
 * 1. Midnight-blue plasma globe rotates counter to the Saturn-style ring flow.
 * 2. Flat ring bands stay physically in place. Their ENERGY travels around them.
 * 3. Spark streaks are shader details ON the rings — never free-orbiting objects.
 * 4. An exposed golden nucleus glows through the translucent outer globe.
 * 5. Hover / click energize the existing system. No backend actions are performed.
 * 6. Materials, geometry, and effects are local-only; no online services required.
 *
 * Future "nerve" navigation is intentionally NOT implemented here.
 */

const BLUE = new THREE.Color("#168aff");
const CYAN = new THREE.Color("#55ddff");
const AMBER = new THREE.Color("#ffb000");
const ORANGE = new THREE.Color("#ff790d");

const SPHERE_VERTEX = /* glsl */ `
  varying vec3 vLocal;
  varying vec3 vViewNormal;
  varying vec3 vEye;
  void main() {
    vLocal = position;
    vec4 p = modelViewMatrix * vec4(position, 1.0);
    vViewNormal = normalize(normalMatrix * normal);
    vEye = normalize(-p.xyz);
    gl_Position = projectionMatrix * p;
  }
`;

const PLANET_FRAGMENT = /* glsl */ `
  precision highp float;
  varying vec3 vLocal;
  varying vec3 vViewNormal;
  varying vec3 vEye;
  uniform float uTime;
  uniform float uHover;
  uniform float uBurst;

  float hash3(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
  }
  float noise3(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f*f*(3.0 - 2.0*f);
    return mix(
      mix(mix(hash3(i),hash3(i+vec3(1.,0.,0.)),f.x),
          mix(hash3(i+vec3(0.,1.,0.)),hash3(i+vec3(1.,1.,0.)),f.x),f.y),
      mix(mix(hash3(i+vec3(0.,0.,1.)),hash3(i+vec3(1.,0.,1.)),f.x),
          mix(hash3(i+vec3(0.,1.,1.)),hash3(i+vec3(1.,1.,1.)),f.x),f.y),f.z);
  }
  float fbm(vec3 p) {
    float v=0.0;
    float a=0.56;
    for (int i=0;i<5;i++) {
      v+=a*noise3(p);
      p=p*2.05+vec3(2.7,1.8,3.2);
      a*=0.51;
    }
    return v;
  }
  void main() {
    vec3 n=normalize(vViewNormal);
    float ndv=abs(dot(n,normalize(vEye)));
    float rim=pow(1.0-ndv,2.3);
    vec3 p=normalize(vLocal);
    float t=uTime*0.09;
    float cloud=fbm(p*3.9+vec3(t,-t*0.7,t*0.5));
    float fine=fbm(p*13.0-vec3(t*1.4,t*0.8,-t));
    float ridged=abs(fbm(p*7.0+vec3(t*1.2,0.,-t))-0.52);
    float longitude=atan(p.z,p.x);
    float electric=pow(0.5+0.5*sin(longitude*15.0+p.y*27.0+fine*9.0-uTime*0.3),21.0);
    float amberArcs=pow(0.5+0.5*sin(longitude*11.0+p.y*22.0+cloud*10.0+uTime*0.11),29.0);
    float strata=smoothstep(0.38,0.70,cloud+fine*0.14);
    vec3 abyss=vec3(0.005,0.021,0.075);
    vec3 midnight=vec3(0.012,0.065,0.23);
    vec3 cobalt=vec3(0.016,0.29,0.92);
    vec3 cyan=vec3(0.11,0.72,1.0);
    vec3 amber=vec3(1.0,0.32,0.016);
    vec3 color=mix(abyss,midnight,0.53+cloud*0.38);
    color=mix(color,cobalt,strata*0.70);
    color+=cyan*(electric*(0.27+0.30*fine)+pow(rim,2.0)*1.22);
    color+=amber*amberArcs*(0.22+0.26*uBurst);
    color+=cobalt*(1.0-ridged)*0.09;
    color+=vec3(0.35,0.71,1.0)*pow(rim,4.0)*0.62;
    color*=1.0+uHover*0.15+uBurst*0.25;
    float alpha=clamp(0.79+0.08*cloud+rim*0.11,0.0,0.97);
    gl_FragColor=vec4(color,alpha);
  }
`;

const ATMOSPHERE_FRAGMENT = /* glsl */ `
  precision highp float;
  varying vec3 vLocal;
  varying vec3 vViewNormal;
  varying vec3 vEye;
  uniform float uTime;
  uniform float uHover;
  float wrap(float x) { return fract(x); }
  void main() {
    float rim = pow(1.0 - abs(dot(normalize(vViewNormal), normalize(vEye))), 3.0);
    float a = atan(vLocal.z, vLocal.x);
    float glint = pow(0.5 + 0.5*sin(a*14.0 + uTime*0.18), 9.0);
    vec3 color = mix(vec3(0.045, 0.16, 0.7), vec3(0.16, 0.78, 1.0), glint);
    gl_FragColor = vec4(color * (1.0 + 0.45*uHover), rim * (0.30 + glint*0.08));
  }
`;

const CORE_FRAGMENT = /* glsl */ `
  precision highp float;
  varying vec3 vLocal;
  varying vec3 vViewNormal;
  varying vec3 vEye;
  uniform float uTime;
  uniform float uHover;
  uniform float uBurst;
  void main() {
    vec3 p=normalize(vLocal);
    float rim=pow(1.0-abs(dot(normalize(vViewNormal),normalize(vEye))),2.0);
    float pulse=0.88+0.12*sin(uTime*2.1);
    float web=pow(0.5+0.5*sin(atan(p.z,p.x)*13.0+p.y*21.0-uTime*1.10),7.0);
    float detail=pow(0.5+0.5*sin(p.y*57.0+uTime*1.35),9.0);
    vec3 gold=vec3(1.0,0.50,0.035);
    vec3 hot=vec3(1.0,0.91,0.58);
    vec3 color=mix(gold,hot,clamp(0.43+web*0.32+detail*0.18+rim*0.22,0.0,1.0));
    color*=(pulse+uHover*0.21+uBurst*0.72);
    gl_FragColor=vec4(color,0.99);
  }
`;

const BAND_VERTEX = /* glsl */ `
  varying vec3 vLocal;
  void main() {
    vLocal = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const BAND_FRAGMENT = /* glsl */ `
  precision highp float;
  varying vec3 vLocal;
  uniform float uTime;
  uniform float uHover;
  uniform float uBurst;
  uniform float uPhase;
  uniform float uSpeed;
  uniform float uInner;
  uniform float uOuter;
  uniform float uStrength;
  uniform vec3 uBlue;
  uniform vec3 uAmber;

  void main() {
    float radius=length(vLocal.xy);
    float x=clamp((radius-uInner)/(uOuter-uInner),0.0,1.0);
    float a=atan(vLocal.y,vLocal.x);
    float t=uTime*uSpeed;
    float edge=smoothstep(0.0,0.035,x)*(1.0-smoothstep(0.955,1.0,x));
    float wideGlow=smoothstep(0.0,0.16,x)*(1.0-smoothstep(0.84,1.0,x));
    float lanes=pow(0.5+0.5*cos(x*56.0+sin(a*4.0)*0.43),7.0);
    float micro=pow(0.5+0.5*cos(x*124.0+sin(a*3.1+uPhase)),22.0);
    float motion=pow(0.5+0.5*cos(a*9.0-t*2.6+x*20.0+uPhase),5.0);
    float wideArc=pow(0.5+0.5*cos(a*3.0-t*0.67+uPhase),4.0);
    // Highlights ride along the material of the ring, not as orbiting spheres.
    float sparks=pow(0.5+0.5*cos(a*49.0-t*6.2+x*31.0),88.0);
    float heat=clamp(0.45+0.47*sin(a*1.8-t*0.12+x*3.3+uPhase),0.0,1.0);
    vec3 color=mix(uBlue,uAmber,heat);
    vec3 innerColor=mix(vec3(0.09,0.52,1.0),vec3(1.0,0.58,0.06),heat);
    color=mix(color,innerColor,lanes*0.50+motion*0.15);
    float intensity=(0.12+wideGlow*0.19+lanes*0.33+micro*0.18+motion*0.33+wideArc*0.22+sparks*0.60)*edge;
    color*=0.88+lanes*0.55+motion*0.46+sparks*1.2;
    float alpha=clamp(intensity*uStrength*(1.0+0.32*uHover+0.65*uBurst),0.0,0.96);
    gl_FragColor=vec4(color,alpha);
  }
`;

const HALO_VERTEX = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
  }
`;

const HALO_FRAGMENT = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform float uHover;
  uniform float uBurst;
  uniform float uWarm;
  uniform float uGain;
  void main() {
    vec2 p = vUv*2.0-1.0;
    float r = length(p);
    float radial = exp(-r*r*5.5);
    float thin = exp(-r*r*19.0);
    float wave = 0.94 + 0.06*sin(uTime*1.8);
    vec3 blue = vec3(0.025,0.23,0.75);
    vec3 gold = vec3(1.0,0.40,0.036);
    vec3 col = mix(blue,gold,uWarm);
    float a = (radial*0.36 + thin*0.46) * wave * (1.0 + uHover*0.28 + uBurst*0.70) * uGain;
    gl_FragColor = vec4(col, a);
  }
`;

function shaderMaterial(
  vertexShader: string,
  fragmentShader: string,
  uniforms: Record<string, THREE.IUniform>,
  extra: Partial<THREE.ShaderMaterialParameters> = {},
) {
  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    ...extra,
  });
}

function useDispose(material: THREE.Material) {
  useEffect(() => () => material.dispose(), [material]);
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);
  return reduced;
}

function useLiveShader(
  material: THREE.ShaderMaterial,
  hover: boolean,
  activation: number,
  reducedMotion: boolean,
) {
  const lastActivation = useRef(activation);
  useFrame((_state, delta) => {
    const dt = Math.min(delta, 0.05);
    if (!reducedMotion && material.uniforms.uTime) {
      material.uniforms.uTime.value += dt;
    }
    if (material.uniforms.uHover) {
      material.uniforms.uHover.value = THREE.MathUtils.damp(
        material.uniforms.uHover.value, hover ? 1 : 0, 5, dt,
      );
    }
    if (lastActivation.current !== activation) {
      lastActivation.current = activation;
      if (material.uniforms.uBurst) material.uniforms.uBurst.value = 1;
    }
    if (material.uniforms.uBurst) {
      material.uniforms.uBurst.value = Math.max(0, material.uniforms.uBurst.value - dt * 0.90);
    }
  });
}

type LiveProps = {
  hover: boolean;
  activation: number;
  reducedMotion: boolean;
};

function PlasmaPlanet({ hover, activation, reducedMotion }: LiveProps) {
  const rotationRef = useRef<THREE.Group>(null);
  const material = useMemo(() => shaderMaterial(SPHERE_VERTEX, PLANET_FRAGMENT, {
    uTime: { value: 0 }, uHover: { value: 0 }, uBurst: { value: 0 },
  }, { blending: THREE.NormalBlending, side: THREE.FrontSide }), []);
  useDispose(material);
  useLiveShader(material, hover, activation, reducedMotion);

  useFrame((_state, delta) => {
    if (rotationRef.current && !reducedMotion) {
      // Planet rotates one way; ring energy visibly circulates the other.
      rotationRef.current.rotation.y -= Math.min(delta, 0.05) * 0.16;
      rotationRef.current.rotation.z += Math.min(delta, 0.05) * 0.018;
    }
  });

  return (
    <group ref={rotationRef}>
      <mesh renderOrder={7}>
        <sphereGeometry args={[1.12, 128, 96]} />
        <primitive object={material} attach="material" />
      </mesh>
    </group>
  );
}

function Atmosphere({ hover, activation, reducedMotion }: LiveProps) {
  const material = useMemo(() => shaderMaterial(SPHERE_VERTEX, ATMOSPHERE_FRAGMENT, {
    uTime: { value: 0 }, uHover: { value: 0 }, uBurst: { value: 0 },
  }, { side: THREE.BackSide }), []);
  useDispose(material);
  useLiveShader(material, hover, activation, reducedMotion);
  return (
    <mesh scale={1.22} renderOrder={8}>
      <sphereGeometry args={[1.08, 96, 64]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

function Nucleus({ hover, activation, reducedMotion }: LiveProps) {
  const material = useMemo(() => shaderMaterial(SPHERE_VERTEX, CORE_FRAGMENT, {
    uTime: { value: 0 }, uHover: { value: 0 }, uBurst: { value: 0 },
  }, { blending: THREE.AdditiveBlending }), []);
  useDispose(material);
  useLiveShader(material, hover, activation, reducedMotion);
  return (
    <group position={[0, 0, 1.14]}>
      <mesh renderOrder={13}>
        <sphereGeometry args={[0.29, 72, 56]} />
        <primitive object={material} attach="material" />
      </mesh>
      <mesh scale={1.55} renderOrder={12}>
        <sphereGeometry args={[0.29, 48, 32]} />
        <meshBasicMaterial color="#ff7c0b" transparent opacity={0.21} blending={THREE.AdditiveBlending} depthWrite={false} depthTest={false} />
      </mesh>
      <mesh scale={2.05} renderOrder={12}>
        <sphereGeometry args={[0.29, 48, 32]} />
        <meshBasicMaterial color="#ff8e1d" transparent opacity={0.08} blending={THREE.AdditiveBlending} depthWrite={false} depthTest={false} />
      </mesh>
      <pointLight color="#ff8613" intensity={3.4} distance={3.2} decay={2} />
    </group>
  );
}

/** Multiple amber plasma arcs surround the nucleus on the near hemisphere. */
function ReactorCorona({ reducedMotion }: { reducedMotion: boolean }) {
  const group = useRef<THREE.Group>(null);
  useFrame((_state, delta) => {
    if (group.current && !reducedMotion) group.current.rotation.z += Math.min(delta, 0.05) * 0.12;
  });
  return (
    <group ref={group} position={[0, 0, 1.21]}>
      <mesh rotation={[0.25, 0.1, -0.30]} renderOrder={14}>
        <torusGeometry args={[0.45, 0.009, 6, 192]} />
        <meshBasicMaterial color="#ff9e26" transparent opacity={0.76} depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      <mesh rotation={[0.40, -0.25, 0.65]} renderOrder={14}>
        <torusGeometry args={[0.53, 0.006, 6, 192]} />
        <meshBasicMaterial color="#ffc35c" transparent opacity={0.46} depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      <mesh rotation={[0.10, 0.37, -0.75]} renderOrder={14}>
        <torusGeometry args={[0.64, 0.004, 5, 192]} />
        <meshBasicMaterial color="#ff7b10" transparent opacity={0.31} depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  );
}

type GlowProps = LiveProps & { size: number; depth: number; warm: boolean; strength: number };
function Halo({ hover, activation, reducedMotion, size, depth, warm, strength }: GlowProps) {
  const material = useMemo(() => shaderMaterial(HALO_VERTEX, HALO_FRAGMENT, {
    uTime: { value: 0 }, uHover: { value: 0 }, uBurst: { value: 0 },
    uWarm: { value: warm ? 1 : 0 },
    uGain: { value: strength },
  }, { depthTest: false }), [warm, strength]);
  useDispose(material);
  useLiveShader(material, hover, activation, reducedMotion);
  return (
    <mesh scale={[size, size, 1]} position={[0, 0, depth]} renderOrder={strength < 1 ? -2 : 6}>
      <planeGeometry args={[1, 1]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

type RingProps = LiveProps & {
  inner: number;
  outer: number;
  tilt: [number, number, number];
  phase: number;
  speed: number;
  strength: number;
  stretch: number;
};
function EnergyBand({ inner, outer, tilt, phase, speed, strength, stretch, hover, activation, reducedMotion }: RingProps) {
  const material = useMemo(() => shaderMaterial(BAND_VERTEX, BAND_FRAGMENT, {
    uTime: { value: 0 }, uHover: { value: 0 }, uBurst: { value: 0 },
    uPhase: { value: phase }, uSpeed: { value: speed },
    uInner: { value: inner }, uOuter: { value: outer },
    uStrength: { value: strength }, uBlue: { value: BLUE }, uAmber: { value: AMBER },
  }, { side: THREE.DoubleSide }), [inner, outer, phase, speed, strength]);
  useDispose(material);
  useLiveShader(material, hover, activation, reducedMotion);

  return (
    <group rotation={tilt} scale={[stretch, 1, 1]}>
      <mesh renderOrder={9}>
        <ringGeometry args={[inner, outer, 320, 8]} />
        <primitive object={material} attach="material" />
      </mesh>
      <mesh renderOrder={10}>
        <torusGeometry args={[outer - 0.03, 0.012, 7, 288]} />
        <meshBasicMaterial color={phase < 2 ? CYAN : ORANGE} transparent opacity={0.41 * strength} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      <mesh renderOrder={10}>
        <torusGeometry args={[inner + 0.07, 0.010, 7, 288]} />
        <meshBasicMaterial color={phase < 2 ? ORANGE : CYAN} transparent opacity={0.36 * strength} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  );
}

function InnerFilaments({ reducedMotion }: { reducedMotion: boolean }) {
  const group = useRef<THREE.Group>(null);
  useFrame((_state, delta) => {
    if (group.current && !reducedMotion) group.current.rotation.y += Math.min(delta, 0.05) * 0.085;
  });
  return (
    <group ref={group} renderOrder={3}>
      <mesh rotation={[1.20, 0.46, -0.22]}>
        <torusGeometry args={[0.69, 0.011, 7, 192]} />
        <meshBasicMaterial color="#ff9b29" transparent opacity={0.34} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      <mesh rotation={[0.65, -0.30, 0.58]}>
        <torusGeometry args={[0.77, 0.008, 6, 192]} />
        <meshBasicMaterial color="#2a98ff" transparent opacity={0.34} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      <mesh rotation={[1.49, 0.41, 0.18]}>
        <torusGeometry args={[0.83, 0.007, 6, 192]} />
        <meshBasicMaterial color="#ffad36" transparent opacity={0.19} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  );
}

function CoreScene({ reducedMotion }: { reducedMotion: boolean }) {
  const [hover, setHover] = useState(false);
  const [activation, setActivation] = useState(0);
  useEffect(() => () => { document.body.style.cursor = "auto"; }, []);
  return (
    <group scale={1.24}>
      {/* Ambient light behind the center, not applied to the warehouse image. */}
      <Halo hover={hover} activation={activation} reducedMotion={reducedMotion} size={7.9} depth={-1.15} warm={false} strength={0.48} />
      <Halo hover={hover} activation={activation} reducedMotion={reducedMotion} size={5.8} depth={-1.0} warm strength={0.52} />
      <InnerFilaments reducedMotion={reducedMotion} />
      <PlasmaPlanet hover={hover} activation={activation} reducedMotion={reducedMotion} />
      <Atmosphere hover={hover} activation={activation} reducedMotion={reducedMotion} />
      <Halo hover={hover} activation={activation} reducedMotion={reducedMotion} size={2.35} depth={1.20} warm strength={0.92} />
      <Nucleus hover={hover} activation={activation} reducedMotion={reducedMotion} />
      <ReactorCorona reducedMotion={reducedMotion} />

      {/* Predominantly Saturn-like bands, with restrained cross-tilted energy. */}
      <EnergyBand inner={1.31} outer={2.24} tilt={[1.15, 0.02, -0.08]} stretch={1.22} phase={0.28} speed={1.42} strength={1.22} hover={hover} activation={activation} reducedMotion={reducedMotion} />
      <EnergyBand inner={1.48} outer={2.32} tilt={[1.18, -0.03, 0.00]} stretch={1.17} phase={2.48} speed={1.68} strength={0.98} hover={hover} activation={activation} reducedMotion={reducedMotion} />
      <EnergyBand inner={1.59} outer={2.20} tilt={[1.13, 0.02, -0.05]} stretch={1.17} phase={4.12} speed={1.14} strength={0.78} hover={hover} activation={activation} reducedMotion={reducedMotion} />

      {/* Invisible interaction target. Not a visible or orbiting sphere. */}
      <mesh
        onPointerOver={(event) => { event.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={(event) => { event.stopPropagation(); setHover(false); document.body.style.cursor = "auto"; }}
        onClick={(event) => { event.stopPropagation(); setActivation((n) => n + 1); }}
        onPointerMissed={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        <sphereGeometry args={[1.36, 40, 32]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} colorWrite={false} />
      </mesh>
    </group>
  );
}

export default function ZaeniaCore3D() {
  const reducedMotion = useReducedMotion();
  return (
    <Canvas
      className="zaenia-core-canvas"
      camera={{ position: [0, 0, 6.75], fov: 39, near: 0.1, far: 60 }}
      gl={{ alpha: true, antialias: true, powerPreference: "high-performance", premultipliedAlpha: false }}
      dpr={[1, 1.75]}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
        gl.outputColorSpace = THREE.SRGBColorSpace;
      }}
      fallback={<div className="zaenia-webgl-fallback">This visual requires an available WebGL graphics renderer.</div>}
      aria-label="Animated ZÆNIA planet-atom core with circulating rings"
    >
      <CoreScene reducedMotion={reducedMotion} />
    </Canvas>
  );
}
