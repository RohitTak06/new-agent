import React from "react";
import { AlertCircle, Inbox, Loader2, RefreshCw } from "lucide-react";

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = "", children }) => (
  <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>{children}</div>
);

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-jklu-blue text-white hover:bg-[#123a63]",
  secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50",
  ghost: "text-slate-600 hover:bg-slate-100",
  danger: "bg-white text-rose-700 border border-rose-300 hover:bg-rose-50",
};

export const Button: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  small?: boolean;
  busy?: boolean;
}> = ({ variant = "primary", small, busy, className = "", children, disabled, type = "button", ...rest }) => (
  <button type={type} disabled={disabled || busy} {...rest}
    className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors
      focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-blue-500
      disabled:opacity-50 disabled:cursor-not-allowed
      ${small ? "text-xs px-2.5 py-1" : "text-sm px-3.5 py-2"} ${BUTTON[variant]} ${className}`}>
    {busy && <Loader2 className="w-4 h-4 animate-spin" />}
    {children}
  </button>
);

export type Tone = "neutral" | "green" | "amber" | "red" | "blue" | "violet";

const BADGE: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
  green: "bg-emerald-50 text-emerald-800 border-emerald-200",
  amber: "bg-amber-50 text-amber-800 border-amber-200",
  red: "bg-rose-50 text-rose-800 border-rose-200",
  blue: "bg-blue-50 text-blue-800 border-blue-200",
  violet: "bg-violet-50 text-violet-800 border-violet-200",
};

export const Badge: React.FC<{ tone?: Tone; className?: string; children: React.ReactNode }> = ({
  tone = "neutral", className = "", children,
}) => (
  <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${BADGE[tone]} ${className}`}>
    {children}
  </span>
);

export const Loading: React.FC<{ label?: string }> = ({ label = "Loading…" }) => (
  <div role="status" className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
    <Loader2 className="w-4 h-4 animate-spin" /> {label}
  </div>
);

export const ErrorBanner: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <div role="alert" className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
    <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
    <span className="flex-1 min-w-0 break-words">{message}</span>
    {onRetry && (
      <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 text-xs font-medium underline">
        <RefreshCw className="w-3 h-3" /> Retry
      </button>
    )}
  </div>
);

export const EmptyState: React.FC<{ title: string; hint?: string }> = ({ title, hint }) => (
  <div className="py-12 text-center">
    <Inbox className="w-8 h-8 text-slate-300 mx-auto mb-2" />
    <p className="text-sm font-medium text-slate-600">{title}</p>
    {hint && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
  </div>
);

export const PageHeader: React.FC<{ title: string; subtitle?: string; actions?: React.ReactNode }> = ({
  title, subtitle, actions,
}) => (
  <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
    <div>
      <h1 className="text-xl font-bold text-jklu-blue">{title}</h1>
      {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
    </div>
    {actions}
  </div>
);
