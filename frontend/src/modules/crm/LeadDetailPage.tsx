import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, BellOff, CalendarCheck, ScrollText } from "lucide-react";
import { formatDateTime, formatTime } from "../../lib/format";
import { leadName } from "../../lib/leads";
import { Badge, Card, EmptyState, ErrorBanner, Loading, type Tone } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Approval, Booking, ChannelMessage, Followup, Interaction, Lead } from "../../lib/types";
import { RichText } from "../agent/RichText";
import { LeadScoreCard } from "../intel/LeadScoreCard";

const POLL_MS = 10_000;

const STATUS_TONE: Record<string, Tone> = {
  pending: "amber", approved: "green", rejected: "red", sent: "green", skipped: "neutral", failed: "red",
};
const ACTOR_TONE: Record<string, Tone> = { student: "blue", agent: "violet", counsellor: "green" };

function humanize(value: string): string {
  return value.replace(/_/g, " ");
}

function messageSource(m: ChannelMessage): string {
  if (m.direction === "inbound") return "from the lead";
  if (m.meta?.followup_id) return `follow-up, written by ${m.meta.written_by === "llm" ? "the agent" : "template"}`;
  if (m.meta?.session_id) return "agent reply";
  return "sent after a counsellor's decision";
}

const Field: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex justify-between gap-4 py-1.5 border-b border-slate-100 last:border-0 text-sm">
    <dt className="text-slate-500 shrink-0">{label}</dt>
    <dd className="text-right text-slate-900 min-w-0 break-words">
      {value === null || value === undefined || value === "" ? <span className="text-slate-400">Not provided</span> : value}
    </dd>
  </div>
);

const Profile: React.FC<{ lead: Lead }> = ({ lead }) => {
  const p = lead.profile;
  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-slate-800 mb-1">Profile</h2>
      <dl>
        <Field label="Email" value={p.email} />
        <Field label="Phone" value={p.phone} />
        <Field label="City" value={p.city} />
        <Field label="Program" value={p.program_interest} />
        <Field label="12th marks" value={p.twelfth_percent === null ? null : `${p.twelfth_percent}%`} />
        <Field label="Entrance exam" value={p.entrance_exam} />
        <Field label="Budget" value={p.budget_lakh === null ? null : `${p.budget_lakh} lakh`} />
        <Field label="Asked about scholarship" value={p.asked_scholarship ? "Yes" : "No"} />
        <Field label="Channel" value={p.channel} />
      </dl>
    </Card>
  );
};

const Bookings: React.FC<{ bookings: Booking[] | null }> = ({ bookings }) => (
  <Card className="p-4">
    <h2 className="text-sm font-semibold text-slate-800 mb-2">Counsellor sessions</h2>
    {!bookings || bookings.length === 0 ? <p className="text-sm text-slate-500">No sessions booked.</p> : (
      <ul className="space-y-2">
        {bookings.map((b) => (
          <li key={b.slot_id} className="flex items-start gap-2 text-sm">
            <CalendarCheck className={`w-4 h-4 mt-0.5 shrink-0 ${b.upcoming ? "text-emerald-600" : "text-slate-400"}`} aria-hidden />
            <span>
              {formatDateTime(b.start)} – {formatTime(b.end)} IST
              <span className="block text-xs text-slate-500">with {b.counsellor}{b.upcoming ? "" : " · past"}</span>
            </span>
          </li>
        ))}
      </ul>
    )}
  </Card>
);

const Row: React.FC<{ badges: React.ReactNode; when?: string; children: React.ReactNode }> = ({ badges, when, children }) => (
  <li className="px-4 py-3">
    <div className="flex flex-wrap items-center gap-1.5 mb-1">
      {badges}
      {when && <span className="ml-auto text-[11px] text-slate-500 whitespace-nowrap">{formatDateTime(when)}</span>}
    </div>
    {children}
  </li>
);

function renderInteractions(rows: Interaction[]) {
  return rows.map((r) => (
    <Row key={r.id} when={r.created_at} badges={<>
      <Badge tone={ACTOR_TONE[r.actor] ?? "neutral"}>{r.actor}</Badge>
      <Badge>{r.channel}</Badge>
      {r.meta?.escalated && <Badge tone="red">escalated</Badge>}
    </>}>
      <div className="text-sm text-slate-800"><RichText text={r.message} citations={r.meta?.citations} /></div>
    </Row>
  ));
}

function renderMessages(rows: ChannelMessage[]) {
  return rows.map((m) => (
    <Row key={m.id} when={m.sent_at} badges={<>
      <Badge>{m.channel}</Badge>
      <span className="text-xs text-slate-500">{messageSource(m)}</span>
    </>}>
      <div className="text-sm text-slate-800"><RichText text={m.text} citations={m.meta?.citations} /></div>
    </Row>
  ));
}

