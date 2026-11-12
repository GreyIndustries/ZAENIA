import { useEffect, useRef, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import "./NodeWorkspaces.css";

type Row = { id?: string; revision?: number; title: string; models?: string[]; category?: string; prompt?: string; answer?: string; enabled?: boolean; mode?: string; sections?: Record<string,string>; url?: string; location?: string; front?: string; back?: string; source?: string; reviewed?: boolean };
const ROOT = "/api/learning-lab";
export function useLabRecords(kind: string) {
  const [items,setItems]=useState<Row[]>([]), [error,setError]=useState(""), [busy,setBusy]=useState(false);
  const lock=useRef(false);
  async function refresh() { if(LIVE_API) setItems((await api<{items:Row[]}>("GET",`${ROOT}/records/${kind}`)).items); }
  useEffect(()=>{void refresh().catch(e=>setError(errorText(e)));},[kind]);
  async function save(row: Row):Promise<Row|undefined> {
    if(lock.current)return;lock.current=true;setBusy(true);setError("");
    try { const {id,revision,...record}=row;const saved=await api<Row>(id?"PUT":"POST",`${ROOT}/records/${kind}${id?`/${id}`:""}`,{record,revision}); await refresh();return saved; }
    catch(e){setError(errorText(e));return undefined;}finally{lock.current=false;setBusy(false);}
  }
  async function remove(row:Row) {if(!row.id||lock.current)return;lock.current=true;setBusy(true);setError("");try{await api("DELETE",`${ROOT}/records/${kind}/${row.id}?revision=${row.revision}`);await refresh();}catch(e){setError(errorText(e));}finally{lock.current=false;setBusy(false);}}
  return {items,error,busy,save,remove,refresh};
}

export function LLMTraining() {
  const lessons=useLabRecords("lessons");
  const [models,setModels]=useState<string[]>([]),[notice,setNotice]=useState(""),[draft,setDraft]=useState<Row>({title:"",category:"response",prompt:"",answer:"",models:[],enabled:false});
  const [results,setResults]=useState<{model:string;answer:string;expected:string;status:string;error?:string}[]>([]),[running,setRunning]=useState(false),[error,setError]=useState("");
  const runningRef=useRef(false);
  useEffect(()=>{if(LIVE_API)void api<{models:{name:string}[];error:string|null}>("GET",`${ROOT}/models`).then(r=>{setModels(r.models.map(m=>m.name));setNotice(r.error??"");},e=>setError(errorText(e)));},[]);
  const fresh=()=>{setDraft({title:"",category:"response",prompt:"",answer:"",models:[],enabled:false});setResults([]);};
  async function save(){const row=await lessons.save(draft);if(row)setDraft(row);}
  async function evaluate(){if(!draft.id||runningRef.current)return;runningRef.current=true;setRunning(true);setError("");try{const result=await api<{results:typeof results}>("POST",`${ROOT}/evaluate/${draft.id}`,{models:draft.models?.slice(0,3)},{timeoutMs:780000});setResults(result.results);}catch(e){setError(errorText(e));}finally{runningRef.current=false;setRunning(false);}}
  return <section className="node-workspace"><header><span className="node-eyebrow">BUILD · TEACH · EVALUATE</span><h2>LLM Training</h2><p>Teach protocols, action behavior, responses and corrections to selected local models.</p></header>
    <div className="node-callout">Reference-based teaching and practice. Model weights and execution permissions stay unchanged. Enabled lessons provide relevant reference examples to the selected model during authorized conversation and practice. Model-weight fine-tuning is separate.</div>
    {!LIVE_API&&<p>Connect to ZAE Core to load and save lessons.</p>}
    {(error||lessons.error)&&<p role="alert">{error||lessons.error}</p>}{notice&&<p role="status">{notice}</p>}
    <div className="node-columns"><aside className="zx-card node-list"><button disabled={running} onClick={fresh}>New lesson</button>{lessons.items.map(row=><button disabled={running} key={row.id} onClick={()=>{setDraft(row);setResults([]);}} aria-pressed={draft.id===row.id}><strong>{row.title}</strong><small>{row.category} · {row.models?.length} models · {row.enabled?"Rehearsal enabled":"Draft"}</small></button>)}</aside>
    <div className="zx-card node-editor"><label>Lesson title<input aria-label="Lesson title" value={draft.title} maxLength={160} onChange={e=>setDraft({...draft,title:e.target.value})}/></label>
      <label>Training module<select aria-label="Training module" value={draft.category} onChange={e=>setDraft({...draft,category:e.target.value})}>{["protocol","action","response","correction"].map(x=><option key={x}>{x}</option>)}</select></label>
      <fieldset><legend>Models to teach</legend>{models.length===0&&<p>No installed chat models were reported.</p>}{models.map(model=><label className="node-check" key={model}><input type="checkbox" checked={draft.models?.includes(model)??false} disabled={running} onChange={e=>setDraft({...draft,models:e.target.checked?[...(draft.models??[]),model]:(draft.models??[]).filter(x=>x!==model)})}/>{model}</label>)}</fieldset>
      <label>Example request<textarea aria-label="Example request" value={draft.prompt} maxLength={2000} onChange={e=>setDraft({...draft,prompt:e.target.value})}/></label>
      <label>Desired response or behavior<textarea aria-label="Desired response" value={draft.answer} maxLength={6000} onChange={e=>setDraft({...draft,answer:e.target.value})}/></label>
      <label className="node-check"><input type="checkbox" checked={draft.enabled??false} onChange={e=>setDraft({...draft,enabled:e.target.checked})}/>Enable model-specific teaching examples</label>
      <div className="node-actions"><button disabled={!LIVE_API||lessons.busy||running||!draft.title||!draft.prompt||!draft.answer||!draft.models?.length} onClick={()=>void save()}>Save lesson</button><button disabled={!LIVE_API||running||!draft.id} onClick={()=>void evaluate()}>{running?"Practicing locally…":"Practice saved lesson"}</button><button disabled={!draft.id||running||lessons.busy} onClick={()=>void lessons.remove(draft).then(fresh)}>Delete lesson</button></div>
      <small>Practice uses the saved revision, up to three assigned models sequentially. Review the answers yourself; a generated answer is not proof of learning.</small>
    </div></div>
    {results.map(row=><article className="zx-card" key={row.model}><h3>{row.model}</h3><p>{row.status}{row.error?` · ${row.error}`:""}</p><pre>{row.answer}</pre><details><summary>Compare desired behavior</summary><pre>{row.expected}</pre></details></article>)}
  </section>;
}

export function LearningHealth() {
  const [state,setState]=useState<{enabled:boolean;insights:{source?:string;confidence?:string}[]}|null>(null),[error,setError]=useState("");
  async function load(){try{setState(await api("GET","/api/assistant/insights"));}catch(e){setError(errorText(e));}}
  useEffect(()=>{if(LIVE_API)void load();},[]);
  return <section className="node-workspace"><h2>Learning & memory health</h2><p>Live settings and stored observations, separate from model-weight training.</p>{error&&<p role="alert">{error}</p>}{state&&<div className="node-metrics"><article className="zx-card"><strong>{state.enabled?"Enabled":"Disabled"}</strong><span>Automatic insight learning</span></article><article className="zx-card"><strong>{state.insights.length}</strong><span>Stored insights (up to 200 displayed)</span></article><article className="zx-card"><strong>{state.insights.filter(i=>i.source==="user_confirmed").length}</strong><span>Owner-confirmed</span></article></div>}<p>Enabled is a configuration state, not proof that the model or extraction worker is healthy. Confirm, correct or delete observations in Assistant → Memory. Learning never grants execution authority.</p><button disabled={!LIVE_API} onClick={()=>void load()}>Refresh learning status</button></section>;
}

const DEFENSE_PROMPTS:Record<string,string>={
  "Problem and objectives":"Define assets, locations, scope and protection objectives.","Risks and mitigations":"Build a threat register with likelihood/impact assumptions and controls.","Operations and suppliers":"Document camera coverage, network segmentation, access, retention and device requirements.","Incident response and continuity":"Define detection, escalation, evidence handling, recovery and exercises.",
};
export function WarRoomPlans({mode}:{mode:"business"|"defense"}) {
  const plans=useLabRecords("plans"),[sections,setSections]=useState<string[]>([]),[section,setSection]=useState("Executive summary"),[draft,setDraft]=useState<Row>({title:"",mode,sections:{}}),[evidence,setEvidence]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(""),[proposal,setProposal]=useState("");
  const lock=useRef(false);
  useEffect(()=>{if(LIVE_API)void api<{sections:string[]}>("GET",`${ROOT}/sections`).then(r=>setSections(r.sections),e=>setError(errorText(e)));},[]);
  async function generate(){if(lock.current)return;lock.current=true;setBusy(true);setError("");setProposal("");try{const result=await api<{result:string}>("POST","/api/research/workshop/analyze",{mode,question:`Plan: ${draft.title}. Section: ${section}. ${mode==="defense"?(DEFENSE_PROMPTS[section]??"Focus this section on defensive security and continuity."):""} Current draft: ${(draft.sections?.[section]??"").slice(0,2000)}`,sources:evidence.trim()?[{title:"Owner-supplied planning evidence and assumptions",text:evidence}]:[]},{timeoutMs:300000});setProposal(result.result);}catch(e){setError(errorText(e));}finally{lock.current=false;setBusy(false);}}
  const content=draft.sections?.[section]??"";
  function exportPlan(){const text=`# ${draft.title}\n\n`+sections.map(s=>`## ${s}\n\n${draft.sections?.[s]||"Not completed"}`).join("\n\n");const url=URL.createObjectURL(new Blob([text],{type:"text/markdown"}));const a=document.createElement("a");a.href=url;a.download="zae-plan.md";a.click();URL.revokeObjectURL(url);}
  return <section className="node-workspace"><header><span className="node-eyebrow">WAR ROOM · {mode.toUpperCase()}</span><h2>{mode==="business"?"Business planning":"Defense planning"}</h2><p>{mode==="business"?"Develop a complete plan section by section, with explicit assumptions and evidence.":"Plan protection, monitoring, incident response and recovery."}</p></header>
    {(error||plans.error)&&<p role="alert">{error||plans.error}</p>}<div className="node-columns"><aside className="zx-card node-list"><button disabled={busy} onClick={()=>{setDraft({title:"",mode,sections:{}});setProposal("");}}>New {mode} plan</button>{plans.items.filter(p=>p.mode===mode).map(row=><button disabled={busy} key={row.id} onClick={()=>{setDraft(row);setProposal("");}}>{row.title}</button>)}<hr/>{sections.map(s=><button disabled={busy} key={s} aria-pressed={section===s} onClick={()=>{setSection(s);setProposal("");}}>{draft.sections?.[s]?.trim()?"✓ ":""}{s}</button>)}</aside>
    <div className="zx-card node-editor"><label>Plan title<input aria-label="Plan title" maxLength={160} value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})}/></label><h3>{section}</h3><label>Section content<textarea className="node-long" aria-label="Section content" maxLength={16000} value={content} onChange={e=>setDraft({...draft,sections:{...draft.sections,[section]:e.target.value}})}/></label><label>Evidence, constraints and assumptions<textarea aria-label="Planning evidence" value={evidence} maxLength={20000} onChange={e=>setEvidence(e.target.value)}/></label>
    <div className="node-actions"><button disabled={!LIVE_API||busy||!draft.title} onClick={()=>void generate()}>{busy?"Drafting locally…":"Draft this section"}</button><button disabled={!LIVE_API||busy||plans.busy||!draft.title} onClick={()=>void plans.save(draft).then(row=>{if(row)setDraft(row);})}>Save plan</button><button disabled={!draft.title} onClick={exportPlan}>Export Markdown</button></div><small>{Object.values(draft.sections??{}).filter(s=>s.trim()).length} / {sections.length} sections written. Financial forecasts and defensive recommendations require validation.</small>
    {proposal&&<article className="node-callout"><h3>Draft for review</h3><pre>{proposal}</pre><button onClick={()=>{setDraft({...draft,sections:{...draft.sections,[section]:proposal}});setProposal("");}}>Use draft in editor</button></article>}</div></div></section>;
}

