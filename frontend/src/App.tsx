import React, { useEffect } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { BarChart3, BookOpen, CalendarClock, Inbox, KanbanSquare, LogIn, LogOut, MessageSquare, ScrollText, ShieldCheck, type LucideIcon } from "lucide-react";
import { AuthProvider, homeFor, useAuth } from "./lib/auth";
import { ErrorBoundary } from "./lib/ErrorBoundary";
import { ErrorBanner, Loading } from "./lib/ui";
import { useApi } from "./lib/useApi";
import type { Approval, Role } from "./lib/types";
import { ChatPage } from "./modules/agent";
import { MessagesPage } from "./modules/channels";
import { AnalyticsPage, APPROVALS_CHANGED, ApprovalsPage, AuditPage, LeadDetailPage, LoginPage, PipelinePage, SchedulingPage } from "./modules/crm";
import { KnowledgeAdmin } from "./modules/intel";

type Viewer = Role | "anonymous";
const STAFF: Viewer[] = ["admin", "counsellor"];

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  viewers: Viewer[];
  group?: string;
}

const NAV: NavItem[] = [
  { to: "/chat", label: "Chat", icon: MessageSquare, viewers: ["anonymous", "student"] },
  { to: "/messages", label: "My messages", icon: Inbox, viewers: ["student"] },
  { to: "/pipeline", label: "Pipeline", icon: KanbanSquare, viewers: STAFF, group: "Leads" },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck, viewers: STAFF, group: "Leads" },
  { to: "/scheduling", label: "Scheduling", icon: CalendarClock, viewers: STAFF, group: "Operations" },
  { to: "/audit", label: "Audit log", icon: ScrollText, viewers: STAFF, group: "Operations" },
  { to: "/analytics", label: "Analytics", icon: BarChart3, viewers: STAFF, group: "Insights" },
  { to: "/knowledge", label: "Knowledge base", icon: BookOpen, viewers: STAFF, group: "Insights" },
  { to: "/chat", label: "Test chat", icon: MessageSquare, viewers: STAFF, group: "Agent" },
];

/** Hides a screen from roles that can't use it. The server still refuses them on every request. */
const RequireRole: React.FC<{ roles: Viewer[]; children: React.ReactElement }> = ({ roles, children }) => {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return roles.includes(user.role) ? children : <Navigate to={homeFor(user)} replace />;
};

const PendingCount: React.FC = () => {
  const { data, reload } = useApi<Approval[]>("/crm/approvals?status=pending", 10_000);
  useEffect(() => {
    const refresh = () => void reload();
    window.addEventListener(APPROVALS_CHANGED, refresh);
    return () => window.removeEventListener(APPROVALS_CHANGED, refresh);
  }, [reload]);
  if (!data?.length) return null;
  return (
    <span aria-label={`${data.length} pending`} className="ml-auto min-w-[20px] rounded-full bg-jklu-gold px-1.5 text-center text-[11px] font-bold leading-5 text-jklu-blue">
      {data.length}
    </span>
  );
};

const Brand: React.FC<{ subtitle?: string }> = ({ subtitle }) => (
  <NavLink to="/" className="flex items-center gap-2.5 shrink-0">
    <span className="w-8 h-8 rounded-lg bg-jklu-gold text-jklu-blue font-black text-sm flex items-center justify-center shadow-sm">JK</span>
    <span className="leading-tight">
      <span className="block font-semibold text-sm text-white">JKLU Admissions</span>
      {subtitle && <span className="block text-[11px] text-slate-400">{subtitle}</span>}
    </span>
  </NavLink>
);

function itemsFor(viewer: Viewer): NavItem[] {
  return NAV.filter((item) => item.viewers.includes(viewer));
}

const Initials: React.FC<{ name: string }> = ({ name }) => (
  <span aria-hidden className="w-8 h-8 rounded-full bg-jklu-line text-[11px] font-semibold text-white flex items-center justify-center shrink-0">
    {name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("")}
  </span>
);

