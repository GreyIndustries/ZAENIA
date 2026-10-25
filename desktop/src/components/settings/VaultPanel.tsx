import { useCallback, useEffect, useState } from "react";
import { api, errorText, IN_TAURI } from "../../core/bridge";
import { Locked, securitySession, setSecuritySession } from "../security/SecurityPanel";
import "../research/Research.css";

type Item = { id: string; title: string; created: string; size: number; kind: "note" | "file"; name: string };
type Full = Item & { text: string; data: string; mime: string };

/** The Vault: passkey-locked documents and notes (same unlock as the Security tab). */
export function VaultPanel() {
  const [session, setSession] = useState<string | null>(securitySession());
  const [items, setItems] = useState<Item[]>([]);
  const [open, setOpen] = useState<Full | null>(null);
  const [draft, setDraft] = useState<{ title: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const call = useCallback(async <T,>(path: string, body: object = {}) => {
    const current = securitySession();
    if (!current) throw new Error("locked");
    return api<T>("POST", path, { session: current, ...body }, { desktop: true, timeoutMs: 120_000 });
  }, []);
  const load = useCallback(async () => {
    try { setItems((await call<{ items: Item[] }>("/api/vault/list")).items); setError(null); }
    catch (failure) {
      const text = errorText(failure);
      if (/locked|401/i.test(text)) { setSecuritySession(null); setSession(null); } else setError(text);
    }
  }, [call]);
  useEffect(() => { if (session) void load(); }, [session, load]);

  if (!IN_TAURI) return <p className="research__note">The Vault opens only in the ZÆNIA desktop app on your PC.</p>;
  if (!session) return <div className="research">
    <p className="research__note">Private documents, notes and saved research, encrypted on this PC. Unlock with your passkey or your spoken phrase plus your voice.</p>
    <Locked onUnlocked={next => { setSecuritySession(next); setSession(next); }}/>
  </div>;

  const saveNote = async () => {
    if (!draft?.title.trim()) return;
    try { await call("/api/vault/save", { title: draft.title, text: draft.text }); setDraft(null); await load(); }
    catch (failure) { setError(errorText(failure)); }
  };
  const addFile = async (file: File) => {
    if (file.size > 15 * 2 ** 20) { setError("Files can be up to 15 MB."); return; }
    const data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
    try { await call("/api/vault/save", { title: file.name, name: file.name, data, mime: file.type }); await load(); }
    catch (failure) { setError(errorText(failure)); }
  };
  const show = async (id: string) => {
    try { setOpen(await call<Full>("/api/vault/item", { id })); } catch (failure) { setError(errorText(failure)); }
  };
  const remove = async (id: string) => {
    if (confirm !== id) { setConfirm(id); return; }
    setConfirm(null);
    try { await call("/api/vault/delete", { id }); if (open?.id === id) setOpen(null); await load(); } catch (failure) { setError(errorText(failure)); }
  };
  const download = (item: Full) => {
    const link = document.createElement("a");
    link.href = `data:${item.mime || "application/octet-stream"};base64,${item.data}`;
    link.download = item.name || item.title;
    link.click();
  };
  return <div className="research">
    <p className="research__note">Unlocked · encrypted on this PC with a key only your Windows account can open. It locks with the Security tab after 10 minutes without activity.</p>
    {error && <p className="research__error" role="alert">{error}</p>}
    <div className="research__actions">
      <button type="button" className="research__primary" onClick={() => setDraft({ title: "", text: "" })}>New note</button>
      <label className="research__primary" style={{ padding: "7px 12px", borderRadius: 8, cursor: "pointer", fontSize: 12 }}>Add a file
        <input type="file" hidden onChange={event => { const file = event.target.files?.[0]; if (file) void addFile(file); event.target.value = ""; }}/></label>
      <button type="button" onClick={() => { setSecuritySession(null); setSession(null); }}>Lock</button>
    </div>
    {draft && <div className="research__side">
      <input aria-label="Title" placeholder="Title" value={draft.title} maxLength={200} onChange={event => setDraft({ ...draft, title: event.target.value })}/>
      <textarea aria-label="Note" value={draft.text} onChange={event => setDraft({ ...draft, text: event.target.value })} style={{ minHeight: 160 }}/>
      <div className="research__actions"><button type="button" className="research__primary" onClick={() => void saveNote()}>Save</button><button type="button" onClick={() => setDraft(null)}>Cancel</button></div>
    </div>}
    <div className="research__split">
      <ul className="research__list">{items.map(item => <li key={item.id} className="research__bar">
        <button type="button" aria-pressed={open?.id === item.id} onClick={() => void show(item.id)} style={{ flex: 1 }}>{item.title}
          <small>{item.kind} · {new Date(item.created).toLocaleDateString()} · {Math.max(1, Math.round(item.size / 1024))} KB</small></button>
        <button type="button" className="research__danger" onClick={() => void remove(item.id)}>{confirm === item.id ? "Delete?" : "✕"}</button>
      </li>)}{!items.length && <li className="research__empty">The vault is empty.</li>}</ul>
      {open && <div className="research__side">
        <h3>{open.title}</h3>
        {open.text && <div className="research__result">{open.text.split("\n").map((line, index) => <p key={index}>{line}</p>)}</div>}
        {open.data && (open.mime.startsWith("image/") ? <img src={`data:${open.mime};base64,${open.data}`} alt={open.title} style={{ maxWidth: "100%", borderRadius: 8 }}/> : null)}
        {open.data && <div className="research__actions"><button type="button" onClick={() => download(open)}>Save a copy</button></div>}
      </div>}
    </div>
  </div>;
}
