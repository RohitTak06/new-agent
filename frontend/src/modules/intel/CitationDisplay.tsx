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
    <div className="mt-3 pt-3 border-t border-line">
      <div className="text-xs font-medium text-ink-muted mb-2 flex items-center gap-1">
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
                aria-expanded={isExpanded}
                className={`text-xs px-2 py-1 rounded-lg border transition-colors flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-navy ${
                  isExpanded
                    ? "bg-info-soft border-info/30 text-info font-medium"
                    : "bg-surface hover:bg-subtle border-line text-ink-secondary"
                }`}
              >
                <span>{i + 1}. {c.source}</span>
              </button>

              {isExpanded && (
                <div className="mt-2 p-3 bg-surface rounded-lg border border-line text-xs text-ink-secondary leading-relaxed max-w-lg">
                  <div className="font-semibold text-ink mb-1 break-all">Source: {c.source}</div>
                  <pre className="whitespace-pre-wrap font-sans text-xs text-ink-secondary">
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
