import { useEffect, useRef, useState } from "react";
import { api, errorText, IN_TAURI, LIVE_API, openSecurityTool } from "../../core/bridge";

export const CALM_PASSWORD_STATUS = "/api/calm/password/status";

export function CalmPasswordSettings() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const refresh = async () => {
    if (!LIVE_API) return;
    try { const status = await api<{ configured: boolean }>("GET", CALM_PASSWORD_STATUS); setConfigured(status.configured); setError(""); }
    catch (failure) { setError(errorText(failure)); }
  };
  useEffect(() => {
    void refresh();
    const focus = () => { void refresh(); };
    window.addEventListener("focus", focus);
    return () => window.removeEventListener("focus", focus);
  }, []);
  const setup = async (reset = false) => {
    setError("");
    try {
      await openSecurityTool(reset ? "calm_password_reset" : "calm_password_setup");
      setNote("Use the ZÆNIA Security window on this PC. It checks your owner passkey before creating or changing this password. Refresh here when finished.");
    } catch (failure) { setError(errorText(failure)); }
  };
  return <section className="zx-card" aria-label="Calm view dashboard password">
    <h3 className="zx-title">Calm view password</h3>
    <p>Return to the dashboard with this password when the mic is off. Verified voice wake-up calls still work while listening.</p>
    <p>{configured === null ? "Checking password setup…" : configured ? "Dashboard password is set." : "Dashboard password has not been created. Calm view stays off with the mic off until setup is complete."}</p>
    <p>Choose 12–128 characters in the local Security window. Your existing owner passkey stays separate.</p>
    {IN_TAURI ? <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      <button type="button" onClick={() => void setup()}>{configured ? "Change dashboard password" : "Create dashboard password"}</button>
      {configured && <button type="button" onClick={() => void setup(true)}>Reset in Security window</button>}
      <button type="button" onClick={() => void refresh()}>Refresh status</button>
    </div> : <p>Create or reset this password from ZÆNIA’s desktop app on the PC.</p>}
    {note && <p role="status">{note}</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

export function CalmPasswordUnlock({ onUnlocked }: { onUnlocked: () => void }) {
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const unlock = async () => {
    if (busy || !password) return;
    setBusy(true); setError("");
    try {
      const result = await api<{ unlocked: boolean }>("POST", "/api/calm/password/verify", { password });
      if (!mounted.current) return;
      if (result.unlocked !== true) throw new Error("The dashboard password was not accepted.");
      setPassword(""); onUnlocked();
    } catch (failure) { if (mounted.current) { setPassword(""); setError(errorText(failure)); } }
    finally { if (mounted.current) setBusy(false); }
  };
  if (!IN_TAURI && !window.isSecureContext) return <p>Open the desktop app or ZÆNIA’s secure HTTPS website to enter your dashboard password.</p>;
  return <form className="calm__password" onSubmit={event => { event.preventDefault(); void unlock(); }}>
    <label htmlFor="calm-password">The mic is off or unavailable. Enter your dashboard password.</label>
    <div><input id="calm-password" type="password" autoComplete="current-password" maxLength={256} value={password} disabled={busy}
      onChange={event => { const value = event.target.value; if (Array.from(value).length <= 128) setPassword(value); }} aria-describedby={error ? "calm-password-error" : undefined}/>
      <button type="submit" disabled={busy || !password}>{busy ? "Checking…" : "Return to dashboard"}</button></div>
    {error && <span id="calm-password-error" role="alert">{error}</span>}
    <small>Forgotten password? Reset it through the local Security window with your owner passkey.</small>
    {IN_TAURI && <button type="button" className="calm__password-reset" onClick={() => void openSecurityTool("calm_password_setup").then(() => setError("Use the local Security window to change your password, then enter the new password here."), failure => setError(errorText(failure)))}>Open password recovery</button>}
  </form>;
}
