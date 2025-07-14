"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, ShieldAlert, X } from "lucide-react";
import { executeAssistantAction, type AssistantSuggestedAction, type AssistantActionExecuteResponse } from "@/services/assistant";

export function AssistantActionCard({
  action,
  onExecuted,
}: {
  action: AssistantSuggestedAction;
  onExecuted?: (result: AssistantActionExecuteResponse) => void;
}) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "cancelled" | "error">("idle");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AssistantActionExecuteResponse | null>(null);

  const handleExecute = async () => {
    setState("loading");
    try {
      const res = await executeAssistantAction(action);
      setResult(res);
      if (res.ok) {
        setState("done");
        setMessage(res.message);
        onExecuted?.(res);
      } else {
        setState("error");
        setMessage(res.message);
      }
    } catch {
      setState("error");
      setMessage("操作执行失败，请稍后重试");
    }
  };

  const handleCancel = () => {
    setState("cancelled");
    setMessage("已取消");
    onExecuted?.({ ok: false, type: action.type, message: "已取消" });
  };

  if (state === "done") {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-green-50 px-3 py-2.5 text-[12px] font-bold text-green-700">
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        <span>{message}</span>
      </div>
    );
  }

  if (state === "cancelled") {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2.5 text-[12px] font-bold text-slate-400">
        <X className="h-4 w-4 shrink-0" />
        <span>{message}</span>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border px-3.5 py-3 ${
      action.risk_level === "medium"
        ? "border-amber-200 bg-amber-50/50"
        : "border-slate-200 bg-white"
    }`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-black text-slate-700">{action.title}</span>
            {action.risk_level === "medium" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                <ShieldAlert className="h-3 w-3" />需要确认
              </span>
            )}
          </div>
          {action.description && (
            <p className="mt-1 text-[11px] font-semibold text-slate-500">{action.description}</p>
          )}
        </div>
      </div>

      {state === "error" && (
        <p className="mt-2 text-[11px] font-bold text-red-500">{message}</p>
      )}

      <div className="mt-2.5 flex items-center gap-2">
        <button
          type="button"
          onClick={handleExecute}
          disabled={state === "loading"}
          className="flex h-8 items-center gap-1.5 rounded-lg bg-green-600 px-3 text-[12px] font-bold text-white transition hover:bg-green-700 disabled:opacity-50"
        >
          {state === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          {action.confirm_label || "确认"}
        </button>
        <button
          type="button"
          onClick={handleCancel}
          disabled={state === "loading"}
          className="flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-[12px] font-bold text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
        >
          {action.cancel_label || "取消"}
        </button>
      </div>
    </div>
  );
}
