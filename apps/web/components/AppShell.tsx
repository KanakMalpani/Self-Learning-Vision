"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import DesktopEngineGate from "@/components/DesktopEngineGate";

interface Props {
  children: ReactNode;
}

const navItems = [
  { href: "/", label: "Remember" },
  { href: "/memories", label: "Memories" },
  { href: "/learning-review", label: "Review" },
  { href: "/memory-runs", label: "Memory Runs" },
  { href: "/evaluation", label: "Evaluation" },
  { href: "/settings", label: "Settings" },
];

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const isAuthRoute = pathname?.startsWith("/login") || pathname?.startsWith("/register");

  if (isAuthRoute) {
    return <DesktopEngineGate>{children}</DesktopEngineGate>;
  }

  return (
    <DesktopEngineGate>
    <div className="min-h-screen flex flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-2 focus:bg-white focus:text-black rounded-md shadow">
        Skip to content
      </a>

      <header className="border-b border-white/10 bg-black/30 backdrop-blur supports-[backdrop-filter]:bg-black/40">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-board-accent/30 border border-board-accent/50 flex items-center justify-center text-board-accent font-black text-sm tracking-tight">
              JV
            </div>
            <div>
              <p className="text-sm text-gray-300">Self-Learning Vision</p>
              <p className="text-xs text-gray-500">Private, local-first memory</p>
            </div>
          </div>

          <nav aria-label="Primary" className="flex items-center gap-2">
            {navItems.map((item) => {
              const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-board-accent ${
                    active ? "bg-white/15 text-white" : "text-gray-200 hover:bg-white/10"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
            <span className="hidden sm:inline-flex items-center gap-2 ml-2 text-xs text-gray-300">
              <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" aria-hidden />
              <span>Local-first</span>
            </span>
          </nav>
        </div>
      </header>

      <main id="main" className="flex-1">
        {children}
      </main>
    </div>
    </DesktopEngineGate>
  );
}

