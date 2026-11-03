import React from "react";
import { AlertTriangle, CheckCircle2, ListChecks, RotateCw, ShieldAlert, Wrench, XCircle } from "lucide-react";
import type { AgentEvent } from "./sse";

const STYLE: Record<string, string> = {
  plan: "border-indigo-200 bg-indigo-50 text-indigo-800",
  tool_call: "border-slate-200 bg-slate-50 text-slate-700",
  tool_result: "border-slate-200 bg-white text-slate-700",
  verify: "border-emerald-200 bg-emerald-50 text-emerald-800",
  verify_fail: "border-amber-200 bg-amber-50 text-amber-800",
  retry: "border-amber-200 bg-amber-50 text-amber-800",
  escalation: "border-rose-200 bg-rose-50 text-rose-800",
  approval_pending: "border-rose-200 bg-rose-50 text-rose-800",
  error: "border-red-200 bg-red-50 text-red-800",
  final: "border-blue-200 bg-blue-50 text-blue-800",
};

function summary(e: AgentEvent): string {
  const d = e.data;
  switch (e.type) {
    case "plan":
      return `intent: ${d.intent}` + (d.steps?.length ? ` · ${d.steps.map((s: any) => s.goal).join(" → ")}` : "");
    case "tool_call":
      return `${d.name}(${JSON.stringify(d.args)})`;
    case "tool_result": {
      if (!d.ok) return `${d.name} failed: ${d.result?.error ?? "error"}`;
      const r = d.result;
      if (r && "answer_found" in r) return `${d.name}: answer_found=${r.answer_found} · ${r.chunks.map((c: any) => c.source).join(", ")}`;
      return `${d.name}: ${JSON.stringify(r).slice(0, 140)}`;
    }
    case "verify":
      return `${d.check}: ${d.ok ? "pass" : `fail → ${d.action}`} · ${d.reason}` +
        (d.ungrounded_numbers ? ` (${d.ungrounded_numbers.join(", ")})` : "");
    case "retry":
      return `${d.target} attempt ${d.attempt}: ${d.error}`;
    case "escalation":
      return d.recorded ? `escalated to counsellor · approval #${d.approval_id} (${d.status})` : `escalation not recorded`;
    case "error":
      return `${d.error}${d.detail ? `: ${d.detail}` : ""}`;
    case "final":
      return `done · ${d.citations?.length ?? 0} citation(s)${d.escalated ? " · escalated" : ""}`;
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

export const TracePanel: React.FC<{ events: AgentEvent[] }> = ({ events }) => {
  const shown = events.filter((e) => e.type !== "message");
  return (
    <aside className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col min-h-0">
      <div className="px-4 py-3 border-b border-slate-100">
        <h2 className="text-sm font-semibold text-slate-800">Reasoning trace</h2>
        <p className="text-xs text-slate-500">Plan, tool calls and verification for the latest turn</p>
      </div>
      <ol className="flex-1 overflow-y-auto p-3 space-y-1.5 text-xs">
        {shown.length === 0 && <li className="text-slate-400 px-1">Send a message to see the agent work.</li>}
        {shown.map((e, i) => {
          const key = e.type === "verify" && !e.data.ok ? "verify_fail" : e.type;
          return (
            <li key={i} className={`border rounded-lg px-2.5 py-1.5 flex gap-2 ${STYLE[key] ?? STYLE.tool_call}`}>
              <Icon e={e} />
              <div className="min-w-0">
                <div className="font-mono text-[10px] uppercase tracking-wide opacity-70">
                  {e.type} · step {e.step}
                </div>
                <div className="break-words">{summary(e)}</div>
              </div>
            </li>
          );
        })}
      </ol>
    </aside>
  );
};
