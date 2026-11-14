import React, { useState } from "react";
import { Link } from "react-router-dom";
import { BellOff, CalendarCheck, Flame, Users } from "lucide-react";
import { Card, EmptyState, ErrorBanner, Loading, PageHeader, StatTile } from "../../lib/ui";
import { useApi } from "../../lib/useApi";

const POLL_MS = 15_000;
const BAR_COLOR = "#2a78d6";

interface Funnel {
  total_leads: number;
  by_status: Record<string, number>;
  by_tier: Record<string, number>;
  by_channel: Record<string, number>;
  opted_out: number;
  booked_sessions: number;
  approvals: Record<string, number>;
}

interface Row {
  label: string;
  value: number;
  to?: string;
}

/** `link` turns a row's key into the page that lists those leads, so every bar can be opened. */
function rows(counts: Record<string, number>, order: [string, string][], link?: (key: string) => string): Row[] {
  return order.map(([key, label]) => ({ label, value: counts[key] ?? 0, to: link?.(key) }));
}

/** One series, one colour. Every value is labelled at the bar's tip; hovering or focusing adds its share; clicking opens the leads. */
const Bars: React.FC<{ title: string; subtitle?: string; data: Row[]; total: number; unit: string }> = ({ title, subtitle, data, total, unit }) => {
  const [active, setActive] = useState<string | null>(null);
  const scale = Math.max(1, ...data.map((d) => d.value));
  return (
    <Card className="p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {data.some((d) => d.to) && <span className="text-[11px] text-slate-400">Click a bar to see them</span>}
      </div>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      <ul className="mt-3 space-y-1">
        {data.map((d) => {
          const share = total ? Math.round((d.value / total) * 100) : 0;
          const Item = (d.to ? Link : "div") as React.ElementType;
          return (
            <li key={d.label} className="relative">
              <Item {...(d.to ? { to: d.to } : { tabIndex: 0 })} aria-label={`${d.label}: ${d.value} ${unit}, ${share} percent`}
              onPointerEnter={() => setActive(d.label)} onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(d.label)} onBlur={() => setActive(null)}
              className={`grid grid-cols-[96px_1fr] items-center gap-2 rounded-md px-1.5 py-1 -mx-1.5
                focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${d.to ? "hover:bg-slate-50 cursor-pointer" : ""}`}>
              <span className="text-xs text-slate-600 truncate">{d.label}</span>
              <span className="flex items-center gap-1.5 min-w-0">
                {d.value > 0 && (
                  <span className="h-5 rounded-r bg-[var(--bar)]" style={{ width: `calc((100% - 2.5rem) * ${d.value / scale})`, "--bar": BAR_COLOR } as React.CSSProperties} />
                )}
                <span className="text-xs font-semibold text-slate-900 tabular-nums">{d.value}</span>
              </span>
              </Item>
              {active === d.label && (
                <span role="tooltip" className="absolute right-0 -top-7 z-10 whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[11px] text-white shadow">
                  <strong className="font-semibold">{d.value}</strong> {unit} · {share}% {d.label.toLowerCase()}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
};

/** Where leads stand right now. Counts of current status, not a measure of conversion over time. */
export const AnalyticsPage: React.FC = () => {
  const { data, error, loading, reload } = useApi<Funnel>("/crm/analytics/funnel", POLL_MS);

  return (
    <>
      <PageHeader eyebrow="Insights" title="Analytics" subtitle="Where leads stand right now. Refreshed every 15 seconds. Click any number to open those leads." />
      {error && <div className="mb-3"><ErrorBanner message={error} onRetry={() => void reload()} /></div>}
      {loading && !data && <Loading label="Loading analytics…" />}
      {data && data.total_leads === 0 && <Card><EmptyState title="No leads yet" /></Card>}
      {data && data.total_leads > 0 && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatTile label="Total leads" value={data.total_leads} icon={Users} to="/pipeline" />
            <StatTile label="Hot leads" value={data.by_tier.hot ?? 0} icon={Flame} accent="text-rose-700 bg-rose-50"
              note={`${data.total_leads ? Math.round(((data.by_tier.hot ?? 0) / data.total_leads) * 100) : 0}% of all leads`} to="/pipeline?tier=hot" />
            <StatTile label="Sessions booked" value={data.booked_sessions} icon={CalendarCheck} accent="text-emerald-700 bg-emerald-50" to="/scheduling" />
            <StatTile label="Opted out" value={data.opted_out} icon={BellOff} accent="text-violet-700 bg-violet-50"
              note="No follow-ups go to these leads" to="/pipeline?opted_out=1" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Bars title="Leads by stage" subtitle="Each lead's current status" unit="leads" total={data.total_leads}
              data={rows(data.by_status, [["new", "New"], ["contacted", "Contacted"], ["qualified", "Qualified"], ["converted", "Converted"], ["lost", "Lost"]],
                (k) => `/pipeline?status=${k}`)} />
            <Bars title="Leads by score" unit="leads" total={data.total_leads}
              data={rows(data.by_tier, [["hot", "Hot"], ["warm", "Warm"], ["cold", "Cold"], ["None", "Not scored"]],
                (k) => `/pipeline?tier=${k === "None" ? "unscored" : k}`)} />
            <Bars title="Leads by channel" unit="leads" total={data.total_leads}
              data={rows(data.by_channel, [["web", "Website"], ["whatsapp", "WhatsApp"], ["email", "Email"]], (k) => `/pipeline?channel=${k}`)} />
            <Bars title="Approval requests" unit="requests" total={Object.values(data.approvals).reduce((a, b) => a + b, 0)}
              data={rows(data.approvals, [["pending", "Pending"], ["approved", "Approved"], ["rejected", "Rejected"]], () => "/approvals")} />
          </div>
        </>
      )}
    </>
  );
};
