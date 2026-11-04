import React, { useState } from "react";
import { BellOff } from "lucide-react";
import { errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { EmptyState, ErrorBanner, Loading, PageHeader } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Channel, ChannelMessage, Lead } from "../../lib/types";
import { streamChat, type AgentEvent } from "../agent/sse";
import { EmailInbox } from "./EmailInbox";
import { PhoneView } from "./PhoneView";

const POLL_MS = 5_000;
type ReplyChannel = Exclude<Channel, "web">;

/** What the agent is doing, in words a student understands. */
function statusFrom(e: AgentEvent): string | null {
  if (e.type === "plan") return "Understanding your message…";
  if (e.type === "tool_call") {
    if (e.data.name === "search_knowledge") return "Checking the knowledge base…";
    if (e.data.name === "book_slot" || e.data.name === "get_slots") return "Checking the calendar…";
    return "Working on it…";
  }
  if (e.type === "verify") return "Checking the answer…";
  return null;
}

function lastSession(messages: ChannelMessage[]): string | undefined {
  return [...messages].reverse().find((m) => m.meta?.session_id)?.meta?.session_id;
}

/** The student's simulated WhatsApp and email, showing real stored messages. Replies go through the agent. */
export const MessagesPage: React.FC = () => {
  const { user } = useAuth();
  const leadId = user?.lead_id ?? null;
  const messages = useApi<ChannelMessage[]>(leadId === null ? null : `/scheduling/messages/${leadId}`, POLL_MS);
  const lead = useApi<Lead>(leadId === null ? null : `/crm/leads/${leadId}`);
  const [sending, setSending] = useState<{ channel: ReplyChannel; text: string; afterId: number } | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reply(channel: ReplyChannel, text: string) {
    if (sending) return;
    setSending({ channel, text, afterId: Math.max(0, ...(messages.data ?? []).map((m) => m.id)) });
    setStatus("Sending…");
    setError(null);
    const history = (messages.data ?? []).filter((m) => m.channel === channel);
    try {
      await streamChat({ message: text, channel, session_id: lastSession(history) }, (ev) => {
        const next = statusFrom(ev);
        if (next) setStatus(next);
      });
      await Promise.all([messages.reload(), lead.reload()]);
    } catch (err) {
      setError(errorMessage(err));
      void messages.reload();
    } finally {
      setSending(null);
      setStatus(null);
    }
  }

  if (leadId === null) {
    return (
      <>
        <PageHeader title="My messages" />
        <EmptyState title="No messages yet" hint="Start a chat and your WhatsApp and email messages will appear here." />
      </>
    );
  }
  if (messages.loading && !messages.data) return <Loading label="Loading your messages…" />;

  const all = messages.data ?? [];
  const whatsapp = all.filter((m) => m.channel === "whatsapp");
  const email = all.filter((m) => m.channel === "email");
  const shared = { busy: false, disabled: Boolean(sending) };
  // The server stores the student's message as soon as it arrives; show it once, not twice.
  const stored = all.some((m) => sending && m.id > sending.afterId && m.direction === "inbound");
  const on = (channel: ReplyChannel) => (sending?.channel === channel
    ? { pendingText: stored ? null : sending.text, status, busy: true } : {});

  return (
    <>
      <PageHeader title="My messages" subtitle="Simulated channels for this demo. Nothing is really sent." />
      <div className="space-y-3 mb-4">
        {messages.error && <ErrorBanner message={messages.error} onRetry={() => void messages.reload()} />}
        {error && <ErrorBanner message={error} />}
        {lead.data?.opted_out && (
          <div role="status" className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-700">
            <BellOff className="w-4 h-4 shrink-0" />
            You've opted out, so we won't send you follow-ups. You can still write to us here.
          </div>
        )}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6 items-start">
        <PhoneView messages={whatsapp} title="JKLU Admissions" onSend={(t) => void reply("whatsapp", t)} {...shared} {...on("whatsapp")} />
        <EmailInbox messages={email} address={lead.data?.profile.email ?? user?.email ?? null} onSend={(t) => void reply("email", t)} {...shared} {...on("email")} />
      </div>
    </>
  );
};
