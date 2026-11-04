import React from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Inbox, KanbanSquare, LogIn, LogOut, MessageSquare, type LucideIcon } from "lucide-react";
import { AuthProvider, homeFor, useAuth } from "./lib/auth";
import { ErrorBoundary } from "./lib/ErrorBoundary";
import { ErrorBanner, Loading } from "./lib/ui";
import type { Role } from "./lib/types";
import { ChatPage } from "./modules/agent";
import { MessagesPage } from "./modules/channels";
import { LeadDetailPage, LoginPage, PipelinePage } from "./modules/crm";

type Viewer = Role | "anonymous";
const STAFF: Viewer[] = ["admin", "counsellor"];

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  viewers: Viewer[];
}

const NAV: NavItem[] = [
  { to: "/chat", label: "Chat", icon: MessageSquare, viewers: ["anonymous", "student"] },
  { to: "/messages", label: "My messages", icon: Inbox, viewers: ["student"] },
  { to: "/pipeline", label: "Pipeline", icon: KanbanSquare, viewers: STAFF },
  { to: "/chat", label: "Test chat", icon: MessageSquare, viewers: STAFF },
];

/** Hides a screen from roles that can't use it. The server still refuses them on every request. */
const RequireRole: React.FC<{ roles: Viewer[]; children: React.ReactElement }> = ({ roles, children }) => {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return roles.includes(user.role) ? children : <Navigate to={homeFor(user)} replace />;
};

const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const viewer: Viewer = user?.role ?? "anonymous";
  return (
    <header className="bg-jklu-blue text-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-wrap items-center gap-x-6 gap-y-1 py-2 min-h-14">
        <NavLink to="/" className="flex items-center gap-2.5 shrink-0">
          <span className="w-8 h-8 rounded-md bg-jklu-gold text-jklu-blue font-black text-sm flex items-center justify-center">JK</span>
          <span className="font-semibold text-sm">JKLU Admissions</span>
        </NavLink>

        <nav aria-label="Main" className="flex items-center gap-1 order-3 sm:order-none w-full sm:w-auto sm:flex-1 overflow-x-auto">
          {NAV.filter((item) => item.viewers.includes(viewer)).map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) =>
              `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm whitespace-nowrap transition-colors ${
                isActive ? "bg-white/15 text-white font-medium" : "text-slate-300 hover:text-white hover:bg-white/10"}`}>
              <item.icon className="w-4 h-4" /> {item.label}
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
            <NavLink to="/login" className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-slate-300 hover:text-white hover:bg-white/10">
              <LogIn className="w-4 h-4" /> Log in
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
      <Route path="/leads/:id" element={<RequireRole roles={STAFF}><LeadDetailPage /></RequireRole>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-800">
          <Header />
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-4">
            <ErrorBoundary>
              <AppRoutes />
            </ErrorBoundary>
          </main>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
