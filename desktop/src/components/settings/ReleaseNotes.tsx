export type ReleaseNote = { kind: "added"|"changed"|"fixed"|"removed"|"performance"|"security"|"limitations"; title: string; description: string };
const labels = { added:"Added",changed:"Changed",fixed:"Fixed",removed:"Removed",performance:"Performance",security:"Security & privacy",limitations:"Known limitations" };
export function ReleaseNotes({entries,fallback=[]}:{entries?:ReleaseNote[];fallback?:string[]}) {
  entries = Array.isArray(entries) ? entries.filter(item=>item && item.kind in labels && typeof item.title==="string" && typeof item.description==="string") : [];
  fallback=Array.isArray(fallback)?fallback.filter(text=>typeof text==="string"):[];
  if (!entries.length) return fallback.length ? <div className="zu-release-notes"><small>Earlier release notes</small><ul>{fallback.map((text,i)=><li key={i}>{text}</li>)}</ul></div> : <p className="zu-muted">Detailed notes weren't recorded for this older update.</p>;
  return <div className="zu-release-notes">{(Object.keys(labels) as (keyof typeof labels)[]).map(kind=>{
    const items=entries.filter(item=>item.kind===kind);return items.length ? <section key={kind}><h4>{labels[kind]}</h4><ul>{items.map((item,i)=><li key={i}><strong>{item.title}</strong><p>{item.description}</p></li>)}</ul></section> : null;
  })}</div>;
}
