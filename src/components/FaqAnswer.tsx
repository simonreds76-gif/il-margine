import Link from "next/link";

/** Check if a block of text is a markdown table (every line contains |) */
function isMarkdownTable(block: string): boolean {
  const lines = block.trim().split("\n").filter(Boolean);
  if (lines.length < 2) return false;
  return lines.every((line) => line.includes("|"));
}

/** Parse markdown table into rows of cells. Skips separator row (|---|---|). */
function parseMarkdownTable(block: string): string[][] {
  const lines = block.trim().split("\n").filter(Boolean);
  const rows: string[][] = [];
  for (const line of lines) {
    const cells = line.split("|").map((c) => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
    if (cells.length === 0) continue;
    const isSeparator = cells.every((c) => /^[-:]+$/.test(c));
    if (isSeparator) continue;
    rows.push(cells);
  }
  return rows;
}

/**
 * Renders FAQ answer: paragraphs, **bold**, [text](url), and markdown tables as proper HTML tables.
 */
export default function FaqAnswer({ text }: { text: string }) {
  const blocks = text.split(/\n\n+/).filter(Boolean);

  return (
    <div className="space-y-4 text-slate-300 text-sm leading-relaxed">
      {blocks.map((block, i) => {
        const trimmed = block.trim();
        if (isMarkdownTable(trimmed)) {
          const rows = parseMarkdownTable(trimmed);
          if (rows.length === 0) return <p key={i}>{trimmed}</p>;
          const [header, ...bodyRows] = rows;
          return (
            <div key={i} className="my-5 overflow-x-auto rounded-lg border border-slate-600/80 shadow-inner overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-emerald-500/10">
                    {header.map((cell, j) => (
                      <th
                        key={j}
                        className="px-4 py-3 text-left text-slate-200 font-semibold text-xs uppercase tracking-wider border-b border-slate-600 border-r border-slate-600/80 last:border-r-0"
                      >
                        {renderInline(cell)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bodyRows.map((row, ri) => (
                    <tr key={ri} className="bg-slate-800/30 hover:bg-slate-800/50 transition-colors border-b border-slate-700/50 last:border-b-0">
                      {row.map((cell, j) => (
                        <td
                          key={j}
                          className="px-4 py-3 text-slate-300 border-r border-slate-700/50 last:border-r-0"
                        >
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return (
          <p key={i} className="leading-relaxed">{renderInline(trimmed)}</p>
        );
      })}
    </div>
  );
}

function renderInline(str: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let pos = 0;

  while (pos < str.length) {
    const boldMatch = str.slice(pos).match(/\*\*([^*]+)\*\*/);
    const linkMatch = str.slice(pos).match(/\[([^\]]+)\]\(([^)]+)\)/);

    let next: { type: "bold"; index: number; end: number; text: string } | { type: "link"; index: number; end: number; text: string; href: string } | null = null;

    if (linkMatch && linkMatch.index !== undefined) {
      const absIndex = pos + linkMatch.index;
      if (!next || linkMatch.index < (boldMatch?.index ?? Infinity)) {
        next = { type: "link", index: absIndex, end: absIndex + linkMatch[0].length, text: linkMatch[1], href: linkMatch[2] };
      }
    }
    if (boldMatch && boldMatch.index !== undefined) {
      const absIndex = pos + boldMatch.index;
      if (!next || boldMatch.index < (linkMatch?.index ?? Infinity)) {
        next = { type: "bold", index: absIndex, end: absIndex + boldMatch[0].length, text: boldMatch[1] };
      }
    }

    if (next) {
      if (next.index > pos) {
        parts.push(str.slice(pos, next.index));
      }
      if (next.type === "bold") {
        parts.push(<strong key={parts.length} className="text-slate-200 font-medium">{next.text}</strong>);
      } else {
        const href = next.href;
        if (href.startsWith("/")) {
          parts.push(<Link key={parts.length} href={href} className="text-emerald-400 hover:text-emerald-300 underline">{next.text}</Link>);
        } else {
          parts.push(<a key={parts.length} href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 underline">{next.text}</a>);
        }
      }
      pos = next.end;
    } else {
      parts.push(str.slice(pos));
      break;
    }
  }

  return <>{parts}</>;
}
