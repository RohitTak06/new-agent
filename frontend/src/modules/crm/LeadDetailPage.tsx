import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, BellOff, CalendarCheck, Loader2, ScrollText } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { formatDateTime, formatTime } from "../../lib/format";
import { leadName } from "../../lib/leads";
import { Badge, Card, EmptyState, ErrorBanner, Loading, type Tone } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Approval, Booking, ChannelMessage, Followup, Interaction, Lead } from "../../lib/types";
import { RichText } from "../agent/RichText";
import { LeadScoreCard } from "../intel/LeadScoreCard";

const POLL_MS = 10_000;

const STATUS_TONE: Record<string, Tone> = {
  pending: "warning", approved: "success", rejected: "danger", sent: "success", skipped: "neutral", failed: "danger",
};
const ACTOR_TONE: Record<string, Tone> = { student: "info", agent: "neutral", counsellor: "success" };

function humanize(value: string): string {
  return value.replace(/_/g, " ");
}

function messageSource(m: ChannelMessage): string {
  if (m.direction === "inbound") return "from the lead";
  if (m.meta?.followup_id) return `follow-up, written by ${m.meta.written_by === "llm" ? "the agent" : "template"}`;
  if (m.meta?.session_id) return "agent reply";
  return "sent after a counsellor's decision";
}

const STAGES: { value: string; label: string }[] = [
  { value: "new", label: "New" }, { value: "contacted", label: "Contacted" }, { value: "qualified", label: "Qualified" },
  { value: "converted", label: "Converted" }, { value: "lost", label: "Lost" },
];

