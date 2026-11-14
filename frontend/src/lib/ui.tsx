import React from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowUpRight, Inbox, Loader2, RefreshCw, type LucideIcon } from "lucide-react";

const FOCUS = "focus:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-1";

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = "", children }) => (
  <div className={`bg-surface rounded-xl border border-line shadow-card ${className}`}>{children}</div>
);

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

/** One primary (navy) action per screen; everything else secondary or ghost. */
const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-navy text-white hover:bg-navy-hover",
  secondary: "bg-surface text-ink-secondary border border-line-strong hover:bg-subtle hover:text-ink",
  ghost: "text-ink-secondary hover:bg-subtle hover:text-ink",
  danger: "bg-surface text-danger border border-danger/30 hover:bg-danger-soft",
};

export const Button: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  small?: boolean;
  busy?: boolean;
}> = ({ variant = "primary", small, busy, className = "", children, disabled, type = "button", ...rest }) => (
  <button type={type} disabled={disabled || busy} {...rest}
    className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors ${FOCUS}
      disabled:opacity-50 disabled:cursor-not-allowed
      ${small ? "text-xs px-2.5 py-1.5" : "text-sm px-4 py-2"} ${BUTTON[variant]} ${className}`}>
    {busy && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
    {children}
  </button>
);

export type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "optout";

const BADGE: Record<Tone, string> = {
  neutral: "bg-subtle text-ink-secondary border-line",
  success: "bg-success-soft text-success border-success/20",
  warning: "bg-warning-soft text-warning border-warning/20",
  danger: "bg-danger-soft text-danger border-danger/20",
  info: "bg-info-soft text-info border-info/20",
  optout: "bg-optout-soft text-optout border-optout/20",
};

export const Badge: React.FC<{ tone?: Tone; className?: string; children: React.ReactNode }> = ({
  tone = "neutral", className = "", children,
}) => (
  <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium leading-4 ${BADGE[tone]} ${className}`}>
    {children}
  </span>
);

export const Loading: React.FC<{ label?: string }> = ({ label = "Loading…" }) => (
  <div role="status" className="flex items-center justify-center gap-2 py-12 text-sm text-ink-muted">
    <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> {label}
  </div>
);

export const ErrorBanner: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger/20 bg-danger-soft px-3 py-2 text-sm text-danger">
    <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
    <span className="flex-1 min-w-0 break-words">{message}</span>
    {onRetry && (
      <button type="button" onClick={onRetry} className={`inline-flex items-center gap-1 rounded text-xs font-medium underline ${FOCUS}`}>
        <RefreshCw className="w-3 h-3" aria-hidden /> Retry
      </button>
    )}
  </div>
);

export const EmptyState: React.FC<{ title: string; hint?: string }> = ({ title, hint }) => (
  <div className="py-12 text-center">
    <Inbox className="w-6 h-6 text-ink-muted mx-auto mb-2" aria-hidden />
    <p className="text-sm font-medium text-ink-secondary">{title}</p>
    {hint && <p className="text-xs text-ink-muted mt-1">{hint}</p>}
  </div>
);

export const PageHeader: React.FC<{ title: string; subtitle?: string; eyebrow?: string; actions?: React.ReactNode }> = ({
  title, subtitle, eyebrow, actions,
}) => (
  <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
    <div className="min-w-0">
      {eyebrow && <p className="text-xs font-medium text-ink-muted mb-1">{eyebrow}</p>}
      <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
      {subtitle && <p className="text-sm text-ink-secondary mt-1">{subtitle}</p>}
    </div>
    {actions}
  </div>
);

/** Section title inside a card: 14px semibold. */
export const SectionTitle: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = "" }) => (
  <h2 className={`text-sm font-semibold text-ink ${className}`}>{children}</h2>
);

/** A headline number. With `to`, the whole tile opens the list behind the number. */
export const StatTile: React.FC<{ label: string; value: number | string; note?: string; icon?: LucideIcon;
  accent?: string; to?: string }> = ({ label, value, note, icon: Icon, accent = "text-ink-muted", to }) => {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-13 font-medium text-ink-secondary">{label}</p>
        {Icon && <Icon className={`w-4 h-4 ${accent}`} aria-hidden />}
      </div>
      <p className="text-2xl font-semibold tracking-tight text-ink mt-2 tabular-nums">{value}</p>
      <div className="mt-1 flex items-center justify-between gap-2 min-h-[1rem]">
        {note ? <p className="text-xs text-ink-muted">{note}</p> : <span />}
        {to && <ArrowUpRight className="w-4 h-4 text-ink-muted group-hover:text-navy transition-colors" aria-hidden />}
      </div>
    </>
  );
  const frame = "block bg-surface rounded-xl border border-line shadow-card p-4";
  return to ? (
    <Link to={to} className={`group ${frame} hover:border-line-strong transition-colors ${FOCUS}`}>{body}</Link>
  ) : <div className={frame}>{body}</div>;
};
