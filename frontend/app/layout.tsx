import type { Metadata } from "next";

import { Nav } from "@/components/nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "LLM-VulnHub",
  description: "AI 大模型漏洞管理与智能分析平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="bg-background text-foreground antialiased">
        <Nav />
        <main className="ml-64 min-h-screen px-8 py-6">{children}</main>
      </body>
    </html>
  );
}
