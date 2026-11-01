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
      <div className="p-4 bg-white rounded-xl shadow-sm border border-slate-200 animate-pulse">
        <div className="h-6 bg-slate-200 rounded w-1/3 mb-4"></div>
        <div className="h-10 bg-slate-100 rounded mb-2"></div>
      </div>
    );
  }

  if (!scoreData) {
    return (
      <div className="p-4 bg-slate-50 rounded-xl border border-dashed border-slate-300 text-slate-500 text-sm">
        No lead profile scored yet.
      </div>
    );
  }

  const { score, tier, reasons } = scoreData;

  const tierStyles = {
    hot: {
      badge: "bg-red-100 text-red-700 border-red-200",
      bar: "bg-red-500",
      label: "HOT LEAD",
    },
    warm: {
      badge: "bg-amber-100 text-amber-700 border-amber-200",
      bar: "bg-amber-500",
      label: "WARM LEAD",
    },
    cold: {
      badge: "bg-blue-100 text-blue-700 border-blue-200",
      bar: "bg-blue-500",
      label: "COLD LEAD",
    },
  }[tier];

  return (
    <div className="p-5 bg-white rounded-xl shadow-sm border border-slate-200 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Qualification Engine
          </span>
          <h3 className="text-lg font-bold text-slate-800">Lead Health & Fit</h3>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-bold border tracking-wide ${tierStyles.badge}`}
        >
          {tierStyles.label}
        </span>
      </div>

      <div>
        <div className="flex justify-between items-baseline mb-1">
          <span className="text-2xl font-black text-slate-900">{score}</span>
          <span className="text-xs text-slate-400 font-medium">/ 100 Points</span>
        </div>
        <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ease-out rounded-full ${tierStyles.bar}`}
            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          />
        </div>
      </div>

      <div className="space-y-1.5 pt-2 border-t border-slate-100">
        <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          Scoring Rationale:
        </h4>
        <ul className="space-y-1">
          {reasons.map((reason, idx) => (
            <li
              key={idx}
              className="text-xs text-slate-600 flex items-start gap-1.5 leading-relaxed"
            >
              <span className="text-emerald-500 font-bold mt-0.5">•</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
