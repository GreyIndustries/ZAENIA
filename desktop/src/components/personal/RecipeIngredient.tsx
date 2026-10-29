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
  per100?: Nutrients | null; grams?: number | null; servingGrams?: number | null; servingLabel?: string; edited?: NutrientKey[] };
type Match = { title: string; dataType: string; servingSize?: string | number | null; servingSizeUnit?: string; servingLabel?: string; quantity?: string; nutrients: Nutrients; source: string; sourceName: string };

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
/** The serving weight a source states: 50 with unit "g", "170 g", "1 cup (240 ml)". ml is counted as grams. */
export function servingGramsOf(m: { servingSize?: string | number | null; servingSizeUnit?: string }): number | null {
  const text = String(m.servingSize ?? ""); const unit = (m.servingSizeUnit ?? "").toLowerCase();
  const inText = /(\d+(?:[.,]\d+)?)\s*(?:g|grams?|ml)\b/i.exec(text);
  if (inText) return Number(inText[1].replace(",", "."));
  const n = parseFloat(text);
  return Number.isFinite(n) && n > 0 && ["g", "grm", "ml", "mlt"].includes(unit) ? n : null;
}
/** How a serving reads: "1 large egg (50 g)", or the source's own text. */
export function servingText(label: string | undefined, grams: number | null, raw?: string | number | null): string {
  const g = grams ? `${Math.round(grams * 10) / 10} g` : "";
  if (label) return g ? `${label} (${g})` : label;
  const text = String(raw ?? "").trim();
  return text && !/^\d+(?:\.\d+)?$/.test(text) ? text : g ? `1 serving (${g})` : "";
}

export function IngredientRow({ item, onChange, onRemove }: { item: Ingredient; onChange: (next: Ingredient) => void; onRemove: () => void }) {
  const [matches, setMatches] = useState<Match[]>([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [note, setNote] = useState("");
  const [active, setActive] = useState(-1);
  const typed = useRef(false);
  const [retry, setRetry] = useState(0);
  const edited = item.edited ?? [];

  useEffect(() => {
    const query = String(item.name || "").trim();
    if (!typed.current || query.length < 2) { setMatches([]); return; }
    const timer = window.setTimeout(async () => {
      setSearching(true); setNote("");
      try {
        const reply = await api<{ matches: Match[]; offline: string[]; sources: string[] }>("POST", `${PATH}/nutrition/suggest`, { query }, { timeoutMs: 30_000 });
        setMatches(reply.matches); setOpen(true); setActive(-1);
        setNote(reply.matches.length ? `${reply.matches.length} matches from ${reply.sources.join(", ")}${reply.offline.length ? ` (${reply.offline.join(" and ")} busy right now)` : ""}. Pick one, then check the numbers.`
          : "No matches. Try a simpler name (\"oats\", \"chicken breast\") or a brand, or enter the label values yourself.");
      } catch (failure) { setNote(errorText(failure)); } finally { setSearching(false); }
    }, 450);
    return () => window.clearTimeout(timer);
  }, [item.name, retry]);

  const pick = (m: Match) => {
    typed.current = false;
    const servingGrams = servingGramsOf(m);
    // Work by servings whenever the food has one (1 serving to start); otherwise by weight.
    const unit = servingGrams ? "serving" : item.unit && UNITS.includes(item.unit) && item.unit !== "serving" ? item.unit : "g";
    const amount = servingGrams ? (item.unit === "serving" && Number(item.amount) > 0 ? item.amount : "1") : item.amount;
    const grams = gramsFor(amount, unit, servingGrams);
    onChange({ ...item, name: m.title, unit, amount, per100: m.nutrients, servingGrams, servingLabel: servingText(m.servingLabel, servingGrams, m.servingSize), grams, edited: [],
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
          onFocus={() => matches.length && setOpen(true)}
          onKeyDown={e => {
            if (!open || !matches.length) return;
            if (e.key === "ArrowDown") { e.preventDefault(); setActive(i => Math.min(matches.length - 1, i + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setActive(i => Math.max(0, i - 1)); }
            else if (e.key === "Enter" && active >= 0) { e.preventDefault(); pick(matches[active]); }
            else if (e.key === "Escape") setOpen(false);
          }}/>
        <span className="ri__searchrow">{searching ? <small className="ri__hint">Searching your recipes, common foods, Open Food Facts and USDA…</small> : null}
          <button type="button" className="ri__link" disabled={String(item.name || "").trim().length < 2} onMouseDown={e => e.preventDefault()} onClick={() => { typed.current = true; setRetry(n => n + 1); }}>Search again</button></span>
        {open && matches.length > 0 && <ul className="ri__list" role="listbox">
          {matches.map((m, i) => <li key={`${m.source}${i}`} role="option" aria-selected={i === active}>
            <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => pick(m)} className={i === active ? "ri__opt ri__opt--on" : "ri__opt"}>
              <span><b>{m.title}</b><small>{m.dataType === "Product" ? `${m.quantity ? `${m.quantity} · ` : ""}Open Food Facts label` : m.dataType === "Yours" ? m.sourceName : m.dataType === "Common food" ? "Common food · typical values" : `USDA · ${m.dataType}`}</small></span>
              <small>{(() => { const g = servingGramsOf(m); const per = (v: number | null) => v == null ? "?" : Math.round(v * (g ?? 100) / 10) / 10;
                return g ? `${servingText(m.servingLabel, g, m.servingSize)}: ${per(m.nutrients.calories)} kcal · ${per(m.nutrients.protein)} g protein`
                  : `${per(m.nutrients.calories)} kcal · ${per(m.nutrients.protein)} g protein per 100 g (no serving size listed)`; })()}</small>
            </button></li>)}
        </ul>}
      </label>
      <label>Amount<input inputMode="decimal" value={item.amount} onChange={e => setAmount(e.target.value)}/></label>
      <label>Unit<select value={UNITS.includes(item.unit) ? item.unit : "g"} onChange={e => setAmount(String(item.amount), e.target.value)}>
        {UNITS.map(u => <option key={u} value={u} disabled={u === "serving" && !item.servingGrams}>{u === "serving" && item.servingGrams ? `serving: ${item.servingLabel || `${item.servingGrams} g`}` : u === "serving" ? "serving (pick a food first)" : u}</option>)}</select></label>
      <button type="button" className="ri__remove" aria-label={`Remove ${item.name || "ingredient"}`} onClick={onRemove}>✕</button>
    </div>
    {note && <small className="ri__hint">{note}</small>}
    {item.per100 && <small className="ri__src">From <a href={item.source} target="_blank" rel="noreferrer">{item.sourceName || "source"}</a>
      {item.servingGrams ? ` · 1 serving = ${item.servingLabel || `${item.servingGrams} g`}` : ""}{item.grams ? ` · this amount is ${Math.round(item.grams)} g` : " · enter how much to scale it"}
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
