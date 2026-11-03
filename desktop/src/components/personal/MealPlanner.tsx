import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { BarcodeScanner } from "./BarcodeScanner";
import { readPhoto } from "../../core/barcode";

const PATH = "/api/platform/personal";
const MEALS = ["Breakfast", "Lunch", "Dinner"] as const;
const NUTRIENTS = ["calories", "protein", "fiber", "carbs", "fat", "saturatedFat", "sugars", "sodiumMg", "cholesterolMg"] as const;
type MealType = typeof MEALS[number];
type Nutrients = Record<string, number | null>;
type Inventory = { id: string; revision: number; title: string; servingsTotal: number; servingsUsed: number; servingLabel: string; servingGrams: number; nutrients: Nutrients; source: string; sourceUrl?: string; barcode?: string; checkedAt?: string };
type Recipe = { id: string; title: string; servings: number; ingredients: any[]; instructions: string; source: string; mealTypes?: MealType[]; category?: string };
type Slot = { id: string; date: string; mealType: MealType; itemType: "inventory" | "recipe"; itemId: string; servings: number; checkInAt: string; status: "scheduled" | "eaten" | "skipped"; loggedFoodId?: string; reminderId?: string };
type Plan = { id: string; revision: number; title: string; archived: boolean; weekStart: string; slots: Slot[] };
type Rows<T> = { items: T[] };
type LocalPhoto = { rootId: string; folder: string; path: string; name: string };
const cleanRecord = <T extends {id?:string;revision?:number;updatedAt?:string;createdAt?:string}>(value:T) => { const {id:_id,revision:_revision,updatedAt:_updated,createdAt:_created,...record}=value; return record; };
const dateText = (day: Date) => `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,"0")}-${String(day.getDate()).padStart(2,"0")}`;
const mondayOf = (value: Date) => { const day = new Date(value); day.setHours(12,0,0,0); day.setDate(day.getDate() - ((day.getDay()+6)%7)); return day; };
const offsetDay = (week: string, n: number) => { const day = new Date(`${week}T12:00:00`); day.setDate(day.getDate()+n); return dateText(day); };
const slotId = () => crypto.randomUUID();

