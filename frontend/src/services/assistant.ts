import { apiPost } from "./api";

const API_BASE = ""; // Next.js rewrites 代理

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ type: string; title: string; id?: string }>;
  suggested_actions?: AssistantSuggestedAction[];
  isStreaming?: boolean;
};

export type ChatRequest = {
  message: string;
  page: string;
  page_context: Record<string, string>;
  session_id?: string;
  history?: ChatMessage[];
};

export type ChatResponse = {
  answer: string;
  session_id: string;
  sources?: Array<{ type: string; title: string; id?: string }>;
  suggested_actions?: AssistantSuggestedAction[];
};

export type AssistantActionType =
  | "open_record_detail"
  | "open_settings"
  | "save_current_record"
  | "export_weekly_report";

export type AssistantSuggestedAction = {
  id: string;
  type: AssistantActionType;
  title: string;
  description?: string;
  confirm_label?: string;
  cancel_label?: string;
  payload: Record<string, unknown>;
  requires_confirmation: boolean;
  risk_level: "low" | "medium";
};

export type AssistantActionExecuteResponse = {
  ok: boolean;
  type: string;
  message: string;
  result?: Record<string, unknown> | null;
  post_action_observation?: Record<string, unknown> | null;
  assistant_followup_message?: string | null;
};

export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  return apiPost<ChatResponse>("/api/assistant/chat", req);
}

export async function sendChatMessageStream(
  payload: ChatRequest,
  handlers: {
    onDelta: (delta: string) => void;
    onSources?: (sources: Array<{ type: string; title: string; id?: string }>) => void;
    onActions?: (actions: AssistantSuggestedAction[]) => void;
    onDone?: (sessionId?: string) => void;
    onError?: (message: string) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const res = await fetch(`${API_BASE}/api/assistant/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (res.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    throw new Error("UNAUTHORIZED");
  }

  if (!res.ok) {
    throw new Error("Stream request failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        const lines = block.split("\n");
        let eventType = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          else if (line.startsWith("data:")) dataStr = line.slice(5).trim();
        }

        if (!eventType || !dataStr) continue;

        try {
          const data = JSON.parse(dataStr);

          switch (eventType) {
            case "message":
              handlers.onDelta(data.delta || "");
              break;
            case "source":
              handlers.onSources?.(data.sources || []);
              break;
            case "action":
              handlers.onActions?.(data.suggested_actions || []);
              break;
            case "done":
              handlers.onDone?.(data.session_id);
              break;
            case "error":
              handlers.onError?.(data.message || "AI 助手暂时不可用");
              break;
          }
        } catch { /* skip malformed blocks */ }
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    throw err;
  }
}

export async function executeAssistantAction(
  action: AssistantSuggestedAction,
): Promise<AssistantActionExecuteResponse> {
  return apiPost<AssistantActionExecuteResponse>("/api/assistant/actions/execute", {
    action_id: action.id,
    type: action.type,
    payload: action.payload,
  });
}
