import React, { useState } from "react";
import { CheckCircle2, Search, ShieldAlert } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Badge, Button, Card, ErrorBanner, Loading, PageHeader } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import { CitationDisplay, type KnowledgeChunk } from "./CitationDisplay";
import { LeadScoreCard, type LeadScoreData } from "./LeadScoreCard";

const PRESETS = [
  "B.Tech JEE 96% scholarship",
  "BBA fees and eligibility",
  "Can I get a hostel waiver?",
  "Do you have MBBS admission?",
];

const PROGRAMS = ["B.Tech CSE", "BBA", "B.Des"];

interface Overview {
  count: number;
  chunks: { source: string; preview: string }[];
}

interface SearchResult {
  answer_found: boolean;
  chunks: KnowledgeChunk[];
}

interface Benchmark {
  accuracy_percent: number;
  passed: number;
  total_questions: number;
  in_scope_accuracy_percent: number;
  zero_hallucination_guard_accuracy_percent: number;
}

const SearchPanel: React.FC = () => {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(query: string) {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api<SearchResult>("/intel/search", { body: { query } }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-slate-800">Search the knowledge base</h2>
      <p className="text-xs text-slate-500 mb-3">The same retrieval the agent uses. No match means it must refuse and escalate.</p>
      <form onSubmit={(e) => { e.preventDefault(); void run(text); }} className="flex gap-2">
        <label htmlFor="kb-search" className="sr-only">Question</label>
        <input id="kb-search" value={text} onChange={(e) => setText(e.target.value)} autoComplete="off"
          placeholder="Ask anything a student might…"
          className="flex-1 min-w-0 text-sm rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        <Button type="submit" busy={busy} disabled={!text.trim()}>{!busy && <Search className="w-4 h-4" />} Search</Button>
      </form>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {PRESETS.map((p) => (
          <Button key={p} small variant="ghost" className="bg-slate-100" disabled={busy} onClick={() => { setText(p); void run(p); }}>{p}</Button>
        ))}
      </div>
      {error && <div className="mt-3"><ErrorBanner message={error} /></div>}
      {result && (
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          {result.answer_found ? (
            <>
              <Badge tone="green"><CheckCircle2 className="w-3 h-3" aria-hidden /> Found in the knowledge base</Badge>
              <CitationDisplay chunks={result.chunks} />
            </>
          ) : (
            <>
              <Badge tone="red"><ShieldAlert className="w-3 h-3" aria-hidden /> Not in the knowledge base</Badge>
              <p className="text-xs text-slate-600 mt-1.5">The agent would say so and pass this to a counsellor, not guess.</p>
            </>
          )}
        </div>
      )}
    </Card>
  );
};

const ScorePanel: React.FC = () => {
  const [name, setName] = useState("Aditya Patel");
  const [program, setProgram] = useState(PROGRAMS[0]);
  const [twelfth, setTwelfth] = useState("91.5");
  const [exam, setExam] = useState("JEE Main 92 percentile");
  const [budget, setBudget] = useState("4");
  const [scholarship, setScholarship] = useState(true);
  const [score, setScore] = useState<LeadScoreData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setScore(await api<LeadScoreData>("/intel/score", {
        body: {
          name, email: "sample.lead@example.test", program_interest: program, entrance_exam: exam,
          twelfth_percent: twelfth ? Number(twelfth) : null, budget_lakh: budget ? Number(budget) : null,
          asked_scholarship: scholarship, channel: "web",
        },
      }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const field = "w-full text-sm rounded-lg border border-slate-300 px-2.5 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500";
  const label = "block text-xs font-medium text-slate-600 mb-1";

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-slate-800">Try the lead scoring</h2>
      <p className="text-xs text-slate-500 mb-3">A sample profile only. Nothing here is saved.</p>
      <form onSubmit={(e) => { e.preventDefault(); void run(); }} className="grid grid-cols-2 gap-3">
        <div><label htmlFor="s-name" className={label}>Name</label>
          <input id="s-name" value={name} onChange={(e) => setName(e.target.value)} className={field} /></div>
        <div><label htmlFor="s-program" className={label}>Program</label>
          <select id="s-program" value={program} onChange={(e) => setProgram(e.target.value)} className={field}>
            {PROGRAMS.map((p) => <option key={p}>{p}</option>)}
          </select></div>
        <div><label htmlFor="s-twelfth" className={label}>12th marks (%)</label>
          <input id="s-twelfth" type="number" min="0" max="100" step="0.1" value={twelfth} onChange={(e) => setTwelfth(e.target.value)} className={field} /></div>
        <div><label htmlFor="s-budget" className={label}>Budget (lakh per year)</label>
          <input id="s-budget" type="number" min="0" step="0.5" value={budget} onChange={(e) => setBudget(e.target.value)} className={field} /></div>
        <div className="col-span-2"><label htmlFor="s-exam" className={label}>Entrance exam</label>
          <input id="s-exam" value={exam} onChange={(e) => setExam(e.target.value)} className={field} /></div>
        <label className="col-span-2 flex items-center gap-2 text-xs font-medium text-slate-700">
          <input type="checkbox" checked={scholarship} onChange={(e) => setScholarship(e.target.checked)} /> Asked about scholarships
        </label>
        <Button type="submit" busy={busy} variant="secondary" className="col-span-2">Score this profile</Button>
      </form>
      {error && <div className="mt-3"><ErrorBanner message={error} /></div>}
      {score && <div className="mt-3"><LeadScoreCard scoreData={score} /></div>}
    </Card>
  );
};

/** Staff view of the knowledge base: search it, test scoring, run the benchmark. Admins can reload it. */
export const KnowledgeAdmin: React.FC = () => {
  const { user } = useAuth();
  const overview = useApi<Overview>("/intel/knowledge");
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [running, setRunning] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  async function runBenchmark() {
    setRunning(true);
    setError(null);
    try {
      setBenchmark(await api<Benchmark>("/intel/benchmark"));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRunning(false);
    }
  }

  async function reloadKb() {
    setReloading(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api<{ total_chunks: number }>("/intel/knowledge/reload", { method: "POST" });
      setNotice(`Reloaded from the markdown files: ${res.total_chunks} passages.`);
      await overview.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setReloading(false);
    }
  }

  const term = filter.trim().toLowerCase();
  const chunks = (overview.data?.chunks ?? []).filter((c) => !term || c.source.toLowerCase().includes(term) || c.preview.toLowerCase().includes(term));

  return (
    <>
      <PageHeader title="Knowledge" subtitle="The verified facts the agent may use. Anything else, it refuses and escalates."
        actions={
          <div className="flex gap-2">
            {user?.role === "admin" && <Button variant="secondary" busy={reloading} onClick={() => void reloadKb()}>Reload knowledge base</Button>}
            <Button busy={running} onClick={() => void runBenchmark()}>Run benchmark</Button>
          </div>
        } />

      <div className="space-y-3 mb-4">
        {error && <ErrorBanner message={error} />}
        {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{notice}</p>}
        {benchmark && (
          <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
            <p className="font-semibold">Retrieval benchmark: {benchmark.passed} of {benchmark.total_questions} passed ({benchmark.accuracy_percent}%)</p>
            <p className="text-xs mt-0.5">
              Questions the knowledge base covers: {benchmark.in_scope_accuracy_percent}% · Questions it must refuse: {benchmark.zero_hallucination_guard_accuracy_percent}%.
              This tests retrieval only, not the model's wording.
            </p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start mb-4">
        <SearchPanel />
        <ScorePanel />
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h2 className="text-sm font-semibold text-slate-800">Indexed passages{overview.data ? ` (${overview.data.count})` : ""}</h2>
          <div>
            <label htmlFor="kb-filter" className="sr-only">Filter passages</label>
            <input id="kb-filter" type="search" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter…"
              className="text-sm rounded-lg border border-slate-300 px-2.5 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
        {overview.error && <ErrorBanner message={overview.error} onRetry={() => void overview.reload()} />}
        {overview.loading && !overview.data && <Loading />}
        {overview.data && (
          <ul className="max-h-72 overflow-y-auto divide-y divide-slate-100">
            {chunks.map((c, i) => (
              <li key={`${c.source}-${i}`} className="py-2 text-xs">
                <p className="font-mono text-blue-800 break-all">{c.source}</p>
                <p className="text-slate-600 mt-0.5">{c.preview}</p>
              </li>
            ))}
            {chunks.length === 0 && <li className="py-3 text-xs text-slate-500">No passages match.</li>}
          </ul>
        )}
      </Card>
    </>
  );
};

export default KnowledgeAdmin;
