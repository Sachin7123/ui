import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";

import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ReMorph · The AI Training Observability Platform",
  description:
    "A premium real-time AI training observability platform. Stream every signal, persist every event, and turn API failures into intelligence.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <div className="ambient-stage" aria-hidden>
          <div className="ambient-grid" />
          <div className="ambient-orb orb-violet" />
          <div className="ambient-orb orb-cyan" />
          <div className="ambient-orb orb-emerald" />
          <div className="ambient-noise" />
          <div className="ambient-vignette" />
        </div>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
