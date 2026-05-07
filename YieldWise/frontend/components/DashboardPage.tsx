"use client";

import { useApp } from "@/lib/store";
import { CATEGORY_CONFIG } from "@/lib/types";
import {
  TrendingUp,
  TrendingDown,
  PiggyBank,
  Target,
  MessageCircle,
  Landmark,
  ArrowRight,
  ChevronRight,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

function formatINR(amount: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

const CHART_COLORS = [
  "#8b5cf6",
  "#f59e0b",
  "#06b6d4",
  "#ec4899",
  "#ef4444",
  "#22c55e",
  "#2dd4a8",
  "#3b82f6",
  "#a855f7",
  "#6b7280",
];

export default function DashboardPage() {
  const { summary, recommendation, transactions, setPage } = useApp();

  if (!summary) return null;

  const pieData = summary.categoryBreakdown.map((c, i) => ({
    name: CATEGORY_CONFIG[c.category].label,
    value: c.amount,
    color: CHART_COLORS[i % CHART_COLORS.length],
    emoji: CATEGORY_CONFIG[c.category].emoji,
  }));

  const barData = summary.monthlyTrend.length > 0
    ? summary.monthlyTrend
    : [{ month: "This month", income: summary.totalIncome, expenses: summary.totalExpenses }];

  return (
    <div className="flex-1 animate-fade-up">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Page header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted text-sm mt-1">
              {transactions.length} transactions analyzed
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setPage("chat")}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-surface border border-border text-sm font-medium hover:border-border-light transition-colors"
            >
              <MessageCircle className="w-4 h-4 text-primary" />
              Ask AI
            </button>
            {recommendation && (
              <button
                onClick={() => setPage("booking")}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-background text-sm font-semibold hover:bg-primary-dim transition-colors"
              >
                <Landmark className="w-4 h-4" />
                View FD Recommendation
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={<TrendingUp className="w-5 h-5" />}
            label="Total Income"
            value={formatINR(summary.totalIncome)}
            color="text-success"
            bgColor="bg-success/10"
          />
          <StatCard
            icon={<TrendingDown className="w-5 h-5" />}
            label="Total Expenses"
            value={formatINR(summary.totalExpenses)}
            color="text-danger"
            bgColor="bg-danger/10"
          />
          <StatCard
            icon={<PiggyBank className="w-5 h-5" />}
            label="Net Savings"
            value={formatINR(summary.netSavings)}
            color="text-primary"
            bgColor="bg-primary/10"
          />
          <StatCard
            icon={<Target className="w-5 h-5" />}
            label="Safe to Save"
            value={formatINR(summary.safeToSave)}
            color="text-accent"
            bgColor="bg-accent/10"
            highlight
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Spending breakdown pie chart */}
          <div className="lg:col-span-1 glass-card p-6">
            <h2 className="font-semibold text-lg mb-1">Spending Breakdown</h2>
            <p className="text-xs text-muted mb-4">Where your money goes</p>

            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="glass-card px-3 py-2 text-sm">
                          <span className="font-medium">{d.emoji} {d.name}</span>
                          <br />
                          <span className="text-muted">{formatINR(d.value)}</span>
                        </div>
                      );
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="space-y-2 mt-2">
              {pieData.slice(0, 5).map((item) => (
                <div key={item.name} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-muted">{item.emoji} {item.name}</span>
                  </div>
                  <span className="font-medium">{formatINR(item.value)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Income vs Expenses bar chart */}
          <div className="lg:col-span-2 glass-card p-6">
            <h2 className="font-semibold text-lg mb-1">Income vs Expenses</h2>
            <p className="text-xs text-muted mb-4">Monthly comparison</p>

            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} barGap={8}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="month" />
                  <YAxis
                    tickFormatter={(v) =>
                      `₹${(v / 1000).toFixed(0)}k`
                    }
                  />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null;
                      return (
                        <div className="glass-card px-4 py-3 text-sm space-y-1">
                          <div className="font-medium mb-1">{label}</div>
                          {payload.map((p) => (
                            <div key={p.dataKey as string} className="flex items-center gap-2">
                              <div
                                className="w-2 h-2 rounded-full"
                                style={{ backgroundColor: p.color }}
                              />
                              <span className="text-muted capitalize">{p.dataKey as string}:</span>
                              <span className="font-medium">{formatINR(p.value as number)}</span>
                            </div>
                          ))}
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="income" fill="#22c55e" radius={[6, 6, 0, 0]} maxBarSize={48} />
                  <Bar dataKey="expenses" fill="#ef4444" radius={[6, 6, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* FD Recommendation card */}
        {recommendation && (
          <div className="glass-card glow-primary p-6 border-primary/30">
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div className="flex-1 min-w-[300px]">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
                    <Sparkles className="w-4 h-4 text-primary" />
                  </div>
                  <span className="text-sm font-semibold text-primary uppercase tracking-wide">
                    AI Recommendation
                  </span>
                </div>

                <h3 className="text-xl font-bold mb-2">
                  Invest {formatINR(recommendation.suggestedAmount)} in a{" "}
                  {recommendation.primary.tenureLabel} FD
                </h3>
                <div className="text-sm text-muted leading-relaxed mb-4 max-w-xl">
                  <span className="font-medium text-foreground">{recommendation.reasonHeadline}</span>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {recommendation.reasonDetails.map((detail, idx) => (
                      <li key={idx}>{detail}</li>
                    ))}
                  </ul>
                </div>

                <div className="flex flex-wrap gap-2 mb-4">
                  {recommendation.primary.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex flex-col items-end gap-3 min-w-[200px]">
                <div className="text-right">
                  <div className="text-sm text-muted">Maturity Amount</div>
                  <div className="text-2xl font-bold text-primary">
                    {formatINR(recommendation.primary.maturityAmount)}
                  </div>
                  <div className="text-xs text-success">
                    +{formatINR(recommendation.primary.interestEarned)} interest
                  </div>
                </div>

                <div className="flex gap-4 text-center">
                  <div>
                    <div className="text-lg font-bold">{recommendation.primary.interestRate}%</div>
                    <div className="text-xs text-muted">Interest Rate</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold">{recommendation.primary.tenureLabel}</div>
                    <div className="text-xs text-muted">Tenure</div>
                  </div>
                </div>

                <button
                  onClick={() => setPage("booking")}
                  className="flex items-center gap-2 mt-2 px-6 py-3 rounded-xl bg-primary text-background font-semibold hover:bg-primary-dim transition-colors"
                >
                  Book this FD
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Recent transactions */}
        <div className="glass-card p-6 mt-6">
          <h2 className="font-semibold text-lg mb-4">Recent Transactions</h2>
          <div className="space-y-1">
            {transactions.slice(0, 15).map((t) => {
              const cat = CATEGORY_CONFIG[t.category];
              const isIncome = t.amount > 0;
              return (
                <div
                  key={t.id}
                  className="flex items-center justify-between py-3 px-3 rounded-lg hover:bg-surface-2/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{cat.emoji}</span>
                    <div>
                      <div className="text-sm font-medium">{t.description}</div>
                      <div className="text-xs text-muted">
                        {new Date(t.date).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                        })}{" "}
                        • {cat.label}
                      </div>
                    </div>
                  </div>
                  <span
                    className={`font-semibold text-sm ${
                      isIncome ? "text-success" : "text-foreground"
                    }`}
                  >
                    {isIncome ? "+" : "-"}{formatINR(Math.abs(t.amount))}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
  bgColor,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
  bgColor: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`glass-card p-5 ${
        highlight ? "border-accent/30 glow-primary" : ""
      }`}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 rounded-xl ${bgColor} flex items-center justify-center ${color}`}>
          {icon}
        </div>
        <span className="text-sm text-muted">{label}</span>
      </div>
      <div className="text-2xl font-bold tracking-tight">{value}</div>
    </div>
  );
}

function Sparkles(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
      <path d="M20 3v4" />
      <path d="M22 5h-4" />
      <path d="M4 17v2" />
      <path d="M5 18H3" />
    </svg>
  );
}
