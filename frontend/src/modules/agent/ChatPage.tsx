import React, { useEffect, useRef, useState } from "react";
import { Loader2, RotateCcw, Send, ShieldAlert } from "lucide-react";
import { streamChat, type AgentEvent } from "./sse";
import { TracePanel } from "./TracePanel";

interface ChatMessage {
  role: "student" | "agent";
  text: string;
  citations?: string[];
  escalated?: boolean;
}

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const session = useRef<{ session_id?: string }>({});
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateAgent = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => [...prev.slice(0, -1), fn(prev[prev.length - 1])]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setEvents([]);
    setBusy(true);
    setMessages((prev) => [...prev, { role: "student", text }, { role: "agent", text: "" }]);
    try {
      await streamChat({ message: text, ...session.current }, (ev) => {
        setEvents((prev) => [...prev, ev]);
        if (ev.type === "message") updateAgent((m) => ({ ...m, text: m.text + ev.data.delta }));
        if (ev.type === "final") {
          session.current = { session_id: ev.data.session_id };
          updateAgent((m) => ({ ...m, text: ev.data.text, citations: ev.data.citations, escalated: ev.data.escalated }));
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    session.current = {};
    setMessages([]);
    setEvents([]);
    setError(null);
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 h-[calc(100vh-11rem)] min-h-[520px]">
      <section className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col min-h-0">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Admissions chat</h2>
            <p className="text-xs text-slate-500">Answers come only from the verified knowledge base, with sources</p>
          </div>
          <button type="button" onClick={reset} disabled={busy}
            className="text-xs flex items-center gap-1 px-2 py-1 rounded-md text-slate-600 hover:bg-slate-100 disabled:opacity-50">
            <RotateCcw className="w-3.5 h-3.5" /> New chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <p className="text-sm text-slate-400">Try: “What is the B.Tech CSE fee and eligibility?”</p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "student" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap ${
                m.role === "student" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"}`}>
                {m.text || (busy && i === messages.length - 1
                  ? <span className="flex items-center gap-1.5 text-slate-500"><Loader2 className="w-3.5 h-3.5 animate-spin" />Thinking…</span>
                  : null)}
                {m.escalated && (
                  <div className="mt-2 flex items-center gap-1 text-[11px] text-rose-700">
                    <ShieldAlert className="w-3.5 h-3.5" /> Passed to a counsellor
                  </div>
                )}
                {m.citations && m.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {m.citations.map((c) => (
                      <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-600">{c}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottom} />
        </div>

        {error && <div className="mx-4 mb-2 text-xs text-red-700 bg-red-50 border border-red-200 rounded-md px-2 py-1">{error}</div>}
        <form onSubmit={send} className="p-3 border-t border-slate-100 flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} disabled={busy} maxLength={2000}
            placeholder="Ask about programs, fees, eligibility, scholarships…"
            className="flex-1 text-sm rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <button type="submit" disabled={busy || !input.trim()}
            className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm flex items-center gap-1.5 disabled:opacity-50">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send
          </button>
        </form>
      </section>

      <TracePanel events={events} />
    </div>
  );
};
