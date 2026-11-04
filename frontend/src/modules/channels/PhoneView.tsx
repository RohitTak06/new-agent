import React, { useEffect, useRef, useState } from "react";
import { CheckCheck, Loader2, Send, Smartphone } from "lucide-react";
import { formatDateTime } from "../../lib/format";
import type { ChannelMessage } from "../../lib/types";
import { RichText } from "../agent/RichText";

interface Props {
  messages: ChannelMessage[];
  title: string;
  /** Leave out for a read-only view (staff looking at a lead). */
  onSend?: (text: string) => void;
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
    if (!text || !onSend) return;
    setDraft("");
    onSend(text);
  }

  const bubble = "max-w-[85%] rounded-lg px-2.5 py-1.5 text-[13px] shadow-sm";
  return (
    <div aria-label="WhatsApp conversation" role="region"
      className="w-full max-w-[340px] mx-auto rounded-[2rem] bg-slate-900 p-2 shadow-lg">
      <div className="rounded-[1.6rem] overflow-hidden flex flex-col h-[560px] bg-[#ece5dd]">
        <div className="bg-[#075e54] text-white px-4 pt-3 pb-2 flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-full bg-jklu-gold text-jklu-blue text-xs font-black flex items-center justify-center shrink-0">JK</span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold truncate">{title}</span>
            <span className="block text-[11px] text-emerald-100 truncate">{status ?? "WhatsApp (simulated)"}</span>
          </span>
        </div>

        <div ref={list} className="flex-1 overflow-y-auto px-2.5 py-3 space-y-1.5">
          {messages.length === 0 && !pendingText && (
            <div className="mt-16 text-center text-xs text-slate-600 px-6">
              <Smartphone className="w-6 h-6 mx-auto mb-1.5 text-slate-500" />
              No WhatsApp messages yet.{onSend ? " Send one to talk to the admissions agent." : ""}
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.direction === "inbound" ? "justify-end" : "justify-start"}`}>
              <div className={`${bubble} ${m.direction === "inbound" ? "bg-[#dcf8c6]" : "bg-white"} text-slate-900`}>
                <RichText text={m.text} citations={m.meta?.citations} />
                {m.meta?.citations?.length > 0 && (
                  <ol className="mt-1.5 pt-1 border-t border-slate-200 text-[10px] leading-snug text-slate-600">
                    {m.meta?.citations.map((c: string, i: number) => <li key={c} className="break-all">{i + 1}. {c}</li>)}
                  </ol>
                )}
                <p className="mt-0.5 flex items-center justify-end gap-1 text-[10px] text-slate-500">
                  {formatDateTime(m.sent_at)}
                  {m.direction === "inbound" && <CheckCheck className="w-3 h-3" />}
                </p>
              </div>
            </div>
          ))}
          {pendingText && (
            <div className="flex justify-end">
              <div className={`${bubble} bg-[#dcf8c6] text-slate-900 whitespace-pre-wrap break-words`}>{pendingText}</div>
            </div>
          )}
          {busy && (
            <div className="flex justify-start">
              <div className={`${bubble} bg-white text-slate-600 flex items-center gap-1.5`}>
                <Loader2 className="w-3 h-3 animate-spin" /> typing…
              </div>
            </div>
          )}
        </div>

        {onSend && (
          <form onSubmit={submit} className="p-2 flex items-center gap-1.5">
            <label htmlFor="whatsapp-input" className="sr-only">WhatsApp message</label>
            <input id="whatsapp-input" value={draft} onChange={(e) => setDraft(e.target.value)} disabled={disabled} maxLength={2000} autoComplete="off"
              placeholder="Type a message"
              className="flex-1 min-w-0 rounded-full bg-white px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#075e54] disabled:opacity-60" />
            <button type="submit" aria-label="Send WhatsApp message" disabled={disabled || !draft.trim()}
              className="w-9 h-9 rounded-full bg-[#075e54] text-white flex items-center justify-center shrink-0 disabled:opacity-50">
              <Send className="w-4 h-4" />
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
