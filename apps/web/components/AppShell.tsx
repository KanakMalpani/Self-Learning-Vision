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
  { href: "/memory-runs", label: "Memory runs" },
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
      <div className="flex min-h-screen flex-col">
        <header className="border-b border-[var(--line)] bg-[var(--ground)]">
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-[12px] focus:bg-[var(--action)] focus:px-3 focus:py-2 focus:text-[var(--action-ink)]"
          >
            Skip to content
          </a>
          <div className="mx-auto flex w-[min(1120px,calc(100%-48px))] flex-wrap items-center justify-between gap-x-6 gap-y-3 py-4 max-sm:w-[min(1120px,calc(100%-32px))]">
            <Link href="/" className="flex items-center gap-3 no-underline">
              <span className="grid h-10 w-10 place-items-center rounded-[12px] bg-[var(--action)] font-display text-lg text-[var(--action-ink)]">
                S
              </span>
              <span>
                <span className="block font-display text-xl leading-none text-[var(--ink)]">Self-Learning Vision</span>
                <span className="kicker mt-1 block">On this machine</span>
              </span>
            </Link>

            <nav aria-label="Primary" className="flex flex-wrap items-center gap-1">
              {navItems.map((item) => {
                const active = item.href === "/"
                  ? pathname === "/"
                  : pathname === item.href || pathname?.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex min-h-11 items-center rounded-[12px] px-3 text-[15px] font-medium no-underline ${
                      active
                        ? "bg-[var(--surface)] text-[var(--ink)]"
                        : "text-[var(--muted)] hover:text-[var(--ink)]"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
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
