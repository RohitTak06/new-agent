import React, { useCallback, useEffect, useRef, useState } from "react";
import { CalendarCheck, Clock, Loader2, Mail, RotateCcw, Send, ShieldAlert } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";
import { Button, ErrorBanner } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Booking, ChannelMessage, Chunk, Interaction, Slot } from "../../lib/types";
import { CitationDisplay } from "../intel/CitationDisplay";
import { BookingCard, bookingFromEvent, bookThisMessage, type BookingView } from "./BookingCard";
import { RichText } from "./RichText";
import { streamChat, type AgentEvent } from "./sse";
import { TracePanel } from "./TracePanel";

interface ChatMessage {
  id: string;
  role: "student" | "agent" | "update";
  text: string;
  citations?: string[];
  sources?: Chunk[];
  escalated?: boolean;
  approvalId?: number | null;
  approvalStatus?: string | null;
  bookings?: BookingView[];
  via?: string;
  time?: string;
}

const UPDATE_POLL_MS = 10_000;
const SUGGESTIONS = [
  "What is the B.Tech CSE fee?",
  "Am I eligible for B.Tech CSE with 85% in 12th?",
  "I'd like to book a counsellor session",
  "Can I get a fee waiver?",
];

/** Outbound messages not produced by a chat turn: follow-ups and counsellor replies. */
function isUpdate(m: ChannelMessage): boolean {
  return m.direction === "outbound" && !m.meta?.session_id;
}

function updateMessage(m: ChannelMessage): ChatMessage {
  return { id: `m${m.id}`, role: "update", text: m.text, citations: m.meta?.citations, via: m.channel, time: m.sent_at };
}

function chatRow(r: Interaction): ChatMessage {
  return {
    id: `i${r.id}`, role: r.direction === "inbound" ? "student" : "agent", text: r.message,
    citations: r.meta?.citations, escalated: r.meta?.escalated,
    approvalId: r.meta?.approval_id, approvalStatus: r.meta?.approval_status,
  };
}

/** Passages behind the cited sources, from this turn's knowledge search results. */
function citedChunks(events: AgentEvent[], citations: string[]): Chunk[] {
  const bySource = new Map<string, Chunk>();
  for (const e of events) {
    if (e.type !== "tool_result" || e.data.name !== "search_knowledge" || !e.data.ok) continue;
    for (const c of (e.data.result?.chunks ?? []) as Chunk[]) {
      if (citations.includes(c.source) && !bySource.has(c.source)) bySource.set(c.source, c);
    }
  }
  return citations.map((c) => bySource.get(c)).filter((c): c is Chunk => Boolean(c));
}

