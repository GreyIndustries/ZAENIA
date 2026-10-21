import { useEffect, useState } from "react";
export type PlanStep = { id: string; title: string; milestone: string; status: "pending" | "active" | "completed"; deadline: string | null; dependsOn: string[] };
export type Plan = { title: string; goal: string; steps: PlanStep[] };
export function ProjectPlanEditor({ plan, version, disabled, onSave, label = "Save reviewed plan" }: { plan: Plan; version: string; disabled: boolean; onSave: (plan: Plan) => Promise<void>; label?: string }) {
  const [draft, setDraft] = useState<Plan>(plan);
  useEffect(() => setDraft({ ...plan, steps: plan.steps.map(step => ({ ...step, dependsOn: [...step.dependsOn] })) }), [version]);
  const update = (id: string, fields: Partial<PlanStep>) => setDraft(value => ({ ...value, steps: value.steps.map(step => step.id === id ? { ...step, ...fields } : step) }));
  return <form onSubmit={event => { event.preventDefault(); void onSave(draft); }}>
    <label>Project title<input value={draft.title} onChange={event => setDraft(value => ({ ...value, title: event.target.value }))} required maxLength={200}/></label>
    <label>Goal<textarea value={draft.goal} onChange={event => setDraft(value => ({ ...value, goal: event.target.value }))} maxLength={2000}/></label>
    {draft.steps.map((step, index) => <fieldset key={step.id}><legend>Step {index + 1}</legend>
      <label>Title<input value={step.title} onChange={event => update(step.id, { title: event.target.value })} required maxLength={300}/></label>
      <div className="platform-columns"><label>Milestone<input value={step.milestone} onChange={event => update(step.id, { milestone: event.target.value })} maxLength={120}/></label><label>Deadline<input type="date" value={step.deadline ?? ""} onChange={event => update(step.id, { deadline: event.target.value || null })}/></label></div>
      <label>Status<select value={step.status} onChange={event => update(step.id, { status: event.target.value as PlanStep["status"] })}><option value="pending">Pending</option><option value="active">In progress</option><option value="completed">Completed</option></select></label>
      <details><summary>Prerequisites ({step.dependsOn.length})</summary>{draft.steps.filter(candidate => candidate.id !== step.id).map(candidate => <label className="platform-check" key={candidate.id}><input type="checkbox" checked={step.dependsOn.includes(candidate.id)} onChange={event => update(step.id, { dependsOn: event.target.checked ? [...step.dependsOn, candidate.id] : step.dependsOn.filter(id => id !== candidate.id) })}/>{candidate.title}</label>)}</details>
      <div className="platform-inline"><button type="button" disabled={disabled || index === 0} onClick={() => setDraft(value => { const steps = [...value.steps]; [steps[index - 1], steps[index]] = [steps[index], steps[index - 1]]; return { ...value, steps }; })}>Move earlier</button><button type="button" disabled={disabled || index === draft.steps.length - 1} onClick={() => setDraft(value => { const steps = [...value.steps]; [steps[index], steps[index + 1]] = [steps[index + 1], steps[index]]; return { ...value, steps }; })}>Move later</button></div>
    </fieldset>)}
    <button type="submit" disabled={disabled || !draft.title.trim()}>{label}</button>
  </form>;
}
