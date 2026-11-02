import React from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import { KnowledgeAdmin } from "./modules/intel";
import { ChannelsDashboard } from "./modules/channels";
import { MessageSquare, Database, BookOpen, Bot, Sparkles } from "lucide-react";

export function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        {/* Top Navbar */}
        <header className="bg-slate-900 text-white shadow-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              {/* Branding */}
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center font-bold text-white shadow-sm">
                  JK
                </div>
                <div>
                  <div className="font-bold text-base flex items-center gap-2">
                    JKLU Admissions AI Agent
                    <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono border border-blue-400/30">
                      PS-04
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">Autonomous Student Recruitment & Nurturing</div>
                </div>
              </div>

              {/* Navigation Links for 4 Modules */}
              <nav className="flex items-center gap-1 sm:gap-2">
                <NavLink
                  to="/channels"
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                      isActive
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-slate-300 hover:text-white hover:bg-slate-800"
                    }`
                  }
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>Channels & Slots (Riya)</span>
                </NavLink>

                <NavLink
                  to="/intel"
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                      isActive
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-slate-300 hover:text-white hover:bg-slate-800"
                    }`
                  }
                >
                  <BookOpen className="w-4 h-4" />
                  <span>Knowledge & Scoring (Guru)</span>
                </NavLink>

                <NavLink
                  to="/agent"
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                      isActive
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-slate-300 hover:text-white hover:bg-slate-800"
                    }`
                  }
                >
                  <Bot className="w-4 h-4" />
                  <span>Agent Brain (Rohit)</span>
                </NavLink>

                <NavLink
                  to="/crm"
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                      isActive
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-slate-300 hover:text-white hover:bg-slate-800"
                    }`
                  }
                >
                  <Database className="w-4 h-4" />
                  <span>CRM & Audit (Dev)</span>
                </NavLink>
              </nav>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Routes>
            <Route path="/" element={<Navigate to="/channels" replace />} />
            <Route path="/channels" element={<ChannelsDashboard />} />
            <Route path="/intel" element={<KnowledgeAdmin />} />
            <Route
              path="/agent"
              element={
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center py-16">
                  <Bot className="w-12 h-12 text-blue-600 mx-auto mb-3" />
                  <h2 className="text-xl font-bold text-slate-800">Agent Brain & Reasoning Trace</h2>
                  <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
                    Rohit's chat screen with live streaming thought process and tool execution panel.
                  </p>
                </div>
              }
            />
            <Route
              path="/crm"
              element={
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center py-16">
                  <Database className="w-12 h-12 text-indigo-600 mx-auto mb-3" />
                  <h2 className="text-xl font-bold text-slate-800">CRM, RBAC & Approvals</h2>
                  <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
                    Dev's lead database, approval inbox (fee waivers, bulk touches), and action audit log.
                  </p>
                </div>
              }
            />
          </Routes>
        </main>

        {/* Global Footer */}
        <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-500">
          JKLU AI-Buildathon 1.0 &bull; PS-04 Intelligent Admission Enquiry &amp; Lead Nurturing Agent
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;

