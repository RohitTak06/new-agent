export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type AgentEventType =
  | "plan" | "tool_call" | "tool_result" | "verify" | "retry" | "escalation"
  | "approval_pending" | "message" | "final" | "error";

export interface AgentEvent {
  type: AgentEventType;
  step: number;
  ts: string;
  data: Record<string, any>;
}

export interface ChatBody {
  message: string;
  session_id?: string;
  lead_id?: number;
  channel?: "web" | "whatsapp" | "email";
}

/** POST /agent/chat and call onEvent for each SSE event. EventSource can't POST, so parse the stream by hand. */
export async function streamChat(body: ChatBody, onEvent: (e: AgentEvent) => void, signal?: AbortSignal) {
  const res = await fetch(`${API_BASE}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Chat failed: HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const data = frame.split("\n").find((l) => l.startsWith("data: "));
      if (data) onEvent(JSON.parse(data.slice(6)) as AgentEvent);
    }
  }
}
