"use client";

import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { Transaction, SpendingSummary, FDRecommendation, ChatMessage } from "@/lib/types";
import { SAMPLE_CSV } from "@/lib/sample-data";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AppState {
  // Data
  transactions: Transaction[];
  summary: SpendingSummary | null;
  recommendation: FDRecommendation | null;
  chatMessages: ChatMessage[];
  // Navigation
  currentPage: "landing" | "dashboard" | "chat" | "booking";
  // Actions
  setPage: (page: AppState["currentPage"]) => void;
  loadSampleData: () => void;
  uploadCSV: (csvText: string) => void;
  addTransaction: (t: Omit<Transaction, "id">) => void;
  sendMessage: (content: string) => void;
  clearData: () => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<SpendingSummary | null>(null);
  const [recommendation, setRecommendation] = useState<FDRecommendation | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [currentPage, setCurrentPage] = useState<AppState["currentPage"]>("landing");

  const recalculate = useCallback(async (txns: Transaction[]) => {
    try {
      // 1. Analyze
      const sResp = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transactions: txns }),
      });
      if (!sResp.ok) throw new Error("Analysis failed");
      const s = await sResp.json();
      setSummary(s);

      // 2. Recommend
      const rResp = await fetch(`${API_BASE}/api/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(s),
      });
      if (rResp.ok) {
        const r = await rResp.json();
        setRecommendation(r);
      } else {
        setRecommendation(null);
      }
    } catch (err) {
      console.error(err);
    }
  }, []);

  const setPage = useCallback((page: AppState["currentPage"]) => {
    setCurrentPage(page);
  }, []);

  const uploadCSV = useCallback(
    async (csvText: string) => {
      const blob = new Blob([csvText], { type: "text/csv" });
      const file = new File([blob], "upload.csv", { type: "text/csv" });
      const formData = new FormData();
      formData.append("file", file);

      try {
        const resp = await fetch(`${API_BASE}/api/upload`, {
          method: "POST",
          body: formData,
        });
        if (!resp.ok) throw new Error("Upload failed");
        const parsed = await resp.json();
        if (parsed.length > 0) {
          setTransactions(parsed);
          await recalculate(parsed);
          setCurrentPage("dashboard");
        }
      } catch (err) {
        console.error(err);
      }
    },
    [recalculate]
  );

  const loadSampleData = useCallback(() => {
    uploadCSV(SAMPLE_CSV);
  }, [uploadCSV]);

  const addTransaction = useCallback(
    (t: Omit<Transaction, "id">) => {
      const newTxn = { ...t, id: `manual-${Date.now()}` };
      const updated = [...transactions, newTxn];
      setTransactions(updated);
      recalculate(updated);
    },
    [transactions, recalculate]
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
        timestamp: new Date(),
      };
      setChatMessages((prev) => [...prev, userMsg]);

      try {
        const resp = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: content, summary, recommendation }),
        });
        if (!resp.ok) throw new Error("Chat failed");
        const data = await resp.json();

        const aiMsg: ChatMessage = {
          id: `ai-${Date.now()}`,
          role: "assistant",
          content: data.reply,
          timestamp: new Date(),
        };
        setChatMessages((prev) => [...prev, aiMsg]);
      } catch (err) {
        console.error(err);
      }
    },
    [summary, recommendation]
  );

  const clearData = useCallback(() => {
    setTransactions([]);
    setSummary(null);
    setRecommendation(null);
    setChatMessages([]);
  }, []);

  return (
    <AppContext.Provider
      value={{
        transactions,
        summary,
        recommendation,
        chatMessages,
        currentPage,
        setPage,
        loadSampleData,
        uploadCSV,
        addTransaction,
        sendMessage,
        clearData,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
