// Runtime error capture → reports the error the user is actually seeing to the
// backend, which classifies it into an actionable remedy (see app/error_service.py).
// This is the "track the live error" layer: the identifier (code/status/message)
// is captured here; the remedy is resolved server-side.

import { apiFetch } from "@/lib/session";

export interface ErrorReport {
  code?: string;
  message?: string;
  http_status?: number;
  screen?: string;
  field?: string;
}

/** The classified remedy the backend returns for a reported error. */
export interface ErrorRemedy {
  error_class: string;
  title: string;
  user_message: string;
  suggested_action: string;
}

/** Report a runtime error to the backend; returns the classified remedy (or null). */
export async function reportError(e: ErrorReport): Promise<ErrorRemedy | null> {
  try {
    const r = await apiFetch("/state/error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(e),
    });
    const data = await r.json();
    return (data?.error as ErrorRemedy) ?? null;
  } catch {
    return null; // best-effort: a failed error-report must never break the app
  }
}

/**
 * Production capture hook: wrap fetch so any non-2xx API response is auto-reported
 * (RFC 9457-aware — reads code/message from the error body). Guards against our
 * own /state/* control plane to avoid recursion. Call once at app start.
 */
export function installApiErrorInterceptor(): void {
  if (typeof window === "undefined" || (window as any).__blostemErrHook) return;
  (window as any).__blostemErrHook = true;
  const orig = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const res = await orig(input, init);
    try {
      const url = typeof input === "string" ? input : input.toString();
      // never report on our own control endpoints (prevents loops)
      if (!res.ok && !url.includes("/state/")) {
        const body: any = await res.clone().json().catch(() => ({}));
        const err = body?.error ?? body;
        void reportError({
          code: err?.code ?? err?.error_code,
          message: err?.detail ?? err?.message ?? res.statusText,
          http_status: res.status,
        });
      }
    } catch {
      /* ignore */
    }
    return res;
  };
}

// ── Demo helper ─────────────────────────────────────────────────────────────
// Maps each Figma stage to a realistic error code so the demo can trigger a
// believable error and watch the assistant explain it + give actionable steps.
const ERROR_BY_SCREEN: Record<string, ErrorReport> = {
  pan_verification: { code: "INVALID_PAN", message: "PAN does not match name on record", http_status: 422 },
  personal_details: { code: "KYC_FAILED", message: "Details could not be verified", http_status: 422 },
  bank_fd_review: { code: "DUPLICATE_NOMINEE", message: "This nominee has already been added", http_status: 409 },
  fd_review_before_vkyc: { code: "AGENT_NOT_AVAILABLE", message: "No VKYC agent available", http_status: 503 },
  payment_screen: { code: "PAYMENT_DECLINED", message: "Your bank declined the payment", http_status: 402 },
  fd_summary_active: { code: "SERVICE_UNAVAILABLE", message: "Our servers are busy", http_status: 503 },
};

/** Trigger a screen-appropriate demo error; returns the classified remedy. */
export async function simulateError(screenId: string): Promise<ErrorRemedy | null> {
  const e = ERROR_BY_SCREEN[screenId] ?? { http_status: 500, message: "Something went wrong" };
  return reportError({ ...e, screen: screenId });
}
