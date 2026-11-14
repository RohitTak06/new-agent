import React, { useEffect, useRef, useState } from "react";
import { CheckCheck, Loader2, Send, Smartphone } from "lucide-react";
import { formatDateTime } from "../../lib/format";
import type { ChannelMessage } from "../../lib/types";
import { RichText } from "../agent/RichText";

interface Props {
  messages: ChannelMessage[];
  title: string;
  onSend: (text: string) => void;
  pendingText?: string | null;
  status?: string | null;
  busy?: boolean;
  disabled?: boolean;
}

/** A simulated WhatsApp conversation in a phone frame. Nothing is really sent. */
export const PhoneView: React.FC<Props> = ({ messages, title, onSend, pendingText, status, busy, disabled }) => {
  const [draft, setDraft] = useState("");
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight });
  }, [messages.length, pendingText, status]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    onSend(text);
  }

  const bubble = "max-w-[85%] rounded-xl px-3 py-2 text-13 shadow-card";
  return (
    <div aria-label="WhatsApp conversation" role="region"
      className="w-full max-w-[340px] mx-auto rounded-[2rem] bg-navy p-2 shadow-card">
      <div className="rounded-[1.6rem] overflow-hidden flex flex-col h-[560px] bg-subtle">
        <div className="bg-navy-hover text-white px-4 pt-3 pb-2.5 flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-full bg-white text-navy text-xs font-bold flex items-center justify-center shrink-0" aria-hidden>JK</span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold truncate">{title}</span>
            <span className="block text-xs text-white/75 truncate">{status ?? "WhatsApp (simulated)"}</span>
          </span>
        </div>

        <div ref={list} className="flex-1 overflow-y-auto px-3 py-3 space-y-2 scroll-quiet">
          {messages.length === 0 && !pendingText && (
            <div className="mt-16 text-center text-xs text-ink-secondary px-6">
              <Smartphone className="w-6 h-6 mx-auto mb-1.5 text-ink-secondary" aria-hidden />
              No WhatsApp messages yet. Send one to talk to the admissions agent.
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.direction === "inbound" ? "justify-end" : "justify-start"}`}>
              <div className={`${bubble} ${m.direction === "inbound" ? "bg-info-soft border border-info/20" : "bg-surface border border-line"} text-ink`}>
                <RichText text={m.text} citations={m.meta?.citations} />
                {m.meta?.citations?.length > 0 && (
                  <ol className="mt-2 pt-1.5 border-t border-line text-xs leading-snug text-ink-secondary">
                    {m.meta?.citations.map((c: string, i: number) => <li key={c} className="break-all">{i + 1}. {c}</li>)}
                  </ol>
                )}
                <p className="mt-1 flex items-center justify-end gap-1 text-xs text-ink-secondary tabular-nums">
                  {formatDateTime(m.sent_at)}
                  {m.direction === "inbound" && <CheckCheck className="w-3.5 h-3.5 text-info" aria-label="Delivered" />}
                </p>
              </div>
            </div>
          ))}
          {pendingText && (
            <div className="flex justify-end">
              <div className={`${bubble} bg-info-soft border border-info/20 text-ink whitespace-pre-wrap break-words`}>{pendingText}</div>
            </div>
          )}
          {busy && (
            <div className="flex justify-start">
              <div className={`${bubble} bg-surface border border-line text-ink-secondary flex items-center gap-1.5`}>
                <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> typing…
              </div>
            </div>
          )}
        </div>

        <form onSubmit={submit} className="p-2 flex items-center gap-1.5 border-t border-line bg-surface">
          <label htmlFor="whatsapp-input" className="sr-only">WhatsApp message</label>
          <input id="whatsapp-input" value={draft} onChange={(e) => setDraft(e.target.value)} disabled={disabled} maxLength={2000} autoComplete="off"
            placeholder="Type a message"
            className="flex-1 min-w-0 rounded-full bg-subtle border border-line px-3.5 py-2 text-sm text-ink placeholder:text-ink-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-navy disabled:opacity-60" />
          <button type="submit" aria-label="Send WhatsApp message" disabled={disabled || !draft.trim()}
            className="w-9 h-9 rounded-full bg-navy hover:bg-navy-hover text-white flex items-center justify-center shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-1 disabled:opacity-50">
            <Send className="w-4 h-4" aria-hidden />
          </button>
        </form>
      </div>
    </div>
  );
};
