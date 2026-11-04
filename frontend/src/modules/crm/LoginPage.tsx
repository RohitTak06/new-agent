import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../../lib/auth";
import { errorMessage } from "../../lib/api";
import { Button, Card, ErrorBanner } from "../../lib/ui";
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

  return (
    <div className="max-w-sm mx-auto pt-8 sm:pt-16">
      <Card className="p-6">
        <h1 className="text-lg font-bold text-jklu-blue">Log in</h1>
        <p className="text-sm text-slate-500 mb-4">Students see their messages. Staff see leads and approvals.</p>
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
          <div className="mt-5 pt-4 border-t border-slate-100">
            <p className="text-xs font-medium text-slate-600 mb-2">Demo accounts (synthetic data)</p>
            <div className="flex flex-col gap-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <Button key={a.email} variant="secondary" small disabled={busy} className="justify-between"
                  aria-label={`Log in as ${a.label}, ${a.email}`} onClick={() => void logIn(a.email, a.password)}>
                  <span>{a.label}</span>
                  <span className="font-normal text-slate-500 truncate">{a.email}</span>
                </Button>
              ))}
            </div>
          </div>
        )}
      </Card>
      <p className="text-center text-sm text-slate-500 mt-4">
        Just have a question? <Link to="/chat" className="text-jklu-blue font-medium underline">Chat without logging in</Link>
      </p>
    </div>
  );
};
