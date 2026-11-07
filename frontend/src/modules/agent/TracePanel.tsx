import React, { useEffect, useRef } from "react";
import { AlertTriangle, CheckCircle2, ListChecks, Loader2, RotateCw, ShieldAlert, Wrench, XCircle } from "lucide-react";
import { formatDateTime } from "../../lib/format";
import { TIER_TONE } from "../../lib/leads";
import { Badge } from "../../lib/ui";
import type { Tier } from "../../lib/types";
import type { AgentEvent } from "./sse";

type RowKind = "plan" | "action" | "check" | "problem" | "counsellor" | "done";

const STYLE: Record<RowKind, string> = {
  plan: "border-indigo-200 bg-indigo-50 text-indigo-900",
  action: "border-slate-200 bg-slate-50 text-slate-700",
  check: "border-emerald-200 bg-emerald-50 text-emerald-900",
  problem: "border-amber-200 bg-amber-50 text-amber-900",
  counsellor: "border-rose-200 bg-rose-50 text-rose-900",
  done: "border-blue-200 bg-blue-50 text-blue-900",
};

const ICON: Record<RowKind, React.ElementType> = {
  plan: ListChecks, action: Wrench, check: CheckCircle2, problem: AlertTriangle, counsellor: ShieldAlert, done: CheckCircle2,
};

const CHECK_NAME: Record<string, string> = {
  grounding: "sources", booking: "booking claims", no_false_grant: "false promises", figures: "figures",
  injection: "rule tampering", outbound: "outgoing message",
};

const RECOVERY: Record<string, string> = {
  replan: "Rewriting the answer.", escalate: "Passing it to a counsellor.", refuse: "Refusing the request.",
};

const SOURCE_NAME: Record<string, string> = {
  programs_and_fees: "programmes and fees", admissions_and_eligibility: "admissions and eligibility",
  scholarships: "scholarships", campus_and_facilities: "campus and placements",
};

const BOOKING_REFUSAL: Record<string, string> = {
  slot_taken: "That session is already taken.", already_booked: "The student already has a session.",
  slot_in_past: "That time has passed.", slot_not_found: "That session doesn't exist.",
};

const WORKING: Record<string, string> = {
  search_knowledge: "Searching the knowledge base…", book_slot: "Trying to book the session…", get_slots: "Checking free sessions…",
  upsert_lead: "Saving the student's details…", score_lead: "Scoring the lead…", get_lead: "Reading the student's record…",
  request_fee_waiver: "Sending the request to a counsellor…", request_booking_override: "Sending the request to a counsellor…",
  request_bulk_message: "Sending the request to a counsellor…", plan_followup: "Planning a follow-up…",
  schedule_followup: "Scheduling a follow-up…", send_message: "Sending a message…", opt_out: "Recording the opt-out…",
};

const REQUEST_TOOLS = new Set(["request_fee_waiver", "request_booking_override", "request_bulk_message"]);

function humanize(value: string): string {
  return value.replace(/_/g, " ");
}

/** What a finished tool call means, in words. */
function resultText(name: string, r: any): string {
  if (r && "answer_found" in r) {
    if (!r.answer_found) return "Searched the knowledge base: nothing relevant found.";
    const files: string[] = r.chunks.map((c: any) => String(c.source).split(".md")[0]);
    return `Searched the knowledge base: found it under ${Array.from(new Set(files)).map((f) => SOURCE_NAME[f] ?? humanize(f)).join(", ")}.`;
  }
  if (name === "book_slot") return r.ok ? "Booked the session." : BOOKING_REFUSAL[r.reason] ?? "The booking was refused.";
  if (name === "get_slots" && Array.isArray(r)) return `Found ${r.length} free session${r.length === 1 ? "" : "s"}.`;
  if (name === "score_lead") return `Scored the lead: ${r.score}/100, ${r.tier}.`;
  if (name === "upsert_lead") return "Saved the student's details.";
  if (name === "get_lead") return "Read the student's record.";
  if (name === "plan_followup") return `Planned a ${humanize(r.template ?? "follow-up")} message for ${r.due_at ? formatDateTime(r.due_at) : "later"}.`;
  if (name === "schedule_followup") return "Scheduled a follow-up.";
  if (name === "send_message") return "Sent the message.";
  if (name === "opt_out") return "Recorded the opt-out.";
  if (REQUEST_TOOLS.has(name)) return `Sent the request to a counsellor (#${r.approval_id}).`;
  return `Finished: ${humanize(name)}.`;
}

function failedText(name: string, r: any): string {
  if (r?.fallback === "other_slots_available") return "The calendar kept failing, so other free sessions were offered.";
  if (r?.fallback === "counsellor_callback") return "The calendar kept failing, so a counsellor will arrange a time.";
  return `Couldn't finish: ${humanize(name)}.`;
}

function retryText(d: Record<string, any>): string {
  const target = String(d.target ?? "");
  const what = target.startsWith("llm") ? "The AI model didn't respond" : target === "book_slot" || target === "get_slots" ? "The calendar failed" : "That step failed";
  return `${what}, so trying again (attempt ${d.attempt}).`;
}

function errorText(d: Record<string, any>): string {
  if (d.error !== "retries_exhausted") return "Something went wrong on this step.";
  return String(d.target ?? "").startsWith("llm") ? "The AI model kept failing, so the agent stopped trying." : "That step kept failing, so the agent stopped trying.";
}

interface Row {
  kind: RowKind;
  title: string;
  text: string;
  failed?: boolean;
  passed?: string[];
}

