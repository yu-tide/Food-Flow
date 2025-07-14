"use client";

import { Loader2, Sparkles, UserRound } from "lucide-react";
import type { ChatMessage, AssistantActionExecuteResponse } from "@/services/assistant";
import { AssistantActionCard } from "./AssistantActionCard";

export function AssistantMessageList({
  messages,
  quickQuestions,
  onQuickQuestionClick,
  onActionExecuted,
}: {
  messages: ChatMessage[];
  quickQuestions?: string[];
  onQuickQuestionClick?: (q: string) => void;
  onActionExecuted?: (result: AssistantActionExecuteResponse, actionId: string) => void;
}) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center">
        <div className="grid h-14 w-14 place-items-center rounded-2xl bg-green-100">
          <Sparkles className="h-7 w-7 text-green-600" />
        </div>
        <p className="text-[14px] font-black text-slate-600">FoodFlow AI 助手</p>
        <p className="text-[12px] font-bold text-slate-400">可以问我关于当前饮食记录、营养目标或每周统计的问题。</p>
        {quickQuestions && quickQuestions.length > 0 && (
          <div className="mt-2 flex flex-wrap justify-center gap-2">
            {quickQuestions.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onQuickQuestionClick?.(q)}
                className="rounded-full bg-slate-100 px-2.5 py-1.5 text-[11px] font-bold text-slate-500 transition hover:bg-green-100 hover:text-green-700"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {messages.map((msg, i) => (
        <div key={i} className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
          <div className={`grid h-7 w-7 shrink-0 place-items-center rounded-full ${msg.role === "assistant" ? "bg-green-100" : "bg-slate-100"}`}>
            {msg.role === "assistant" ? <Sparkles className="h-3.5 w-3.5 text-green-600" /> : <UserRound className="h-3.5 w-3.5 text-slate-500" />}
          </div>
          <div className="min-w-0 max-w-[85%]">
            <div className={`rounded-2xl px-4 py-3 text-[13px] leading-6 space-y-1.5 ${
              msg.role === "assistant"
                ? "border border-slate-100 bg-white text-slate-700"
                : "bg-green-500 text-white"
            }`}>
              {msg.content ? (
                msg.content.split("\n").map((line, li) => (
                  <p key={li} className={line.trim() ? "" : "h-2"}>{line || " "}</p>
                ))
              ) : msg.isStreaming && msg.role === "assistant" ? (
                <span className="flex items-center gap-1.5 text-slate-400">
                  <Loader2 className="h-3 w-3 animate-spin" />正在思考...
                </span>
              ) : null}
            </div>
            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1 px-0.5">
                {msg.sources.map((s, si) => (
                  <span key={si} className="rounded-full bg-green-50 px-1.5 py-0.5 text-[10px] font-bold text-green-600">{s.title}</span>
                ))}
              </div>
            )}
            {msg.suggested_actions && msg.suggested_actions.length > 0 && (
              <div className="mt-2.5 flex flex-col gap-2">
                {msg.suggested_actions.map((a) => (
                  <AssistantActionCard key={a.id} action={a} onExecuted={(result) => onActionExecuted?.(result, a.id)} />
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
