export interface Transaction {
  id: string;
  date: string;
  description: string;
  amount: number; // negative = expense, positive = income
  category: Category;
}

export type Category =
  | "income"
  | "rent"
  | "food"
  | "travel"
  | "shopping"
  | "bills"
  | "entertainment"
  | "health"
  | "education"
  | "other";

export const CATEGORY_CONFIG: Record<
  Category,
  { label: string; emoji: string; color: string }
> = {
  income: { label: "Income", emoji: "💰", color: "#22c55e" },
  rent: { label: "Rent & Housing", emoji: "🏠", color: "#8b5cf6" },
  food: { label: "Food & Dining", emoji: "🍕", color: "#f59e0b" },
  travel: { label: "Travel", emoji: "✈️", color: "#06b6d4" },
  shopping: { label: "Shopping", emoji: "🛍️", color: "#ec4899" },
  bills: { label: "Bills & Utilities", emoji: "📱", color: "#ef4444" },
  entertainment: { label: "Entertainment", emoji: "🎬", color: "#a855f7" },
  health: { label: "Health", emoji: "💊", color: "#14b8a6" },
  education: { label: "Education", emoji: "📚", color: "#3b82f6" },
  other: { label: "Other", emoji: "📦", color: "#6b7280" },
};

export interface CategoryBreakdown {
  category: Category;
  label: string;
  emoji: string;
  amount: number;
  percentage: number;
}

export interface MonthlyTrend {
  month: string;
  income: number;
  expenses: number;
}

export interface SpendingSummary {
  totalIncome: number;
  totalExpenses: number;
  netSavings: number;
  safeToSave: number;
  savingsRate: number;
  stabilityScore: "stable" | "moderate" | "volatile";
  categoryBreakdown: CategoryBreakdown[];
  monthlyTrend: MonthlyTrend[];
  insight: string;
}

export interface FDProduct {
  issuer: string;
  type: string;
  interestRate: number;
  minAmount: number;
  tenureMonths: number;
  tenureLabel: string;
  lockInNote: string;
  trustContext: string;
  maturityAmount: number;
  interestEarned: number;
  tags: string[];
}

export interface FDRecommendation {
  primary: FDProduct;
  alternatives: FDProduct[];
  suggestedAmount: number;
  reasonHeadline: string;
  reasonDetails: string[];
  riskLevel: string;
  liquidityNote: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}
