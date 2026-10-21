import { useId } from "react";
import jarvisHologram from "../../assets/jarvis-hologram.png";
import jarvisReference from "../../assets/jarvis-reference.png";
import type { CoreTelemetry } from "../../core/coreTelemetry";
import "./SystemProgressCore.css";

type VisualMode = "blend" | "hologram" | "progress" | "original";
type Props = { telemetry: CoreTelemetry | null; source: "preview" | "local"; motion: boolean; visualMode: VisualMode };
const ringDash = (radius: number, ...percents: number[]) => percents.map((n) => (2 * Math.PI * radius * n / 100).toFixed(2)).join(" ");
const ringOffset = (radius: number, percent: number) => -2 * Math.PI * radius * percent / 100;
const point = (cx: number, cy: number, r: number, angle: number) => ({
  x: cx + Math.cos((angle - 90) * Math.PI / 180) * r,
  y: cy + Math.sin((angle - 90) * Math.PI / 180) * r,
});
const ticks = Array.from({ length: 144 }, (_, i) => {
  const a = i * 2.5;
  const main = i % 12 === 0;
  const inside = point(400, 400, main ? 258 : 263, a);
  const outside = point(400, 400, main ? 275 : 268, a);
  return { ...inside, tx: outside.x, ty: outside.y, key: i, main };
});
const blueSegments = Array.from({ length: 60 }, (_, i) => i).filter((i) => i < 12 || (i > 20 && i < 31) || (i > 47 && i < 56));
const starPoints = Array.from({ length: 65 }, (_, i) => ({
  x: 55 + ((i * 193 + 41) % 695), y: 67 + ((i * 149 + 113) % 670),
  opacity: 0.12 + (i % 4) * 0.085, r: i % 11 === 0 ? 1.3 : 0.58,
}));

