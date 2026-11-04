import React from "react";

const SOURCE = String.raw`[^\[\]\s,;]+\.md(?:#[^\[\]\s,;]*)?`;
const GROUP = String.raw`\[\s*${SOURCE}(?:\s*[,;]\s*${SOURCE})*\s*\]`;
const CITATION = new RegExp(`^${GROUP}$`);
const INLINE = new RegExp(String.raw`(\*\*[^*]+\*\*|${GROUP})`, "g");
const BULLET = /^\s*(?:[-*•]\s+|\d+[.)]\s+)/;

/** Bold and numbered citation marks. Everything else stays plain text, so model output can't inject markup. */
function inline(text: string, citations: string[]): React.ReactNode[] {
  return text.split(INLINE).filter(Boolean).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    if (CITATION.test(part)) {
      return part.slice(1, -1).split(/[,;]/).map((source) => source.trim()).map((source) => {
        const n = citations.indexOf(source) + 1;
        return (
          <sup key={`${i}-${source}`} title={source}
            className="ml-0.5 px-1 rounded bg-blue-100 text-blue-800 text-[10px] font-semibold cursor-help">
            {n > 0 ? n : "src"}
          </sup>
        );
      });
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

/** Render an agent reply: paragraphs, bullet lists, bold, and inline citation marks. */
export const RichText: React.FC<{ text: string; citations?: string[] }> = ({ text, citations = [] }) => {
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      blocks.push(
        <ul key={blocks.length} className="list-disc pl-5 space-y-0.5">
          {bullets.map((b, i) => <li key={i}>{inline(b, citations)}</li>)}
        </ul>,
      );
      bullets = [];
    }
  };
  for (const line of text.split("\n")) {
    if (BULLET.test(line)) {
      bullets.push(line.replace(BULLET, ""));
    } else {
      flush();
      if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line, citations)}</p>);
    }
  }
  flush();
  return <div className="space-y-1.5 break-words">{blocks}</div>;
};