export function MealPlanner() {
  const [weekStart, setWeekStart] = useState(() => dateText(mondayOf(new Date())));
  const [inventory, setInventory] = useState<Inventory[]>([]); const [recipes, setRecipes] = useState<Recipe[]>([]); const [plans, setPlans] = useState<Plan[]>([]); const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState(""); const [note, setNote] = useState(""); const [busy, setBusy] = useState(false);
  const [scanOpen, setScanOpen] = useState(false); const [barcode, setBarcode] = useState(""); const [found, setFound] = useState<any>(null); const [saveMode, setSaveMode] = useState<"pantry"|"meal">("pantry");
  const [localPhotos, setLocalPhotos] = useState<LocalPhoto[]>([]); const [localPhotoId, setLocalPhotoId] = useState("");
  const [servingGrams, setServingGrams] = useState("100"); const [stockServings, setStockServings] = useState("1"); const [mealDay, setMealDay] = useState(weekStart); const [mealType, setMealType] = useState<MealType>("Breakfast"); const [mealItem, setMealItem] = useState(""); const [mealServings, setMealServings] = useState("1"); const [mealTime, setMealTime] = useState("08:00");
  const load = useCallback(async () => {
    if (!LIVE_API) return;
    const [stock, recipeRows, plans] = await Promise.all([
      api<Rows<Inventory>>("GET", `${PATH}/inventory?archived=false&offset=0`), api<Rows<Recipe>>("GET", `${PATH}/recipes?archived=false&offset=0`), api<Rows<Plan>>("GET", `${PATH}/meal-plans?archived=false&offset=0`),
    ]);
    setInventory(stock.items); setRecipes(recipeRows.items); setPlans(plans.items);
    setPlan(plans.items.find(row => row.weekStart === weekStart) ?? null);
  }, [weekStart]);
  useEffect(() => { void load().catch(failure => setError(errorText(failure))); }, [load]);
  const slots = plan?.slots ?? [];
  const reserved = useMemo(() => { const result: Record<string, number> = {}; for (const week of plans) for (const slot of week.slots ?? []) if (slot.itemType === "inventory" && slot.status === "scheduled") result[slot.itemId] = (result[slot.itemId] ?? 0) + slot.servings; return result; }, [plans]);
  const stockLeft = (item: Inventory) => Math.max(0, item.servingsTotal-item.servingsUsed-(reserved[item.id] ?? 0));
  const itemLabel = (slot: Slot) => slot.itemType === "inventory" ? inventory.find(item => item.id === slot.itemId)?.title ?? "Unavailable food" : recipes.find(item => item.id === slot.itemId)?.title ?? "Unavailable recipe";
  const savePlan = async (next: Slot[]) => {
    const body = { title: `Meals · week of ${weekStart}`, archived: false, weekStart, slots: next };
    const saved = plan ? await api<Plan>("PUT", `${PATH}/meal-plans/${plan.id}`, { record: body, revision: plan.revision }) : await api<Plan>("POST", `${PATH}/meal-plans`, { record: body });
    setPlan(saved); setPlans(current => [...current.filter(item => item.weekStart !== weekStart), saved]); setNote("Meal plan saved.");
  };
  const addSlot = async () => {
    if (!mealItem) return;
    const [itemType, itemId] = mealItem.split(":") as ["inventory"|"recipe", string]; const count = Number(mealServings);
    if (!(count > 0) || (itemType === "inventory" && count > stockLeft(inventory.find(x => x.id === itemId)!))) { setError("That exceeds the unreserved servings. Adjust the amount or release another planned serving."); return; }
    setBusy(true); setError("");
    try {
      const selected = itemType === "inventory" ? inventory.find(item => item.id === itemId) : recipes.find(item => item.id === itemId);
      if (!selected) throw new Error("Choose a food or recipe that is still available.");
      const slot: Slot = { id: slotId(), date: mealDay, mealType, itemType, itemId, servings: count, checkInAt: mealTime, status: "scheduled" };
      const due = new Date(`${mealDay}T${mealTime}:00`);
      if (due > new Date()) {
        try { const reminder = await api<{id:string}>("POST", "/api/reminders", { text: `Meal check-in: did you eat ${selected.title} for ${mealType.toLowerCase()}? Open Fitness & Health → Weekly meal planner to confirm or skip.`, due: due.toISOString(), channels: ["screen", "speak"], repeat: "none" }); slot.reminderId = reminder.id; }
        catch { setNote("Meal saved. The in-app check-in is ready; a scheduled reminder could not be added."); }
      }
      try { await savePlan([...slots, slot]); } catch (failure) { if (slot.reminderId) await api("DELETE", `/api/reminders/${slot.reminderId}`).catch(()=>undefined); throw failure; }
      setMealServings("1");
    } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  };
  const removeSlot = async (slot: Slot) => { setBusy(true); setError(""); try { if (slot.reminderId) await api("DELETE", `/api/reminders/${slot.reminderId}`); await savePlan(slots.filter(value=>value.id!==slot.id)); } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); } };
  const transition = async (slot: Slot, status: "eaten"|"skipped") => {
    if (!plan) return; setBusy(true); setError("");
    try {
      const row = slot.itemType === "inventory" ? inventory.find(item => item.id === slot.itemId) : recipes.find(item => item.id === slot.itemId);
      if (!row) throw new Error("That meal item is no longer available.");
      if (status === "eaten") {
        let nutrients: Nutrients; let label: string; let source: string;
        if (slot.itemType === "inventory") { const food = row as Inventory; nutrients = food.nutrients; label = food.servingLabel; source = food.source; }
        else { const recipe = row as Recipe; if (!recipe.ingredients?.length) throw new Error("Add sourced ingredient amounts to this recipe before logging its nutrition."); const math = await api<{perServing: Nutrients}>("POST", `${PATH}/nutrition/recipe-math`, { ingredients: recipe.ingredients, servings: recipe.servings }); nutrients = math.perServing; label = "recipe serving"; source = `Recipe · ${recipe.source}`; }
        if (["calories","protein","fiber"].some(key => nutrients[key] == null)) throw new Error("Calories, protein, and fiber must be known before ZAE can add this meal to the food log.");
        const factor = slot.servings; const checked = Object.fromEntries(Object.entries(nutrients).map(([key,value]) => [key, value == null ? null : Math.round(value*factor*100)/100]));
        const saved = await api<any>("POST", `${PATH}/nutrition/log`, { description: `${slot.mealType}: ${row.title} (${slot.servings} ${label}${slot.servings === 1 ? "" : "s"})`, date: slot.date, items: [{ name: row.title, amount: slot.servings, unit: label, nutrients: checked, source: (row as Inventory).sourceUrl ?? "", sourceName: source, checkedAt: (row as Inventory).checkedAt ?? new Date().toISOString() }] });
        if (slot.itemType === "inventory") { const stock = row as Inventory; await api("PUT", `${PATH}/inventory/${stock.id}`, { revision: stock.revision, record: cleanRecord({ ...stock, servingsUsed: stock.servingsUsed+slot.servings }) }); }
        slot = { ...slot, loggedFoodId: saved.id ?? "" };
      }
      if (slot.reminderId) await api("DELETE", `/api/reminders/${slot.reminderId}`).catch(()=>undefined);
      await savePlan(slots.map(value => value.id === slot.id ? { ...slot, status, reminderId: "" } : value)); await load(); setNote(status === "eaten" ? "Meal confirmed and added to today’s nutrition log." : "Meal skipped. Nutrition was not logged.");
    } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  };
  const useScanned = async () => {
    if (!found) return; setBusy(true); setError("");
    try {
      const count = Number(mealServings); if (saveMode === "meal" && (!(count > 0) || count > Number(stockServings))) throw new Error(`Choose between 0 and ${stockServings} available serving(s) for this meal.`);
      const grams = Number(servingGrams), amount = Number(stockServings); if (!(grams > 0) || !(amount > 0)) throw new Error("Enter a serving weight and a positive number of servings.");
      const per100 = found.nutrients ?? found.values ?? {}; const facts: Nutrients = Object.fromEntries(Object.entries(per100).map(([key,value]) => [key, typeof value === "number" ? (found.fromLabel ? value : Math.round(value*grams/100*100)/100) : null]));
      if (["calories","protein","fiber"].some(key => facts[key] == null)) throw new Error("Confirm calories, protein, and fiber from the package before saving the food.");
      const item = await api<Inventory>("POST", `${PATH}/inventory`, { record: { title: found.productName || found.title || "Scanned food", archived: false, barcode, source: found.sourceName || "Owner-verified package", sourceName: found.sourceName || "", sourceUrl: found.source || "", servingLabel: found.servingSize || `${grams} g`, servingGrams: grams, servingsTotal: amount, servingsUsed: 0, nutrients: facts, checkedAt: new Date().toISOString() } });
      if (saveMode === "meal") { const slot: Slot = { id: slotId(), date: mealDay, mealType, itemType: "inventory", itemId: item.id, servings: count, checkInAt: mealTime, status: "scheduled" }; const due = new Date(`${mealDay}T${mealTime}:00`); if (due > new Date()) { try { const reminder = await api<{id:string}>("POST", "/api/reminders", { text: `Meal check-in: did you eat ${item.title} for ${mealType.toLowerCase()}? Open Fitness & Health → Weekly meal planner to confirm or skip.`, due: due.toISOString(), channels: ["screen", "speak"], repeat: "none" }); slot.reminderId = reminder.id; } catch { setNote("Meal saved. The in-app check-in is ready; a scheduled reminder could not be added."); } } await savePlan([...slots, slot]); }
      await load(); setFound(null); setNote(saveMode === "meal" ? "Scanned food added to the selected meal. It will count as eaten only after check-in." : "Scanned food added to pantry inventory.");
    } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  };
  const lookup = async (code = barcode) => { if (!code.trim()) return; setBusy(true); setError(""); try { const result = await api<any>("POST", `${PATH}/nutrition/barcode`, { barcode: code }); setFound(result); setBarcode(code); setServingGrams(String(Number.parseFloat(String(result.servingSize ?? "").match(/[\d.]+/)?.[0] ?? "100"))); } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); } };
  const photo = async (file?: File) => { if (!file) return; try { const code = await readPhoto(file); if (code) await lookup(code); else if (file.size < 8_000_000) { const data = new Uint8Array(await file.arrayBuffer()); let binary=""; data.forEach(byte => binary += String.fromCharCode(byte)); const result = await api<any>("POST", `${PATH}/nutrition/label`, { data: btoa(binary) }, { timeoutMs: 120000 }); setFound({ ...result, fromLabel: true, sourceName: "Local label photo · owner verified" }); setServingGrams("100"); } else throw new Error("Choose a photo under 8 MB."); } catch (failure) { setError(errorText(failure)); } };
  const loadLocalPhotos = async () => { try { const result = await api<{images:LocalPhoto[]}>("GET", "/api/platform/documents/images"); setLocalPhotos(result.images); if (result.images.length) setLocalPhotoId(`${result.images[0].rootId}:${result.images[0].path}`); } catch (failure) { setError(errorText(failure)); } };
  const readLocalPhoto = async () => { const selected=localPhotos.find(item=>`${item.rootId}:${item.path}`===localPhotoId); if (!selected) return; setBusy(true); setError(""); try { const result=await api<any>("POST", "/api/platform/documents/read-image", {rootId:selected.rootId,path:selected.path}, {desktop:true,timeoutMs:120000}); setFound({...result,fromLabel:true}); setBarcode(""); setServingGrams("100"); setNote("Read the saved photo locally. Verify the nutrition values and serving label before saving."); } catch(failure) { setError(errorText(failure)); } finally { setBusy(false); } };
  const weekDays = Array.from({length:7},(_,i)=>offsetDay(weekStart,i));
  if (!LIVE_API) return <section className="zx-card"><h2>Weekly meal planner</h2><p className="fs-muted">Open ZAE’s desktop or phone app to plan and save meals.</p></section>;
  return <div className="fs-progress">
    <section className="zx-card"><div className="fs-row fs-row--between"><div><h2 className="zx-title">Weekly meal planner</h2><small className="fs-muted">Monday–Sunday · assignments reserve servings · a check-in logs food only when you confirm you ate it.</small></div><div className="fs-row"><button type="button" onClick={() => setWeekStart(offsetDay(dateText(new Date(`${weekStart}T12:00:00`)), -7))}>Previous week</button><b>{new Date(`${weekStart}T12:00:00`).toLocaleDateString([], {month:"short",day:"numeric"})}–{new Date(`${offsetDay(weekStart,6)}T12:00:00`).toLocaleDateString([], {month:"short",day:"numeric",year:"numeric"})}</b><button type="button" onClick={() => setWeekStart(offsetDay(weekStart, 7))}>Next week</button><button type="button" onClick={() => setWeekStart(dateText(mondayOf(new Date())))}>This week</button></div></div></section>
    {(error || note) && <p role={error ? "alert" : "status"} className={error ? "fs-error" : "fs-note"}>{error || note}</p>}
    <section className="zx-card"><h3 className="zx-title">Add food by barcode or label photo</h3><p className="fs-muted">Choose pantry or a selected meal. Package facts are scaled to the serving size you confirm; scans do not count as eaten.</p><div className="fs-row"><input aria-label="Food barcode" placeholder="Type barcode" value={barcode} onChange={event=>setBarcode(event.target.value)}/><button disabled={busy||barcode.length<8} onClick={()=>void lookup()}>Look up</button><button onClick={()=>setScanOpen(true)}>Use camera</button><label>Barcode / nutrition photo<input type="file" accept="image/*" capture="environment" onChange={event=>{void photo(event.target.files?.[0]);event.target.value="";}}/></label></div>
      <div className="fs-row"><button type="button" disabled={busy} onClick={()=>void loadLocalPhotos()}>Load indexed OneDrive photos</button>{localPhotos.length>0&&<><label>Saved photo<select value={localPhotoId} onChange={event=>setLocalPhotoId(event.target.value)}>{localPhotos.map(item=><option key={`${item.rootId}:${item.path}`} value={`${item.rootId}:${item.path}`}>{item.folder} / {item.path}</option>)}</select></label><button type="button" disabled={busy||!localPhotoId} onClick={()=>void readLocalPhoto()}>Read selected photo locally</button></>}</div>
      {scanOpen && <BarcodeScanner onClose={()=>setScanOpen(false)} onCode={code=>{setScanOpen(false);void lookup(code);}} onPhoto={file=>{setScanOpen(false);void photo(file);}}/>}
      {found && <div className="zx-inset"><b>{found.productName||found.title||"Scanned food"}</b><p className="fs-muted">{found.servingSize||found.basis||"Review facts from the package"} · {Object.entries(found.nutrients||found.values||{}).map(([key,value])=>`${key}: ${value ?? "not listed"}`).join(" · ")}</p><details open><summary>Review or correct the scanned nutrition facts</summary><div className="fs-row">{NUTRIENTS.map(key=>{const field=found.nutrients?"nutrients":"values";const facts=found[field]||{};return <label key={key}>{key}<input type="number" min="0" step="any" value={facts[key]??""} onChange={event=>setFound({...found,[field]:{...facts,[key]:event.target.value===""?null:Number(event.target.value)}})}/></label>;})}</div></details><div className="fs-row"><label>Serving label<input value={found.servingSize||""} onChange={event=>setFound({...found,servingSize:event.target.value})}/></label><label>Serving weight (g)<input inputMode="decimal" value={servingGrams} onChange={event=>setServingGrams(event.target.value)}/></label><label>Available servings<input inputMode="decimal" value={stockServings} onChange={event=>setStockServings(event.target.value)}/></label><label>Save to<select value={saveMode} onChange={event=>setSaveMode(event.target.value as "pantry"|"meal")}><option value="pantry">Pantry inventory</option><option value="meal">Selected meal</option></select></label>{saveMode==="meal"&&<><label>Day<select value={mealDay} onChange={event=>setMealDay(event.target.value)}>{weekDays.map(day=><option key={day} value={day}>{new Date(`${day}T12:00:00`).toLocaleDateString([], {weekday:"long",month:"short",day:"numeric"})}</option>)}</select></label><label>Meal<select value={mealType} onChange={event=>setMealType(event.target.value as MealType)}>{MEALS.map(meal=><option key={meal}>{meal}</option>)}</select></label></>}<button disabled={busy} onClick={()=>void useScanned()}>Save scanned food</button></div></div>}</section>
    <section className="zx-card"><h3 className="zx-title">Schedule a meal</h3><div className="fs-row"><label>Day<select value={mealDay} onChange={event=>setMealDay(event.target.value)}>{weekDays.map(day=><option key={day} value={day}>{new Date(`${day}T12:00:00`).toLocaleDateString([], {weekday:"long",month:"short",day:"numeric"})}</option>)}</select></label><label>Meal<select value={mealType} onChange={event=>setMealType(event.target.value as MealType)}>{MEALS.map(meal=><option key={meal}>{meal}</option>)}</select></label><label>Check-in time<input type="time" value={mealTime} onChange={event=>setMealTime(event.target.value)}/></label><label>Food or recipe<select value={mealItem} onChange={event=>setMealItem(event.target.value)}><option value="">Choose…</option><optgroup label="Pantry">{inventory.map(item=><option key={item.id} value={`inventory:${item.id}`} disabled={stockLeft(item)<=0}>{item.title} · {stockLeft(item)} available</option>)}</optgroup><optgroup label="Recipes">{recipes.map(item=><option key={item.id} value={`recipe:${item.id}`}>{item.title}{item.mealTypes?.length?` · ${item.mealTypes.join(", ")}`:""}</option>)}</optgroup></select></label><label>Servings<input inputMode="decimal" value={mealServings} onChange={event=>setMealServings(event.target.value)}/></label><button className="fs-primary" disabled={busy||!mealItem} onClick={()=>void addSlot()}>Add to week</button></div></section>
    {weekDays.map(day=><section className="zx-card" key={day}><h3 className="zx-title">{new Date(`${day}T12:00:00`).toLocaleDateString([], {weekday:"long",month:"short",day:"numeric"})}</h3><div className="fs-kpis fs-kpis--meal">{MEALS.map(meal=><article className="zx-inset" key={meal}><b>{meal}</b>{slots.filter(slot=>slot.date===day&&slot.mealType===meal).map(slot=><div className="fs-meal-slot" key={slot.id}><span>{itemLabel(slot)} · {slot.servings} serving{slot.servings===1?"":"s"} · check-in {slot.checkInAt}</span><small className={slot.status==="eaten"?"fs-note":slot.status==="skipped"?"fs-muted":""}>{slot.status==="eaten"?"Confirmed eaten":slot.status==="skipped"?"Skipped":"Scheduled"}</small>{slot.status==="scheduled"&&<div className="fs-row"><button disabled={busy} onClick={()=>void transition(slot,"eaten")}>I ate this</button><button disabled={busy} onClick={()=>void transition(slot,"skipped")}>Skip</button><button disabled={busy} onClick={()=>void removeSlot(slot)}>Remove</button></div>}</div>)}{!slots.some(slot=>slot.date===day&&slot.mealType===meal)&&<small className="fs-muted">No meal planned</small>}</article>)}</div></section>)}
    <section className="zx-card"><h3 className="zx-title">Pantry · remaining servings</h3>{inventory.map(item=><article className="zx-inset fs-row fs-row--between" key={item.id}><span><b>{item.title}</b><small className="fs-muted"> · {item.servingLabel} · {item.servingsUsed} used · {reserved[item.id]??0} reserved</small></span><b>{stockLeft(item)} remaining</b><button disabled={busy} onClick={()=>{const amount=Number(prompt(`How many ${item.servingLabel} did you use? Remaining now: ${Math.max(0,item.servingsTotal-item.servingsUsed)}`));if(amount>0&&amount<=item.servingsTotal-item.servingsUsed)void api("PUT",`${PATH}/inventory/${item.id}`,{revision:item.revision,record:cleanRecord({...item,servingsUsed:item.servingsUsed+amount})}).then(load).catch(failure=>setError(errorText(failure)));}}>Record servings used</button></article>)}{!inventory.length&&<p className="fs-muted">Scan a food label or barcode to start your pantry.</p>}</section>
  </div>;
}
