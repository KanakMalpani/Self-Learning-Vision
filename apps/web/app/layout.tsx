import type { Metadata } from "next";
import { Manrope, Newsreader } from "next/font/google";
import { AuthProvider } from "@/lib/auth-context";
import AppShell from "@/components/AppShell";
import "./globals.css";

const sans = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
});

const display = Newsreader({
  subsets: ["latin"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "Self-Learning Vision",
  description: "Private, local-first personal memory assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}