export function WarRoomCameras() {
  const cams=useLabRecords("cameras"),[draft,setDraft]=useState<Row>({title:"",url:"",location:""});
  return <section className="node-workspace"><span className="node-eyebrow">WAR ROOM · CAMERAS</span><h2>Camera registry</h2><p>Register the security camera viewer addresses you choose. Open a viewer explicitly; ZAE does not scan your network.</p><div className="node-callout">Viewer links only in this release. Live RTSP/ONVIF video, recording, detection and camera authentication need a device-specific integration. No camera is marked connected or monitored here.</div>{cams.error&&<p role="alert">{cams.error}</p>}
    <div className="zx-card node-editor"><label>Camera name<input aria-label="Camera name" value={draft.title} maxLength={160} onChange={e=>setDraft({...draft,title:e.target.value})}/></label><label>Camera location<input aria-label="Camera location" value={draft.location} maxLength={200} onChange={e=>setDraft({...draft,location:e.target.value})}/></label><label>Camera viewer URL<input aria-label="Camera viewer URL" type="url" placeholder="https://camera.example/view" value={draft.url} maxLength={1000} onChange={e=>setDraft({...draft,url:e.target.value})}/></label><small>Use a viewer address without passwords or query tokens. Keep credentials in the Vault.</small><button disabled={!LIVE_API||cams.busy||!draft.title||!draft.url} onClick={()=>void cams.save(draft).then(row=>{if(row)setDraft({title:"",url:"",location:""});})}>Save camera</button></div>
    <div className="node-metrics">{cams.items.map(row=><article className="zx-card" key={row.id}><h3>{row.title}</h3><p>{row.location}</p><p>Registered · connection not tested</p><a href={row.url} target="_blank" rel="noreferrer noopener">Open camera viewer</a><button disabled={cams.busy} onClick={()=>void cams.remove(row)}>Remove camera</button></article>)}</div></section>;
}