/** The lead's pipeline stage. The agent moves it forward; a counsellor can set any stage, and the change is audited. */
const StageSelect: React.FC<{ lead: Lead; onChanged: () => void }> = ({ lead, onChanged }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function change(status: string) {
    setBusy(true);
    setError(null);
    try {
      await api<Lead>(`/crm/leads/${lead.id}/status`, { method: "PATCH", body: { status } });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5">
      <label htmlFor="lead-stage" className="text-xs font-medium text-ink-secondary">Stage</label>
      <select id="lead-stage" value={lead.status} disabled={busy} onChange={(e) => void change(e.target.value)}
        className="field w-auto pl-2.5 pr-8 py-1.5 font-medium disabled:opacity-60">
        {STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
      {busy && <Loader2 className="w-4 h-4 animate-spin text-ink-muted" aria-label="Saving" />}
      {error && <span role="alert" className="text-xs text-danger">{error}</span>}
    </span>
  );
};

const Field: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex justify-between gap-4 py-1.5 border-b border-line last:border-0 text-sm">
    <dt className="text-ink-secondary shrink-0">{label}</dt>
    <dd className="text-right text-ink min-w-0 break-words">
      {value === null || value === undefined || value === "" ? <span className="text-ink-muted">Not provided</span> : value}
    </dd>
  </div>
);

const Profile: React.FC<{ lead: Lead }> = ({ lead }) => {
  const p = lead.profile;
  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-ink mb-2">Profile</h2>
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
    <h2 className="text-sm font-semibold text-ink mb-2">Counsellor sessions</h2>
    {!bookings || bookings.length === 0 ? <p className="text-sm text-ink-muted">No sessions booked.</p> : (
      <ul className="space-y-2">
        {bookings.map((b) => (
          <li key={b.slot_id} className="flex items-start gap-2 text-sm">
            <CalendarCheck className={`w-4 h-4 mt-0.5 shrink-0 ${b.upcoming ? "text-success" : "text-ink-muted"}`} aria-hidden />
            <span>
              <span className="tabular-nums">{formatDateTime(b.start)} – {formatTime(b.end)} IST</span>
              <span className="block text-xs text-ink-muted">with {b.counsellor}{b.upcoming ? "" : " · past"}</span>
            </span>
          </li>
        ))}
      </ul>
    )}
  </Card>
);

const Row: React.FC<{ badges: React.ReactNode; when?: string; children: React.ReactNode }> = ({ badges, when, children }) => (
  <li className="px-4 py-3.5">
    <div className="flex flex-wrap items-center gap-1.5 mb-1">
      {badges}
      {when && <span className="ml-auto text-xs text-ink-muted tabular-nums whitespace-nowrap">{formatDateTime(when)}</span>}
    </div>
    {children}
  </li>
);

function renderInteractions(rows: Interaction[]) {
  return rows.map((r) => (
    <Row key={r.id} when={r.created_at} badges={<>
      <Badge tone={ACTOR_TONE[r.actor] ?? "neutral"}>{r.actor}</Badge>
      <Badge>{r.channel}</Badge>
      {r.meta?.escalated && <Badge tone="warning">escalated</Badge>}
    </>}>
      <div className="text-sm text-ink"><RichText text={r.message} citations={r.meta?.citations} /></div>
    </Row>
  ));
}

function renderMessages(rows: ChannelMessage[]) {
  return rows.map((m) => (
    <Row key={m.id} when={m.sent_at} badges={<>
      <Badge>{m.channel}</Badge>
      <span className="text-xs text-ink-muted">{messageSource(m)}</span>
    </>}>
      <div className="text-sm text-ink"><RichText text={m.text} citations={m.meta?.citations} /></div>
    </Row>
  ));
}

function renderApprovals(rows: Approval[]) {
  return rows.map((a) => (
    <Row key={a.id} when={a.created_at} badges={<>
      <Badge tone={STATUS_TONE[a.status]}>{a.status}</Badge>
      <span className="text-sm font-medium text-ink">#{a.id} {humanize(a.action)}</span>
    </>}>
      {(a.payload.question || a.payload.reason) && (
        <p className="text-sm text-ink-secondary">{a.payload.question ?? a.payload.reason}</p>
      )}
      {a.reason && <p className="text-xs text-ink-muted mt-1">Counsellor's note: {a.reason}</p>}
    </Row>
  ));
}

function renderFollowups(rows: Followup[]) {
  return rows.map((f) => (
    <Row key={f.id} when={f.due_at} badges={<>
      <Badge tone={STATUS_TONE[f.status]}>{f.status}</Badge>
      <span className="text-sm font-medium text-ink">{humanize(f.template)}</span>
    </>}>
      {f.payload?.outcome && <p className="text-xs text-ink-muted">Outcome: {humanize(String(f.payload.outcome))}</p>}
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
    <Link to="/pipeline" className="inline-flex items-center gap-1 rounded-lg text-sm text-ink-secondary hover:text-navy mb-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">
      <ArrowLeft className="w-4 h-4" aria-hidden /> Pipeline
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
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-6">
        <div className="min-w-0">
          <p className="text-13 font-medium text-ink-muted tabular-nums mb-1">Lead #{lead.data.id}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{leadName(lead.data)}</h1>
        </div>
        {lead.data.opted_out && <Badge tone="optout"><BellOff className="w-3 h-3" aria-hidden /> opted out of follow-ups</Badge>}
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <StageSelect lead={lead.data} onChanged={() => void lead.reload()} />
          <Link to={`/audit?lead_id=${leadId}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-sm font-medium text-ink-secondary hover:bg-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-1">
            <ScrollText className="w-4 h-4" aria-hidden /> Audit trail
          </Link>
        </div>
      </div>
      {lead.error && <div className="mb-3"><ErrorBanner message={lead.error} /></div>}

      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4 items-start">
        <div className="space-y-4">
          <LeadScoreCard scoreData={lead.data.score} />
          <Bookings bookings={bookings.data} />
          <Profile lead={lead.data} />
        </div>

        <Card className="min-w-0">
          <div role="tablist" aria-label="Lead activity" className="flex overflow-x-auto overflow-y-hidden border-b border-line px-2 scroll-quiet">
            {tabs.map((t) => (
              <button key={t.key} type="button" role="tab" aria-selected={t.key === active.key} onClick={() => setTab(t.key)}
                className={`px-3 py-3 text-sm whitespace-nowrap border-b-2 -mb-px transition-colors tabular-nums focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-navy ${
                  t.key === active.key ? "border-navy text-navy font-semibold" : "border-transparent text-ink-secondary hover:text-ink"}`}>
                {t.label}{t.state.data ? ` (${(t.state.data as unknown[]).length})` : ""}
              </button>
            ))}
          </div>
          <div role="tabpanel">
            {active.state.error && <div className="p-3"><ErrorBanner message={active.state.error} onRetry={() => void active.state.reload()} /></div>}
            {active.state.loading && !rows && <Loading />}
            {rows && rows.length === 0 && <EmptyState title={active.empty} />}
            {rows && rows.length > 0 && (
              <ul className="divide-y divide-line max-h-[calc(100dvh-13rem)] overflow-y-auto scroll-quiet">{active.render(rows)}</ul>
            )}
          </div>
        </Card>
      </div>
    </>
  );
};