export function SystemProgressCore({ telemetry, source, motion, visualMode }: Props) {
  const id = useId().replace(/:/g, "");
  const value = telemetry?.progress ?? null;
  const clamped = value === null ? 0 : Math.max(0, Math.min(100, value));
  const firstArc = Math.min(18, clamped / 78 * 18);
  const secondArc = Math.min(18, Math.max(0, (clamped - 20) / 58 * 18));
  const modules = telemetry?.modules ?? [];
  const complete = modules.filter((m) => m.phase === "ready" || m.phase === "working").length;
  const stage = telemetry?.phase || "AWAITING DATA";
  const diagnostics = telemetry?.diagnostics || "UNAVAILABLE";
  const sync = telemetry?.synchronization || "NOT CONNECTED";
  const c = { x: 400, y: 400 };
  if (visualMode === "original") return <div className="system-core system-core--original"><img src={jarvisReference} alt="Original J.A.R.V.I.S. reference photograph" className="system-core__original" draggable={false}/></div>;
  const showHologram = visualMode === "blend" || visualMode === "hologram";
  return (
    <div className={`system-core ${motion ? "system-core--motion" : "system-core--still"} system-core--${visualMode}`}>

      <svg className="system-core__svg" viewBox="0 0 800 800" role="img"
        aria-label={`${source === "preview" ? "Preview sample" : "Local status"}: ${value === null ? "progress unknown" : `${clamped}%`}, ${stage}. ${complete} of ${modules.length} modules reporting ready or working.`}>
        <defs>
          <radialGradient id={`${id}-bg`}><stop offset="0" stopColor="#df8a32" stopOpacity=".13"/><stop offset=".48" stopColor="#144371" stopOpacity=".035"/><stop offset="1" stopColor="#05101e" stopOpacity="0"/></radialGradient>
          <linearGradient id={`${id}-amber`} x1="0" x2="1" y1="0" y2="1"><stop stopColor="#fff2ae"/><stop offset=".25" stopColor="#ffb647"/><stop offset=".62" stopColor="#f59a25"/><stop offset="1" stopColor="#b85d15"/></linearGradient>
          <linearGradient id={`${id}-blue`} x1="0" x2="1" y1="0" y2="1"><stop stopColor="#3fa5ff"/><stop offset=".5" stopColor="#9ecaff"/><stop offset="1" stopColor="#174c97"/></linearGradient>
          <filter id={`${id}-glow`} x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="8"/></filter>
          <filter id={`${id}-smallglow`} x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="3"/></filter>
        </defs>
        <circle cx="400" cy="400" r="340" fill={`url(#${id}-bg)`} />
        <g className="system-core__dust">{starPoints.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={p.r} fill={i % 3 === 0 ? "#eda94d" : "#457ea8"} opacity={p.opacity}/>)}</g>
        <g className="system-core__reticle" stroke="#b9894c" fill="none">
          <path d="M 74 400 H 325 M 475 400 H 728 M 400 72 V 310 M 400 490 V 727" strokeWidth=".8" opacity=".28"/>
          <path d="M 170 400 H 300 M 500 400 H 632" strokeWidth="1.2" opacity=".5"/>
          <circle cx="400" cy="400" r="302" opacity=".32" strokeWidth=".9"/>
          <circle cx="400" cy="400" r="279" opacity=".26" strokeDasharray="2 9"/>
          <circle cx="400" cy="400" r="285" opacity=".44" strokeWidth="1"/>
          <circle cx="400" cy="400" r="255" opacity=".24" strokeWidth="1"/>
          <circle cx="400" cy="400" r="243" opacity=".21" strokeWidth=".9"/>
        </g>
        <g className="system-core__crossnodes">
          {[{x:400,y:98},{x:400,y:702},{x:98,y:400},{x:702,y:400}].map((p,i)=><g key={i}><circle cx={p.x} cy={p.y} r="11" fill="#f6a734" opacity=".14" filter={`url(#${id}-glow)`}/><circle cx={p.x} cy={p.y} r={i===0||i===1?3.2:3.7} fill="#f6b452"/></g>)}
        </g>
        <g className="system-core__tick-ring" stroke="#cb9d65">
          {ticks.map(t=><line key={t.key} x1={t.x} y1={t.y} x2={t.tx} y2={t.ty} opacity={t.main ? 0.58 : 0.22} strokeWidth={t.main ? 1.4 : 0.6}/>) }
        </g>
        <g className="system-core__tracks" fill="none" transform="rotate(-90 400 400)">
          <circle cx="400" cy="400" r="226" stroke="#593719" strokeWidth="20" opacity=".34"/>
          <circle cx="400" cy="400" r="226" stroke={`url(#${id}-amber)`} strokeWidth="21" strokeDasharray={ringDash(226, firstArc, 100 - firstArc)} strokeDashoffset={ringOffset(226,1)} opacity=".78" filter={`url(#${id}-glow)`}/>
          <circle cx="400" cy="400" r="226" stroke={`url(#${id}-amber)`} strokeWidth="17" strokeDasharray={ringDash(226, firstArc, 100 - firstArc)} strokeDashoffset={ringOffset(226,1)} opacity={value === null ? .2 : .92}/>
          <circle cx="400" cy="400" r="226" stroke={`url(#${id}-amber)`} strokeWidth="21" strokeDasharray={ringDash(226, secondArc, 100 - secondArc)} strokeDashoffset={ringOffset(226,51)} opacity=".19" filter={`url(#${id}-glow)`}/>
          <circle cx="400" cy="400" r="226" stroke={`url(#${id}-amber)`} strokeWidth="17" strokeDasharray={ringDash(226, secondArc, 100 - secondArc)} strokeDashoffset={ringOffset(226,51)} opacity={value === null ? .2 : .96}/>
          <circle cx="400" cy="400" r="248" stroke="#e4a04d" strokeWidth="1.2" strokeDasharray={ringDash(248, clamped, 100-clamped)} opacity={value===null?0:.85}/>
          <circle cx="400" cy="400" r="203" stroke="#7e521f" strokeWidth="1.7" strokeDasharray="3 8" opacity=".52"/>
          <circle cx="400" cy="400" r="191" stroke="#f3a33c" strokeWidth="7" strokeDasharray={ringDash(191,18,32,9,41)} opacity=".76"/>
          <circle cx="400" cy="400" r="177" stroke="#2c74af" strokeWidth="4" strokeDasharray={ringDash(177,11,4,7,22,3,7,7,39)} opacity=".75"/>
          <circle cx="400" cy="400" r="158" stroke="#a87538" strokeWidth="2" strokeDasharray="2 11" opacity=".42"/>
          <circle cx="400" cy="400" r="144" stroke="#80501e" strokeWidth="10" strokeDasharray={ringDash(144,12,16,4,10,20,38)} opacity=".56"/>
        </g>
        <g className="system-core__blue-ticks" stroke={`url(#${id}-blue)`} strokeWidth="4.7">
          {blueSegments.map((i)=>{
            const a = i * 6;
            const p1=point(c.x,c.y,214,a);const p2=point(c.x,c.y,215,a+2.35);
            return <path key={i} d={`M${p1.x.toFixed(2)} ${p1.y.toFixed(2)} A 215 215 0 0 1 ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`} opacity={i%5 === 0 ? 0.95 : 0.6}/>;
          })}
        </g>
        <g className="system-core__rotor" fill="none">
          <circle cx="400" cy="400" r="238" stroke="#3f91d6" strokeDasharray={ringDash(238,14,12,4,53)} strokeWidth="2" opacity=".78"/>
          <circle cx="400" cy="400" r="267" stroke="#eeb15b" strokeDasharray={ringDash(267,1.5,2,3,28)} strokeWidth="2" opacity=".52"/>
          <circle cx="400" cy="400" r="173" stroke="#3987d3" strokeDasharray={ringDash(173,6,1,1,92)} strokeWidth="2.5" opacity=".7"/>
        </g>
        {showHologram && <g className="system-core__hologram" aria-hidden="true">
          <image href={jarvisHologram} x="222" y="222" width="356" height="356" preserveAspectRatio="xMidYMid meet" opacity=".9"/>
        </g>}
        <g className="system-core__core-center">
          <circle cx="400" cy="400" r={showHologram ? "79" : "137"} fill="#080e18" opacity={showHologram ? ".76" : ".79"}/>
          <circle cx="400" cy="400" r="131" stroke="#ffa83e" strokeWidth="17" opacity={showHologram ? ".12" : ".33"} fill="none" filter={`url(#${id}-glow)`}/>
          <circle cx="400" cy="400" r="128" stroke="#fdad48" strokeWidth="7" opacity={showHologram ? ".18" : ".88"} fill="none" filter={`url(#${id}-smallglow)`}/>
          <circle cx="400" cy="400" r="121" stroke={`url(#${id}-amber)`} strokeWidth="6" fill="none" opacity={showHologram ? ".22" : ".94"}/>
          <circle cx="400" cy="400" r="111" stroke="#df8c36" strokeWidth="1" fill="none" opacity=".4"/>
          <circle cx="400" cy="400" r="97" stroke="#eb9d46" strokeWidth=".7" fill="none" opacity=".2"/>
        </g>
        <g className="system-core__center-text" textAnchor="middle">
          <text x="400" y="382" fill="#ffc16e" fontSize="25" letterSpacing="10" fontWeight="500">ZÆNIA</text>
          <text x="400" y="408" fill="#e7aa57" fontSize="9.6" letterSpacing="3.5" fontWeight="650">{stage}</text>
          <line x1="351" x2="449" y1="426" y2="426" stroke="#c58f4a" strokeWidth="1"/>
          <circle cx="400" cy="426" r="2" fill="#f8bb65" />
          <text x="400" y="467" fill={value===null?"#8194aa":"#ffc16e"} fontSize="27" letterSpacing="4" fontWeight="500">{value===null?"—":`${clamped}%`}</text>
          <text x="400" y="489" fill="#758ca7" fontSize="8.8" letterSpacing="2">{source === "preview" ? "PREVIEW DATA" : "LOCAL STATUS"}</text>
        </g>
        <g className="system-core__callouts" fill="#86a3c3" fontSize="9.3" letterSpacing="2.1">
          <g><circle cx="85" cy="193" r="2.8" fill="#fcb453"/><path d="M 105 210 H 161 L 189 237" stroke="#50789a" fill="none"/><text x="108" y="181">SYSTEM BOOT</text><text x="108" y="198" fill="#a6bdd3" letterSpacing="1.4">{stage === "AWAITING DATA" ? "NO TELEMETRY" : "PREPARING CORE..."}</text></g>
          <g><circle cx="718" cy="196" r="2.8" fill="#fcb453"/><path d="M 610 236 L 636 212 H 693" stroke="#50789a" fill="none"/><text x="646" y="181">MODULES</text><text x="646" y="198" letterSpacing="1.4" fill="#a6bdd3">{String(complete).padStart(2,"0")} / {String(modules.length).padStart(2,"0")}</text></g>
          <g><circle cx="45" cy="512" r="2.8" fill="#fcb453"/><path d="M 77 513 H 145 L 186 482" stroke="#50789a" fill="none"/><text x="64" y="496">DIAGNOSTICS</text><text x="64" y="515" letterSpacing="1.2" fill="#a6bdd3">{diagnostics}</text><g fill="#f0a343">{[0,1,2,3].map(i=><circle key={i} cx={66+i*14} cy="538" r="2.7" opacity={value===null ? 0.18 : 1}/>)}</g></g>
          <g><circle cx="759" cy="512" r="2.8" fill="#fcb453"/><path d="M 610 482 L 642 513 H 737" stroke="#50789a" fill="none"/><text x="649" y="496">SYNCHRONIZATION</text><text x="649" y="515" letterSpacing="1" fill="#a6bdd3">{sync}</text><g>{[0,1,2,3,4].map(i=><circle key={i} cx={652+i*14} cy="538" r="2.8" fill={i<3 && value!==null?"#f0a343":"#3d5572"}/>)}</g></g>
        </g>
        <g className="system-core__microtext" fontSize="9" letterSpacing="2" fill="#7290ab">
          <text x="152" y="758">VISUAL CORE</text><text x="152" y="774" fill="#d8a35c" letterSpacing="1.2">01 / 01</text>
          <text x="590" y="758">STATUS SOURCE</text><text x="590" y="774" fill="#d8a35c" letterSpacing="1.2">{source === "preview" ? "SIMULATED" : "LOOPBACK"}</text>
        </g>
      </svg>
    </div>
  );
}
