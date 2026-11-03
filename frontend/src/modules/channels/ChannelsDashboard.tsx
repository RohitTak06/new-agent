import React, { useState } from "react";
import { MessageSquare, Mail, Calendar, Clock, FastForward, CheckCircle2 } from "lucide-react";

export const ChannelsDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"whatsapp" | "email" | "calendar" | "timeline">("whatsapp");

  return (
    <div className="space-y-6">
      {/* Module Header */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                Module 4: Scheduling & Channels
              </span>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mt-2">
              Multi-Channel Simulator & Appointment Engine
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              Simulated WhatsApp, Email inbox, Counsellor clash-proof booking, and adaptive follow-up timeline.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => alert("Fast-Forward 24h triggered! Pending follow-ups dispatched.")}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-lg font-medium text-sm hover:from-amber-600 hover:to-orange-600 shadow-sm transition-all"
            >
              <FastForward className="w-4 h-4" />
              <span>Fast-Forward 24h (Demo)</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 mt-6 gap-2">
          <button
            onClick={() => setActiveTab("whatsapp")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "whatsapp"
                ? "border-emerald-600 text-emerald-700 bg-emerald-50/50"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <MessageSquare className="w-4 h-4 text-emerald-600" />
            <span>WhatsApp Simulator</span>
          </button>

          <button
            onClick={() => setActiveTab("email")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "email"
                ? "border-blue-600 text-blue-700 bg-blue-50/50"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <Mail className="w-4 h-4 text-blue-600" />
            <span>Simulated Email Inbox</span>
          </button>

          <button
            onClick={() => setActiveTab("calendar")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "calendar"
                ? "border-purple-600 text-purple-700 bg-purple-50/50"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <Calendar className="w-4 h-4 text-purple-600" />
            <span>Counsellor Calendar</span>
          </button>

          <button
            onClick={() => setActiveTab("timeline")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "timeline"
                ? "border-orange-600 text-orange-700 bg-orange-50/50"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <Clock className="w-4 h-4 text-orange-600" />
            <span>Follow-up Queue & Timeline</span>
          </button>
        </div>
      </div>

      {/* Tab Panels */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 min-h-[400px]">
        {activeTab === "whatsapp" && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <MessageSquare className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900">WhatsApp Phone Simulator</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
              Interactive mobile phone UI with real-time student chats, quick reply buttons, and agent typing indicators.
            </p>
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 bg-slate-100 rounded-full text-xs text-slate-600">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span>Ready for Day 3 implementation</span>
            </div>
          </div>
        )}

        {activeTab === "email" && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <Mail className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900">Simulated Email Inbox</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
              Two-pane inbox previewing admission enquiries, brochures, and counsellor appointment confirmations.
            </p>
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 bg-slate-100 rounded-full text-xs text-slate-600">
              <CheckCircle2 className="w-3.5 h-3.5 text-blue-500" />
              <span>Ready for Day 3 implementation</span>
            </div>
          </div>
        )}

        {activeTab === "calendar" && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <Calendar className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900">Counsellor Availability & Booking</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
              Interactive slot grid showing Dr. Sharma and Ms. Verma's availability, clash prevention, and alternative slot picker.
            </p>
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 bg-slate-100 rounded-full text-xs text-slate-600">
              <CheckCircle2 className="w-3.5 h-3.5 text-purple-500" />
              <span>Ready for Day 4 implementation</span>
            </div>
          </div>
        )}

        {activeTab === "timeline" && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-orange-100 text-orange-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <Clock className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900">Follow-up Pipeline & Nurture Queue</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
              Visual sequence of scheduled touches (24h inactive reminder, scholarship deadline, campus tour invitation).
            </p>
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 bg-slate-100 rounded-full text-xs text-slate-600">
              <CheckCircle2 className="w-3.5 h-3.5 text-orange-500" />
              <span>Ready for Day 6 implementation</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