function renderApprovals(rows: Approval[]) {
  return rows.map((a) => (
    <Row key={a.id} when={a.created_at} badges={<>
      <Badge tone={STATUS_TONE[a.status]}>{a.status}</Badge>
      <span className="text-sm font-medium text-slate-800">#{a.id} {humanize(a.action)}</span>
    </>}>
      {(a.payload.question || a.payload.reason) && (
        <p className="text-sm text-slate-700">{a.payload.question ?? a.payload.reason}</p>
      )}
      {a.reason && <p className="text-xs text-slate-500 mt-1">Counsellor's note: {a.reason}</p>}
    </Row>
  ));
}

function renderFollowups(rows: Followup[]) {
  return rows.map((f) => (
    <Row key={f.id} when={f.due_at} badges={<>
      <Badge tone={STATUS_TONE[f.status]}>{f.status}</Badge>
      <span className="text-sm font-medium text-slate-800">{humanize(f.template)}</span>
    </>}>
      {f.payload?.outcome && <p className="text-xs text-slate-500">Outcome: {humanize(String(f.payload.outcome))}</p>}
    </Row>
  ));
}

/** Everything staff need on one lead. Each section refreshes on its own. */
export const LeadDetailPage: React.FC = () => {
  const { id } = useParams();
  const leadId = /^\d+$/.test(id ?? "") ? Number(id) : null;
  const path = (template: string) => (leadId === null ? null : template.replace("{id}", String(leadId)));
  const lead = useApi<Lead>(path("/crm/leads/{id}"), POLL_MS);
  const interactions = useApi<Interaction[]>(path("/crm/leads/{id}/interactions"), POLL_MS);
  const messages = useApi<ChannelMessage[]>(path("/scheduling/messages/{id}"), POLL_MS);
  const bookings = useApi<Booking[]>(path("/scheduling/bookings?lead_id={id}"), POLL_MS);
  const followups = useApi<Followup[]>(path("/scheduling/followups?lead_id={id}"), POLL_MS);
  const approvals = useApi<Approval[]>(path("/crm/approvals?lead_id={id}"), POLL_MS);
  const [tab, setTab] = useState("conversation");

  const back = (
    <Link to="/pipeline" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-jklu-blue mb-3">
      <ArrowLeft className="w-4 h-4" /> Pipeline
    </Link>
  );
  if (leadId === null) return <>{back}<ErrorBanner message="That isn't a valid lead link." /></>;
  if (lead.loading && !lead.data) return <>{back}<Loading label="Loading lead…" /></>;
  if (!lead.data) return <>{back}<ErrorBanner message={lead.error ?? "Lead not found"} onRetry={() => void lead.reload()} /></>;

  const tabs = [
    { key: "conversation", label: "Conversation", state: interactions, render: renderInteractions as (rows: any[]) => React.ReactNode, empty: "No conversation yet" },
    { key: "messages", label: "Channel messages", state: messages, render: renderMessages as (rows: any[]) => React.ReactNode, empty: "No WhatsApp or email messages yet" },
    { key: "approvals", label: "Requests", state: approvals, render: renderApprovals as (rows: any[]) => React.ReactNode, empty: "No requests for approval" },
    { key: "followups", label: "Follow-ups", state: followups, render: renderFollowups as (rows: any[]) => React.ReactNode, empty: "No follow-ups scheduled" },
  ];
  const active = tabs.find((t) => t.key === tab) ?? tabs[0];
  const rows = active.state.data as unknown[] | null;

  return (
    <>
      {back}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <h1 className="text-xl font-bold text-jklu-blue">{leadName(lead.data)}</h1>
        <Badge>{lead.data.status}</Badge>
        {lead.data.opted_out && <Badge tone="violet"><BellOff className="w-3 h-3" aria-hidden /> opted out of follow-ups</Badge>}
        <Link to={`/audit?lead_id=${leadId}`} className="ml-auto inline-flex items-center gap-1 text-sm text-jklu-blue underline">
          <ScrollText className="w-4 h-4" /> Audit trail
        </Link>
      </div>
      {lead.error && <div className="mb-3"><ErrorBanner message={lead.error} /></div>}

      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4 items-start">
        <div className="space-y-4">
          <LeadScoreCard scoreData={lead.data.score} />
          <Bookings bookings={bookings.data} />
          <Profile lead={lead.data} />
        </div>

        <Card className="min-w-0">
          <div role="tablist" aria-label="Lead activity" className="flex overflow-x-auto overflow-y-hidden border-b border-slate-200 px-2">
            {tabs.map((t) => (
              <button key={t.key} type="button" role="tab" aria-selected={t.key === active.key} onClick={() => setTab(t.key)}
                className={`px-3 py-2.5 text-sm whitespace-nowrap border-b-2 transition-colors ${
                  t.key === active.key ? "border-jklu-blue text-jklu-blue font-semibold" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
                {t.label}{t.state.data ? ` (${(t.state.data as unknown[]).length})` : ""}
              </button>
            ))}
          </div>
          <div role="tabpanel">
            {active.state.error && <div className="p-3"><ErrorBanner message={active.state.error} onRetry={() => void active.state.reload()} /></div>}
            {active.state.loading && !rows && <Loading />}
            {rows && rows.length === 0 && <EmptyState title={active.empty} />}
            {rows && rows.length > 0 && (
              <ul className="divide-y divide-slate-100 max-h-[calc(100dvh-13rem)] overflow-y-auto">{active.render(rows)}</ul>
            )}
          </div>
        </Card>
      </div>
    </>
  );
};
