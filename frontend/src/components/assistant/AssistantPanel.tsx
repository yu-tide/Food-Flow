"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Minimize2, X } from "lucide-react";
import { AssistantMessageList } from "./AssistantMessageList";
import { AssistantComposer } from "./AssistantComposer";
import { sendChatMessage, type ChatMessage, type AssistantSuggestedAction, type AssistantActionExecuteResponse } from "@/services/assistant";

export function AssistantPanel({
  page,
  buildPageContext,
  quickQuestions,
  onClose,
}: {
  page: string;
  buildPageContext: () => Record<string, string>;
  quickQuestions?: string[];
  onClose: () => void;
}) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [sending, setSending] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [messages]);

  const lastFollowupRef = useRef<string>("");

  const handleActionExecuted = useCallback((result: AssistantActionExecuteResponse, actionId: string) => {
    if (!result.ok) return;

    const followup = result.assistant_followup_message;
    if (followup && lastFollowupRef.current !== actionId) {
      lastFollowupRef.current = actionId;
      setMessages((prev) => [...prev, { role: "assistant", content: followup }]);
    }

    if (result.type === "save_current_record") {
      router.refresh();
    } else if (result.type === "open_record_detail" && result.result?.url) {
      router.push(result.result.url as string);
    } else if (result.type === "open_settings") {
      router.push("/settings");
    } else if (result.type === "export_weekly_report" && result.result?.content) {
      setMessages((prev) => [...prev, { role: "assistant", content: result.result!.content as string }]);
    }
  }, [router]);

  const handleSend = useCallback(async (text: string) => {
    if (sending) return;
    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);

    const placeholder: ChatMessage = { role: "assistant", content: "", isStreaming: true };
    setMessages((prev) => [...prev, placeholder]);

    const freshContext = buildPageContext();

    try {
      const res = await sendChatMessage({
        message: text,
        page,
        page_context: freshContext,
        session_id: sessionId,
        history: messages.slice(-6),
      });
      setSessionId(res.session_id);
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = {
            role: "assistant",
            content: res.answer,
            sources: res.sources || [],
            suggested_actions: res.suggested_actions || [],
            isStreaming: false,
          };
        }
        return next;
      });
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = {
            ...last,
            content: "抱歉，AI 助手暂时不可用。请稍后重试。",
            isStreaming: false,
          };
        }
        return next;
      });
    } finally {
      setSending(false);
    }
  }, [page, buildPageContext, sessionId, messages, sending]);

  return (
    <div className={`flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_16px_48px_rgba(15,23,42,0.12)] transition-all duration-200 ${minimized ? "h-[52px]" : "h-[480px] max-h-[calc(100vh-120px)]"}`}>
      <div className="flex shrink-0 items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2"><div className="grid h-7 w-7 place-items-center rounded-lg bg-green-100"><span className="text-[13px]">✨</span></div><span className="text-[14px] font-black text-slate-700">FoodFlow AI</span></div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setMinimized(!minimized)} className="grid h-7 w-7 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100"><Minimize2 className="h-3.5 w-3.5" /></button>
          <button type="button" onClick={onClose} className="grid h-7 w-7 place-items-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-500"><X className="h-3.5 w-3.5" /></button>
        </div>
      </div>
      {!minimized && (<>
        <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-4"><AssistantMessageList messages={messages} quickQuestions={quickQuestions} onQuickQuestionClick={handleSend} onActionExecuted={handleActionExecuted} /></div>
        <AssistantComposer onSend={handleSend} sending={sending} isStreaming={false} onStop={() => {}} />
      </>)}
    </div>
  );
}