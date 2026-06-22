"use client";

import { useApp } from "@/lib/store";
import { apiFetch } from "@/lib/session";
import { useState, useEffect } from "react";
import { Shield, ArrowRight, Check, ShieldCheck, Coins, AlertTriangle } from "lucide-react";
import { simulateError, type ErrorRemedy } from "@/lib/errorReporter";
import { sendPageContext } from "@/lib/realtime";

/**
 * FD onboarding journey — modelled on the actual JFS Web SDK Figma stages
 * (see data/figma/screen_graph.json). Each stage maps 1:1 to a graph screen_id,
 * which we POST to /state/screen so the voice assistant knows EXACTLY which
 * screen the user is on (and what comes next).
 */

interface Stage {
  id: string;            // graph screen_id (matches screen_graph.json)
  step: number;          // backend step_map fallback
  short: string;         // stepper label
}

const STAGES: Stage[] = [
  { id: "gold_landing",          step: 4, short: "Offer" },
  { id: "tenure_selection",      step: 4, short: "Amount" },
  { id: "pan_verification",      step: 2, short: "PAN" },
  { id: "personal_details",      step: 2, short: "Details" },
  { id: "bank_fd_review",        step: 7, short: "Review" },
  { id: "fd_review_before_vkyc", step: 2, short: "VKYC" },
  { id: "payment_screen",        step: 8, short: "Payment" },
  { id: "fd_summary_active",     step: 9, short: "Active" },
];

// ── Small presentational helpers ────────────────────────────────────────────
function Row({ label, value, strong, field }: { label: string; value: string; strong?: boolean; field?: string }) {
  return (
    <div data-field={field} className="flex justify-between items-center text-sm py-1.5">
      <span className="text-muted">{label}</span>
      <span className={strong ? "font-bold text-primary" : "font-medium text-foreground"}>{value}</span>
    </div>
  );
}
function Field({ label, value, hint, field }: { label: string; value: string; hint?: string; field?: string }) {
  return (
    <div data-field={field} className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-muted">{label}</label>
      <div className="bg-surface rounded-xl border border-border px-4 py-3 text-sm text-foreground">{value}</div>
      {hint && <span className="text-[11px] text-muted">{hint}</span>}
    </div>
  );
}

