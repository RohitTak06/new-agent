import React from "react";

export interface LeadScoreData {
  score: number;
  tier: "hot" | "warm" | "cold";
  reasons: string[];
}

interface LeadScoreCardProps {
  scoreData?: LeadScoreData | null;
  loading?: boolean;
}

export const LeadScoreCard: React.FC<LeadScoreCardProps> = ({ scoreData, loading }) => {
  if (loading) {
    return (
      <div className="p-4 bg-surface rounded-xl shadow-card border border-line animate-pulse">
        <div className="h-6 bg-line rounded-lg w-1/3 mb-4"></div>
        <div className="h-10 bg-subtle rounded-lg mb-2"></div>
      </div>
    );
  }

  if (!scoreData) {
    return (
      <div className="p-4 bg-surface rounded-xl border border-dashed border-line-strong text-ink-secondary text-sm">
        No lead profile scored yet.
      </div>
    );
  }

  const { score, tier, reasons } = scoreData;

  const tierStyles = {
    hot: {
      badge: "bg-danger-soft text-danger border-danger/30",
      bar: "bg-danger",
      label: "Hot lead",
    },
    warm: {
      badge: "bg-warning-soft text-warning border-warning/30",
      bar: "bg-warning",
      label: "Warm lead",
    },
    cold: {
      badge: "bg-info-soft text-info border-info/30",
      bar: "bg-info",
      label: "Cold lead",
    },
  }[tier];

  return (
    <div className="p-4 bg-surface rounded-xl shadow-card border border-line space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-medium text-ink-muted">
            Qualification Engine
          </span>
          <h3 className="text-sm font-semibold text-ink">Lead Health & Fit</h3>
        </div>
        <span
          className={`px-2 py-0.5 rounded-lg text-xs font-medium border ${tierStyles.badge}`}
        >
          {tierStyles.label}
        </span>
      </div>

      <div>
        <div className="flex justify-between items-baseline mb-1">
          <span className="text-2xl font-semibold tabular-nums text-ink">{score}</span>
          <span className="text-xs text-ink-muted tabular-nums">/ 100 Points</span>
        </div>
        <div className="w-full bg-subtle h-2 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ease-out rounded-full ${tierStyles.bar}`}
            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          />
        </div>
      </div>

      <div className="space-y-1.5 pt-2 border-t border-line">
        <h4 className="text-13 font-semibold text-ink">
          Scoring Rationale:
        </h4>
        <ul className="space-y-1">
          {reasons.map((reason, idx) => (
            <li
              key={idx}
              className="text-13 text-ink-secondary flex items-start gap-2 leading-relaxed"
            >
              <span className="text-ink-muted" aria-hidden>•</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
