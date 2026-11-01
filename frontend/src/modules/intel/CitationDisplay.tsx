import React, { useState } from "react";

export interface KnowledgeChunk {
  text: string;
  source: string;
  score: number;
}

interface CitationDisplayProps {
  chunks: KnowledgeChunk[];
}

export const CitationDisplay: React.FC<CitationDisplayProps> = ({ chunks }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (!chunks || chunks.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 pt-2.5 border-t border-slate-100">
      <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
        <span>Verified Citations ({chunks.length})</span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {chunks.map((c, i) => {
          const isExpanded = expandedIndex === i;
          return (
            <div key={i} className="inline-block">
              <button
                type="button"
                onClick={() => setExpandedIndex(isExpanded ? null : i)}
                className={`text-[11px] px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
                  isExpanded
                    ? "bg-blue-50 border-blue-300 text-blue-700 font-medium"
                    : "bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-600"
                }`}
              >
                <span>📎 {c.source}</span>
                <span className="text-[10px] text-slate-400">
                  ({Math.round(c.score * 100)}%)
                </span>
              </button>

              {isExpanded && (
                <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-blue-200 text-xs text-slate-700 leading-relaxed max-w-lg shadow-sm">
                  <div className="font-semibold text-blue-900 mb-1 flex justify-between items-center">
                    <span>Source: {c.source}</span>
                    <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">
                      Confidence {c.score}
                    </span>
                  </div>
                  <pre className="whitespace-pre-wrap font-sans text-xs text-slate-600">
                    {c.text}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
