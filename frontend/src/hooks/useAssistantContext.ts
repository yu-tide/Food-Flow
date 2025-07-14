"use client";

import { useCallback, useMemo } from "react";
import { usePathname } from "next/navigation";

const QUICK_QUESTIONS: Record<string, string[]> = {
  "/dashboard": [
    "今天我吃得怎么样？",
    "为什么今天还没有记录？",
    "帮我看看最近饮食问题",
  ],
  "/records": [
    "这顿饭热量为什么这么高？",
    "这顿饭脂肪是否偏高？",
    "我应该怎么校准这条记录？",
  ],
  "/confirm": [
    "这条记录为什么还不能保存？",
    "我应该怎么调整成分重量？",
    "菜名候选是什么意思？",
  ],
  "/upload": [
    "上传什么样的图片识别更准？",
    "为什么图片可能识别失败？",
    "如何让 AI 更准确分析？",
  ],
  "/statistics": [
    "帮我总结这周饮食",
    "这周哪天热量最高？",
    "我蛋白质达标了吗？",
  ],
  "/settings": [
    "怎么设置适合我的目标？",
    "蛋白质目标怎么计算？",
    "AI 分析偏好是什么意思？",
  ],
};

const DEFAULT_QUESTIONS = [
  "FoodFlow AI 能帮我做什么？",
  "如何让统计更准确？",
  "为什么未保存记录不进入统计？",
];

function matchQuickQuestions(pathname: string): string[] {
  for (const [prefix, questions] of Object.entries(QUICK_QUESTIONS)) {
    if (pathname.startsWith(prefix)) return questions;
  }
  return DEFAULT_QUESTIONS;
}

export function useAssistantContext() {
  const pathname = usePathname();

  const pageInfo = useMemo(() => {
    const recordId =
      pathname.startsWith("/records/") || pathname.startsWith("/confirm/")
        ? pathname.split("/")[2] || ""
        : "";
    return { page: pathname, recordId };
  }, [pathname]);

  const buildPageContext = useCallback(() => {
    const now = new Date();
    const ctx: Record<string, string> = {
      page: pageInfo.page,
      client_time_iso: now.toISOString(),
      local_hour: String(now.getHours()),
      local_minute: String(now.getMinutes()),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      local_time_text: now.toLocaleTimeString("zh-CN", {
        hour: "2-digit", minute: "2-digit", hour12: false,
      }),
    };
    if (pageInfo.recordId) {
      ctx["record_id"] = pageInfo.recordId;
    }
    return ctx;
  }, [pageInfo]);

  return {
    page: pageInfo.page,
    buildPageContext,
    isLoginPage: pathname === "/login" || pathname === "/register",
    quickQuestions: matchQuickQuestions(pathname),
  };
}
