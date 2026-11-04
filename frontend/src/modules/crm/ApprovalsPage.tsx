import React, { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ShieldCheck, XCircle } from "lucide-react";
import { api, ApiError, errorMessage } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { leadName } from "../../lib/leads";
import { Badge, Button, Card, EmptyState, ErrorBanner, Loading, PageHeader, type Tone } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Approval, Booking, Lead } from "../../lib/types";

const POLL_MS = 10_000;

/** Fired after a decision, so the count in the navigation doesn't wait for its next refresh. */
export const APPROVALS_CHANGED = "approvals-changed";

const STATUS_TONE: Record<Approval["status"], Tone> = { pending: "amber", approved: "green", rejected: "red" };
const TABS = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
  { key: "", label: "All" },
];

const ACTION_LABEL: Record<string, string> = {
  fee_waiver: "Fee waiver request",
  booking_override: "Booking override",
  bulk_message: "Bulk message",
  escalate_question: "Question for a counsellor",
};

/** What approving does, so nobody has to guess before clicking. */
const APPROVE_EFFECT: Record<string, string> = {
  fee_waiver: "Records the waiver as approved and tells the student. The agent never states the terms, so write them here if you know them.",
  booking_override: "Force-books this slot for the lead. Anyone holding it loses it and is told, with other free times.",
  bulk_message: "Sends this exact text to every listed lead. Leads who opted out are refused.",
  escalate_question: "Sends your reply to the student. The knowledge base didn't answer this, so the answer has to come from you.",
};

const NEEDS_REPLY = new Set(["escalate_question"]);
const TAKES_REPLY = new Set(["escalate_question", "fee_waiver"]);

type Outcome = Record<string, any> | null;

function outcomeText(action: string, status: string, o: Outcome): string {
  if (status === "rejected") {
    return o?.notified ? "Rejected. The student was told the reason and offered a call." : "Rejected. The student could not be notified.";
  }
  if (action === "bulk_message") {
    const refused = o?.refused?.length ?? 0;
    return `Approved. Sent to ${o?.sent?.length ?? 0} lead(s)${refused ? `; ${refused} refused (opted out or not found)` : ""}.`;
  }
  if (action === "booking_override") {
    const moved = o?.displaced_lead_id ? ` Lead #${o.displaced_lead_id} lost the slot${o.displaced_notified ? " and was told" : " and could not be notified"}.` : "";
    return `Approved. Slot booked${o?.notified ? " and the student told" : ", but the student could not be notified"}.${moved}`;
  }
  return o?.notified ? "Approved. The student has been notified." : "Approved, but the student could not be notified (opted out or unreachable).";
}

const Detail: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div>
    <dt className="text-xs font-medium text-slate-500">{label}</dt>
    <dd className="text-sm text-slate-900 whitespace-pre-wrap break-words">{children}</dd>
  </div>
);

const Payload: React.FC<{ approval: Approval; bookings: Booking[] }> = ({ approval, bookings }) => {
  const p = approval.payload;
  const held = bookings.find((b) => b.slot_id === String(p.slot_id));
  return (
    <dl className="grid gap-2">
      {p.question && <Detail label="The student asked">{p.question}</Detail>}
      {p.reason && <Detail label={p.question ? "Why the agent passed it on" : "Reason given"}>{p.reason}</Detail>}
      {p.slot_id && (
        <Detail label="Slot">
          {held ? `${formatDateTime(held.start)} IST with ${held.counsellor}, now held by ${held.lead_name ?? `lead #${held.lead_id}`}` : `#${String(p.slot_id)} (not currently booked)`}
        </Detail>
      )}
      {approval.action === "bulk_message" && (
        <>
          <Detail label="Recipients">{p.lead_ids?.length ?? 0} lead(s) by {p.channel}</Detail>
          <Detail label="Message">{p.text}</Detail>
        </>
      )}
    </dl>
  );
};

const DecisionForm: React.FC<{ approval: Approval; onDone: (text: string) => void; onStale: (text: string) => void }> = ({ approval, onDone, onStale }) => {
  const [reply, setReply] = useState("");
  const [note, setNote] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const needsReply = NEEDS_REPLY.has(approval.action);

  async function decide(path: string, body: object, status: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ outcome: Outcome }>(`/crm/approvals/${approval.id}/${path}`, { body });
      onDone(outcomeText(approval.action, status, result.outcome));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        onStale(`${err.message}. Someone else decided it first, and your decision was not applied.`);
        return;
      }
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  const approve = () => decide("approve", { reply: reply.trim() || null, note: note.trim() || null }, "approved");
  const reject = () => decide("reject", { reason: reason.trim() }, "rejected");
  const field = "w-full text-sm rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50";

  return (
    <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
      <p className="text-xs text-slate-600">{APPROVE_EFFECT[approval.action] ?? "Runs this action."}</p>
      {TAKES_REPLY.has(approval.action) && !rejecting && (
        <div>
          <label htmlFor={`reply-${approval.id}`} className="block text-xs font-medium text-slate-600 mb-1">
            Your message to the student{needsReply ? " (required)" : " (optional)"}
          </label>
          <textarea id={`reply-${approval.id}`} rows={2} maxLength={2000} value={reply} disabled={busy}
            onChange={(e) => setReply(e.target.value)} className={field} />
        </div>
      )}
      {!rejecting && !needsReply && (
        <div>
          <label htmlFor={`note-${approval.id}`} className="block text-xs font-medium text-slate-600 mb-1">Note for the record (optional)</label>
          <input id={`note-${approval.id}`} maxLength={2000} value={note} disabled={busy} autoComplete="off"
            onChange={(e) => setNote(e.target.value)} className={field} />
        </div>
      )}
      {rejecting && (
        <div>
          <label htmlFor={`reason-${approval.id}`} className="block text-xs font-medium text-slate-600 mb-1">
            Reason for rejecting (required; the student sees this)
          </label>
          <textarea id={`reason-${approval.id}`} rows={2} maxLength={2000} value={reason} disabled={busy}
            onChange={(e) => setReason(e.target.value)} className={field} />
        </div>
      )}
      {error && <ErrorBanner message={error} />}
      <div className="flex flex-wrap gap-2">
        {rejecting ? (
          <>
            <Button variant="danger" busy={busy} disabled={!reason.trim()} onClick={() => void reject()}>Confirm rejection</Button>
            <Button variant="ghost" disabled={busy} onClick={() => setRejecting(false)}>Back</Button>
          </>
        ) : (
          <>
            <Button busy={busy} disabled={needsReply && !reply.trim()} onClick={() => void approve()}>
              {!busy && <CheckCircle2 className="w-4 h-4" />} {needsReply ? "Approve and send reply" : "Approve"}
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => setRejecting(true)}>
              <XCircle className="w-4 h-4" /> Reject
            </Button>
          </>
        )}
      </div>
    </div>
  );
};

