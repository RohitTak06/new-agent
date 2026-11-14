import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BellOff, Globe, Mail, MessageCircle, Search, Sparkles, X } from "lucide-react";
import { isAnonymous, leadName, TIER_TONE } from "../../lib/leads";
import { Badge, Card, EmptyState, ErrorBanner, Loading, PageHeader, type Tone } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Channel, Lead, Tier } from "../../lib/types";

const POLL_MS = 10_000;
const HIGHLIGHT_MS = 20_000;

type Column = Tier | "unscored";

const COLUMNS: { key: Column; label: string; tone: Tone; rule: string }[] = [
  { key: "hot", label: "Hot", tone: TIER_TONE.hot, rule: "bg-danger" },
  { key: "warm", label: "Warm", tone: TIER_TONE.warm, rule: "bg-warning" },
  { key: "cold", label: "Cold", tone: TIER_TONE.cold, rule: "bg-info" },
  { key: "unscored", label: "Not scored yet", tone: "neutral", rule: "bg-line-strong" },
];

const CHANNEL_ICON: Record<Channel, React.ElementType> = { web: Globe, whatsapp: MessageCircle, email: Mail };

function columnOf(lead: Lead): Column {
  return lead.score?.tier ?? "unscored";
}

/** Filters that Analytics links to, e.g. /pipeline?tier=hot or ?status=qualified. All applied here, on the loaded leads. */
const FILTERS: { key: string; label: (v: string) => string; test: (lead: Lead, v: string) => boolean }[] = [
  { key: "tier", label: (v) => (v === "unscored" ? "Not scored" : `${v[0].toUpperCase()}${v.slice(1)} leads`), test: (l, v) => columnOf(l) === v },
  { key: "status", label: (v) => `Stage: ${v}`, test: (l, v) => l.status === v },
  { key: "channel", label: (v) => `Channel: ${v === "web" ? "website" : v}`, test: (l, v) => l.profile.channel === v },
  { key: "opted_out", label: () => "Opted out", test: (l) => l.opted_out },
];

/** Highest score first; anonymous visitors go last, because there's nobody to contact yet. */
function byPriority(a: Lead, b: Lead): number {
  const anonymous = Number(isAnonymous(a)) - Number(isAnonymous(b));
  return anonymous || (b.score?.score ?? -1) - (a.score?.score ?? -1) || b.id - a.id;
}

function matches(lead: Lead, term: string): boolean {
  const p = lead.profile;
  return [leadName(lead), p.email, p.phone, p.city, p.program_interest, lead.status, String(lead.id)]
    .some((value) => value?.toLowerCase().includes(term));
}

/** Leads that are new or changed tier since the last refresh, so they stand out during a live demo. */
function useRecentChanges(leads: Lead[] | null): Set<number> {
  const seen = useRef<Map<number, Column> | null>(null);
  const [recent, setRecent] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!leads) return;
    const before = seen.current;
    seen.current = new Map(leads.map((l) => [l.id, columnOf(l)]));
    if (!before) return;
    const changed = leads.filter((l) => before.get(l.id) !== columnOf(l)).map((l) => l.id);
    if (changed.length === 0) return;
    setRecent((now) => new Set([...now, ...changed]));
    // Not cleared on the next refresh: `leads` changes every 10 seconds, and the highlight must still end.
    setTimeout(() => {
      setRecent((now) => new Set([...now].filter((id) => !changed.includes(id))));
    }, HIGHLIGHT_MS);
  }, [leads]);

  return recent;
}

const LeadCard: React.FC<{ lead: Lead; highlighted: boolean }> = ({ lead, highlighted }) => {
  const Icon = CHANNEL_ICON[lead.profile.channel];
  const anonymous = isAnonymous(lead);
  return (
    <li>
      <Link to={`/leads/${lead.id}`}
        className={`block rounded-lg border bg-surface px-3 py-2.5 shadow-card hover:border-line-strong transition-colors
          focus:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-1
          ${highlighted ? "border-navy ring-2 ring-navy/20" : "border-line"}`}>
        <div className="flex items-start justify-between gap-2">
          <p className={`text-sm font-medium truncate ${anonymous ? "text-ink-muted" : "text-ink"}`}>{leadName(lead)}</p>
          {lead.score && <span className="text-sm font-semibold tabular-nums text-ink">{lead.score.score}</span>}
        </div>
        <p className="text-xs text-ink-secondary truncate">
          {[lead.profile.program_interest, lead.profile.city].filter(Boolean).join(" · ") || "No details yet"}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          <Badge><Icon className="w-3 h-3" aria-hidden /> {lead.profile.channel}</Badge>
          <Badge>{lead.status}</Badge>
          {lead.opted_out && <Badge tone="optout"><BellOff className="w-3 h-3" aria-hidden /> opted out</Badge>}
          {highlighted && <Badge tone="info"><Sparkles className="w-3 h-3" aria-hidden /> just updated</Badge>}
        </div>
      </Link>
    </li>
  );
};

