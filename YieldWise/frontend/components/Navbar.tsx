"use client";

import { useApp } from "@/lib/store";
import {
  TrendingUp,
  LayoutDashboard,
  MessageCircle,
  Landmark,
  Home,
  Shield,
} from "lucide-react";

export default function Navbar() {
  const { currentPage, setPage, summary, recommendation } = useApp();

  // Don't show navbar on landing
  if (currentPage === "landing") return null;

  const navItems = [
    { page: "chat" as const, icon: MessageCircle, label: "Ask AI" },
    { page: "booking" as const, icon: Landmark, label: "Book FD", highlight: !!recommendation },
  ];

  return (
    <nav className="border-b border-border bg-surface/70 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-14">
        {/* Logo */}
        <button
          onClick={() => setPage("landing")}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <div className="w-7 h-7 rounded-lg bg-primary/20 flex items-center justify-center">
            <TrendingUp className="w-4 h-4 text-primary" />
          </div>
          <span className="font-bold text-sm tracking-tight">SaveSmart</span>
        </button>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          {navItems.map(({ page, icon: Icon, label, highlight }) => {
            const isActive = currentPage === page;
            return (
              <button
                key={page}
                onClick={() => setPage(page)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all
                  ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted hover:text-foreground hover:bg-surface-2"
                  }
                  ${highlight && !isActive ? "text-accent" : ""}`}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{label}</span>
                {highlight && !isActive && (
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse-dot" />
                )}
              </button>
            );
          })}
        </div>

        {/* Blostem badge */}
        <div className="flex items-center gap-1.5 text-xs text-muted">
          <Shield className="w-3.5 h-3.5 text-primary" />
          <span className="hidden sm:inline">Powered by Blostem</span>
        </div>
      </div>
    </nav>
  );
}
