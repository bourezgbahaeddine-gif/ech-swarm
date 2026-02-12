import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/lib/providers";
import { AuthProvider } from "@/lib/auth";
import AppShell from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "غرفة الشروق الذكية | Echorouk AI Swarm",
  description: "منصة ذكاء اصطناعي لأتمتة غرفة الأخبار — AI-powered newsroom automation platform",
  keywords: ["echorouk", "ai", "newsroom", "algeria", "automation", "gemini"],
  authors: [{ name: "Echorouk AI Team" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body className="min-h-screen bg-[#0a0a0f] antialiased">
        <Providers>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
