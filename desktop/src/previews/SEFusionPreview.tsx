import { useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type { BrainId } from "../components/tools/seActivity";
import type { ConstellationFeed } from "../components/tools/se3d/constellation";
import { SEFusionCanvas } from "../components/tools/se3d/SEFusionCanvas";
import { FUSION_BRAINS } from "../components/tools/se3d/fusionModel";
import "./SEFusionPreview.css";

/** Standalone synthetic preview. No API, owner data, provider, microphone or permissions are consulted. */
function Preview() {
  const [mode, setMode] = useState("resting");
  const [motion, setMotion] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const latest = useRef(mode); latest.current = mode;
  const state = (id: BrainId) => latest.current === "all" || (latest.current === "reading" && (id === "talk" || id === "seek")) || (latest.current === "research" && id === "study");
  const feed = useMemo<ConstellationFeed>(() => ({
    signals: () => ["talk", "seek", "study", "keep"].map(id => ({ installed: true, level: state(id as BrainId) ? 1 : 0.25 })),
    text: id => { const spec = FUSION_BRAINS.find(brain => brain.id === id)!; return { name: spec.name, model: spec.model, job: id, state: state(id) ? "Example: active" : "Example: resting" }; },
    tip: id => { const spec = FUSION_BRAINS.find(brain => brain.id === id)!; return { key: id, title: spec.name, color: spec.color, sub: spec.model, lines: [], note: "Sample activity for this preview. The app uses its existing model-status feed." }; },
    hubTip: () => ({ key: "hub", title: "Conductor", color: "#fff0cb", lines: [], note: "Coordinates Talk, Seek, Study and Keep. Permissions remain with Core." }),
  }), []);
  return <main className="fusion-preview zaenia-app" data-motion={motion ? "full" : "reduced"}>
    <header><span>ZÆNIA · SYNERGIZED ENCEPHALON</span><h1>Constellation Fusion</h1><p>A real 3D model combining the orbital, crystalline and lattice designs with four connected model clusters.</p></header>
    <nav aria-label="Example model activity">{[["resting", "Resting"], ["reading", "Reading"], ["research", "Research"], ["all", "All active"]].map(([id, name]) => <button key={id} aria-pressed={mode === id} onClick={() => setMode(id)}>{name}</button>)}
      <button aria-pressed={!motion} onClick={() => setMotion(value => !value)}>Reduce motion</button>
      <a href="/models/zaenia-se-fusion.glb" download="zaenia-se-fusion.glb">Download 3D model</a></nav>
    <SEFusionCanvas feed={feed} onSelect={id => setSelected(id)}/>
    <footer><span>Preview · sample activity only · {selected ? `Selected: ${selected}` : "Select a model for details"}</span><span>The execution gate is a visual boundary. This model performs no actions.</span></footer>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Preview/>);