/** Turn raw events into readable rows. A tool's call and result become one row, and passed checks group together. */
function rowsFrom(events: AgentEvent[]): Row[] {
  const finished = new Set(events.filter((e) => e.type === "tool_result").map((e) => e.data.id));
  const rows: Row[] = [];
  for (const { type, data: d } of events) {
    if (type === "plan") {
      const goals: string[] = (d.steps ?? []).map((s: any) => s.goal).filter(Boolean);
      rows.push({ kind: "plan", title: "Plan", text: goals.length ? goals.join(", then ") : `Handle this as: ${humanize(String(d.intent))}.` });
    } else if (type === "tool_call" && !finished.has(d.id)) {
      rows.push({ kind: "action", title: "Action", text: WORKING[d.name] ?? `Running: ${humanize(d.name)}…` });
    } else if (type === "tool_result") {
      rows.push(d.ok
        ? { kind: "action", title: "Action", text: resultText(d.name, d.result) }
        : { kind: "problem", title: "Problem", text: failedText(d.name, d.result) });
    } else if (type === "verify" && d.ok) {
      const name = CHECK_NAME[d.check] ?? humanize(d.check);
      const last = rows[rows.length - 1];
      if (last?.passed) last.passed.push(name);
      else rows.push({ kind: "check", title: "Checks passed", text: "", passed: [name] });
    } else if (type === "verify") {
      rows.push({ kind: "problem", title: "Check failed", failed: true,
        text: `${CHECK_NAME[d.check] ?? humanize(d.check)}: ${d.reason}. ${RECOVERY[d.action] ?? ""}`.trim() });
    } else if (type === "retry") {
      rows.push({ kind: "problem", title: "Retrying", text: retryText(d) });
    } else if (type === "escalation") {
      rows.push({ kind: "counsellor", title: "Counsellor", text: d.recorded ? `Passed to a counsellor (#${d.approval_id}).` : "Couldn't record the request for a counsellor." });
    } else if (type === "approval_pending") {
      rows.push({ kind: "counsellor", title: "Waiting for a counsellor", text: `Request #${d.approval_id}: ${humanize(d.action)}. Nothing happens until a counsellor decides.` });
    } else if (type === "error") {
      rows.push({ kind: "problem", title: "Problem", text: errorText(d) });
    } else if (type === "final") {
      const sources = d.citations?.length ?? 0;
      rows.push({ kind: "done", title: "Answered", text: sources ? `Sent the reply with ${sources} source${sources === 1 ? "" : "s"}.` : "Sent the reply." });
    }
  }
  return rows;
}

const PHASES: { label: string; types: AgentEvent["type"][] }[] = [
  { label: "Plan", types: ["plan"] },
  { label: "Act", types: ["tool_call", "tool_result"] },
  { label: "Verify", types: ["verify"] },
  { label: "Respond", types: ["final"] },
];

const PhaseStrip: React.FC<{ events: AgentEvent[] }> = ({ events }) => (
  <ol aria-label="Agent progress" className="flex items-center gap-1 text-[11px]">
    {PHASES.map((p, i) => {
      const reached = events.some((e) => p.types.includes(e.type));
      return (
        <li key={p.label} className="flex items-center gap-1">
          {i > 0 && <span aria-hidden className="text-slate-300">→</span>}
          <span className={`rounded px-1.5 py-0.5 font-medium ${reached ? "bg-jklu-blue text-white" : "bg-slate-100 text-slate-500"}`}>
            {p.label}
          </span>
        </li>
      );
    })}
  </ol>
);

const LeadState: React.FC<{ final?: AgentEvent }> = ({ final }) => {
  const score = final?.data.lead_score;
  const missing: string[] = final?.data.missing_fields ?? [];
  if (!score && missing.length === 0) return null;
  return (
    <div className="px-4 py-2 border-b border-slate-100 flex flex-wrap items-center gap-1.5 text-xs text-slate-600">
      {score && <Badge tone={TIER_TONE[score.tier as Tier]}>{score.tier} lead · {score.score}/100</Badge>}
      {missing.length > 0 && <span>Still needed: {missing.join(", ").replace(/_/g, " ")}</span>}
    </div>
  );
};

export const TracePanel: React.FC<{ events: AgentEvent[]; busy?: boolean; id?: string; className?: string }> = ({ events, busy, id, className = "" }) => {
  const shown = events.filter((e) => e.type !== "message");
  const rows = rowsFrom(shown);
  const list = useRef<HTMLOListElement>(null);

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight });
  }, [shown.length, busy]);

  return (
    <aside id={id} aria-label="How the agent worked" className={`bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col min-h-0 ${className}`}>
      <div className="px-4 py-3 border-b border-slate-100 space-y-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">How the agent worked</h2>
          <p className="text-xs text-slate-500">What it planned, did and checked for the latest message</p>
        </div>
        <PhaseStrip events={shown} />
      </div>
      <LeadState final={shown.find((e) => e.type === "final")} />
      <ol ref={list} className="flex-1 overflow-y-auto p-3 space-y-1.5 text-xs">
        {rows.length === 0 && !busy && <li className="text-slate-500 px-1">Send a message to see the agent work.</li>}
        {rows.map((row, i) => {
          const Icon = row.failed ? XCircle : row.title === "Retrying" ? RotateCw : ICON[row.kind];
          return (
            <li key={i} className={`border rounded-lg px-2.5 py-1.5 flex gap-2 ${STYLE[row.kind]}`}>
              <Icon className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden />
              <div className="min-w-0">
                <div className="font-semibold">{row.title}</div>
                <div className="break-words">{row.passed ? row.passed.join(", ") : row.text}</div>
              </div>
            </li>
          );
        })}
        {busy && (
          <li className="flex items-center gap-1.5 text-slate-500 px-1 py-1">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Working…
          </li>
        )}
      </ol>
    </aside>
  );
};
