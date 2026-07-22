import type { Metadata } from "next";

import { Nav } from "@/components/nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "LLM-VulnHub",
  description: "面向 LLM、RAG 与 Agent 应用的漏洞情报管理平台",
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
        <main className="min-h-screen px-4 pb-8 pt-20 sm:px-6 lg:ml-64 lg:px-8 lg:py-6">{children}</main>
      </body>
    </html>
  );
}
