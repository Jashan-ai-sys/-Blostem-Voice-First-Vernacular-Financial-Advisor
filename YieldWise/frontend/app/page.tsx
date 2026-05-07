"use client";

import { AppProvider, useApp } from "@/lib/store";
import Navbar from "@/components/Navbar";
import LandingPage from "@/components/LandingPage";
import ChatPage from "@/components/ChatPage";
import BookingPage from "@/components/BookingPage";
import { useEffect, useState } from "react";

const BACKEND = 'http://localhost:8000';
const VOICE_AGENT = 'http://localhost:7860/client/';

function AppContent() {
  const { currentPage } = useApp();
  const [ragContext, setRagContext] = useState<string | null>(null);
  const [transcripts, setTranscripts] = useState<any[]>([]);

  // Sync screen state to FastAPI backend
  useEffect(() => {
    fetch(`${BACKEND}/state/screen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'yieldwise', step: currentPage }),
    }).catch(err => console.error('[Blostem] Screen sync failed:', err));
  }, [currentPage]);

  // Poll backend for RAG context and Transcripts
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${BACKEND}/state/get`)
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
    <div className="flex flex-col h-screen overflow-hidden">
      <Navbar />
      <div className="flex flex-1 overflow-hidden relative">
        {/* Main Content Area (Journey / Booking) */}
        {currentPage === "landing" && (
          <div className="flex-1 overflow-y-auto pb-10 pr-[480px]">
            <LandingPage />
          </div>
        )}
        {currentPage === "booking" && (
          <div className="flex-1 overflow-y-auto pb-10">
            <BookingPage />
          </div>
        )}

        {/* Chat / Voice Container (Persistent to keep Voice connection alive) */}
        <div 
          className={`
            ${currentPage === "landing" 
                ? "absolute right-0 top-0 bottom-0 w-[480px] bg-card border-l border-border/50 flex flex-col shadow-2xl z-10 transition-all duration-300" 
                : currentPage === "chat"
                  ? "flex-1 bg-background flex flex-col transition-all duration-300"
                  : "hidden"}
          `}
        >
          <ChatPage ragContext={ragContext} transcripts={transcripts} isSidebar={currentPage === "landing"} />
        </div>

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
