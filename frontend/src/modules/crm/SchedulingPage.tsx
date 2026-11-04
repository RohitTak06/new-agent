import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CalendarCheck, Clock, FastForward, Send, SkipForward } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { addDays, formatDateTime, formatDay, formatTime } from "../../lib/format";
import { leadName } from "../../lib/leads";
import { Badge, Button, Card, EmptyState, ErrorBanner, Loading, PageHeader } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Booking, ChannelMessage, Followup, Lead, Slot } from "../../lib/types";
import { RichText } from "../agent/RichText";

const POLL_MS = 10_000;

interface ClockState {
  now: string;
  offset_hours: number;
}

interface Processed {
  followup_id: number;
  lead_id: number;
  status: "sent" | "skipped";
  detail: string;
  message_id: number | null;
}

interface AdvanceResult extends ClockState {
  followups: { sent: number; skipped: number; processed: Processed[] };
}

interface FaultStatus {
  enabled: boolean;
  remaining: Record<string, number>;
}

function humanize(value: string): string {
  return value.replace(/_/g, " ");
}

const SKIP_REASON: Record<string, string> = {
  opted_out: "the lead opted out",
  lead_replied: "the lead has replied since",
};

/** The agent's follow-ups written by this run, so the demo shows the words and not just a count. */
async function loadSent(processed: Processed[]): Promise<Map<number, ChannelMessage>> {
  const leadIds = Array.from(new Set(processed.filter((p) => p.status === "sent").map((p) => p.lead_id)));
  const lists = await Promise.all(leadIds.map((id) => api<ChannelMessage[]>(`/scheduling/messages/${id}`)));
  return new Map(lists.flat().map((m) => [m.id, m]));
}

