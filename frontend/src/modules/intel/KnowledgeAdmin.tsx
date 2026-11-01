import React, { useState, useEffect } from "react";
import { CitationDisplay, KnowledgeChunk } from "./CitationDisplay";
import { LeadScoreCard, LeadScoreData } from "./LeadScoreCard";

const API_BASE = "http://localhost:8000";

export const KnowledgeAdmin: React.FC = () => {
  const [query, setQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResult, setSearchResult] = useState<{
    answer_found: boolean;
    chunks: KnowledgeChunk[];
  } | null>(null);

  // Lead qualification simulator state
  const [name, setName] = useState("Aditya Patel");
  const [twelfthPercent, setTwelfthPercent] = useState<number>(91.5);
  const [program, setProgram] = useState("B.Tech CSE");
  const [entranceExam, setEntranceExam] = useState("JEE Mains: 92 Percentile");
  const [budget, setBudget] = useState<number>(12);
  const [askedScholarship, setAskedScholarship] = useState(true);
  const [phone, setPhone] = useState("+91 98290 12345");
  const [email, setEmail] = useState("aditya.patel@example.com");
  const [simScore, setSimScore] = useState<LeadScoreData | null>(null);

  // Benchmark suite runner
  const [benchRunning, setBenchRunning] = useState(false);
  const [benchReport, setBenchReport] = useState<any>(null);

  // Indexed chunks overview
  const [indexedOverview, setIndexedOverview] = useState<{
    count: number;
    chunks: { source: string; preview: string }[];
  } | null>(null);

  useEffect(() => {
    fetchKnowledgeOverview();
    handleSimulateScore();
  }, []);

  const fetchKnowledgeOverview = async () => {
    try {
      const res = await fetch(`${API_BASE}/intel/knowledge`);
      if (res.ok) {
        const data = await res.json();
        setIndexedOverview(data);
      }
    } catch (e) {
      console.warn("Backend not running or CORS blocked", e);
    }
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    setSearchLoading(true);
    try {
      const res = await fetch(`${API_BASE}/intel/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      setSearchResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleSimulateScore = async () => {
    try {
      const res = await fetch(`${API_BASE}/intel/score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          phone,
          email,
          program_interest: program,
          twelfth_percent: twelfthPercent ? Number(twelfthPercent) : null,
          entrance_exam: entranceExam,
          budget_lakh: budget ? Number(budget) : null,
          asked_scholarship: askedScholarship,
          channel: "web",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSimScore(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunBenchmark = async () => {
    setBenchRunning(true);
    try {
      const res = await fetch(`${API_BASE}/intel/benchmark`);
      if (res.ok) {
        const data = await res.json();
        setBenchReport(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setBenchRunning(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8 font-sans text-slate-800">
      <header className="border-b border-slate-200 pb-4 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-black text-slate-900">
            Admissions Knowledge & Lead Intelligence
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Institutional RAG retrieval, zero-hallucination guard, and lead qualification engine (Owner: Guru)
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchKnowledgeOverview}
            className="px-3 py-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg border border-slate-300"
          >
            Reload KB
          </button>
          <button
            onClick={handleRunBenchmark}
            disabled={benchRunning}
            className="px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm"
          >
            {benchRunning ? "Evaluating 45 Questions..." : "Run 45-Q Benchmark"}
          </button>
        </div>
      </header>

      {/* Benchmark Banner */}
      {benchReport && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
          <div>
            <div className="text-sm font-bold text-emerald-900 flex items-center gap-2">
              <span>Benchmark Results:</span>
              <span className="text-emerald-700 font-extrabold text-base">
                {benchReport.accuracy_percent}% Passed
              </span>
              <span className="text-xs text-emerald-600 font-normal">
                ({benchReport.passed}/{benchReport.total_questions} queries)
              </span>
            </div>
            <div className="text-xs text-emerald-700 mt-1 flex gap-4">
              <span>In-Scope Accuracy: {benchReport.in_scope_accuracy_percent}%</span>
              <span>Zero-Hallucination Guard: {benchReport.zero_hallucination_guard_accuracy_percent}%</span>
            </div>
          </div>
          <span className="text-2xl">🎯</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Knowledge Search Tester */}
        <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
            <span>🔍 Interactive Knowledge Retrieval</span>
          </h2>
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. What is the scholarship for 93% in 12th?"
              className="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={searchLoading}
              className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {searchLoading ? "Searching..." : "Search"}
            </button>
          </form>

          {/* Quick preset buttons */}
          <div className="flex flex-wrap gap-1.5 text-xs">
            <span className="text-slate-400 self-center">Presets:</span>
            {[
              "B.Tech JEE 96% scholarship",
              "Math score 52 penalty",
              "BBA fees and eligibility",
              "Can I get a hostel waiver?",
              "Do you have MBBS admission?",
            ].map((p, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setQuery(p);
                  setTimeout(() => handleSearch(), 50);
                }}
                className="px-2 py-0.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded"
              >
                {p}
              </button>
            ))}
          </div>

          {searchResult && (
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Retrieval Verdict
                </span>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${
                    searchResult.answer_found
                      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                      : "bg-rose-100 text-rose-800 border-rose-200"
                  }`}
                >
                  {searchResult.answer_found ? "Answer Verified (Grounded)" : "Refuse & Escalate (No Guessing)"}
                </span>
              </div>

              {searchResult.answer_found ? (
                <div>
                  <CitationDisplay chunks={searchResult.chunks} />
                </div>
              ) : (
                <p className="text-xs text-rose-700 italic">
                  Information not found in verified institutional records or is out-of-scope. Agent must escalate to counsellor rather than guessing.
                </p>
              )}
            </div>
          )}
        </section>

        {/* Lead Scoring Simulator */}
        <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
            <span>⚡ Lead Qualification & Scoring Simulator</span>
          </h2>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-medium text-slate-600 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-600 mb-1">Program</label>
              <select
                value={program}
                onChange={(e) => setProgram(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded bg-white"
              >
                <option value="B.Tech CSE">B.Tech CSE</option>
                <option value="B.Tech AI & DS">B.Tech AI & DS</option>
                <option value="BBA">BBA</option>
                <option value="B.Des">B.Des</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-600 mb-1">12th Marks (%)</label>
              <input
                type="number"
                value={twelfthPercent}
                onChange={(e) => setTwelfthPercent(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-600 mb-1">Entrance Exam</label>
              <input
                type="text"
                value={entranceExam}
                onChange={(e) => setEntranceExam(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-600 mb-1">Budget (in Lakhs)</label>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded"
              />
            </div>
            <div className="flex items-center gap-2 pt-4">
              <input
                type="checkbox"
                id="askedScholarship"
                checked={askedScholarship}
                onChange={(e) => setAskedScholarship(e.target.checked)}
                className="rounded text-blue-600"
              />
              <label htmlFor="askedScholarship" className="font-medium text-slate-700">
                Asked Scholarship
              </label>
            </div>
          </div>

          <button
            type="button"
            onClick={handleSimulateScore}
            className="w-full py-1.5 text-xs font-bold bg-slate-800 hover:bg-slate-900 text-white rounded-lg transition"
          >
            Re-calculate Score
          </button>

          <LeadScoreCard scoreData={simScore} />
        </section>
      </div>

      {/* Indexed Documents Table */}
      {indexedOverview && (
        <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-slate-800">
              Indexed Institutional Knowledge Chunks ({indexedOverview.count})
            </h3>
            <span className="text-xs text-slate-500">Live memory store</span>
          </div>
          <div className="max-h-60 overflow-y-auto divide-y divide-slate-100 text-xs">
            {indexedOverview.chunks.map((item, idx) => (
              <div key={idx} className="py-2 flex items-start justify-between gap-4">
                <span className="font-mono text-blue-700 shrink-0 font-medium">
                  {item.source}
                </span>
                <span className="text-slate-500 text-right truncate">
                  {item.preview}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default KnowledgeAdmin;
