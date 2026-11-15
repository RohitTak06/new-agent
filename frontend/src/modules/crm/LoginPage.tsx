import React, { useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { BookOpenCheck, ScrollText, ShieldCheck } from "lucide-react";
import { homeFor, useAuth } from "../../lib/auth";
import { errorMessage } from "../../lib/api";
import { Button, ErrorBanner } from "../../lib/ui";
import { DEMO_ACCOUNTS } from "./demoAccounts";
import { RegisterForm } from "./RegisterForm";

type Tab = "register" | "login";

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [params, setParams] = useSearchParams();
  // Register comes first; a redirect from a protected page, or ?tab=login, opens Log in.
  const tab: Tab = params.get("tab") === "login" || (from && params.get("tab") !== "register") ? "login" : "register";
  const showTab = (next: Tab) => setParams((now) => { const p = new URLSearchParams(now); p.set("tab", next); return p; }, { replace: true });
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

  const field = "field";

  const points = [
    { icon: BookOpenCheck, title: "Answers with sources", text: "Every fee, date and rule is checked against JKLU's official pages before a student sees it." },
    { icon: ShieldCheck, title: "People decide", text: "Waivers, overrides and bulk messages wait for a counsellor's approval." },
    { icon: ScrollText, title: "Everything on record", text: "Each plan, tool call, check and decision lands in an audit log nobody can edit." },
  ];

  return (
    <div className="max-w-5xl mx-auto pt-4 sm:pt-10">
      <div className="grid md:grid-cols-[0.85fr_1.15fr] overflow-hidden rounded-xl border border-line bg-surface shadow-card">
        <section className="hidden md:flex flex-col bg-navy text-white p-8">
          <span className="w-10 h-10 rounded-lg bg-white text-navy font-bold flex items-center justify-center" aria-hidden>JK</span>
          <h2 className="mt-6 text-2xl font-semibold tracking-tight">JKLU Admissions</h2>
          <p className="mt-1 text-sm text-white/75">From a student's first question to a counsellor session.</p>
          <ul className="mt-8 space-y-5">
            {points.map((pt) => (
              <li key={pt.title} className="flex gap-3">
                <span className="mt-0.5 rounded-lg bg-white/10 p-2 h-fit"><pt.icon className="w-4 h-4 text-white" aria-hidden /></span>
                <span>
                  <span className="block text-sm font-medium">{pt.title}</span>
                  <span className="block text-13 text-white/75 mt-0.5 leading-relaxed">{pt.text}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-auto pt-8 text-xs text-white/70">Synthetic student data. WhatsApp, email and calendar are simulated.</p>
        </section>

        <section className="p-6 sm:p-8">
          <div role="tablist" aria-label="Register or log in" className="inline-flex gap-1 mb-6 p-1 rounded-lg bg-subtle border border-line">
            {([["register", "Register"], ["login", "Log in"]] as [Tab, string][]).map(([key, label]) => (
              <button key={key} type="button" role="tab" id={`tab-${key}`} aria-selected={tab === key} aria-controls={`panel-${key}`}
                onClick={() => showTab(key)}
                className={`px-4 py-1.5 rounded-lg text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-navy ${
                  tab === key ? "bg-surface text-navy font-medium shadow-card" : "text-ink-secondary hover:text-ink"}`}>
                {label}
              </button>
            ))}
          </div>

          {tab === "register" ? (
            <div role="tabpanel" id="panel-register" aria-labelledby="tab-register">
              <h1 className="text-2xl font-semibold tracking-tight text-ink">Start your application</h1>
              <p className="text-sm text-ink-secondary mt-1 mb-6">Create your account to chat with the admissions assistant and book a counsellor.</p>
              <RegisterForm onRegistered={() => navigate("/chat", { replace: true })}
                onLogin={(address) => { setEmail(address); setError(null); showTab("login"); }} />
            </div>
          ) : (
          <div role="tabpanel" id="panel-login" aria-labelledby="tab-login">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Log in</h1>
          <p className="text-sm text-ink-secondary mt-1 mb-6">Students see their chat and messages. Staff see leads, approvals and scheduling.</p>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-ink-secondary mb-1">Email</label>
              <input id="email" type="email" required autoComplete="username" value={email}
                onChange={(e) => setEmail(e.target.value)} className={field} />
            </div>
            <div>
              <label htmlFor="password" className="block text-xs font-medium text-ink-secondary mb-1">Password</label>
              <input id="password" type="password" required autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} className={field} />
            </div>
            {error && <ErrorBanner message={error} />}
            <Button type="submit" busy={busy} className="w-full">Log in</Button>
          </form>
          <p className="text-sm text-ink-secondary mt-4 text-center">
            New here?{" "}
            <button type="button" onClick={() => showTab("register")}
              className="font-medium text-navy underline underline-offset-2 hover:text-navy-hover rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">
              Register
            </button>
          </p>
          </div>
          )}

          {import.meta.env.DEV && (
            <div className="mt-6 pt-6 border-t border-line">
              <p className="text-xs font-medium text-ink-secondary mb-2">Demo accounts <span className="font-normal text-ink-muted">(synthetic data)</span></p>
              <div className="flex flex-col gap-1.5">
                {DEMO_ACCOUNTS.map((a) => (
                  <Button key={a.email} variant="secondary" small disabled={busy} className="justify-between py-1.5"
                    aria-label={`Log in as ${a.label}, ${a.email}`} onClick={() => void logIn(a.email, a.password)}>
                    <span>{a.label}</span>
                    <span className="font-normal text-ink-muted text-xs truncate">{a.email}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