export default function LandingPage() {
  const { setPage, setScreenId } = useApp();
  const [i, setI] = useState(0);
  const [simErr, setSimErr] = useState<ErrorRemedy | null>(null);
  const stage = STAGES[i];

  // Sync the EXACT Figma screen to the voice backend on every stage change,
  // and clear any simulated error (it's stale once you navigate).
  useEffect(() => {
    setScreenId(stage.id);
    setSimErr(null);
    // Push structured page context over the realtime channel (page-aware copilot)…
    sendPageContext({
      route: `/journey/${stage.id}`,
      title: stage.short,
      screen_id: stage.id,
      journey: "fd_onboarding",
      step_id: stage.id,
      primary_cta_enabled: true,
    });
    // …and keep the HTTP screen sync as a fallback for when the WS is down.
    apiFetch("/state/screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "journey", step: stage.step, screen_id: stage.id }),
    }).catch((e) => console.error("[Blostem] screen sync failed:", e));
  }, [stage.id, stage.step, setScreenId]);

  const next = () => (i < STAGES.length - 1 ? setI(i + 1) : setPage("chat"));
  const back = () => i > 0 && setI(i - 1);

  return (
    <div className="flex-1 flex flex-col items-center pb-16 pt-6">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[420px] rounded-full bg-primary/5 blur-[120px] pointer-events-none" />

      {/* Brand row */}
      <div className="relative w-full max-w-md px-5 flex items-center justify-between mb-4">
        <span className="text-base font-bold tracking-tight">SaveSmart</span>
        <span className="text-xs text-muted flex items-center gap-1">
          <Shield className="w-3.5 h-3.5 text-primary" /> Powered by Blostem
        </span>
      </div>

      {/* Stepper */}
      <div className="relative w-full max-w-md px-5 mb-4">
        <div className="flex items-center justify-between">
          {STAGES.map((s, idx) => (
            <div key={s.id} className="flex flex-col items-center gap-1 flex-1">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all
                  ${idx === i ? "bg-primary text-background" : idx < i ? "bg-primary/30 text-primary" : "bg-surface-2 text-muted border border-border"}`}
              >
                {idx < i ? <Check className="w-3 h-3" /> : idx + 1}
              </div>
              <span className={`text-[9px] ${idx === i ? "text-primary font-semibold" : "text-muted"}`}>{s.short}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Mobile-frame card */}
      <div className="relative w-full max-w-md px-5">
        <div className="glass-card border border-primary/20 rounded-3xl overflow-hidden shadow-[0_0_40px_rgba(16,185,129,0.06)]">
          {/* Phone status strip */}
          <div className="bg-surface-2/60 px-5 py-2 flex items-center justify-between text-[11px] text-muted border-b border-border/60">
            <span>Shivalik Small Finance Bank</span>
            <span className="flex items-center gap-1 text-primary"><ShieldCheck className="w-3 h-3" /> Secure</span>
          </div>

          <div className="p-5 min-h-[440px] flex flex-col">
            <div className="flex-1 animate-in fade-in zoom-in-95 duration-300">
              {renderStage(stage.id)}
            </div>

            {/* Actions */}
            <div className="mt-6 flex items-center gap-3">
              {i > 0 && (
                <button onClick={back} className="px-5 py-3 rounded-xl border border-border text-muted font-medium hover:text-foreground hover:bg-surface transition-colors">
                  Back
                </button>
              )}
              <button onClick={next} className="flex-1 px-6 py-3 rounded-xl bg-primary text-background font-bold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity">
                {ctaLabel(stage.id)} <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            {/* Demo: trigger a screen-appropriate error → backend classifies it
                → we show the actionable remedy (and the voice bot also reacts). */}
            {simErr ? (
              <div className="mt-3 rounded-xl border border-danger/40 bg-danger/5 p-3 text-left animate-in fade-in">
                <div className="flex items-center gap-1.5 text-danger text-xs font-semibold">
                  <AlertTriangle className="w-3.5 h-3.5" /> {simErr.title}
                </div>
                <p className="text-[12px] text-foreground mt-1">{simErr.user_message}</p>
                <p className="text-[12px] text-primary mt-1">→ {simErr.suggested_action}</p>
                <button onClick={() => setSimErr(null)} className="mt-2 text-[11px] text-muted hover:text-foreground">Dismiss</button>
              </div>
            ) : (
              <button
                onClick={async () => setSimErr(await simulateError(stage.id))}
                className="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-muted hover:text-danger transition-colors"
              >
                <AlertTriangle className="w-3 h-3" /> Simulate an error (demo)
              </button>
            )}
          </div>
        </div>
        <p className="text-center text-[11px] text-muted mt-3">
          Tap the <span className="text-primary font-medium">Need help?</span> button anytime — the assistant knows this screen.
        </p>
      </div>
    </div>
  );
}

function ctaLabel(id: string): string {
  switch (id) {
    case "gold_landing": return "Book FD now";
    case "bank_fd_review": return "Invest ₹50,000";
    case "fd_review_before_vkyc": return "Proceed to Video KYC";
    case "payment_screen": return "Go to my transactions";
    case "fd_summary_active": return "Ask the advisor";
    default: return "Proceed";
  }
}

// ── Stage content (real values from the Figma screen graph) ──────────────────
function renderStage(id: string) {
  switch (id) {
    case "gold_landing":
      return (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-primary"><Coins className="w-5 h-5" /><span className="text-xs font-semibold uppercase tracking-wide">Goldback Offer</span></div>
          <h2 className="text-2xl font-extrabold leading-tight">More Savings.<br />More Gold.</h2>
          <p className="text-sm text-muted">Book an FD and get <strong className="text-foreground">1% Gold back up to ₹125</strong> on Gold purchases. Valid for 30 days after FD booking.</p>
          <div className="grid grid-cols-2 gap-3 mt-1">
            <div className="bg-surface rounded-xl border border-border p-3"><div className="text-[11px] text-muted">Minimum FD</div><div className="font-bold">₹50,000</div></div>
            <div className="bg-surface rounded-xl border border-border p-3"><div className="text-[11px] text-muted">Reward</div><div className="font-bold text-primary">Max ₹125</div></div>
            <div className="bg-surface rounded-xl border border-border p-3"><div className="text-[11px] text-muted">Tenure</div><div className="font-bold">&gt; 7 days</div></div>
            <div className="bg-surface rounded-xl border border-border p-3"><div className="text-[11px] text-muted">Coupon Validity</div><div className="font-bold">30 days</div></div>
          </div>
        </div>
      );

    case "tenure_selection":
      return (
        <div className="flex flex-col gap-4">
          <h2 className="text-xl font-bold">Choose Amount & Tenure</h2>
          <Field label="Investment Amount" value="₹50,000" hint="Start investing from ₹1,000" field="amount" />
          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-muted">Tenure</label>
            <div className="flex flex-wrap gap-2">
              <button className="px-3 py-2 rounded-lg border border-border bg-surface text-xs">1Y · 8.7%</button>
              <button className="px-3 py-2 rounded-lg border border-border bg-surface text-xs">3Y · 8.9%</button>
              <button className="px-3 py-2 rounded-lg border-2 border-primary bg-primary/10 text-primary text-xs font-semibold">5Y · 9.10% p.a.</button>
            </div>
          </div>
          <div className="flex gap-2 text-[11px]">
            <span className="px-2 py-1 rounded-full bg-surface-2 border border-border">Senior +0.5%</span>
            <span className="px-2 py-1 rounded-full bg-surface-2 border border-border">Women +0.2%</span>
            <span className="px-2 py-1 rounded-full bg-surface-2 border border-border">Tax Saver</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-primary mt-1"><ShieldCheck className="w-3.5 h-3.5" /> Up to ₹5,00,000 insured by DICGC</div>
        </div>
      );

    case "pan_verification":
      return (
        <div className="flex flex-col gap-4">
          <h2 className="text-xl font-bold">PAN Verification</h2>
          <p className="text-sm text-muted">We require your PAN to initiate the FD process.</p>
          <Field label="Enter PAN" value="XXXXX1234A" field="pan" />
          <div className="bg-surface rounded-xl border border-border p-4">
            <div className="text-[10px] uppercase tracking-wide text-muted mb-2">Income Tax Department · Govt of India</div>
            <Row label="Name on PAN" value="John Doe" />
            <Row label="DOB" value="01.01.2000" />
            <Row label="PAN Number" value="XXXXX1234A" />
          </div>
          <div className="flex items-center gap-2 text-[11px] text-primary"><ShieldCheck className="w-3.5 h-3.5" /> Your data is 100% safe and secure</div>
        </div>
      );

    case "personal_details":
      return (
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-bold">Personal Details</h2>
          <Field label="Email Address" value="example@gmail.com" field="email" />
          <Field label="Annual Income (In ₹)" value="< 50K" />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Father's Name" value="Raj Saxena" hint="As on PAN" />
            <Field label="Mother's Maiden Name" value="Rajni Saxena" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Education" value="Graduate" />
            <Field label="Occupation" value="Salaried Person" />
          </div>
        </div>
      );

    case "bank_fd_review":
      return (
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-bold">Bank FD Review</h2>
          <div className="bg-surface rounded-xl border border-border p-4">
            <div className="text-[11px] text-muted">Deposit Amount</div>
            <div className="text-2xl font-extrabold">₹50,000</div>
            <div className="text-[11px] text-primary flex items-center gap-1 mt-1"><ShieldCheck className="w-3 h-3" /> Up to ₹5,00,000 insured by DICGC</div>
          </div>
          <div className="bg-surface rounded-xl border border-border p-4">
            <div className="text-xs font-semibold text-muted mb-1">Investment Overview</div>
            <Row label="Tenure" value="1 Year" />
            <Row label="Partner Bank" value="Shivalik SF Bank" />
            <Row label="Interest Rate p.a." value="7.5%" />
            <Row label="Annual Yield" value="8.65%" />
            <Row label="Total Gains" value="₹6,525" />
            <Row label="Maturity Amount" value="₹56,525" strong />
            <Row label="Interest Payout" value="At Maturity" />
            <Row label="Action On Maturity" value="Reinvest" />
          </div>
          <div className="bg-surface rounded-xl border border-border p-4">
            <Row label="Account Details" value="XXXX 1620" />
            <Row label="Nominee" value="Pankaj Pratap Singh" field="nominee" />
          </div>
          <label className="flex items-center gap-2 text-[11px] text-muted"><input type="checkbox" defaultChecked className="accent-primary" /> I agree to the Terms &amp; Conditions</label>
        </div>
      );

    case "fd_review_before_vkyc":
      return (
        <div className="flex flex-col gap-4">
          <h2 className="text-xl font-bold">Review before Video KYC</h2>
          <p className="text-sm text-muted">Kindly note these details for the VKYC verification process.</p>
          <div className="bg-surface rounded-xl border border-border p-4">
            <Row label="Name" value="Yash Saxena" />
            <Row label="Date of Birth" value="25th Dec 1990" />
            <Row label="Income Range" value="1L – 5L" />
            <Row label="Maturity Amount" value="₹56,525" />
          </div>
          <div className="text-xs font-semibold text-muted">Keep the following handy:</div>
          <div className="flex gap-3">
            <div className="flex-1 bg-surface rounded-xl border border-border p-3 text-center"><div className="text-xl">🪪</div><div className="text-[11px] mt-1">PAN Card</div></div>
            <div className="flex-1 bg-surface rounded-xl border border-border p-3 text-center"><div className="text-xl">✍️</div><div className="text-[11px] mt-1">Pen &amp; paper</div></div>
          </div>
        </div>
      );

    case "payment_screen":
      return (
        <div className="flex flex-col gap-4 items-center text-center">
          <div className="w-14 h-14 rounded-full bg-primary/20 text-primary flex items-center justify-center text-2xl mt-2"><Check className="w-7 h-7" /></div>
          <h2 className="text-xl font-bold">Payment Successful!</h2>
          <div className="text-3xl font-extrabold">₹50,000.00</div>
          <div className="w-full bg-surface rounded-xl border border-border p-4 text-left">
            <Row label="Tenure" value="12 Months" />
            <Row label="ROI" value="8.2%" />
            <Row label="Annual Yield" value="8.65%" />
            <Row label="Payment Mode" value="UPI" />
            <Row label="Date" value="1st Jan '27" />
            <Row label="Order ID" value="20190857 189579" />
          </div>
        </div>
      );

    case "fd_summary_active":
      return (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">FD Details</h2>
            <span className="px-2.5 py-1 rounded-full bg-primary/15 text-primary text-[11px] font-semibold">Active</span>
          </div>
          <div className="bg-surface rounded-xl border border-border p-4">
            <div className="flex justify-between items-baseline">
              <div><div className="text-[11px] text-muted">Invested</div><div className="text-xl font-extrabold">₹50,000</div></div>
              <div className="text-right"><div className="text-[11px] text-muted">Interest</div><div className="text-lg font-bold text-primary">8.2% p.a</div></div>
            </div>
          </div>
          <div className="bg-surface rounded-xl border border-border p-4">
            <Row label="Maturity Amount" value="₹59,400" strong />
            <Row label="Gains" value="+₹9,400" />
            <Row label="Maturity Date" value="1st Jan '27" />
            <Row label="Partner Bank" value="Shivalik SF Bank" />
            <Row label="Account Details" value="XXXX 1620" />
            <Row label="Nominee" value="Pankaj Pratap Singh" field="nominee" />
            <Row label="Lock-In Period" value="7 Days" />
          </div>
          <div className="flex gap-2">
            <button className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-xs font-medium">Download Receipt</button>
            <button className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-xs font-medium">Withdraw FD</button>
          </div>
        </div>
      );

    default:
      return <div className="text-muted">Unknown screen.</div>;
  }
}
