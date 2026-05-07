"use client";

import { useApp } from "@/lib/store";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  ArrowLeft,
  Bot,
  User,
  Sparkles,
  MessageCircle,
  X,
  BookOpen,
} from "lucide-react";

interface ChatPageProps {
  ragContext: string | null;
  transcripts?: any[];
  isSidebar?: boolean;
}

const VOICE_AGENT = 'http://localhost:7860/client/';
const BACKEND = 'http://localhost:8000';

// Financial terms the highlighter will detect (case-insensitive match)
const FINANCIAL_TERMS = [
  "FD", "Fixed Deposit", "TDS", "KYC", "PAN", "Aadhaar",
  "compound interest", "simple interest", "maturity",
  "principal", "tenure", "interest rate", "nominee",
  "tax saving", "Section 80C", "80C", "IFSC",
  "UPI", "net banking", "senior citizen",
  "NRE", "NRO", "recurring deposit", "RD",
  "PPF", "EPF", "mutual fund", "SIP",
  "capital gains", "income tax", "old regime", "new regime",
  "deduction", "exemption", "rebate", "surcharge", "cess",
  "premature withdrawal", "auto-renewal", "cumulative",
  "non-cumulative", "quarterly payout", "annualized",
  "CAGR", "ROI", "liquidity", "lock-in period",
];

interface TermPopup {
  term: string;
  explanation: string | null;
  loading: boolean;
  x: number;
  y: number;
}

