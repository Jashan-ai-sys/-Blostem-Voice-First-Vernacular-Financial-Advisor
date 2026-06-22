"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { ChatMessage } from "@/lib/types";
import { apiFetch } from "@/lib/session";

interface AppState {
  chatMessages: ChatMessage[];
  currentPage: "landing" | "chat";
  setPage: (page: AppState["currentPage"]) => void;
  sendMessage: (content: string) => void;
  // The Figma stage the user is on (graph screen id), so the floating voice
  // assistant can surface screen-specific quick questions.
  currentScreenId: string | null;
  setScreenId: (id: string | null) => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [currentPage, setCurrentPage] = useState<AppState["currentPage"]>("landing");
  const [currentScreenId, setCurrentScreenId] = useState<string | null>(null);

  const setPage = useCallback((page: AppState["currentPage"]) => {
    setCurrentPage(page);
  }, []);

  const setScreenId = useCallback((id: string | null) => setCurrentScreenId(id), []);

  const sendMessage = useCallback(async (content: string) => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date(),
    };
    setChatMessages((prev) => [...prev, userMsg]);

    try {
      // Session-scoped text chat fallback (RAG-grounded) — see app/main.py /chat
      const resp = await apiFetch(`/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: content, language: "Hinglish" }),
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
  }, []);

  return (
    <AppContext.Provider value={{ chatMessages, currentPage, setPage, sendMessage, currentScreenId, setScreenId }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
