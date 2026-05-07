"use client";

import { useApp } from "@/lib/store";
import { useState, useEffect } from "react";
import { Sparkles, TrendingUp, Shield, ArrowRight } from "lucide-react";

const JOURNEY_STEPS = [
  { id: 1, title: 'SIM', icon: '📱' },
  { id: 2, title: 'KYC', icon: '🪪' },
  { id: 3, title: 'Address', icon: '📍' },
  { id: 4, title: 'Amount', icon: '💰' },
  { id: 5, title: 'Bank', icon: '🏦' },
  { id: 6, title: 'Nominee', icon: '👤' },
  { id: 7, title: 'Review', icon: '📋' },
  { id: 8, title: 'Payment', icon: '💳' },
  { id: 9, title: 'Active', icon: '✅' }
];

export default function LandingPage() {
  const { setPage } = useApp();
  const [step, setStep] = useState(1);

  // Sync the exact journey step to the Voice Agent backend
  useEffect(() => {
    const stepName = JOURNEY_STEPS.find(s => s.id === step)?.title || `Step ${step}`;
    fetch('http://localhost:8000/state/screen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'journey', step: `Journey - ${stepName}` }),
    }).catch(err => console.error('[Blostem] Screen sync failed:', err));
  }, [step]);

  const goToNextStep = () => {
    if (step < 9) {
      setStep(step + 1);
    } else {
      setPage("chat");
    }
  };

  return (
    <div className="flex-1 flex flex-col pb-16">
      {/* Background glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] rounded-full bg-primary/5 blur-[120px] pointer-events-none" />
      <div className="absolute top-20 right-1/4 w-[400px] h-[300px] rounded-full bg-accent/5 blur-[100px] pointer-events-none" />

      <div className="relative max-w-6xl mx-auto px-6 pt-10 w-full">
        {/* Nav */}
        <nav className="flex items-center justify-between mb-12">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-primary" />
            </div>
            <span className="text-lg font-bold tracking-tight">SaveSmart</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted">
            <span>Powered by</span>
            <span className="font-semibold text-foreground flex items-center gap-1">
              <Shield className="w-3.5 h-3.5 text-primary" />
              Blostem
            </span>
          </div>
        </nav>

        {/* Main hero */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-surface-2 border border-border text-sm text-muted mb-6">
            <Sparkles className="w-4 h-4 text-primary" />
            <span>AI-powered money guidance</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-[1.08] mb-4">
            Secure your financial future.
            <br />
            <span className="text-primary">Step-by-step.</span>
          </h1>

          <p className="text-base text-muted leading-relaxed max-w-2xl mx-auto">
            Complete your onboarding journey to unlock personalized fixed deposit recommendations and open your account instantly.
          </p>
        </div>

        {/* JOURNEY FLOW */}
        <div className="max-w-3xl mx-auto w-full">
          {/* Stepper Header */}
          <div className="flex justify-between items-center mb-8 relative px-2">
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-border -z-10 transform -translate-y-1/2"></div>
            {JOURNEY_STEPS.map((s) => (
              <div key={s.id} className="flex flex-col items-center gap-2 z-10 bg-background px-1">
                <div 
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all
                    ${step === s.id ? 'bg-primary border-2 border-primary text-background' : 
                      step > s.id ? 'bg-primary border-2 border-primary text-background' : 
                      'bg-surface border-2 border-border text-muted'}
                  `}
                >
                  {step > s.id ? '✓' : s.icon}
                </div>
                <span className={`text-xs ${step === s.id ? 'text-primary font-medium' : 'text-muted'}`}>
                  {s.title}
                </span>
              </div>
            ))}
          </div>

          {/* Step Cards */}
          <div className="glass-card p-8 min-h-[350px] flex flex-col relative border border-primary/20 shadow-[0_0_30px_rgba(16,185,129,0.05)]">
            <div className="inline-block bg-primary/10 text-primary px-3 py-1 rounded-full text-xs font-semibold mb-4 w-max">
              Step {step} of 9
            </div>

            {step === 1 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">Verify Mobile Number</h2>
                <p className="text-muted text-sm mb-4">We need to verify your SIM to ensure bank-grade security.</p>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">Mobile Number</label>
                  <div className="flex bg-surface rounded-xl border border-border overflow-hidden">
                    <span className="px-4 py-3 bg-surface-2 border-r border-border text-muted font-medium">+91</span>
                    <input type="tel" defaultValue="9876543210" disabled className="bg-transparent border-0 px-4 py-3 flex-1 outline-none text-foreground" />
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">KYC Verification</h2>
                <p className="text-muted text-sm mb-4">As per RBI guidelines, we need to verify your identity.</p>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">PAN Number</label>
                  <input type="text" defaultValue="ABCDE1234F" className="bg-surface rounded-xl border border-border px-4 py-3 outline-none text-foreground focus:border-primary" />
                </div>
                <div className="mt-4 p-4 rounded-xl bg-surface-2 border border-border flex items-center gap-4">
                  <div className="text-3xl">📷</div>
                  <div>
                    <h4 className="font-semibold text-sm">Video KYC Required</h4>
                    <p className="text-xs text-muted mt-1">Keep your original PAN card handy.</p>
                  </div>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">Confirm Address</h2>
                <p className="text-muted text-sm mb-4">This address was fetched from your Aadhaar KYC.</p>
                <div className="p-5 rounded-xl bg-surface border border-border flex gap-4">
                  <div className="text-2xl">📍</div>
                  <div>
                    <div className="text-primary font-medium mb-1">Current Address</div>
                    <div className="text-sm">123, Financial District, Tech Park</div>
                    <div className="text-sm text-muted">Hyderabad, Telangana 500032</div>
                  </div>
                </div>
                <label className="flex items-center gap-3 mt-4 text-sm cursor-pointer">
                  <input type="checkbox" defaultChecked className="w-4 h-4 rounded text-primary focus:ring-primary accent-primary" />
                  My communication address is the same as above.
                </label>
              </div>
            )}

            {step === 4 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">Investment Details</h2>
                <p className="text-muted text-sm mb-4">Choose how much and how long you want to invest.</p>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">Investment Amount (₹)</label>
                  <input type="number" defaultValue={50000} className="bg-surface rounded-xl border border-border px-4 py-3 outline-none text-foreground focus:border-primary" />
                </div>
                <div className="flex flex-col gap-2 mt-4">
                  <label className="text-sm font-medium">Tenure</label>
                  <div className="flex flex-wrap gap-2">
                    <button className="px-4 py-2 rounded-lg border border-border bg-surface text-sm">6 Months</button>
                    <button className="px-4 py-2 rounded-lg border border-primary bg-primary/10 text-primary text-sm font-medium">1 Year (8.1%)</button>
                    <button className="px-4 py-2 rounded-lg border border-border bg-surface text-sm">3 Years</button>
                    <button className="px-4 py-2 rounded-lg border border-border bg-surface text-sm">5 Years</button>
                  </div>
                </div>
              </div>
            )}

            {step === 5 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">Link Bank Account</h2>
                <p className="text-muted text-sm mb-4">Your FD maturity amount will be credited here.</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-2 col-span-2">
                    <label className="text-sm font-medium">Bank Name</label>
                    <input type="text" defaultValue="HDFC Bank" className="bg-surface rounded-xl border border-border px-4 py-3 outline-none focus:border-primary" />
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Account Number</label>
                    <input type="password" defaultValue="1234567890" className="bg-surface rounded-xl border border-border px-4 py-3 outline-none focus:border-primary" />
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">IFSC Code</label>
                    <input type="text" defaultValue="HDFC0001234" className="bg-surface rounded-xl border border-border px-4 py-3 outline-none focus:border-primary" />
                  </div>
                </div>
              </div>
            )}

            {step === 6 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">Add Nominee</h2>
                <p className="text-muted text-sm mb-4">Secure your investment by adding a nominee.</p>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">Nominee Full Name</label>
                  <input type="text" placeholder="E.g. Rahul Sharma" className="bg-surface rounded-xl border border-border px-4 py-3 outline-none focus:border-primary" />
                </div>
                <div className="flex flex-col gap-2 mt-4">
                  <label className="text-sm font-medium">Relationship</label>
                  <select className="bg-surface rounded-xl border border-border px-4 py-3 outline-none focus:border-primary appearance-none">
                    <option>Spouse</option>
                    <option>Child</option>
                    <option>Parent</option>
                    <option>Sibling</option>
                  </select>
                </div>
              </div>
            )}

            {step === 7 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">Review FD Details</h2>
                <div className="bg-surface border border-border rounded-xl p-5 mt-2 space-y-4">
                  <div className="flex justify-between text-sm"><span className="text-muted">Amount:</span> <strong className="text-foreground">₹50,000</strong></div>
                  <div className="flex justify-between text-sm"><span className="text-muted">Interest Rate:</span> <strong className="text-foreground">8.1% p.a.</strong></div>
                  <div className="flex justify-between text-sm"><span className="text-muted">Tenure:</span> <strong className="text-foreground">1 Year</strong></div>
                  <hr className="border-border" />
                  <div className="flex justify-between text-base"><span className="text-primary font-medium">Maturity Amount:</span> <strong className="text-primary font-bold">₹54,050</strong></div>
                </div>
              </div>
            )}

            {step === 8 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold">Payment Processing</h2>
                <p className="text-muted text-sm mb-4">Select a method to fund your FD.</p>
                <div className="flex flex-col gap-3">
                  <label className="p-4 rounded-xl border-2 border-primary bg-primary/5 flex items-center gap-4 cursor-pointer">
                    <input type="radio" name="payment" defaultChecked className="accent-primary w-4 h-4" />
                    <div className="font-bold text-primary px-2">UPI</div>
                    <div>
                      <div className="text-sm font-medium">Pay via UPI</div>
                      <div className="text-xs text-muted">GPay, PhonePe, Paytm</div>
                    </div>
                  </label>
                  <label className="p-4 rounded-xl border border-border bg-surface flex items-center gap-4 cursor-pointer hover:border-primary/50 transition-colors">
                    <input type="radio" name="payment" className="accent-primary w-4 h-4" />
                    <div className="text-xl px-2">🏦</div>
                    <div>
                      <div className="text-sm font-medium">Net Banking</div>
                      <div className="text-xs text-muted">Direct bank transfer</div>
                    </div>
                  </label>
                </div>
              </div>
            )}

            {step === 9 && (
              <div className="flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300 items-center justify-center text-center flex-1">
                <div className="w-16 h-16 bg-primary/20 text-primary rounded-full flex items-center justify-center text-3xl mb-4">
                  🎉
                </div>
                <h2 className="text-2xl font-bold">FD Created Successfully!</h2>
                <p className="text-muted text-sm mb-6">Your investment of ₹50,000 is now active.</p>
                
                <div className="grid grid-cols-2 gap-4 w-full text-left">
                  <div className="bg-surface border border-border rounded-xl p-4">
                    <div className="text-xs text-muted mb-1">Total Invested</div>
                    <div className="text-lg font-bold text-foreground">₹50,000</div>
                  </div>
                  <div className="bg-surface border border-border rounded-xl p-4">
                    <div className="text-xs text-muted mb-1">Expected Returns</div>
                    <div className="text-lg font-bold text-primary">+₹4,050</div>
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="mt-auto pt-8 flex justify-between">
              <button 
                onClick={() => setStep(step - 1)}
                className={`px-6 py-3 rounded-xl border border-border text-muted font-medium hover:text-foreground hover:bg-surface transition-colors ${step === 1 ? 'invisible' : ''}`}
              >
                ← Back
              </button>
              
              <button 
                onClick={goToNextStep}
                className="px-8 py-3 rounded-xl bg-primary text-background font-bold flex items-center gap-2 hover:opacity-90 transition-opacity"
              >
                {step === 9 ? 'Ask AI' : 'Next'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
