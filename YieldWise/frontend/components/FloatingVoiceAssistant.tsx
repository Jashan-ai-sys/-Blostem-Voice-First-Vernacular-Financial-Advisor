"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MessageCircle, Mic, X } from "lucide-react";
import { connectVoice, VoiceConnection, VoiceState } from "@/lib/voiceClient";

/**
 * FloatingVoiceAssistant — VOICE-ONLY.
 * Collapsed it's a small floating button. Tapping it starts a live voice call and
 * the button morphs IN PLACE into a compact voice pill (pulsing mic + animated
 * equalizer). There is NO chat UI, no text input, no panel covering the screen —
 * you only talk. Tap the ✕ to end and it shrinks back to the button.
 */
export default function FloatingVoiceAssistant() {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const audioRef = useRef<HTMLAudioElement>(null);
  const connRef = useRef<VoiceConnection | null>(null);

  const startVoice = useCallback(async () => {
    if (voiceState === "connecting" || voiceState === "live") return;
    try {
      connRef.current = await connectVoice({
        onState: setVoiceState,
        onRemoteStream: (stream) => {
          if (audioRef.current) {
            audioRef.current.srcObject = stream;
            audioRef.current.play().catch(() => {}); // autoplay-policy safety
          }
        },
      });
    } catch {
      /* state already set to error by connectVoice */
    }
  }, [voiceState]);

  const stopVoice = useCallback(() => {
    connRef.current?.disconnect();
    connRef.current = null;
    setVoiceState("idle");
  }, []);

  // Tear down the call if the widget unmounts.
  useEffect(() => () => connRef.current?.disconnect(), []);

  const active = voiceState === "connecting" || voiceState === "live";

  return (
    <div className="absolute bottom-5 right-4 z-50">
      <audio ref={audioRef} autoPlay className="hidden" />
      <AnimatePresence mode="popLayout" initial={false}>
        {!active ? (
          /* ── Collapsed: the floating button ── */
          <motion.button
            key="btn"
            layout
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.85, opacity: 0 }}
            whileTap={{ scale: 0.94 }}
            transition={{ type: "spring", stiffness: 400, damping: 28 }}
            onClick={startVoice}
            aria-label="Talk to the assistant"
            className="flex items-center gap-2 rounded-full bg-primary text-background pl-3.5 pr-4 py-3 shadow-xl shadow-primary/30 hover:bg-primary-dim transition-colors"
          >
            <span className="relative flex">
              <MessageCircle className="w-5 h-5" />
              <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-success animate-pulse" />
            </span>
            <span className="text-sm font-semibold">
              {voiceState === "error" ? "Mic blocked — retry"
                : voiceState === "ended" ? "Talk again"
                : "Need help?"}
            </span>
          </motion.button>
        ) : (
          /* ── Active: a small voice pill that expanded in place ── */
          <motion.div
            key="pill"
            layout
            initial={{ scale: 0.7, opacity: 0, originX: 1, originY: 1 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.7, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 26 }}
            className="flex items-center gap-3 rounded-2xl bg-surface border border-primary/30 shadow-2xl shadow-primary/20 pl-3 pr-2 py-2"
          >
            {voiceState === "connecting" ? (
              <>
                <span className="w-4 h-4 border-2 border-primary/40 border-t-primary rounded-full animate-spin" />
                <span className="text-sm font-medium text-foreground pr-1">Connecting…</span>
              </>
            ) : (
              <>
                {/* pulsing mic */}
                <span className="relative flex items-center justify-center">
                  <motion.span
                    className="absolute w-9 h-9 rounded-full bg-primary/20"
                    animate={{ scale: [1, 1.7], opacity: [0.55, 0] }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
                  />
                  <span className="relative w-8 h-8 rounded-full bg-primary/15 flex items-center justify-center">
                    <Mic className="w-4 h-4 text-primary" />
                  </span>
                </span>
                {/* live equalizer */}
                <div className="flex items-end gap-[3px] h-5">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <motion.span
                      key={i}
                      className="w-[3px] rounded-full bg-primary"
                      animate={{ height: ["6px", "20px", "9px", "16px", "7px"] }}
                      transition={{ duration: 0.9, repeat: Infinity, ease: "easeInOut", delay: i * 0.1 }}
                    />
                  ))}
                </div>
                <span className="text-xs font-medium text-muted">Listening…</span>
              </>
            )}

            {/* end-call */}
            <button
              onClick={stopVoice}
              aria-label="End"
              className="ml-1 w-8 h-8 rounded-full bg-danger/10 text-danger flex items-center justify-center hover:bg-danger/20 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
