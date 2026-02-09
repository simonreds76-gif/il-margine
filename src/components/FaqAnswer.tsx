import Link from "next/link";

/**
 * Renders FAQ answer text: paragraphs, **bold**, and [text](url) links.
 * Internal paths use Next Link; external use <a>.
 */
export default function FaqAnswer({ text }: { text: string }) {
  const paragraphs = text.split(/\n\n+/).filter(Boolean);

  return (
    <div className="space-y-3 text-slate-300 text-sm leading-relaxed">
      {paragraphs.map((para, i) => (
        <p key={i}>{renderInline(para)}</p>
      ))}
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
