import { useEffect, useRef, useState } from "react";
import { api, errorText } from "../../core/bridge";

/**
 * One recipe ingredient with search-as-you-type (Open Food Facts products + USDA FoodData Central).
 * Picking a match fills its nutrients per 100 g, scaled to the amount; every value stays editable,
 * and an edited value is kept (marked "edited") until you reset it to the source.
 */
const PATH = "/api/platform/personal";
export const NUTRIENT_KEYS = ["calories", "protein", "carbs", "fat", "saturatedFat", "fiber", "sugars", "sodiumMg", "cholesterolMg"] as const;
export type NutrientKey = typeof NUTRIENT_KEYS[number];
export type Nutrients = Record<NutrientKey, number | null>;
export type Ingredient = { name: string; amount: string | number; unit: string; nutrients: Nutrients; source: string; sourceName?: string;
  per100?: Nutrients | null; grams?: number | null; servingGrams?: number | null; edited?: NutrientKey[] };
type Match = { title: string; dataType: string; servingSize?: string | number | null; servingSizeUnit?: string; nutrients: Nutrients; source: string; sourceName: string };

export const LABELS: Record<NutrientKey, string> = { calories: "kcal", protein: "Protein g", carbs: "Carbs g", fat: "Fat g", saturatedFat: "Sat. fat g",
  fiber: "Fiber g", sugars: "Sugars g", sodiumMg: "Sodium mg", cholesterolMg: "Cholest. mg" };
const UNITS = ["g", "kg", "oz", "lb", "ml", "serving"];
const GRAMS: Record<string, number> = { g: 1, kg: 1000, oz: 28.3495, lb: 453.592, ml: 1 };
export const emptyNutrients = (): Nutrients => Object.fromEntries(NUTRIENT_KEYS.map(k => [k, null])) as Nutrients;

/** Grams for an amount and unit (ml counted as grams; "serving" uses the product's serving size). */
export function gramsFor(amount: string | number, unit: string, servingGrams?: number | null): number | null {
  const value = Number(String(amount).replace(",", "."));
  if (!Number.isFinite(value) || value <= 0) return null;
  if (unit === "serving") return servingGrams ? value * servingGrams : null;
  return GRAMS[unit] ? value * GRAMS[unit] : null;
}
/** Nutrients for `grams` of a food given per 100 g; edited values are kept as typed. */
export function scaled(per100: Nutrients, grams: number | null, current: Nutrients, edited: NutrientKey[] = []): Nutrients {
  return Object.fromEntries(NUTRIENT_KEYS.map(k => [k, edited.includes(k) ? current[k]
    : per100[k] == null || grams == null ? null : Math.round(Number(per100[k]) * grams / 100 * 10) / 10])) as Nutrients;
}
const servingGramsOf = (m: Match): number | null => {
  const text = String(m.servingSize ?? ""); const unit = (m.servingSizeUnit ?? "").toLowerCase();
  const n = parseFloat(text);
  if (!Number.isFinite(n) || n <= 0) return null;
  if (/\b(?:g|gram)/i.test(text) || unit === "g" || unit === "grm") return n;
  if (/\bml\b/i.test(text) || unit === "ml" || unit === "mlt") return n;
  return null;
};

