import { useState } from "react";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export type SetupProfile = { age: number | null; sex: string; heightIn: number | null; weightLb: number | null; bodyFat: number | null; goalWeightLb: number | null;
  rateLbPerWeek: number; activity: string; gymDays: string[]; homeDays: string[]; reminders: { workout: string; weighIn: string; food: string } };

/** ZAE's setup questions as a pop-up: everything she needs for calorie targets, the calendar and reminders. */
export function TrainingSetup({ profile, videoGoal, onSave, onClose }: { profile: SetupProfile; videoGoal?: number | null; onSave: (changes: Partial<SetupProfile>) => Promise<void>; onClose: () => void }) {
  const [p, setP] = useState<SetupProfile>({ ...profile, goalWeightLb: profile.goalWeightLb ?? videoGoal ?? null });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chip = (on: boolean, label: string, click: () => void) => <button type="button" key={label} aria-pressed={on} className={on ? "ts-chip ts-chip--on" : "ts-chip"} onClick={click}>{label}</button>;
  const days = (key: "gymDays" | "homeDays") => WEEKDAYS.map(day => chip(p[key].includes(day), day.slice(0, 3), () => setP({ ...p, [key]: p[key].includes(day) ? p[key].filter(d => d !== day) : [...p[key], day] })));
  const num = (value: string) => value.trim() === "" ? null : Number(value);
  const save = async () => {
    setSaving(true); setError(null);
    try { await onSave({ age: p.age, sex: p.sex, heightIn: p.heightIn, weightLb: p.weightLb, bodyFat: p.bodyFat, goalWeightLb: p.goalWeightLb, rateLbPerWeek: p.rateLbPerWeek, activity: p.activity, gymDays: p.gymDays, homeDays: p.homeDays, reminders: p.reminders }); onClose(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); } finally { setSaving(false); }
  };
  return <div className="ts-backdrop" role="dialog" aria-label="ZAE's questions for your training program" onKeyDown={event => { if (event.key === "Escape") onClose(); }}>
    <div className="ts">
      <header><div><strong>A few questions from ZAE</strong><small>So she can work out your calories, put your workouts on the right days and remind you.</small></div>
        <button type="button" className="ts-close" onClick={onClose} aria-label="Close">✕</button></header>
      <fieldset><legend>How old are you?</legend><input type="number" min={13} max={100} value={p.age ?? ""} onChange={e => setP({ ...p, age: num(e.target.value) })} placeholder="Age"/></fieldset>
      <fieldset><legend>Sex (for the calorie formula)</legend>{chip(p.sex === "male", "Male", () => setP({ ...p, sex: "male" }))}{chip(p.sex === "female", "Female", () => setP({ ...p, sex: "female" }))}</fieldset>
      <fieldset><legend>How tall are you?</legend>
        <input type="number" min={4} max={7} value={p.heightIn ? Math.floor(p.heightIn / 12) : ""} placeholder="ft" onChange={e => setP({ ...p, heightIn: (Number(e.target.value) || 0) * 12 + ((p.heightIn ?? 0) % 12) })}/>
        <input type="number" min={0} max={11} value={p.heightIn ? Math.round(p.heightIn % 12) : ""} placeholder="in" onChange={e => setP({ ...p, heightIn: Math.floor((p.heightIn ?? 0) / 12) * 12 + (Number(e.target.value) || 0) })}/></fieldset>
      <fieldset><legend>Weight and body fat now</legend>
        <input type="number" step="0.1" value={p.weightLb ?? ""} placeholder="lb" onChange={e => setP({ ...p, weightLb: num(e.target.value) })}/>
        <input type="number" step="0.1" value={p.bodyFat ?? ""} placeholder="% body fat" onChange={e => setP({ ...p, bodyFat: num(e.target.value) })}/></fieldset>
      <fieldset><legend>Goal weight{videoGoal ? ` (the video says ${videoGoal} lb)` : ""}</legend>
        <input type="number" step="0.1" value={p.goalWeightLb ?? ""} placeholder="lb" onChange={e => setP({ ...p, goalWeightLb: num(e.target.value) })}/></fieldset>
      <fieldset><legend>How fast?</legend>{[0.5, 1, 1.5, 2].map(rate => chip(p.rateLbPerWeek === rate, `${rate} lb/week`, () => setP({ ...p, rateLbPerWeek: rate })))}</fieldset>
      <fieldset><legend>Outside workouts, your day is mostly…</legend>{[["sitting", "Sitting"], ["light", "On my feet some"], ["active", "Active job"], ["very active", "Very active"]].map(([value, label]) => chip(p.activity === value, label, () => setP({ ...p, activity: value })))}</fieldset>
      <fieldset><legend>Gym days</legend>{days("gymDays")}</fieldset>
      <fieldset><legend>Home / outdoor days</legend>{days("homeDays")}</fieldset>
      <fieldset><legend>Phone reminders (leave blank for none)</legend>
        {([["workout", "Workout"], ["weighIn", "Weigh-in"], ["food", "Log food"]] as const).map(([key, label]) => <label key={key}>{label}<input type="time" value={p.reminders[key]} onChange={e => setP({ ...p, reminders: { ...p.reminders, [key]: e.target.value } })}/></label>)}</fieldset>
      {error && <p className="ts-error" role="alert">{error}</p>}
      <footer><button type="button" onClick={onClose}>Later</button><button type="button" className="ts-save" disabled={saving} onClick={() => void save()}>{saving ? "Saving…" : "Save answers"}</button></footer>
    </div>
  </div>;
}

