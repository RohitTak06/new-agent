import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronRight, Lock, RefreshCw } from "lucide-react";
import { query } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { Badge, Button, Card, EmptyState, ErrorBanner, Loading, PageHeader, type Tone } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { AuditRow } from "../../lib/types";

const PAGE_SIZE = 50;

const EVENT_TYPES = [
  "plan", "tool_call", "tool_result", "verify", "retry", "escalation", "error", "final", "approval_requested",
  "approval_decision", "approval_execution_failed", "api_action", "followup", "channel_message", "login", "access_denied", "rate_limited",
];

const TONE: Record<string, Tone> = {
  plan: "info", verify: "success", final: "neutral", retry: "warning", escalation: "warning", approval_requested: "warning",
  approval_decision: "success", approval_execution_failed: "danger", error: "danger", access_denied: "danger", rate_limited: "danger",
};

const FILTERS = ["lead_id", "session_id", "type", "from", "to"] as const;
type Filters = Record<(typeof FILTERS)[number], string>;

/** The date inputs are in IST, like the rest of the app, whatever timezone this browser is in. */
function toInstant(local: string): string {
  return local ? `${local}:00+05:30` : "";
}

const Json: React.FC<{ label: string; value: unknown }> = ({ label, value }) => (
  value === null || value === undefined ? null : (
    <div className="min-w-0">
      <p className="text-xs font-medium text-ink-secondary mb-1">{label}</p>
      <pre className="text-xs leading-snug bg-surface text-ink border border-line rounded-lg p-3 overflow-x-auto max-h-64 whitespace-pre-wrap break-words scroll-quiet">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
);

const Row: React.FC<{ row: AuditRow; onFilter: (key: keyof Filters, value: string) => void }> = ({ row, onFilter }) => {
  const [open, setOpen] = useState(false);
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <>
      <tr className="border-t border-line align-top hover:bg-subtle">
        <td className="pl-2 py-2 w-6">
          <button type="button" aria-expanded={open} aria-label={`${open ? "Hide" : "Show"} details of audit row ${row.id}`} onClick={() => setOpen(!open)}
            className="p-0.5 rounded-lg text-ink-muted hover:bg-line hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">
            <Chevron className="w-4 h-4" aria-hidden />
          </button>
        </td>
        <td className="px-2 py-2 text-xs text-ink-muted tabular-nums whitespace-nowrap">#{row.id}</td>
        <td className="px-2 py-2 text-xs text-ink-secondary tabular-nums whitespace-nowrap">{formatDateTime(row.created_at)}</td>
        <td className="px-2 py-2 text-xs text-ink whitespace-nowrap max-w-[160px] truncate" title={row.actor}>{row.actor}</td>
        <td className="px-2 py-2 whitespace-nowrap"><Badge tone={TONE[row.event_type] ?? "neutral"}>{row.event_type.replace(/_/g, " ")}</Badge></td>
        <td className="px-2 py-2 text-xs font-mono text-ink-secondary whitespace-nowrap max-w-[150px] truncate" title={row.tool_name ?? ""}>{row.tool_name ?? ""}</td>
        <td className="px-2 py-2 text-xs text-ink-secondary min-w-[180px]">{row.reasoning_step ?? ""}</td>
        <td className="px-2 py-2 text-xs whitespace-nowrap">
          {row.lead_id !== null && <Link to={`/leads/${row.lead_id}`} className="text-navy underline underline-offset-2 tabular-nums">#{row.lead_id}</Link>}
        </td>
      </tr>
      {open && (
        <tr className="bg-subtle">
          <td colSpan={8} className="px-4 pb-4 pt-2">
            <div className="flex flex-wrap gap-2 mb-2 text-xs">
              {row.lead_id !== null && <Button small variant="secondary" onClick={() => onFilter("lead_id", String(row.lead_id))}>Only this lead</Button>}
              {row.session_id && <Button small variant="secondary" onClick={() => onFilter("session_id", row.session_id as string)}>Only this conversation</Button>}
              {row.approval_id !== null && <Badge tone="warning">approval #{row.approval_id}</Badge>}
              {row.request_id && <span className="text-ink-secondary self-center break-all">request {row.request_id}</span>}
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <Json label="Input" value={row.input} />
              <Json label="Output" value={row.output} />
            </div>
            {row.input === null && row.output === null && <p className="text-xs text-ink-secondary">No input or output recorded.</p>}
          </td>
        </tr>
      )}
    </>
  );
};

/** Read-only view of the audit log. Filters live in the URL, so a view can be linked to from a lead. */
export const AuditPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const applied: Filters = {
    lead_id: params.get("lead_id") ?? "", session_id: params.get("session_id") ?? "", type: params.get("type") ?? "",
    from: params.get("from") ?? "", to: params.get("to") ?? "",
  };
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const [draft, setDraft] = useState<Filters>(applied);
  const appliedKey = JSON.stringify(applied);

  useEffect(() => setDraft(JSON.parse(appliedKey)), [appliedKey]);

  const path = `/crm/audit${query({
    lead_id: applied.lead_id, session_id: applied.session_id, type: applied.type,
    from: toInstant(applied.from), to: toInstant(applied.to), limit: PAGE_SIZE, offset,
  })}`;
  const { data, error, loading, reload } = useApi<AuditRow[]>(path);

  function apply(next: Filters, nextOffset = 0) {
    const clean = Object.entries(next).filter(([, v]) => v.trim());
    setParams(Object.fromEntries([...clean.map(([k, v]) => [k, v.trim()]), ...(nextOffset ? [["offset", String(nextOffset)]] : [])]));
  }

  const update = (key: keyof Filters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setDraft({ ...draft, [key]: e.target.value });
  const field = "field py-1.5";
  const label = "block text-xs font-medium text-ink-secondary mb-1";
  const filtered = FILTERS.some((k) => applied[k]);

  return (
    <>
      <PageHeader eyebrow="Operations" title="Audit log" subtitle="Every agent step, tool call, decision and refusal, newest first."
        actions={
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1 text-xs text-ink-muted"><Lock className="w-4 h-4" aria-hidden /> Append-only</span>
            <Button variant="secondary" small onClick={() => void reload()}><RefreshCw className="w-4 h-4" aria-hidden /> Refresh</Button>
          </div>
        } />

      <Card className="p-4 mb-4">
        <form onSubmit={(e) => { e.preventDefault(); apply(draft); }} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[90px_1fr_170px_190px_190px_auto] items-end">
          <div>
            <label htmlFor="f-lead" className={label}>Lead</label>
            <input id="f-lead" inputMode="numeric" pattern="[0-9]*" value={draft.lead_id} onChange={update("lead_id")} className={field} />
          </div>
          <div>
            <label htmlFor="f-session" className={label}>Conversation ID</label>
            <input id="f-session" value={draft.session_id} onChange={update("session_id")} autoComplete="off" className={field} />
          </div>
          <div>
            <label htmlFor="f-type" className={label}>Event type</label>
            <select id="f-type" value={draft.type} onChange={update("type")} className={field}>
              <option value="">All</option>
              {EVENT_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="f-from" className={label}>From (IST)</label>
            <input id="f-from" type="datetime-local" value={draft.from} onChange={update("from")} className={field} />
          </div>
          <div>
            <label htmlFor="f-to" className={label}>To (IST)</label>
            <input id="f-to" type="datetime-local" value={draft.to} onChange={update("to")} className={field} />
          </div>
          <div className="flex gap-2">
            <Button type="submit" small className="py-2">Apply</Button>
            {filtered && <Button small variant="ghost" className="py-2" onClick={() => setParams({})}>Clear</Button>}
          </div>
        </form>
      </Card>

      {error && <div className="mb-3"><ErrorBanner message={error} onRetry={() => void reload()} /></div>}
      {loading && !data && <Loading label="Loading audit log…" />}
      {data && data.length === 0 && <Card><EmptyState title="No audit rows match" hint={filtered ? "Try fewer filters." : undefined} /></Card>}
      {data && data.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="text-xs text-ink-secondary bg-subtle border-b border-line">
                <tr>
                  <th scope="col" className="pl-2 py-2"><span className="sr-only">Details</span></th>
                  <th scope="col" className="px-2 py-2 font-medium">Row</th>
                  <th scope="col" className="px-2 py-2 font-medium">When (IST)</th>
                  <th scope="col" className="px-2 py-2 font-medium">Actor</th>
                  <th scope="col" className="px-2 py-2 font-medium">Event</th>
                  <th scope="col" className="px-2 py-2 font-medium">Tool</th>
                  <th scope="col" className="px-2 py-2 font-medium">Reason</th>
                  <th scope="col" className="px-2 py-2 font-medium">Lead</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row) => <Row key={row.id} row={row} onFilter={(key, value) => apply({ ...applied, [key]: value })} />)}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-t border-line text-xs text-ink-secondary">
            <span className="tabular-nums">Showing {offset + 1}–{offset + data.length}</span>
            <div className="flex gap-2">
              <Button small variant="secondary" disabled={offset === 0} onClick={() => apply(applied, Math.max(0, offset - PAGE_SIZE))}>Newer</Button>
              <Button small variant="secondary" disabled={data.length < PAGE_SIZE} onClick={() => apply(applied, offset + PAGE_SIZE)}>Older</Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
};
