import React from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorBanner, Loading, PageHeader, type Tone } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { Role } from "../../lib/types";

interface UserRow {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  lead_id: number | null;
}

const ROLE_TONE: Record<Role, Tone> = { admin: "violet", counsellor: "blue", student: "neutral" };

/** What each role may do. The server enforces this on every request; the menu only hides what a role can't use. */
const ROLE_RIGHTS: { role: Role; rights: string }[] = [
  { role: "admin", rights: "Everything a counsellor can do, plus see this list of users, reload the knowledge base and run the failure demo." },
  { role: "counsellor", rights: "Leads, approvals, scheduling, audit log, analytics and knowledge search. Approves or rejects sensitive requests." },
  { role: "student", rights: "Their own chat, messages and sessions only. No access to other leads or any staff screen." },
];

/** Admin-only list of accounts. Read-only: accounts come from the seed, and nothing here can change a role or password. */
export const UsersPage: React.FC = () => {
  const { data, error, loading, reload } = useApi<UserRow[]>("/crm/users");
  const cell = "px-3 py-2 text-sm";
  const head = "px-3 py-2 font-medium";

  return (
    <>
      <PageHeader title="Users" subtitle="Every account and what its role allows. Read-only, and visible to admins only." />

      <Card className="p-4 mb-4">
        <h2 className="text-sm font-semibold text-slate-800 mb-2">Roles</h2>
        <dl className="grid gap-2 sm:grid-cols-3">
          {ROLE_RIGHTS.map(({ role, rights }) => (
            <div key={role} className="rounded-lg border border-slate-200 p-3">
              <dt className="mb-1"><Badge tone={ROLE_TONE[role]}>{role}</Badge></dt>
              <dd className="text-xs text-slate-600">{rights}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {error && <div className="mb-3"><ErrorBanner message={error} onRetry={() => void reload()} /></div>}
      {loading && !data && <Loading label="Loading users…" />}
      {data && data.length === 0 && <Card><EmptyState title="No accounts yet" /></Card>}
      {data && data.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="text-[11px] uppercase tracking-wide text-slate-500 bg-slate-50">
                <tr>
                  <th scope="col" className={head}>Name</th>
                  <th scope="col" className={head}>Email</th>
                  <th scope="col" className={head}>Role</th>
                  <th scope="col" className={head}>Status</th>
                  <th scope="col" className={head}>Lead</th>
                  <th scope="col" className={head}>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.map((u) => (
                  <tr key={u.id} className="border-t border-slate-100">
                    <td className={`${cell} font-medium text-slate-900 whitespace-nowrap`}>{u.full_name}</td>
                    <td className={`${cell} text-slate-600`}>{u.email}</td>
                    <td className={cell}><Badge tone={ROLE_TONE[u.role]}>{u.role}</Badge></td>
                    <td className={cell}>{u.is_active ? <Badge tone="green">active</Badge> : <Badge>disabled</Badge>}</td>
                    <td className={cell}>
                      {u.lead_id !== null ? <Link to={`/leads/${u.lead_id}`} className="text-jklu-blue underline">#{u.lead_id}</Link> : <span className="text-slate-400">–</span>}
                    </td>
                    <td className={`${cell} text-slate-500 whitespace-nowrap`}>{formatDateTime(u.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
};
