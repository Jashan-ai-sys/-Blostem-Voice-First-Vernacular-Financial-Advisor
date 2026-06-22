"use client";

import { AppProvider, useApp } from "@/lib/store";
import Navbar from "@/components/Navbar";
import LandingPage from "@/components/LandingPage";
import ChatPage from "@/components/ChatPage";
import FloatingVoiceAssistant from "@/components/FloatingVoiceAssistant";
import { useEffect, useState } from "react";
import { apiFetch, registerVoiceSession } from "@/lib/session";
import { connectRealtime } from "@/lib/realtime";

function AppContent() {
  const { currentPage } = useApp();
  const [ragContext, setRagContext] = useState<string | null>(null);
  const [transcripts, setTranscripts] = useState<any[]>([]);

  // Register this session for the voice connection + open the realtime
  // (page-aware) WebSocket channel once on mount.
  useEffect(() => {
    registerVoiceSession();
    connectRealtime();
  }, []);

  // The journey (LandingPage) owns screen sync via screen_id. Here we only flag
  // the advisor/chat mode so the bot knows the user left the journey.
  useEffect(() => {
    if (currentPage !== "chat") return;
    apiFetch(`/state/screen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: "advisor" }),
    }).catch(err => console.error('[Blostem] Screen sync failed:', err));
  }, [currentPage]);

  // Poll backend for RAG context and Transcripts (scoped to this session)
  useEffect(() => {
    const interval = setInterval(() => {
      apiFetch(`/state/get`)
        .then(r => r.json())
        .then(data => {
          if (data.current_rag_text) {
            setRagContext(data.current_rag_text);
          }
          if (data.conversation) {
            setTranscripts(data.conversation);
          }
        })
        .catch(() => {});
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  return (
    // Backdrop — neutral surround so the app reads as a phone on desktop.
    <div className="min-h-screen w-full bg-surface-2 flex items-center justify-center sm:p-6">
      {/* Mobile frame: full-screen on real phones; a centered device frame on
          desktop. `relative` so the floating assistant anchors INSIDE the phone. */}
      <div className="relative bg-background flex flex-col w-full h-screen overflow-hidden sm:w-[420px] sm:h-[880px] sm:max-h-[94vh] sm:rounded-[2.25rem] sm:border sm:border-border sm:shadow-2xl">
      <Navbar />
      <div className="flex flex-1 overflow-hidden relative">
        {/* Main Content Area (FD onboarding journey) — full width; the
            assistant rides along as a floating button, not a sidebar. */}
        {currentPage === "landing" && (
          <div className="flex-1 overflow-y-auto pb-10">
            <LandingPage />
          </div>
        )}

        {/* Full Chat / Voice view (only on the dedicated chat page) */}
        {currentPage === "chat" && (
          <div className="flex-1 bg-background flex flex-col">
            <ChatPage ragContext={ragContext} transcripts={transcripts} isSidebar={false} />
          </div>
        )}

        {/* RAG Context Panel — Right side, only in chat mode */}
        {currentPage === "chat" && (
          <div className="w-[360px] shrink-0 border-l border-border/50 bg-surface/30 backdrop-blur-sm overflow-y-auto flex flex-col">
            <div className="p-5 border-b border-border/50">
              <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase flex items-center gap-2">
                🔍 RAG Context
              </h3>
            </div>
            <div className="p-5 flex-1 overflow-y-auto">
              <div className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap">
                {ragContext ? ragContext : "Navigate screens to see auto-retrieved context."}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Floating voice assistant — tap to talk; morphs into a small voice pill
          in place (no chat UI). Hidden on the full chat page. */}
      {currentPage !== "chat" && <FloatingVoiceAssistant />}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}
