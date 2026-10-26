import { useCallback, useEffect, useState } from "react";
import { api, errorText, LIVE_API } from "../../core/bridge";
import { deliveryMessage, disablePush, enablePush, localPush, PUSH_CATEGORIES, pushHint } from "../../core/phonePush";
import type { PushCategory, PushDevice, PushPreferences, PushState, PushStatus } from "../../core/phonePush";
import "./PhoneNotifications.css";

const labels: Record<PushCategory, string> = { reminder: "Reminders", calendar: "Calendar events", task: "Task deadlines", training: "Training & health reminders", email: "Important email", research: "Research updates", other: "Other assistant notices" };

/** Shared in Settings, Reminders and Training. Permission is requested only by a tap. */
export function PhoneNotifications() {
  const [status, setStatus] = useState<PushStatus | null>(null);
  const [state, setState] = useState<PushState>("unsupported");
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const load = useCallback(async () => {
    const [server, local] = await Promise.all([api<PushStatus>("GET", "/api/push/status"), localPush()]);
    setStatus(server); setDeviceId(local.id);
    setState(local.state === "on" && !server.devices.some(device => device.id === local.id) ? "unregistered" : local.state);
  }, []);
  useEffect(() => {
    if (!LIVE_API) return;
    let active = true;
    const refresh = () => { if (active) void load().catch(failure => { if (active) setError(errorText(failure)); }); };
    refresh(); window.addEventListener("focus", refresh);
    return () => { active = false; window.removeEventListener("focus", refresh); };
  }, [load]);
  async function run(action: () => Promise<unknown>, message = "") {
    setBusy(true); setError(""); setNote("");
    try { await action(); if (message) setNote(message); await load(); }
    catch (failure) { setError(errorText(failure)); }
    finally { setBusy(false); }
  }
  function save(device: PushDevice, patch: Partial<PushPreferences>) {
    void run(() => api("POST", "/api/push/device", { deviceId: device.id, preferences: { ...device.preferences, ...patch } }), "Notification choices saved.");
  }
  async function test(id: string) {
    await run(async () => {
      const reply = await api<{ sent: number; results: { result: string }[] }>("POST", "/api/push/test", { deviceId: id });
      if (!reply.sent) throw new Error(deliveryMessage(reply.results[0]?.result ?? null));
      setNote("Test accepted by the push service. Check your phone's notifications.");
    });
  }
  return <section className="phone-notifications" aria-label="Phone notifications" aria-busy={busy}>
    <h3>Phone notifications</h3>
    <p>Get reminders and assistant updates on your phone even while ZAE's page is closed. Your PC and ZAE's server must stay on and online.</p>
    <p>Browser push uses Apple, Google, Mozilla or Microsoft's push service. Notification contents are encrypted in transit. Details stay hidden on the lock screen unless you enable previews.</p>
    {error && <p role="alert" className="phone-notifications__error">{error}</p>}
    {note && <p role="status">{note}</p>}
    {!LIVE_API ? <p>Connect to ZAE's server to set up notifications.</p> : <>
      {state === "on" ? <p>This browser is registered with ZAE.</p> : <p>{state === "blocked" ? "Notifications are blocked. Allow them for ZAE in this phone's notification settings, then refresh." : state === "unregistered" ? "This browser has a subscription, but ZAE doesn't have it. Reconnect below." : pushHint() || "Turn on notifications for this browser."}</p>}
      <div className="phone-notifications__actions">
        {(state === "off" || state === "unregistered") && <button type="button" disabled={busy || !status?.transportAvailable} onClick={() => void run(enablePush, "This browser is connected. Send a test to check your phone.")}>{state === "unregistered" ? "Reconnect notifications here" : "Turn on notifications here"}</button>}
        {state === "on" && <button type="button" disabled={busy} onClick={() => void run(disablePush, "Notifications are off for this browser.")}>Turn off on this device</button>}
        <button type="button" disabled={busy} onClick={() => void run(load)}>Refresh status</button>
      </div>
      {status && !status.transportAvailable && <p role="alert">The push package is missing on the PC. Install ZAE's requirements before enabling notifications.</p>}
      {status && !status.workerRunning && <p role="status">Automatic phone delivery is inactive. Restart ZAE's server with its existing authentication to start the delivery worker.</p>}
      {status?.workerError && <p role="status">Phone delivery needs attention ({status.workerError}). The worker will retry.</p>}
      {status?.devices.length === 0 && <p>No browsers connected yet. Enable notifications from your phone.</p>}
      {status?.devices.map(device => <fieldset key={device.id} disabled={busy}>
        <legend>{device.label}{device.id === deviceId ? " · this device" : ""}</legend>
        <div className="phone-notifications__choices">{PUSH_CATEGORIES.map(category => <label key={category}><input type="checkbox" checked={device.preferences.categories.includes(category)} onChange={event => save(device, { categories: event.target.checked ? [...device.preferences.categories, category] : device.preferences.categories.filter(value => value !== category) })}/>{labels[category]}</label>)}</div>
        <label className="phone-notifications__preview"><input type="checkbox" checked={device.preferences.preview} onChange={event => save(device, { preview: event.target.checked })}/>Show titles and message details in notifications</label>
        <p>{deliveryMessage(device.lastResult, device.deliveryState)}{device.lastAcceptedAt ? ` Last accepted: ${new Date(device.lastAcceptedAt).toLocaleString()}.` : ""}</p>
        <button type="button" onClick={() => void test(device.id)}>Send test to {device.label}</button>
      </fieldset>)}
      <p>Uses the quiet hours and pause setting in Assistant → Follow-through. Muted or snoozed notices remain in the inbox. A test sends immediately.</p>
    </>}
  </section>;
}
