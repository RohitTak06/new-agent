import React, { useEffect, useState } from "react";
import { Loader2, Mail } from "lucide-react";
import { formatDateTime } from "../../lib/format";
import { Button, Card, EmptyState } from "../../lib/ui";
import type { ChannelMessage } from "../../lib/types";
import { RichText } from "../agent/RichText";

interface Props {
  messages: ChannelMessage[];
  address: string | null;
  /** Leave out for a read-only view (staff looking at a lead). */
  onSend?: (text: string) => void;
  pendingText?: string | null;
  status?: string | null;
  busy?: boolean;
  disabled?: boolean;
}

/** Messages have no subject line, so the list shows what kind of email each one is. */
function subject(m: ChannelMessage): string {
  if (m.direction === "inbound") return "Your email to JKLU Admissions";
  if (m.meta?.followup_id) return "A follow-up from JKLU Admissions";
  if (m.meta?.session_id) return "Reply from the admissions agent";
  return "A message from a counsellor";
}

function preview(text: string): string {
  return text.replace(/\[[^\]\s]+\.md[^\]]*\]/g, "").replace(/\*\*/g, "").slice(0, 80);
}

/** A simulated email inbox: list on the left, the open email on the right. Nothing is really sent. */
export const EmailInbox: React.FC<Props> = ({ messages, address, onSend, pendingText, status, busy, disabled }) => {
  const [openId, setOpenId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const newestFirst = [...messages].reverse();
  const newestId = newestFirst[0]?.id ?? null;
  const open = newestFirst.find((m) => m.id === openId) ?? newestFirst[0];

  useEffect(() => {
    setOpenId(newestId);          // a new email (usually the reply just sent for) opens by itself
  }, [newestId]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !onSend) return;
    setDraft("");
    onSend(text);
  }

  return (
    <Card className="overflow-hidden flex flex-col min-h-[560px]">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <Mail className="w-4 h-4 text-slate-500" />
        <h2 className="text-sm font-semibold text-slate-800">Email inbox</h2>
        <span className="text-xs text-slate-500 truncate">{address ?? "no address on file"} · simulated</span>
      </div>

      <div className="flex-1 grid grid-cols-1 md:grid-cols-[230px_1fr] min-h-0">
        <ul aria-label="Emails" className="border-b md:border-b-0 md:border-r border-slate-100 overflow-y-auto max-h-48 md:max-h-[500px]">
          {pendingText && (
            <li className="px-3 py-2 border-b border-slate-100 bg-slate-50">
              <p className="text-xs font-medium text-slate-700">Sending…</p>
              <p className="text-xs text-slate-500 truncate">{pendingText}</p>
            </li>
          )}
          {newestFirst.map((m) => (
            <li key={m.id} className="border-b border-slate-100">
              <button type="button" onClick={() => setOpenId(m.id)} aria-current={open?.id === m.id}
                className={`w-full text-left px-3 py-2 hover:bg-slate-50 ${open?.id === m.id ? "bg-blue-50" : ""}`}>
                <span className="block text-xs font-medium text-slate-800 truncate">{subject(m)}</span>
                <span className="block text-xs text-slate-500 truncate">{preview(m.text)}</span>
                <span className="block text-[10px] text-slate-500 mt-0.5">{formatDateTime(m.sent_at)}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto p-4">
            {open ? (
              <article>
                <h3 className="text-sm font-semibold text-slate-900">{subject(open)}</h3>
                <p className="text-xs text-slate-500 mb-3">
                  {open.direction === "inbound" ? `From ${address ?? "you"} to JKLU Admissions` : `From JKLU Admissions to ${address ?? "you"}`}
                  {" · "}{formatDateTime(open.sent_at)} IST
                </p>
                <div className="text-sm text-slate-800"><RichText text={open.text} citations={open.meta?.citations} /></div>
                {open.meta?.citations?.length > 0 && (
                  <ol className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-500 space-y-0.5">
                    {open.meta?.citations.map((c: string, i: number) => <li key={c} className="break-all">{i + 1}. {c}</li>)}
                  </ol>
                )}
              </article>
            ) : (
              !pendingText && <EmptyState title="No emails yet" hint={onSend ? "Write below to email the admissions agent." : undefined} />
            )}
            {busy && (
              <p className="mt-4 flex items-center gap-1.5 text-xs text-slate-500">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> {status ?? "Writing a reply…"}
              </p>
            )}
          </div>

          {onSend && (
            <form onSubmit={submit} className="p-3 border-t border-slate-100 space-y-2">
              <label htmlFor="email-input" className="block text-xs font-medium text-slate-600">Email JKLU Admissions</label>
              <textarea id="email-input" value={draft} onChange={(e) => setDraft(e.target.value)} disabled={disabled} maxLength={2000} rows={2}
                className="w-full text-sm rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50" />
              <div className="flex justify-end">
                <Button type="submit" small disabled={disabled || !draft.trim()}>Send email</Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </Card>
  );
};