const ApprovalCard: React.FC<{
  approval: Approval;
  lead?: Lead;
  bookings: Booking[];
  onDone: (id: number, text: string) => void;
  onStale: (id: number, text: string) => void;
}> = ({ approval, lead, bookings, onDone, onStale }) => (
  <li>
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <h2 className="text-sm font-semibold text-slate-900">#{approval.id} {ACTION_LABEL[approval.action] ?? approval.action.replace(/_/g, " ")}</h2>
        <Badge tone={STATUS_TONE[approval.status]}>{approval.status}</Badge>
        {lead?.opted_out && <Badge tone="violet">opted out</Badge>}
        <span className="ml-auto text-xs text-slate-500">{formatDateTime(approval.created_at)}</span>
      </div>
      <p className="text-xs text-slate-500 mb-2">
        {approval.lead_id !== null
          ? <>For <Link to={`/leads/${approval.lead_id}`} className="font-medium text-jklu-blue underline">{lead ? leadName(lead) : `Lead #${approval.lead_id}`}</Link> · </>
          : null}
        requested by {approval.requested_by_actor}
      </p>
      <Payload approval={approval} bookings={bookings} />
      {approval.status === "pending" ? (
        <DecisionForm approval={approval} onDone={(text) => onDone(approval.id, text)} onStale={(text) => onStale(approval.id, text)} />
      ) : (
        <p className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-600">
          {approval.status === "approved" ? "Approved" : "Rejected"}{approval.resolved_at ? ` ${formatDateTime(approval.resolved_at)}` : ""}
          {approval.reason ? ` · ${approval.status === "approved" ? "Note" : "Reason"}: ${approval.reason}` : ""}
        </p>
      )}
    </Card>
  </li>
);

/** The human gate: sensitive actions wait here and run only when staff approve. */
export const ApprovalsPage: React.FC = () => {
  const [tab, setTab] = useState("pending");
  const list = useApi<Approval[]>(`/crm/approvals${tab ? `?status=${tab}` : ""}`, POLL_MS);
  const leads = useApi<Lead[]>("/crm/leads", POLL_MS);
  const bookings = useApi<Booking[]>("/scheduling/bookings", POLL_MS);
  const [results, setResults] = useState<{ id: number; text: string; conflict: boolean }[]>([]);

  function record(id: number, text: string, conflict: boolean) {
    setResults((now) => [{ id, text, conflict }, ...now]);
    void list.reload();
    window.dispatchEvent(new Event(APPROVALS_CHANGED));
  }

  const leadById = new Map((leads.data ?? []).map((l) => [l.id, l]));

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader title="Approvals" subtitle="The agent can't grant anything. These run only after a person approves." />

      <div role="tablist" aria-label="Filter by status" className="flex gap-1 mb-4">
        {TABS.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              tab === t.key ? "bg-jklu-blue text-white font-medium" : "text-slate-600 hover:bg-slate-200"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {results.length > 0 && (
        <ul className="space-y-2 mb-4">
          {results.map((r) => (
            <li key={r.id} role="status" className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${
              r.conflict ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}>
              {r.conflict ? <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> : <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" />}
              <span><strong className="font-semibold">#{r.id}:</strong> {r.text}</span>
            </li>
          ))}
        </ul>
      )}

      {list.error && <div className="mb-3"><ErrorBanner message={list.error} onRetry={() => void list.reload()} /></div>}
      {list.loading && !list.data && <Loading label="Loading approvals…" />}
      {list.data && list.data.length === 0 && (
        <Card><EmptyState title={tab === "pending" ? "Nothing is waiting for a decision" : "No approvals here"} /></Card>
      )}
      {list.data && list.data.length > 0 && (
        <ul className="space-y-3">
          {list.data.map((a) => (
            <ApprovalCard key={a.id} approval={a} lead={a.lead_id !== null ? leadById.get(a.lead_id) : undefined}
              bookings={bookings.data ?? []} onDone={(id, text) => record(id, text, false)} onStale={(id, text) => record(id, text, true)} />
          ))}
        </ul>
      )}
    </div>
  );
};