/** Staff board of every lead by tier. Refreshes itself, so a lead scored in a chat appears on its own. */
export const PipelinePage: React.FC = () => {
  const { data, error, loading, reload } = useApi<Lead[]>("/crm/leads", POLL_MS);
  const [search, setSearch] = useState("");
  const [params, setParams] = useSearchParams();
  const recent = useRecentChanges(data);
  const term = search.trim().toLowerCase();
  const active = FILTERS.filter((f) => params.get(f.key)).map((f) => ({ ...f, value: params.get(f.key) ?? "" }));
  const filterKey = active.map((f) => `${f.key}=${f.value}`).join("&");

  const columns = useMemo(() => {
    const shown = (data ?? [])
      .filter((l) => !term || matches(l, term))
      .filter((l) => active.every((f) => f.test(l, f.value)))
      .sort(byPriority);
    return COLUMNS.map((c) => ({ ...c, leads: shown.filter((l) => columnOf(l) === c.key) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, term, filterKey]);
  const shownCount = columns.reduce((n, c) => n + c.leads.length, 0);

  function clear(key?: string) {
    const next = new URLSearchParams(params);
    for (const f of FILTERS) if (!key || f.key === key) next.delete(f.key);
    setParams(next, { replace: true });
  }

  return (
    <>
      <PageHeader eyebrow="Leads" title="Lead pipeline" subtitle={data ? `${data.length} leads by score, refreshed every 10 seconds` : undefined}
        actions={
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-ink-muted absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden />
            <label htmlFor="lead-search" className="sr-only">Search leads</label>
            <input id="lead-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, program, city…"
              className="field w-full pl-8" />
          </div>
        } />

      {active.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-xs text-ink-secondary">Showing</span>
          {active.map((f) => (
            <button key={f.key} type="button" onClick={() => clear(f.key)} aria-label={`Remove filter ${f.label(f.value)}`}
              className="inline-flex items-center gap-1 rounded-lg border border-line-strong bg-surface px-2.5 py-1 text-xs font-medium text-ink hover:bg-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">
              {f.label(f.value)} <X className="w-3 h-3" aria-hidden />
            </button>
          ))}
          <span className="text-xs text-ink-secondary tabular-nums">· {shownCount} of {data?.length ?? 0}</span>
          <button type="button" onClick={() => clear()} className="text-xs text-ink-secondary underline hover:text-navy">Show all</button>
        </div>
      )}
      {error && <div className="mb-3"><ErrorBanner message={error} onRetry={() => void reload()} /></div>}
      {loading && !data && <Loading label="Loading leads…" />}
      {data && (term || active.length > 0) && shownCount === 0 && (
        <Card><EmptyState title={term ? `No leads match "${search.trim()}"` : "No leads match these filters"} /></Card>
      )}
      {data && data.length === 0 && <Card><EmptyState title="No leads yet" hint="A lead appears here when someone starts a chat." /></Card>}

      {data && data.length > 0 && shownCount > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 items-start">
          {columns.map((c) => (
            <section key={c.key} aria-label={`${c.label} leads`}
              className="rounded-xl border border-line bg-subtle flex flex-col xl:max-h-[calc(100dvh-12rem)]">
              <h2 className="px-3 py-2.5 flex items-center justify-between text-sm font-semibold text-ink">
                <span className="flex items-center gap-2"><span className={`w-2 h-2 rounded-full ${c.rule}`} aria-hidden />{c.label}</span>
                <Badge tone={c.tone}><span className="tabular-nums">{c.leads.length}</span></Badge>
              </h2>
              {c.leads.length === 0 ? (
                <p className="px-3 pb-3 text-xs text-ink-secondary">None</p>
              ) : (
                <ul className="px-2 pb-2 space-y-1.5 overflow-y-auto scroll-quiet">
                  {c.leads.map((lead) => <LeadCard key={lead.id} lead={lead} highlighted={recent.has(lead.id)} />)}
                </ul>
              )}
            </section>
          ))}
        </div>
      )}
    </>
  );
};
