import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/lib/providers";
import { AuthProvider } from "@/lib/auth";
import AppShell from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "Echorouk Editorial OS | Intelligent Editorial Workflows",
  description:
    "Echorouk Editorial OS - The Operating System for Intelligent Editorial Workflows.",
  keywords: ["echorouk", "editorial", "newsroom", "algeria", "workflows", "governance"],
  authors: [{ name: "Echorouk Editorial OS Team" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body className="min-h-screen app-main-shell antialiased">
        <Providers>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
