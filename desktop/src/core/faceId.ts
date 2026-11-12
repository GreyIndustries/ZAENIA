/**
 * Face ID sign-in for the phone web app (2026-11-01): a WebAuthn passkey on the iPhone. Safari asks for Face ID;
 * ZAE's server only sees the signed answer (core/api/face_passkey.py). Adding a key also needs approval on the PC.
 */
import { api } from "./bridge";

const fromB64u = (text: string) => Uint8Array.from(atob(text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4)), c => c.charCodeAt(0));
const toB64u = (buffer: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(buffer))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function auth<T>(path: string, body?: unknown): Promise<T> {
  const reply = await fetch(path, {
    method: body === undefined ? "GET" : "POST", cache: "no-store", credentials: "same-origin",
    headers: { Accept: "application/json", "X-ZAENIA-APP": "1", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await reply.json().catch(() => ({}));
  if (!reply.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Face ID didn't work. Try again.");
  return data as T;
}

/** This phone can do Face ID passkeys at all. */
export async function faceIdSupported(): Promise<boolean> {
  try { return Boolean(window.PublicKeyCredential) && await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable(); }
  catch { return false; }
}

/** An approved Face ID key exists, so the sign-in screen can offer it. */
export async function faceIdReady(): Promise<boolean> {
  if (!(await faceIdSupported())) return false;
  try { return (await auth<{ available: boolean }>("/api/auth/passkey/status")).available; } catch { return false; }
}

type LoginOptions = { challenge: string; rpId: string; timeout: number; allowCredentials: { id: string; transports?: AuthenticatorTransport[] }[] };
export async function signInWithFaceId(): Promise<void> {
  const o = await auth<LoginOptions>("/api/auth/passkey/login/options", {});
  const credential = await navigator.credentials.get({ publicKey: {
    challenge: fromB64u(o.challenge), rpId: o.rpId, timeout: o.timeout, userVerification: "required",
    allowCredentials: o.allowCredentials.map(c => ({ type: "public-key", id: fromB64u(c.id), transports: c.transports })),
  } }) as PublicKeyCredential | null;
  if (!credential) throw new Error("Face ID was cancelled.");
  const r = credential.response as AuthenticatorAssertionResponse;
  await auth("/api/auth/passkey/login", { id: credential.id, clientDataJSON: toB64u(r.clientDataJSON), authenticatorData: toB64u(r.authenticatorData), signature: toB64u(r.signature) });
}

type RegisterOptions = { challenge: string; rp: { id: string; name: string }; user: { id: string; name: string; displayName: string };
  pubKeyCredParams: { type: "public-key"; alg: number }[]; timeout: number; authenticatorSelection: AuthenticatorSelectionCriteria; excludeCredentials: { id: string }[] };
/** On a signed-in phone: make the Face ID key. It works once Grey approves it on the PC. */
export async function addFaceId(): Promise<void> {
  const o = await auth<RegisterOptions>("/api/auth/passkey/register/options", {});
  const credential = await navigator.credentials.create({ publicKey: {
    challenge: fromB64u(o.challenge), rp: o.rp, user: { ...o.user, id: fromB64u(o.user.id) }, pubKeyCredParams: o.pubKeyCredParams,
    timeout: o.timeout, authenticatorSelection: o.authenticatorSelection, attestation: "none",
    excludeCredentials: o.excludeCredentials.map(c => ({ type: "public-key", id: fromB64u(c.id) })),
  } }) as PublicKeyCredential | null;
  if (!credential) throw new Error("Face ID was cancelled.");
  const r = credential.response as AuthenticatorAttestationResponse;
  await auth("/api/auth/passkey/register", { clientDataJSON: toB64u(r.clientDataJSON), attestationObject: toB64u(r.attestationObject), label: "iPhone" });
}

/** On the PC (desktop key): the phone keys, and approving or removing one. */
export type FaceIdKey = { id: string; label: string; approved: boolean; created: number };
export const listFaceIdKeys = () => api<{ keys: FaceIdKey[] }>("GET", "/api/passkeys", undefined, { desktop: true });
export const approveFaceIdKey = (id: string) => api<{ keys: FaceIdKey[] }>("POST", `/api/passkeys/${id}/approve`, undefined, { desktop: true });
export const removeFaceIdKey = (id: string) => api<{ keys: FaceIdKey[] }>("DELETE", `/api/passkeys/${id}`, undefined, { desktop: true });