export default function ChatPage({ ragContext, transcripts = [], isSidebar = false }: ChatPageProps) {
  const { chatMessages, sendMessage, setPage } = useApp();
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [popup, setPopup] = useState<TermPopup | null>(null);

  const allMessages = [
    ...chatMessages.map(m => ({ ...m, type: 'text' })),
    ...(transcripts || []).map((t: any, idx: number) => ({
      id: `transcript-${idx}`,
      role: t.role === 'bot' ? 'assistant' : t.role === 'tool' ? 'tool' : 'user',
      content: t.text,
      timestamp: new Date(t.timestamp),
      type: 'voice'
    }))
  ].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [allMessages]);

  useEffect(() => {
    const lastMsg = allMessages[allMessages.length - 1];
    if (lastMsg?.role === "user" && lastMsg.type === "text") {
      setIsTyping(true);
    } else {
      setIsTyping(false);
    }
  }, [allMessages]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    sendMessage(trimmed);
    setInput("");
    inputRef.current?.focus();
  };

  // Fetch explanation for a clicked term
  const handleTermClick = useCallback(async (term: string, event: React.MouseEvent) => {
    const rect = (event.target as HTMLElement).getBoundingClientRect();
    setPopup({
      term,
      explanation: null,
      loading: true,
      x: rect.left + rect.width / 2,
      y: rect.top - 8,
    });

    try {
      const resp = await fetch(`${BACKEND}/tools/explain_term`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term, language: 'en' }),
      });
      const data = await resp.json();
      setPopup(prev => prev ? { ...prev, explanation: data.explanation || "No explanation available.", loading: false } : null);
    } catch {
      setPopup(prev => prev ? { ...prev, explanation: "Could not fetch explanation.", loading: false } : null);
    }
  }, []);

  // Close popup when clicking outside
  useEffect(() => {
    const close = () => setPopup(null);
    if (popup) {
      window.addEventListener('click', close, { once: true });
      return () => window.removeEventListener('click', close);
    }
  }, [popup]);

  const quickQuestions = [
    "What is an FD?",
    "Why are you recommending this?",
    "Can I save ₹5000 this month?",
  ];

  return (
    <div className={`flex-1 flex flex-col h-full ${isSidebar ? 'bg-surface/30' : 'animate-fade-up max-w-5xl mx-auto w-full'}`}>
      {/* Header */}
      <div className="border-b border-border bg-surface/50 backdrop-blur-sm shrink-0">
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {!isSidebar && (
              <button
                onClick={() => setPage("landing")}
                className="p-2 rounded-lg hover:bg-surface-2 transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-muted" />
              </button>
            )}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/15 flex items-center justify-center">
                <Bot className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-semibold text-sm">AI Money Coach</h2>
                <div className="flex items-center gap-1.5 text-xs text-muted">
                  <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-dot" />
                  Voice Active
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Area */}
      <div className="flex-1 overflow-y-auto flex flex-col">
        {/* Voice Agent Section */}
        <div className={`p-4 flex shrink-0 ${isSidebar ? 'border-b border-border/50' : 'border-b border-border bg-surface/20'}`}>
          {/* Voice Embed — compact, just the Connect button */}
          <div className={`rounded-xl overflow-hidden border border-border/50 bg-background/50 shadow-inner ${isSidebar ? 'h-[50px] w-full' : 'h-[50px] w-[280px]'}`}>
            <iframe 
              src={VOICE_AGENT} 
              allow="microphone; camera; autoplay" 
              title="Voice Agent" 
              className="w-full h-full border-0"
            />
          </div>
        </div>

        {/* Text Messages */}
        <div className="flex-1 px-6 py-6 space-y-6 overflow-y-auto">
          {allMessages.length === 0 && (
            <div className="text-center py-8">
              <div className="w-12 h-12 mx-auto mb-4 rounded-2xl bg-primary/10 flex items-center justify-center">
                <MessageCircle className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">
                Ask me anything about your money
              </h3>
              
              <div className="flex flex-col gap-2 mt-6 max-w-sm mx-auto">
                {quickQuestions.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="text-left px-4 py-2.5 rounded-xl border border-border bg-surface hover:bg-surface-2 transition-all text-sm text-muted hover:text-foreground flex items-center"
                  >
                    <Sparkles className="w-3.5 h-3.5 mr-2 text-primary shrink-0" />
                    <span className="truncate">{q}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {allMessages.map((msg) => {
            if (msg.role === "tool") {
              return (
                <div key={msg.id} className="flex justify-center my-2">
                  <div className="px-3 py-1.5 rounded-full bg-surface-2 border border-border/50 text-[11px] text-muted flex items-center gap-2">
                    <Sparkles className="w-3 h-3 text-primary/70" />
                    {msg.content}
                  </div>
                </div>
              );
            }

            const isImage = msg.content.startsWith("[IMAGE: ") && msg.content.endsWith("]");
            const imagePath = isImage ? msg.content.replace("[IMAGE: ", "").replace("]", "") : null;

            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center shrink-0 mt-1">
                    <Bot className="w-4 h-4 text-primary" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed
                    ${msg.role === "user" ? "bg-primary text-background rounded-br-md" : "glass-card rounded-bl-md"}`}
                >
                  {isImage ? (
                    <div className="rounded-xl overflow-hidden border border-border/50 mt-1">
                      <img src={imagePath?.startsWith('http') ? imagePath : `${BACKEND}/${imagePath}`} alt="Reference" className="max-w-full h-auto object-contain max-h-[200px]" />
                    </div>
                  ) : (
                    <HighlightedMessage
                      content={msg.content}
                      isUser={msg.role === "user"}
                      onTermClick={handleTermClick}
                    />
                  )}
                  {msg.type === "voice" && msg.role === "user" && (
                    <div className="text-[10px] opacity-50 mt-1 text-right italic">🗣️ Voice</div>
                  )}
                </div>
              </div>
            );
          })}

          {isTyping && (
            <div className="flex gap-3 items-start">
              <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="glass-card rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex gap-1.5">
                  <div className="w-2 h-2 bg-muted rounded-full animate-bounce [animation-delay:0ms]" />
                  <div className="w-2 h-2 bg-muted rounded-full animate-bounce [animation-delay:150ms]" />
                  <div className="w-2 h-2 bg-muted rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Term Explanation Popup */}
      {popup && (
        <div
          className="fixed z-50 max-w-xs animate-in fade-in zoom-in-95 duration-200"
          style={{
            left: `${Math.min(popup.x, window.innerWidth - 320)}px`,
            top: `${popup.y}px`,
            transform: 'translate(-50%, -100%)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bg-surface border border-border rounded-xl shadow-2xl p-4 relative">
            <button
              onClick={() => setPopup(null)}
              className="absolute top-2 right-2 p-1 rounded-md hover:bg-surface-2 transition-colors"
            >
              <X className="w-3 h-3 text-muted" />
            </button>
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4 text-primary" />
              <span className="text-xs font-bold text-primary uppercase tracking-wider">{popup.term}</span>
            </div>
            {popup.loading ? (
              <div className="flex items-center gap-2 text-xs text-muted">
                <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                Fetching explanation…
              </div>
            ) : (
              <p className="text-xs text-foreground/80 leading-relaxed">{popup.explanation}</p>
            )}
            {/* Arrow */}
            <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-surface border-b border-r border-border rotate-45" />
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="border-t border-border bg-surface/50 backdrop-blur-sm p-4 shrink-0">
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about FDs, savings..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-surface-2 border border-border text-sm placeholder-muted focus:outline-none focus:border-primary/50 transition-all"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-4 py-2.5 rounded-xl bg-primary text-background hover:bg-primary-dim disabled:opacity-40 transition-all flex items-center justify-center"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Highlighted Message Component ──
// Detects financial terms in bot messages and makes them clickable

function HighlightedMessage({
  content,
  isUser,
  onTermClick,
}: {
  content: string;
  isUser: boolean;
  onTermClick: (term: string, e: React.MouseEvent) => void;
}) {
  if (isUser || !content) {
    return (
      <div
        className="prose prose-sm prose-invert max-w-none [&_p]:mb-1 [&_p:last-child]:mb-0"
        dangerouslySetInnerHTML={{ __html: formatMarkdown(content) }}
      />
    );
  }

  // Build a regex from financial terms (sorted longest-first to avoid partial matches)
  const sorted = [...FINANCIAL_TERMS].sort((a, b) => b.length - a.length);
  const escaped = sorted.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi');

  // Split the formatted HTML content into parts
  const html = formatMarkdown(content);
  const parts: { text: string; isTerm: boolean; term: string }[] = [];
  let lastIndex = 0;
  let match;

  // We need to work on plain text for matching, then render with formatting
  // Use a simpler approach: find terms in plain text, render with React nodes
  const plainText = content;
  const regex = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi');
  
  while ((match = regex.exec(plainText)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: plainText.slice(lastIndex, match.index), isTerm: false, term: '' });
    }
    parts.push({ text: match[0], isTerm: true, term: match[0] });
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < plainText.length) {
    parts.push({ text: plainText.slice(lastIndex), isTerm: false, term: '' });
  }

  // If no terms found, fall back to dangerouslySetInnerHTML
  if (parts.length === 0 || parts.every(p => !p.isTerm)) {
    return (
      <div
        className="prose prose-sm prose-invert max-w-none [&_p]:mb-1 [&_p:last-child]:mb-0"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }

  return (
    <div className="prose prose-sm prose-invert max-w-none [&_p]:mb-1 [&_p:last-child]:mb-0">
      {parts.map((part, i) => {
        if (part.isTerm) {
          return (
            <span
              key={i}
              onClick={(e) => {
                e.stopPropagation();
                onTermClick(part.term, e);
              }}
              className="underline decoration-primary/40 decoration-dotted underline-offset-2 cursor-pointer hover:text-primary hover:decoration-primary transition-colors font-medium"
              title={`Click to learn: ${part.term}`}
            >
              {part.text}
            </span>
          );
        }
        // Render non-term text with markdown formatting
        return (
          <span
            key={i}
            dangerouslySetInnerHTML={{ __html: formatMarkdown(part.text) }}
          />
        );
      })}
    </div>
  );
}

function formatMarkdown(text: string): string {
  if (!text) return '';

  let html = text
    // Code blocks (```)
    .replace(/```([\s\S]*?)```/g, '<pre class="bg-surface-2 rounded-lg p-3 my-2 text-xs overflow-x-auto border border-border/50"><code>$1</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-surface-2 px-1.5 py-0.5 rounded text-xs text-primary">$1</code>')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-foreground font-semibold">$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Headings
    .replace(/^### (.*$)/gm, '<h4 class="text-sm font-bold text-primary mt-3 mb-1">$1</h4>')
    .replace(/^## (.*$)/gm, '<h3 class="text-base font-bold text-foreground mt-3 mb-1">$1</h3>')
    .replace(/^# (.*$)/gm, '<h2 class="text-lg font-bold text-foreground mt-3 mb-1">$1</h2>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr class="border-border/50 my-3"/>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-primary underline underline-offset-2">$1</a>');

  // Process lines for lists
  const lines = html.split('\n');
  const processed: string[] = [];
  let inUl = false;
  let inOl = false;

  for (const line of lines) {
    const ulMatch = line.match(/^[\-\*] (.*)$/);
    const olMatch = line.match(/^\d+\. (.*)$/);

    if (ulMatch) {
      if (!inUl) { processed.push('<ul class="list-disc list-inside space-y-1 my-2 text-foreground/80">'); inUl = true; }
      if (inOl) { processed.push('</ol>'); inOl = false; }
      processed.push(`<li class="leading-relaxed">${ulMatch[1]}</li>`);
    } else if (olMatch) {
      if (!inOl) { processed.push('<ol class="list-decimal list-inside space-y-1 my-2 text-foreground/80">'); inOl = true; }
      if (inUl) { processed.push('</ul>'); inUl = false; }
      processed.push(`<li class="leading-relaxed">${olMatch[1]}</li>`);
    } else {
      if (inUl) { processed.push('</ul>'); inUl = false; }
      if (inOl) { processed.push('</ol>'); inOl = false; }
      if (line.trim() === '') {
        processed.push('<div class="h-2"></div>');
      } else if (!line.startsWith('<h') && !line.startsWith('<hr') && !line.startsWith('<pre') && !line.startsWith('<ul') && !line.startsWith('<ol')) {
        processed.push(`<p class="leading-relaxed mb-1">${line}</p>`);
      } else {
        processed.push(line);
      }
    }
  }
  if (inUl) processed.push('</ul>');
  if (inOl) processed.push('</ol>');

  return processed.join('');
}
