// Realtime control channel (event-driven, page-aware copilot).
// Streams structured PageContext + user/voice events to the backend over a
// WebSocket — replacing the 1.5s poll with a push. The backend folds these into
// the session store the voice agent reads, so the bot is situationally aware.

import { BACKEND, getSessionId } from "@/lib/session";

export interface PageContext {
  route?: string;
  title?: string;
  screen_id?: string;
  journey?: string;
  step_id?: string;
  visible_fields?: string[];
  focused_field?: string;
  errors?: { field: string; code: string }[];
  primary_cta_enabled?: boolean;
  page_version: number;
}

let ws: WebSocket | null = null;
let version = 0;
let queue: unknown[] = [];
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function wsUrl(): string {
  const base = BACKEND.replace(/^http/, "ws"); // http→ws, https→wss
  return `${base}/ws/${encodeURIComponent(getSessionId())}`;
}

/** Open the realtime channel (idempotent). Auto-reconnects with backoff. */
export function connectRealtime(): void {
  if (typeof window === "undefined") return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  try {
    ws = new WebSocket(wsUrl());
  } catch {
    return scheduleReconnect();
  }
  ws.onopen = () => {
    queue.forEach((m) => ws?.send(JSON.stringify(m)));
    queue = [];
  };
  ws.onclose = () => scheduleReconnect();
  ws.onerror = () => ws?.close();
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "ui_action" && msg.action) executeUiAction(msg.action);
    } catch {
      /* ignore non-JSON */
    }
  };
}

// ── UI Action executor ───────────────────────────────────────────────────────
// The agent points at the screen: highlight/scroll/focus a field, show a tooltip.
// Fields are resolved by `data-field="<key>"`; unknown action types are dispatched
// as a window event so the app can handle them (open_help, handoff, …).
interface UIAction { type: string; field?: string; message?: string }

function findField(field?: string): HTMLElement | null {
  if (!field || typeof document === "undefined") return null;
  return document.querySelector<HTMLElement>(`[data-field="${field}"]`);
}

function showTooltip(el: HTMLElement, msg: string): void {
  const tip = document.createElement("div");
  tip.className = "agent-tooltip";
  tip.textContent = msg;
  document.body.appendChild(tip);
  const r = el.getBoundingClientRect();
  tip.style.top = `${window.scrollY + r.top - tip.offsetHeight - 8}px`;
  tip.style.left = `${window.scrollX + r.left}px`;
  setTimeout(() => tip.remove(), 5000);
}

export function executeUiAction(action: UIAction): void {
  const el = findField(action.field);
  switch (action.type) {
    case "highlight_field":
    case "scroll_into_view":
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("agent-highlight");
        setTimeout(() => el.classList.remove("agent-highlight"), 4000);
        if (action.message) showTooltip(el, action.message);
      }
      break;
    case "focus_field":
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      (el as HTMLElement | null)?.focus?.();
      break;
    case "show_tooltip":
      if (el && action.message) showTooltip(el, action.message);
      break;
    default:
      if (typeof window !== "undefined")
        window.dispatchEvent(new CustomEvent("agent-ui-action", { detail: action }));
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectRealtime();
  }, 2000);
}

function send(msg: Record<string, unknown>): void {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  else {
    queue.push(msg);
    connectRealtime();
  }
}

/** Push the current page context. Bumps page_version so the backend can drop
 *  out-of-order (stale) SPA updates. */
export function sendPageContext(p: Omit<PageContext, "page_version">): void {
  version += 1;
  send({ type: "page_context_update", page: { ...p, page_version: version } });
}

export function sendVoice(text: string, final: boolean): void {
  send({ type: final ? "voice_final" : "voice_partial", text });
}

export function sendUserEvent(event: Record<string, unknown>): void {
  send({ type: "user_event", event });
}
