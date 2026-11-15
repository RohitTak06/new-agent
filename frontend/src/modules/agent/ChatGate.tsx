import React from "react";
import { Link } from "react-router-dom";
import { LogIn, MessageSquare, UserPlus } from "lucide-react";
import { Card } from "../../lib/ui";

const LINK = "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors " +
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-1";

/** What a visitor who isn't logged in sees on /chat: the chat needs an account, so register or log in first. */
export const ChatGate: React.FC = () => (
  <div className="max-w-xl mx-auto pt-4 sm:pt-10">
    <Card className="p-6 sm:p-8 text-center">
      <span className="mx-auto mb-4 flex w-12 h-12 items-center justify-center rounded-xl bg-subtle text-navy">
        <MessageSquare className="w-6 h-6" aria-hidden />
      </span>
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Chat with JKLU Admissions</h1>
      <p className="text-sm text-ink-secondary mt-2">
        Register or log in to ask about programmes, fees, eligibility and scholarships, and to book a session with a counsellor.
      </p>
      <div className="mt-6 flex flex-col sm:flex-row gap-2 justify-center">
        <Link to="/login?tab=register" className={`${LINK} bg-navy text-white hover:bg-navy-hover`}>
          <UserPlus className="w-4 h-4" aria-hidden /> Register
        </Link>
        <Link to="/login?tab=login" className={`${LINK} bg-surface text-ink-secondary border border-line-strong hover:bg-subtle`}>
          <LogIn className="w-4 h-4" aria-hidden /> Log in
        </Link>
      </div>
    </Card>
  </div>
);