const Bubble: React.FC<{ m: ChatMessage; waiting: boolean; disabled: boolean; onBook: (s: Slot) => void }> = ({ m, waiting, disabled, onBook }) => {
  if (m.role === "student") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2 text-sm whitespace-pre-wrap break-words bg-jklu-blue text-white">{m.text}</div>
      </div>
    );
  }
  if (m.role === "update") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl rounded-bl-md px-3.5 py-2 text-sm bg-amber-50 border border-amber-200">
          <p className="flex items-center gap-1 text-[11px] font-medium text-amber-800 mb-1">
            <Mail className="w-3.5 h-3.5" /> From JKLU Admissions, sent by {m.via}{m.time ? ` · ${formatDateTime(m.time)}` : ""}
          </p>
          <RichText text={m.text} citations={m.citations} />
        </div>
      </div>
    );
  }
  const confirmed = m.bookings?.find((b) => b.kind === "confirmed");
  const cards = confirmed ? [confirmed] : m.bookings ?? [];
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md px-3.5 py-2 text-sm bg-slate-100 text-slate-800">
        {m.text ? <RichText text={m.text} citations={m.citations} /> : waiting ? (
          <span className="flex items-center gap-1.5 text-slate-500"><Loader2 className="w-3.5 h-3.5 animate-spin" />Checking…</span>
        ) : null}
        {cards.map((b, i) => <BookingCard key={i} view={b} disabled={disabled} onBook={onBook} />)}
        {m.approvalId ? (
          <p className="mt-2 flex items-center gap-1 text-[11px] font-medium text-amber-800">
            <Clock className="w-3.5 h-3.5" /> Sent to a counsellor for a decision (request #{m.approvalId})
          </p>
        ) : m.escalated ? (
          <p className="mt-2 flex items-center gap-1 text-[11px] font-medium text-rose-700">
            <ShieldAlert className="w-3.5 h-3.5" /> Passed to a counsellor
          </p>
        ) : null}
        {m.sources && m.sources.length > 0 ? <CitationDisplay chunks={m.sources} /> : m.citations && m.citations.length > 0 && (
          <ol className="mt-2 flex flex-wrap gap-1">
            {m.citations.map((c, i) => (
              <li key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-600">{i + 1}. {c}</li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
};

export const ChatPage: React.FC = () => {
  const { user, refresh } = useAuth();
  const student = user?.role === "student" ? user : null;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const session = useRef<{ session_id?: string }>({});
  const seenUpdates = useRef<Set<number> | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const bookings = useApi<Booking[]>(student ? "/scheduling/bookings" : null);
  const upcoming = bookings.data?.find((b) => b.upcoming);
  const leadId = student?.lead_id ?? null;
  const lastAgentId = [...messages].reverse().find((m) => m.role === "agent")?.id;  // older offers may be out of date

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // A student's conversation lives on the server: restore it, with anything counsellors sent.
  useEffect(() => {
    if (leadId === null) return;
    let stale = false;
    Promise.all([
      api<Interaction[]>(`/crm/leads/${leadId}/interactions`),
      api<ChannelMessage[]>(`/scheduling/messages/${leadId}`),
    ]).then(([rows, sent]) => {
      if (stale) return;
      const chat = rows.filter((r) => r.channel === "web" && r.actor !== "counsellor");
      const updates = sent.filter(isUpdate);
      seenUpdates.current = new Set(updates.map((m) => m.id));
      const timed = [
        ...chat.map((r) => ({ at: r.created_at, message: chatRow(r) })),
        ...updates.map((m) => ({ at: m.created_at, message: updateMessage(m) })),
      ].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
      setMessages((now) => [...timed.map((t) => t.message), ...now]);
      const lastSession = [...chat].reverse().find((r) => r.meta?.session_id)?.meta?.session_id;
      if (lastSession && !session.current.session_id) session.current = { session_id: lastSession };
    }).catch((err) => { if (!stale) setError(errorMessage(err)); });
    return () => { stale = true; };
  }, [leadId]);

  // New follow-ups and counsellor replies appear here while the page is open.
  useEffect(() => {
    if (leadId === null) return;
    const timer = setInterval(() => {
      api<ChannelMessage[]>(`/scheduling/messages/${leadId}`).then((sent) => {
        const seen = seenUpdates.current;
        if (!seen) return;
        const fresh = sent.filter((m) => isUpdate(m) && !seen.has(m.id));
        fresh.forEach((m) => seen.add(m.id));
        if (fresh.length) setMessages((now) => [...now, ...fresh.map(updateMessage)]);
      }).catch(() => { /* the next poll tries again */ });
    }, UPDATE_POLL_MS);
    return () => clearInterval(timer);
  }, [leadId]);

  const sendText = useCallback(async (raw: string) => {
    const text = raw.trim();
    if (!text || busy) return;
    const agentId = `a${Date.now()}`;
    const update = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((now) => now.map((m) => (m.id === agentId ? fn(m) : m)));
    setInput("");
    setError(null);
    setEvents([]);
    setBusy(true);
    setMessages((now) => [...now, { id: `s${Date.now()}`, role: "student", text }, { id: agentId, role: "agent", text: "" }]);
    const turn: AgentEvent[] = [];
    let finished = false;
    try {
      await streamChat({ message: text, ...session.current }, (ev) => {
        turn.push(ev);
        setEvents((now) => [...now, ev]);
        if (ev.type === "message") update((m) => ({ ...m, text: m.text + ev.data.delta }));
        const booking = bookingFromEvent(ev);
        if (booking) update((m) => ({ ...m, bookings: [...(m.bookings ?? []), booking] }));
        if (ev.type === "final") {
          finished = true;
          session.current = { session_id: ev.data.session_id };
          update((m) => ({
            ...m, text: ev.data.text, citations: ev.data.citations, escalated: ev.data.escalated,
            approvalId: ev.data.approval_id, approvalStatus: ev.data.approval_status,
            sources: citedChunks(turn, ev.data.citations ?? []),
          }));
        }
      });
      if (!finished) throw new Error("The reply was cut off. Please try again.");
      if (student) {
        void bookings.reload();
        if (student.lead_id === null) void refresh();
      }
    } catch (err) {
      setError(errorMessage(err));
      setMessages((now) => now.filter((m) => m.id !== agentId || m.text));
    } finally {
      setBusy(false);
    }
  }, [busy, student, bookings, refresh]);

  function reset() {
    session.current = {};
    setMessages([]);
    setEvents([]);
    setError(null);
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 lg:h-[calc(100dvh-5.5rem)] lg:min-h-[520px]">
      <section aria-label="Chat" className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col min-h-0 h-[75dvh] lg:h-auto">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
          <div>
            <h1 className="text-sm font-semibold text-slate-800">Admissions chat</h1>
            <p className="text-xs text-slate-500">Answers come only from the verified knowledge base, with sources</p>
          </div>
          {!student && (
            <Button variant="ghost" small onClick={reset} disabled={busy} className="shrink-0 whitespace-nowrap"><RotateCcw className="w-3.5 h-3.5" /> New chat</Button>
          )}
        </div>

        {upcoming && (
          <div className="px-4 py-2 border-b border-emerald-100 bg-emerald-50 text-xs text-emerald-900 flex items-center gap-1.5">
            <CalendarCheck className="w-4 h-4 shrink-0" />
            Your session: {formatDateTime(upcoming.start)} IST with {upcoming.counsellor}
          </div>
        )}

        <div ref={list} className="flex-1 overflow-y-auto p-4 space-y-3" aria-live="polite">
          {messages.length === 0 && (
            <div className="py-6">
              <p className="text-sm text-slate-600 mb-3">Ask about programs, fees, eligibility or scholarships, or book a counsellor session.</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <Button key={s} variant="secondary" small disabled={busy} onClick={() => void sendText(s)}>{s}</Button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <Bubble key={m.id} m={m} waiting={busy && i === messages.length - 1}
              disabled={busy || m.id !== lastAgentId} onBook={(s) => void sendText(bookThisMessage(s))} />
          ))}
        </div>

        {error && <div className="mx-4 mb-2"><ErrorBanner message={error} /></div>}
        <form onSubmit={(e) => { e.preventDefault(); void sendText(input); }} className="p-3 border-t border-slate-100 flex gap-2">
          <label htmlFor="chat-input" className="sr-only">Your message</label>
          <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} disabled={busy} maxLength={2000} autoComplete="off"
            placeholder="Type your question…"
            className="flex-1 min-w-0 text-sm rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50" />
          <Button type="submit" busy={busy} disabled={!input.trim()}>
            {!busy && <Send className="w-4 h-4" />} Send
          </Button>
        </form>
      </section>

      <TracePanel events={events} busy={busy} className="h-[60dvh] lg:h-auto" />
    </div>
  );
};