export function IngredientRow({ item, onChange, onRemove }: { item: Ingredient; onChange: (next: Ingredient) => void; onRemove: () => void }) {
  const [matches, setMatches] = useState<Match[]>([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [note, setNote] = useState("");
  const [active, setActive] = useState(-1);
  const typed = useRef(false);
  const edited = item.edited ?? [];

  useEffect(() => {
    const query = String(item.name || "").trim();
    if (!typed.current || query.length < 3) { setMatches([]); return; }
    const timer = window.setTimeout(async () => {
      setSearching(true); setNote("");
      try {
        const reply = await api<{ matches: Match[]; offline: string[] }>("POST", `${PATH}/nutrition/suggest`, { query }, { timeoutMs: 30_000 });
        setMatches(reply.matches); setOpen(true); setActive(-1);
        if (reply.offline.length) setNote(`${reply.offline.join(" and ")} didn't answer; showing what did.`);
        if (!reply.matches.length) setNote("No matches. Type a brand or a simpler name, or enter the label values yourself.");
      } catch (failure) { setNote(errorText(failure)); } finally { setSearching(false); }
    }, 500);
    return () => window.clearTimeout(timer);
  }, [item.name]);

  const pick = (m: Match) => {
    typed.current = false;
    const servingGrams = servingGramsOf(m);
    const unit = item.unit && UNITS.includes(item.unit) ? item.unit : "g";
    const grams = gramsFor(item.amount, unit, servingGrams);
    onChange({ ...item, name: m.title, unit, per100: m.nutrients, servingGrams, grams, edited: [],
      nutrients: scaled(m.nutrients, grams, item.nutrients ?? emptyNutrients()), source: m.source, sourceName: m.sourceName });
    setOpen(false); setMatches([]);
  };
  const setAmount = (amount: string, unit = item.unit) => {
    const grams = gramsFor(amount, unit, item.servingGrams);
    onChange({ ...item, amount, unit, grams, nutrients: item.per100 ? scaled(item.per100, grams, item.nutrients, edited) : item.nutrients });
  };
  const setValue = (k: NutrientKey, raw: string) => {
    const value = raw === "" ? null : Number(raw);
    onChange({ ...item, nutrients: { ...item.nutrients, [k]: value }, edited: item.per100 ? [...new Set([...edited, k])] : edited });
  };
  const resetToSource = () => item.per100 && onChange({ ...item, edited: [], nutrients: scaled(item.per100, item.grams ?? null, item.nutrients) });

  return <article className="nutrition-recipe__ingredient ri">
    <div className="ri__top">
      <label className="ri__name">Ingredient
        <input value={item.name} maxLength={200} role="combobox" aria-expanded={open && matches.length > 0} aria-autocomplete="list" placeholder="Start typing: greek yogurt, oats, Chobani…"
          onChange={e => { typed.current = true; onChange({ ...item, name: e.target.value }); }}
          onFocus={() => matches.length && setOpen(true)} onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={e => {
            if (!open || !matches.length) return;
            if (e.key === "ArrowDown") { e.preventDefault(); setActive(i => Math.min(matches.length - 1, i + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setActive(i => Math.max(0, i - 1)); }
            else if (e.key === "Enter" && active >= 0) { e.preventDefault(); pick(matches[active]); }
            else if (e.key === "Escape") setOpen(false);
          }}/>
        {searching && <small className="ri__hint">Searching…</small>}
        {open && matches.length > 0 && <ul className="ri__list" role="listbox">
          {matches.map((m, i) => <li key={`${m.source}${i}`} role="option" aria-selected={i === active}>
            <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => pick(m)} className={i === active ? "ri__opt ri__opt--on" : "ri__opt"}>
              <span><b>{m.title}</b><small>{m.dataType === "Product" ? "Product · Open Food Facts" : `USDA · ${m.dataType}`}</small></span>
              <small>{m.nutrients.calories ?? "?"} kcal · {m.nutrients.protein ?? "?"} g protein /100 g</small>
            </button></li>)}
        </ul>}
      </label>
      <label>Amount<input inputMode="decimal" value={item.amount} onChange={e => setAmount(e.target.value)}/></label>
      <label>Unit<select value={UNITS.includes(item.unit) ? item.unit : "g"} onChange={e => setAmount(String(item.amount), e.target.value)}>
        {UNITS.map(u => <option key={u} value={u} disabled={u === "serving" && !item.servingGrams}>{u === "serving" && item.servingGrams ? `serving (${item.servingGrams} g)` : u}</option>)}</select></label>
      <button type="button" className="ri__remove" aria-label={`Remove ${item.name || "ingredient"}`} onClick={onRemove}>✕</button>
    </div>
    {note && <small className="ri__hint">{note}</small>}
    {item.per100 && <small className="ri__src">From <a href={item.source} target="_blank" rel="noreferrer">{item.sourceName || "source"}</a>
      {item.grams ? ` · ${Math.round(item.grams)} g` : " · enter the amount in g, oz or lb to scale it"}
      {edited.length > 0 && <> · {edited.length} edited by you <button type="button" className="ri__link" onClick={resetToSource}>Reset to source</button></>}</small>}
    <div className="ri__grid">
      {NUTRIENT_KEYS.map(k => <label key={k} className={edited.includes(k) ? "ri__edited" : undefined}>{LABELS[k]}
        <input type="number" min={0} step="any" value={item.nutrients?.[k] ?? ""} onChange={e => setValue(k, e.target.value)}/></label>)}
    </div>
    {!item.per100 && <label className="ri__srcin">Source<input maxLength={300} value={item.source || ""} placeholder="Label, or pick a search match" onChange={e => onChange({ ...item, source: e.target.value })}/></label>}
  </article>;
}

/** Totals for the whole recipe and one serving; a nutrient is shown only when every ingredient has it. */
export function RecipeTotals({ ingredients, servings }: { ingredients: Ingredient[]; servings: number }) {
  if (!ingredients.length) return null;
  const totals = Object.fromEntries(NUTRIENT_KEYS.map(k => [k, ingredients.every(i => i.nutrients?.[k] != null)
    ? ingredients.reduce((s, i) => s + Number(i.nutrients[k]), 0) : null])) as Nutrients;
  const per = servings > 0 ? servings : 1;
  return <div className="ri__totals" aria-live="polite">
    <strong>Recipe total</strong><strong>Per serving ({per})</strong>
    {NUTRIENT_KEYS.map(k => <div key={k} className="ri__total"><span>{LABELS[k]}</span>
      <b>{totals[k] == null ? "—" : Math.round(totals[k]! * 10) / 10}</b><b>{totals[k] == null ? "—" : Math.round(totals[k]! / per * 10) / 10}</b></div>)}
    <small>“—” means at least one ingredient doesn't have that value yet.</small>
  </div>;
}
