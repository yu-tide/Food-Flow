import type { Metadata } from "next";
import { AssistantProvider } from "@/components/assistant/AssistantProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "FoodFlow",
  description: "AI 驱动的饮食记录与营养分析",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        {children}
        <AssistantProvider />
      </body>
    </html>
  );
}
