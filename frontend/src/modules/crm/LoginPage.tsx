import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { BookOpenCheck, ScrollText, ShieldCheck } from "lucide-react";
import { homeFor, useAuth } from "../../lib/auth";
import { errorMessage } from "../../lib/api";
import { Button, ErrorBanner } from "../../lib/ui";
import { DEMO_ACCOUNTS } from "./demoAccounts";

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function logIn(address: string, secret: string) {
    setBusy(true);
    setError(null);
    try {
      const user = await login(address, secret);
      navigate(from ?? homeFor(user), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    void logIn(email.trim(), password);
  }

  const field = "w-full text-sm rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500";

  const points = [
    { icon: BookOpenCheck, title: "Answers with sources", text: "Every fee, date and rule is checked against JKLU's official pages before a student sees it." },
    { icon: ShieldCheck, title: "People decide", text: "Waivers, overrides and bulk messages wait for a counsellor's approval." },
    { icon: ScrollText, title: "Everything on record", text: "Each plan, tool call, check and decision lands in an audit log nobody can edit." },
  ];

  return (
    <div className="max-w-4xl mx-auto pt-4 sm:pt-10">
      <div className="grid md:grid-cols-[1.05fr_1fr] overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-raised">
        <section className="hidden md:flex flex-col bg-jklu-blue text-white p-8">
          <span className="w-10 h-10 rounded-lg bg-jklu-gold text-jklu-blue font-black flex items-center justify-center">JK</span>
          <h2 className="mt-6 text-2xl font-semibold tracking-tight">JKLU Admissions</h2>
          <p className="mt-1 text-sm text-slate-300">From a student's first question to a counsellor session.</p>
          <ul className="mt-8 space-y-5">
            {points.map((pt) => (
              <li key={pt.title} className="flex gap-3">
                <span className="mt-0.5 rounded-lg bg-white/10 p-2 h-fit"><pt.icon className="w-4 h-4 text-jklu-gold" aria-hidden /></span>
                <span>
                  <span className="block text-sm font-medium">{pt.title}</span>
                  <span className="block text-xs text-slate-300 mt-0.5 leading-relaxed">{pt.text}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-auto pt-8 text-[11px] text-slate-400">Synthetic student data. WhatsApp, email and calendar are simulated.</p>
        </section>

        <section className="p-6 sm:p-8">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">Log in</h1>
          <p className="text-sm text-slate-500 mt-1 mb-5">Students see their chat and messages. Staff see leads, approvals and the audit log.</p>
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-slate-600 mb-1">Email</label>
              <input id="email" type="email" required autoComplete="username" value={email}
                onChange={(e) => setEmail(e.target.value)} className={field} />
            </div>
            <div>
              <label htmlFor="password" className="block text-xs font-medium text-slate-600 mb-1">Password</label>
              <input id="password" type="password" required autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} className={field} />
            </div>
            {error && <ErrorBanner message={error} />}
            <Button type="submit" busy={busy} className="w-full">Log in</Button>
          </form>

          {import.meta.env.DEV && (
            <div className="mt-6 pt-5 border-t border-slate-100">
              <p className="text-xs font-medium text-slate-600 mb-2">Demo accounts <span className="font-normal text-slate-400">(synthetic data)</span></p>
              <div className="flex flex-col gap-1.5">
                {DEMO_ACCOUNTS.map((a) => (
                  <Button key={a.email} variant="secondary" small disabled={busy} className="justify-between py-1.5"
                    aria-label={`Log in as ${a.label}, ${a.email}`} onClick={() => void logIn(a.email, a.password)}>
                    <span>{a.label}</span>
                    <span className="font-normal text-slate-500 truncate">{a.email}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}
          <p className="text-sm text-slate-500 mt-6">
            Just have a question? <Link to="/chat" className="text-jklu-blue font-medium underline">Chat without logging in</Link>
          </p>
        </section>
      </div>
    </div>
  );
};