const ForwardResult: React.FC<{ result: AdvanceResult; messages: Map<number, ChannelMessage>; name: (id: number) => string }> = ({ result, messages, name }) => {
  const { processed, sent, skipped } = result.followups;
  return (
    <div role="status" className="mt-3 pt-3 border-t border-slate-100">
      <p className="text-sm font-medium text-slate-800">
        Clock moved to {formatDateTime(result.now)} IST: {sent} follow-up{sent === 1 ? "" : "s"} sent, {skipped} skipped.
      </p>
      {processed.length === 0 && <p className="text-xs text-slate-500 mt-1">Nothing was due in that time.</p>}
      <ul className="mt-2 space-y-2">
        {processed.map((p) => {
          const message = p.message_id !== null ? messages.get(p.message_id) : undefined;
          return (
            <li key={p.followup_id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="flex flex-wrap items-center gap-1.5 text-xs text-slate-700">
                {p.status === "sent"
                  ? <Badge tone="green"><Send className="w-3 h-3" aria-hidden /> sent by {p.detail}</Badge>
                  : <Badge><SkipForward className="w-3 h-3" aria-hidden /> skipped</Badge>}
                <Link to={`/leads/${p.lead_id}`} className="font-medium text-jklu-blue underline">{name(p.lead_id)}</Link>
                {p.status === "skipped" && <span>because {SKIP_REASON[p.detail] ?? humanize(p.detail)}</span>}
              </p>
              {message && (
                <div className="mt-1.5 text-sm text-slate-800">
                  <RichText text={message.text} citations={message.meta?.citations} />
                  <p className="text-[11px] text-slate-500 mt-1">
                    {message.meta?.written_by === "llm" ? "Written by the agent from the knowledge base" : "From a fixed template"}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
};

const FreeSlots: React.FC<{ slots: Slot[] }> = ({ slots }) => {
  const days = useMemo(() => {
    const byDay = new Map<string, Map<string, Slot[]>>();
    for (const slot of slots) {
      const day = byDay.get(slot.start.slice(0, 10)) ?? new Map<string, Slot[]>();
      day.set(slot.start, [...(day.get(slot.start) ?? []), slot]);
      byDay.set(slot.start.slice(0, 10), day);
    }
    return Array.from(byDay.entries());
  }, [slots]);

  return (
    <ul className="space-y-3">
      {days.map(([day, times]) => (
        <li key={day}>
          <p className="text-xs font-medium text-slate-600 mb-1">{formatDay(day)}</p>
          <ul className="flex flex-wrap gap-1">
            {Array.from(times.entries()).map(([start, free]) => (
              <li key={start} title={free.map((s) => s.counsellor).join(", ")}
                className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] text-slate-700">
                {formatTime(start)}{free.length > 1 ? ` · ${free.length} free` : ""}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
};

/** Admin only: makes the calendar fail so the demo can show retries and the fallback (S5). */
const FailureDemo: React.FC = () => {
  const status = useApi<FaultStatus>("/scheduling/faults", POLL_MS);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function arm(targets: string[], failures: number) {
    setBusy(true);
    setError(null);
    try {
      await Promise.all(targets.map((target) => api("/scheduling/faults", { body: { target, failures } })));
      await status.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (status.loading && !status.data) return null;
  const remaining = status.data?.remaining ?? {};
  const armed = Object.values(remaining).some((n) => n > 0);
  return (
    <Card className="p-4 border-amber-200">
      <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
        <AlertTriangle className="w-4 h-4 text-amber-600" aria-hidden /> Failure demo
        <Badge className="ml-auto">admin only</Badge>
      </h2>
      {status.error && <div className="mt-2"><ErrorBanner message={status.error} onRetry={() => void status.reload()} /></div>}
      {status.data && !status.data.enabled ? (
        <p className="text-xs text-slate-600 mt-1.5">Off. Start the API with ENABLE_FAULT_INJECTION=1 to use it.</p>
      ) : status.data && (
        <>
          <p className="text-xs text-slate-600 mt-1.5">
            Makes real calendar calls fail, then ask the agent to book a session in Test chat. It retries twice, then falls back.
          </p>
          <div className="flex flex-wrap gap-2 mt-3">
            <Button small variant="secondary" disabled={busy} onClick={() => void arm(["book_slot"], 3)}>Fail booking</Button>
            <Button small variant="secondary" disabled={busy} onClick={() => void arm(["book_slot", "get_slots"], 3)}>Fail whole calendar</Button>
            {armed && <Button small variant="ghost" disabled={busy} onClick={() => void arm(["book_slot", "get_slots"], 0)}>Clear</Button>}
          </div>
          <p role="status" className="text-xs mt-2 text-slate-600">
            {armed ? `Armed: next ${remaining.book_slot ?? 0} booking and ${remaining.get_slots ?? 0} availability calls will fail.` : "Not armed. The calendar is working normally."}
          </p>
        </>
      )}
      {error && <div className="mt-2"><ErrorBanner message={error} /></div>}
    </Card>
  );
};

/** The virtual clock, sessions, follow-ups and free slots. Fast-forward is how the demo shows follow-ups firing (S6). */
export const SchedulingPage: React.FC = () => {
  const { user } = useAuth();
  const clock = useApi<ClockState>("/scheduling/clock", POLL_MS);
  const bookings = useApi<Booking[]>("/scheduling/bookings", POLL_MS);
  const followups = useApi<Followup[]>("/scheduling/followups?status=pending", POLL_MS);
  const leads = useApi<Lead[]>("/crm/leads", POLL_MS);
  const today = clock.data?.now.slice(0, 10) ?? null;
  // Loaded once per day, not polled: each read would use up a failure armed for the failure demo.
  const slots = useApi<Slot[]>(today ? `/scheduling/slots?date_from=${today}&date_to=${addDays(today, 7)}` : null);
  const [advancing, setAdvancing] = useState<number | null>(null);
  const [result, setResult] = useState<AdvanceResult | null>(null);
  const [sentMessages, setSentMessages] = useState<Map<number, ChannelMessage>>(new Map());
  const [error, setError] = useState<string | null>(null);

  const leadById = new Map((leads.data ?? []).map((l) => [l.id, l]));
  const name = (id: number) => {
    const lead = leadById.get(id);
    return lead ? leadName(lead) : `Lead #${id}`;
  };

  async function fastForward(hours: number) {
    setAdvancing(hours);
    setError(null);
    try {
      const moved = await api<AdvanceResult>("/scheduling/clock/advance", { body: { hours } });
      setSentMessages(await loadSent(moved.followups.processed));
      setResult(moved);
      await Promise.all([clock.reload(), bookings.reload(), followups.reload()]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAdvancing(null);
    }
  }

  const upcoming = (bookings.data ?? []).filter((b) => b.upcoming);
  const pastCount = (bookings.data?.length ?? 0) - upcoming.length;
  const cell = "px-3 py-2 text-sm";
  const head = "px-3 py-2 font-medium";

  return (
    <>
      <PageHeader title="Scheduling" subtitle="Counsellor sessions and follow-ups, on the demo's virtual clock." />

      <Card className="p-4 mb-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Clock className="w-5 h-5 text-slate-500" aria-hidden />
            <div>
              <p className="text-xs text-slate-500">Virtual time (IST)</p>
              <p className="text-lg font-bold text-jklu-blue">{clock.data ? formatDateTime(clock.data.now) : "…"}</p>
            </div>
          </div>
          {clock.data && clock.data.offset_hours > 0 && <Badge tone="amber">{clock.data.offset_hours} h ahead of real time</Badge>}
          <div className="flex flex-wrap gap-2 ml-auto">
            {[24, 48].map((hours) => (
              <Button key={hours} busy={advancing === hours} disabled={advancing !== null} variant={hours === 24 ? "primary" : "secondary"}
                onClick={() => void fastForward(hours)}>
                {advancing !== hours && <FastForward className="w-4 h-4" />} Fast-forward {hours}h
              </Button>
            ))}
          </div>
        </div>
        {advancing !== null && <p role="status" className="text-xs text-slate-500 mt-2">Sending anything now due. The agent writes some follow-ups, so this can take up to 30 seconds.</p>}
        {clock.error && <div className="mt-3"><ErrorBanner message={clock.error} onRetry={() => void clock.reload()} /></div>}
        {error && <div className="mt-3"><ErrorBanner message={error} /></div>}
        {result && <ForwardResult result={result} messages={sentMessages} name={name} />}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 items-start">
        <div className="space-y-4 min-w-0">
          <Card className="overflow-hidden">
            <h2 className="px-4 pt-3 pb-2 text-sm font-semibold text-slate-800 flex items-center gap-1.5">
              <CalendarCheck className="w-4 h-4 text-slate-500" aria-hidden /> Upcoming sessions
              {pastCount > 0 && <span className="ml-auto text-xs font-normal text-slate-500">{pastCount} in the past</span>}
            </h2>
            {bookings.error && <div className="px-4 pb-3"><ErrorBanner message={bookings.error} onRetry={() => void bookings.reload()} /></div>}
            {bookings.loading && !bookings.data && <Loading />}
            {bookings.data && upcoming.length === 0 && <EmptyState title="No upcoming sessions" />}
            {upcoming.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="text-[11px] uppercase tracking-wide text-slate-500 bg-slate-50">
                    <tr><th scope="col" className={head}>When (IST)</th><th scope="col" className={head}>Counsellor</th><th scope="col" className={head}>Lead</th></tr>
                  </thead>
                  <tbody>
                    {upcoming.map((b) => (
                      <tr key={b.slot_id} className="border-t border-slate-100">
                        <td className={`${cell} whitespace-nowrap`}>{formatDateTime(b.start)}</td>
                        <td className={`${cell} whitespace-nowrap`}>{b.counsellor}</td>
                        <td className={cell}><Link to={`/leads/${b.lead_id}`} className="text-jklu-blue underline">{name(b.lead_id)}</Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card className="overflow-hidden">
            <h2 className="px-4 pt-3 pb-2 text-sm font-semibold text-slate-800">Pending follow-ups</h2>
            {followups.error && <div className="px-4 pb-3"><ErrorBanner message={followups.error} onRetry={() => void followups.reload()} /></div>}
            {followups.loading && !followups.data && <Loading />}
            {followups.data?.length === 0 && <EmptyState title="No follow-ups waiting" />}
            {followups.data && followups.data.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="text-[11px] uppercase tracking-wide text-slate-500 bg-slate-50">
                    <tr><th scope="col" className={head}>Due (IST)</th><th scope="col" className={head}>Follow-up</th><th scope="col" className={head}>Lead</th></tr>
                  </thead>
                  <tbody>
                    {followups.data.map((f) => (
                      <tr key={f.id} className="border-t border-slate-100">
                        <td className={`${cell} whitespace-nowrap`}>{formatDateTime(f.due_at)}</td>
                        <td className={`${cell} whitespace-nowrap`}>{humanize(f.template)}</td>
                        <td className={cell}><Link to={`/leads/${f.lead_id}`} className="text-jklu-blue underline">{name(f.lead_id)}</Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-4 min-w-0">
          {user?.role === "admin" && <FailureDemo />}
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-slate-800">Free sessions</h2>
            <p className="text-xs text-slate-500 mb-3">The next 50 in the coming week. Hover a time to see who's free.</p>
            {slots.error && <ErrorBanner message={slots.error} onRetry={() => void slots.reload()} />}
            {slots.loading && !slots.data && <Loading />}
            {slots.data?.length === 0 && <EmptyState title="No free sessions this week" />}
            {slots.data && slots.data.length > 0 && <FreeSlots slots={slots.data} />}
          </Card>
        </div>
      </div>
    </>
  );
};