const REGIONS: Record<string, { front?: string[]; back?: string[] }> = {
  Chest: { front: ["M38 42 Q50 38 49 52 L38 55 Q33 50 38 42Z", "M62 42 Q50 38 51 52 L62 55 Q67 50 62 42Z"] },
  Shoulders: { front: ["M30 40 Q34 34 40 38 L37 48 Q30 47 30 40Z", "M70 40 Q66 34 60 38 L63 48 Q70 47 70 40Z"], back: ["M130 40 Q134 34 140 38 L137 48 Q130 47 130 40Z", "M170 40 Q166 34 160 38 L163 48 Q170 47 170 40Z"] },
  Biceps: { front: ["M29 49 L36 50 L34 64 L28 62Z", "M71 49 L64 50 L66 64 L72 62Z"] },
  Triceps: { back: ["M129 49 L136 50 L134 64 L128 62Z", "M171 49 L164 50 L166 64 L172 62Z"] },
  Core: { front: ["M42 56 L58 56 L57 78 L43 78Z"] },
  "Upper back": { back: ["M140 38 L160 38 L158 52 L142 52Z"] },
  Lats: { back: ["M138 52 L148 54 L147 72 L140 66Z", "M162 52 L152 54 L153 72 L160 66Z"] },
  Quads: { front: ["M40 84 L49 84 L48 112 L41 110Z", "M60 84 L51 84 L52 112 L59 110Z"] },
  Glutes: { back: ["M140 76 L150 76 L150 88 L140 88Z", "M160 76 L150 76 L150 88 L160 88Z"] },
  Hamstrings: { back: ["M140 90 L149 90 L148 112 L141 110Z", "M160 90 L151 90 L152 112 L159 110Z"] },
  Calves: { front: ["M41 118 L47 118 L46 136 L42 136Z", "M59 118 L53 118 L54 136 L58 136Z"], back: ["M141 118 L147 118 L146 136 L142 136Z", "M159 118 L153 118 L154 136 L158 136Z"] },
};

/** A front and back figure; each muscle lights up by how many sets it got this week (10+ is full). */
export function BodyMap({ sets }: { sets: Record<string, number> }) {
  const glow = (muscle: string) => Math.min(1, (sets[muscle] ?? 0) / 10);
  const outline = (x: number) => `M${x + 50} 10 a8 9 0 1 1 0.1 0 M${x + 38} 30 Q${x + 50} 26 ${x + 62} 30 L${x + 72} 44 L${x + 74} 66 L${x + 68} 68 L${x + 64} 50 L${x + 62} 80 L${x + 61} 140 L${x + 52} 140 L${x + 50} 86 L${x + 48} 140 L${x + 39} 140 L${x + 38} 80 L${x + 36} 50 L${x + 32} 68 L${x + 26} 66 L${x + 28} 44Z`;
  return <svg className="tp-bodymap" viewBox="0 0 200 146" role="img" aria-label="Muscles trained this week">
    <path d={outline(0)} className="tp-bodymap__body"/><path d={outline(100)} className="tp-bodymap__body"/>
    {Object.entries(REGIONS).flatMap(([muscle, sides]) => [...(sides.front ?? []), ...(sides.back ?? [])].map((d, i) =>
      <path key={`${muscle}${i}`} d={d} className="tp-bodymap__muscle" style={{ opacity: 0.15 + glow(muscle) * 0.85 }}><title>{`${muscle}: ${sets[muscle] ?? 0} sets`}</title></path>))}
    <text x="50" y="145" className="tp-bodymap__label">FRONT</text><text x="150" y="145" className="tp-bodymap__label">BACK</text>
  </svg>;
}
