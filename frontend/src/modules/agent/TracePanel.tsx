import React, { useEffect, useRef } from "react";
import { AlertTriangle, CheckCircle2, ListChecks, Loader2, RotateCw, ShieldAlert, Wrench, XCircle } from "lucide-react";
import { TIER_TONE } from "../../lib/leads";
import { Badge } from "../../lib/ui";
import type { Tier } from "../../lib/types";
import type { AgentEvent } from "./sse";

const STYLE: Record<string, string> = {
  plan: "border-indigo-200 bg-indigo-50 text-indigo-900",
  tool_call: "border-slate-200 bg-slate-50 text-slate-700",
  tool_result: "border-slate-200 bg-white text-slate-700",
  verify: "border-emerald-200 bg-emerald-50 text-emerald-900",
  verify_fail: "border-amber-200 bg-amber-50 text-amber-900",
  retry: "border-amber-200 bg-amber-50 text-amber-900",
  escalation: "border-rose-200 bg-rose-50 text-rose-900",
  approval_pending: "border-rose-200 bg-rose-50 text-rose-900",
  error: "border-red-200 bg-red-50 text-red-900",
  final: "border-blue-200 bg-blue-50 text-blue-900",
};

/** Provider errors run long; the first sentence says what happened. */
function firstSentence(text: string): string {
  return String(text).split(". ")[0];
}

function toolSummary(name: string, r: any): string {
  if (r && "answer_found" in r) {
    const sources = Array.from(new Set(r.chunks.map((c: any) => c.source))).join(", ");
    return `${name}: ${r.answer_found ? `found in ${sources}` : "nothing relevant in the knowledge base"}`;
  }
  if (name === "book_slot") return r.ok ? `book_slot: booked slot ${r.slot?.slot_id}` : `book_slot: refused (${r.reason})`;
  if (name === "get_slots" && Array.isArray(r)) return `get_slots: ${r.length} free session(s)`;
  if (name === "score_lead") return `score_lead: ${r.score}/100, ${r.tier}`;
  return `${name}: ${JSON.stringify(r).slice(0, 140)}`;
}

function summary(e: AgentEvent): string {
  const d = e.data;
  switch (e.type) {
    case "plan":
      return `Intent: ${d.intent}` + (d.steps?.length ? ` · ${d.steps.map((s: any) => s.goal).join(" → ")}` : "");
    case "tool_call":
      return `${d.name}(${JSON.stringify(d.args)})`;
    case "tool_result":
      return d.ok ? toolSummary(d.name, d.result) : `${d.name} failed: ${d.result?.error ?? "error"}` +
        (d.result?.fallback ? ` · fallback: ${d.result.fallback}` : "");
    case "verify":
      return `${d.check}: ${d.ok ? "pass" : `fail → ${d.action}`} · ${d.reason}` +
        (d.ungrounded_numbers ? ` (${d.ungrounded_numbers.join(", ")})` : "");
    case "retry":
      return `${d.target} attempt ${d.attempt}: ${firstSentence(d.error)}`;
    case "escalation":
      return d.recorded ? `Escalated to a counsellor · approval #${d.approval_id} (${d.status})` : "Escalation not recorded";
    case "approval_pending":
      return `Approval #${d.approval_id} requested: ${d.action} (${d.status}). Nothing runs until a counsellor decides.`;
    case "error":
      return `${d.error}${d.detail ? `: ${firstSentence(d.detail)}` : ""}`;
    case "final":
      return `Done · ${d.citations?.length ?? 0} citation(s)${d.escalated ? " · escalated" : ""}`;
    default:
      return JSON.stringify(d).slice(0, 140);
  }
}

function Icon({ e }: { e: AgentEvent }) {
  const cls = "w-3.5 h-3.5 shrink-0 mt-0.5";
  if (e.type === "plan") return <ListChecks className={cls} />;
  if (e.type === "tool_call" || e.type === "tool_result") return <Wrench className={cls} />;
  if (e.type === "verify") return e.data.ok ? <CheckCircle2 className={cls} /> : <XCircle className={cls} />;
  if (e.type === "retry") return <RotateCw className={cls} />;
  if (e.type === "escalation" || e.type === "approval_pending") return <ShieldAlert className={cls} />;
  if (e.type === "error") return <AlertTriangle className={cls} />;
  return <CheckCircle2 className={cls} />;
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

export const TracePanel: React.FC<{ events: AgentEvent[]; busy?: boolean; className?: string }> = ({ events, busy, className = "" }) => {
  const shown = events.filter((e) => e.type !== "message");
  const list = useRef<HTMLOListElement>(null);

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight });
  }, [shown.length, busy]);

  return (
    <aside aria-label="Reasoning trace" className={`bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col min-h-0 ${className}`}>
      <div className="px-4 py-3 border-b border-slate-100 space-y-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Reasoning trace</h2>
          <p className="text-xs text-slate-500">What the agent planned, called and checked for the latest message</p>
        </div>
        <PhaseStrip events={shown} />
      </div>
      <LeadState final={shown.find((e) => e.type === "final")} />
      <ol ref={list} className="flex-1 overflow-y-auto p-3 space-y-1.5 text-xs">
        {shown.length === 0 && !busy && <li className="text-slate-500 px-1">Send a message to see the agent work.</li>}
        {shown.map((e, i) => {
          const key = e.type === "verify" && !e.data.ok ? "verify_fail" : e.type;
          return (
            <li key={i} className={`border rounded-lg px-2.5 py-1.5 flex gap-2 ${STYLE[key] ?? STYLE.tool_call}`}>
              <Icon e={e} />
              <div className="min-w-0">
                <div className="font-mono text-[10px] uppercase tracking-wide opacity-70">
                  {e.type.replace("_", " ")} · step {e.step}
                </div>
                <div className="break-words">{summary(e)}</div>
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