/** Staff on a wide screen: a fixed sidebar, grouped by what the counsellor is doing. */
const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const items = itemsFor(user?.role ?? "anonymous");
  const groups = Array.from(new Set(items.map((i) => i.group ?? "")));
  return (
    <aside className="hidden lg:flex fixed inset-y-0 left-0 z-40 w-60 flex-col bg-jklu-blue text-white">
      <div className="px-4 h-16 flex items-center border-b border-jklu-line">
        <Brand subtitle="Counsellor workspace" />
      </div>
      <nav aria-label="Main" className="flex-1 overflow-y-auto px-3 py-4 space-y-5 scroll-quiet">
        {groups.map((group) => (
          <div key={group}>
            {group && <p className="px-2 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">{group}</p>}
            <ul className="space-y-0.5">
              {items.filter((i) => (i.group ?? "") === group).map((item) => (
                <li key={`${item.to}-${item.label}`}>
                  <NavLink to={item.to} className={({ isActive }: { isActive: boolean }) =>
                    `relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${
                      isActive ? "bg-white/10 text-white font-medium before:absolute before:left-0 before:top-2 before:bottom-2 before:w-0.5 before:rounded-full before:bg-jklu-gold"
                               : "text-slate-300 hover:text-white hover:bg-white/5"}`}>
                    <item.icon className="w-4 h-4 shrink-0" /> {item.label}
                    {item.to === "/approvals" && <PendingCount />}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      {user && (
        <div className="border-t border-jklu-line p-3 flex items-center gap-2.5">
          <Initials name={user.full_name} />
          <div className="min-w-0 flex-1 leading-tight">
            <p className="text-xs font-medium truncate">{user.full_name}</p>
            <p className="text-[11px] text-jklu-gold capitalize">{user.role}</p>
          </div>
          <button type="button" onClick={logout} aria-label="Log out" title="Log out"
            className="rounded-md p-1.5 text-slate-300 hover:text-white hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-jklu-gold">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      )}
    </aside>
  );
};

/** Students and visitors everywhere, and staff on narrow screens. */
const Header: React.FC<{ staff: boolean }> = ({ staff }) => {
  const { user, logout } = useAuth();
  const viewer: Viewer = user?.role ?? "anonymous";
  return (
    <header className={`bg-jklu-blue text-white sticky top-0 z-50 shadow-sm ${staff ? "lg:hidden" : ""}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-wrap items-center gap-x-6 gap-y-1 py-2 min-h-14">
        <Brand subtitle={staff ? undefined : "Admissions assistant"} />

        <nav aria-label="Main" className="flex items-center gap-1 order-3 sm:order-none w-full sm:w-auto sm:flex-1 overflow-x-auto">
          {itemsFor(viewer).map((item) => (
            <NavLink key={`${item.to}-${item.label}`} to={item.to} className={({ isActive }: { isActive: boolean }) =>
              `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm whitespace-nowrap transition-colors ${
                isActive ? "bg-white/15 text-white font-medium" : "text-slate-300 hover:text-white hover:bg-white/10"}`}>
              <item.icon className="w-4 h-4" /> {item.label}
              {item.to === "/approvals" && <PendingCount />}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3 text-sm">
          {user ? (
            <>
              <span className="hidden md:block text-right leading-tight">
                <span className="block text-xs font-medium">{user.full_name}</span>
                <span className="block text-[11px] text-jklu-gold capitalize">{user.role}</span>
              </span>
              <button type="button" onClick={logout} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-slate-300 hover:text-white hover:bg-white/10">
                <LogOut className="w-4 h-4" /> Log out
              </button>
            </>
          ) : (
            <NavLink to="/login" className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/10 text-white hover:bg-white/15">
              <LogIn className="w-4 h-4" /> Staff or student log in
            </NavLink>
          )}
        </div>
      </div>
    </header>
  );
};

const AppRoutes: React.FC = () => {
  const { user, ready, unreachable, refresh } = useAuth();
  if (!ready) return <Loading />;
  if (unreachable && !user) {
    return <ErrorBanner message="Can't reach the server, so we can't check your login. Check that the API is running." onRetry={() => void refresh()} />;
  }
  return (
    <Routes>
      <Route path="/" element={<Navigate to={homeFor(user)} replace />} />
      <Route path="/login" element={user ? <Navigate to={homeFor(user)} replace /> : <LoginPage />} />
      {/* Remounts on login and logout, so one person's conversation never shows for the next. */}
      <Route path="/chat" element={<ChatPage key={user?.id ?? "anonymous"} />} />
      <Route path="/messages" element={<RequireRole roles={["student"]}><MessagesPage /></RequireRole>} />
      <Route path="/pipeline" element={<RequireRole roles={STAFF}><PipelinePage /></RequireRole>} />
      <Route path="/approvals" element={<RequireRole roles={STAFF}><ApprovalsPage /></RequireRole>} />
      <Route path="/audit" element={<RequireRole roles={STAFF}><AuditPage /></RequireRole>} />
      <Route path="/scheduling" element={<RequireRole roles={STAFF}><SchedulingPage /></RequireRole>} />
      <Route path="/analytics" element={<RequireRole roles={STAFF}><AnalyticsPage /></RequireRole>} />
      <Route path="/knowledge" element={<RequireRole roles={STAFF}><KnowledgeAdmin /></RequireRole>} />
      <Route path="/leads/:id" element={<RequireRole roles={STAFF}><LeadDetailPage /></RequireRole>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

const Shell: React.FC = () => {
  const { user } = useAuth();
  const staff = Boolean(user && user.role !== "student");
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-800">
      {staff && <Sidebar />}
      <Header staff={staff} />
      <main className={`flex-1 w-full ${staff ? "lg:pl-60" : ""}`}>
        <div className={`mx-auto px-4 sm:px-6 py-4 ${staff ? "max-w-[1400px] lg:px-8 lg:py-6" : "max-w-7xl"}`}>
          <ErrorBoundary>
            <AppRoutes />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
};

export function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
