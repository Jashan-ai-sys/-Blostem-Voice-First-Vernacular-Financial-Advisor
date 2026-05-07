"use client";

import { useApp } from "@/lib/store";
import { useState } from "react";
import {
  ArrowLeft,
  Shield,
  CheckCircle2,
  Clock,
  Percent,
  Banknote,
  TrendingUp,
  Calendar,
  ExternalLink,
  MessageCircle,
  Sparkles,
  Lock,
  Info,
} from "lucide-react";

function formatINR(amount: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function BookingPage() {
  const { recommendation, summary, setPage } = useApp();
  const [bookingStep, setBookingStep] = useState<"review" | "confirm" | "success">("review");

  if (!recommendation || !summary) {
    return (
      <div className="flex-1 flex items-center justify-center animate-fade-up">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-2 flex items-center justify-center">
            <Info className="w-7 h-7 text-muted" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No recommendation yet</h2>
          <p className="text-muted text-sm mb-6">
            Upload your transactions first to get a personalized FD recommendation.
          </p>
          <button
            onClick={() => setPage("landing")}
            className="px-6 py-3 rounded-xl bg-primary text-background font-semibold hover:bg-primary-dim transition-colors"
          >
            Go to Home
          </button>
        </div>
      </div>
    );
  }

  const interest = recommendation.primary.interestEarned;

  return (
    <div className="flex-1 animate-fade-up">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button
            onClick={() => setPage("dashboard")}
            className="p-2 rounded-lg hover:bg-surface-2 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-muted" />
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {bookingStep === "success"
                ? "Booking Submitted! 🎉"
                : "Book Fixed Deposit"}
            </h1>
            <p className="text-sm text-muted mt-0.5">
              Powered by Blostem's secure FD infrastructure
            </p>
          </div>
        </div>

        {/* Progress steps */}
        <div className="flex items-center gap-2 mb-8">
          {["Review", "Confirm", "Booked"].map((step, i) => {
            const stepKeys = ["review", "confirm", "success"];
            const currentIdx = stepKeys.indexOf(bookingStep);
            const isActive = i <= currentIdx;
            const isCurrent = i === currentIdx;
            return (
              <div key={step} className="flex items-center gap-2 flex-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                    isActive
                      ? "bg-primary text-background"
                      : "bg-surface-2 text-muted"
                  } ${isCurrent ? "ring-2 ring-primary/30 ring-offset-2 ring-offset-background" : ""}`}
                >
                  {isActive && i < currentIdx ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : (
                    i + 1
                  )}
                </div>
                <span
                  className={`text-sm font-medium ${
                    isActive ? "text-foreground" : "text-muted"
                  }`}
                >
                  {step}
                </span>
                {i < 2 && (
                  <div
                    className={`flex-1 h-0.5 rounded-full ${
                      i < currentIdx ? "bg-primary" : "bg-border"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {bookingStep === "success" ? (
          /* ── Success state ── */
          <div className="text-center py-12">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-success/15 flex items-center justify-center">
              <CheckCircle2 className="w-10 h-10 text-success" />
            </div>
            <h2 className="text-2xl font-bold mb-2">FD Booking Submitted!</h2>
            <p className="text-muted max-w-md mx-auto mb-8">
              This booking would now be executed via Blostem’s FD infrastructure (multi-bank marketplace, KYC, payments, and servicing).
            </p>

            <div className="glass-card p-6 max-w-md mx-auto mb-8 text-left">
              <h3 className="font-semibold mb-4 text-sm uppercase tracking-wide text-primary">
                Booking Summary
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted">Bank</span>
                  <span className="font-medium">{recommendation.primary.issuer}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Amount</span>
                  <span className="font-medium">{formatINR(recommendation.suggestedAmount)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Tenure</span>
                  <span className="font-medium">{recommendation.primary.tenureLabel}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Interest Rate</span>
                  <span className="font-medium">{recommendation.primary.interestRate}% p.a.</span>
                </div>
                <div className="h-px bg-border my-2" />
                <div className="flex justify-between">
                  <span className="text-muted">Maturity Amount</span>
                  <span className="font-bold text-primary">{formatINR(recommendation.primary.maturityAmount)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Interest Earned</span>
                  <span className="font-bold text-success">{formatINR(interest)}</span>
                </div>
              </div>
            </div>

            <div className="flex gap-3 justify-center">
              <button
                onClick={() => setPage("dashboard")}
                className="px-6 py-3 rounded-xl bg-surface border border-border font-medium hover:bg-surface-2 transition-colors text-sm"
              >
                Back to Dashboard
              </button>
              <button
                onClick={() => setPage("chat")}
                className="px-6 py-3 rounded-xl bg-primary text-background font-semibold hover:bg-primary-dim transition-colors text-sm flex items-center gap-2"
              >
                <MessageCircle className="w-4 h-4" />
                Ask AI about this FD
              </button>
            </div>
          </div>
        ) : (
          /* ── Review / Confirm states ── */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main card */}
            <div className="lg:col-span-2 space-y-6">
              {/* FD details card */}
              <div className="glass-card p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Sparkles className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold">{recommendation.primary.issuer}</h2>
                    <p className="text-sm text-muted">Fixed Deposit</p>
                  </div>
                  <div className="ml-auto flex gap-2">
                    {recommendation.primary.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <DetailBox
                    icon={<Banknote className="w-5 h-5" />}
                    label="Investment"
                    value={formatINR(recommendation.suggestedAmount)}
                  />
                  <DetailBox
                    icon={<Percent className="w-5 h-5" />}
                    label="Interest Rate"
                    value={`${recommendation.primary.interestRate}% p.a.`}
                  />
                  <DetailBox
                    icon={<Calendar className="w-5 h-5" />}
                    label="Tenure"
                    value={recommendation.primary.tenureLabel}
                  />
                  <DetailBox
                    icon={<TrendingUp className="w-5 h-5" />}
                    label="Maturity"
                    value={formatINR(recommendation.primary.maturityAmount)}
                    highlight
                  />
                </div>
              </div>

              {/* Why this recommendation */}
              <div className="glass-card p-6">
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <Info className="w-4 h-4 text-primary" />
                  Why this recommendation?
                </h3>
                <div className="text-sm text-muted leading-relaxed">
                  <span className="font-medium text-foreground">{recommendation.reasonHeadline}</span>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {recommendation.reasonDetails.map((detail, idx) => (
                      <li key={idx}>{detail}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Your finances summary */}
              <div className="glass-card p-6">
                <h3 className="font-semibold mb-4">Your Financial Snapshot</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="rounded-xl bg-surface-2/50 p-4 text-center">
                    <div className="text-sm text-muted mb-1">Monthly Income</div>
                    <div className="text-lg font-bold text-success">
                      {formatINR(summary.totalIncome)}
                    </div>
                  </div>
                  <div className="rounded-xl bg-surface-2/50 p-4 text-center">
                    <div className="text-sm text-muted mb-1">Monthly Expenses</div>
                    <div className="text-lg font-bold text-danger">
                      {formatINR(summary.totalExpenses)}
                    </div>
                  </div>
                  <div className="rounded-xl bg-surface-2/50 p-4 text-center">
                    <div className="text-sm text-muted mb-1">Safe to Save</div>
                    <div className="text-lg font-bold text-accent">
                      {formatINR(summary.safeToSave)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Booking summary */}
              <div className="glass-card p-6 glow-primary border-primary/20">
                <h3 className="font-semibold mb-4 text-sm uppercase tracking-wide text-primary">
                  {bookingStep === "review" ? "Booking Summary" : "Confirm Booking"}
                </h3>

                <div className="space-y-3 mb-6 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted">Deposit Amount</span>
                    <span className="font-semibold">{formatINR(recommendation.suggestedAmount)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Interest Rate</span>
                    <span className="font-semibold">{recommendation.primary.interestRate}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Tenure</span>
                    <span className="font-semibold">{recommendation.primary.tenureLabel}</span>
                  </div>
                  <div className="h-px bg-border" />
                  <div className="flex justify-between">
                    <span className="text-muted">Interest Earned</span>
                    <span className="font-bold text-success">{formatINR(interest)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Maturity Amount</span>
                    <span className="font-bold text-primary text-lg">{formatINR(recommendation.primary.maturityAmount)}</span>
                  </div>
                </div>

                {bookingStep === "review" ? (
                  <button
                    onClick={() => setBookingStep("confirm")}
                    className="w-full py-3.5 rounded-xl bg-primary text-background font-semibold hover:bg-primary-dim transition-colors flex items-center justify-center gap-2"
                  >
                    Proceed to Book
                    <ExternalLink className="w-4 h-4" />
                  </button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-accent/5 border border-accent/20 text-xs text-accent">
                      <Shield className="w-4 h-4 shrink-0 mt-0.5" />
                      <span>
                        By clicking confirm, this booking would be executed via Blostem's FD infrastructure (multi-bank marketplace, KYC, payments, and servicing).
                      </span>
                    </div>
                    <button
                      onClick={() => setBookingStep("success")}
                      className="w-full py-3.5 rounded-xl bg-primary text-background font-bold hover:bg-primary-dim transition-colors flex items-center justify-center gap-2"
                    >
                      <Lock className="w-4 h-4" />
                      Confirm & Book FD
                    </button>
                    <button
                      onClick={() => setBookingStep("review")}
                      className="w-full py-2.5 rounded-xl text-sm text-muted hover:text-foreground transition-colors"
                    >
                      Go back
                    </button>
                  </div>
                )}
              </div>

              {/* Trust signals */}
              <div className="glass-card p-5 space-y-3">
                <TrustItem
                  icon={<Shield className="w-4 h-4 text-success" />}
                  text="DICGC insured up to ₹5 lakh"
                />
                <TrustItem
                  icon={<Lock className="w-4 h-4 text-primary" />}
                  text="Secure booking via Blostem"
                />
                <TrustItem
                  icon={<Clock className="w-4 h-4 text-accent" />}
                  text="Early withdrawal available"
                />
                <TrustItem
                  icon={<CheckCircle2 className="w-4 h-4 text-success" />}
                  text="No hidden charges"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailBox({
  icon,
  label,
  value,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl p-4 text-center ${
        highlight
          ? "bg-primary/10 border border-primary/20"
          : "bg-surface-2/50"
      }`}
    >
      <div className={`mx-auto mb-2 ${highlight ? "text-primary" : "text-muted"}`}>
        {icon}
      </div>
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className={`font-bold text-sm ${highlight ? "text-primary" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function TrustItem({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      {icon}
      <span className="text-muted">{text}</span>
    </div>
  );
}
