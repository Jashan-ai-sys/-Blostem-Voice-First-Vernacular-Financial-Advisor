// Per-browser session identity + a fetch wrapper that scopes every backend
// call to this session. This is what makes the backend multi-user safe: the
// server keys all state by the X-Session-Id header we send here.

export const BACKEND =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Root of the voice agent (its /api/offer WebRTC endpoint lives here).
export const VOICE_BASE =
  process.env.NEXT_PUBLIC_VOICE_URL || "http://localhost:7860";
const VOICE_AGENT_BASE = `${VOICE_BASE}/client/`;

const STORAGE_KEY = "blostem_session_id";

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `sess-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

/** Stable id for this browser tab/session, persisted in localStorage. */
export function getSessionId(): string {
  if (typeof window === "undefined") return "default";
  let id = window.localStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = uuid();
    window.localStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}

/** fetch() against the backend with the session header injected. */
export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("X-Session-Id", getSessionId());
  return fetch(`${BACKEND}${path}`, { ...init, headers });
}

/** Voice iframe URL carrying the session id (best-effort; backend handshake is
 *  the authoritative binding). */
export function voiceAgentUrl(): string {
  const sep = VOICE_AGENT_BASE.includes("?") ? "&" : "?";
  return `${VOICE_AGENT_BASE}${sep}session_id=${encodeURIComponent(getSessionId())}`;
}

/** Tell the backend which session the next voice connection belongs to.
 *  Call this right before mounting the voice iframe. */
export async function registerVoiceSession(): Promise<void> {
  try {
    await apiFetch("/session/voice-pending", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: getSessionId() }),
    });
  } catch {
    /* best-effort */
  }
}
