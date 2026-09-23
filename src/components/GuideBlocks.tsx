import Link from "next/link";
import EditorialIcon from "./EditorialIcon";
import type { GuideSection } from "@/lib/resource-guides";
import GuideDiagram from "./GuideDiagram";

export default function GuideBlocks({ sections }: { sections: GuideSection[] }) {
  return <>{sections.map((section, index) => <section key={section.id} id={section.id} className="guide-section">
    <div className="guide-section-heading"><span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><h2>{section.title}</h2></div>
    {section.paragraphs?.map((text) => <p key={text}>{text}</p>)}
    {section.example && <aside className="guide-example" aria-label="Worked example">
      <div className="guide-label"><EditorialIcon name={section.example.icon ?? "analysis"} className="h-8 w-8" />Worked example · hypothetical figures</div>
      <h3>{section.example.title}</h3>
      <div className="guide-figures">{section.example.figures.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <p>{section.example.explanation}</p>
    </aside>}
    {section.diagram && <GuideDiagram kind={section.diagram} />}
    {section.table && <><p className="guide-table-hint">Swipe the table sideways to see every column.</p><div className="guide-table-wrap" role="region" aria-label={section.table.caption} tabIndex={0}><table><caption>{section.table.caption}</caption><thead><tr>{section.table.headings.map(h => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{section.table.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => j === 0 ? <th key={j} scope="row">{cell}</th> : <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div></>}
    {section.steps && <ol className="guide-checklist">{section.steps.map(([title, detail]) => <li key={title}><div><strong>{title}</strong><p>{detail}</p></div></li>)}</ol>}
    {section.note && <div className="guide-note"><EditorialIcon name="about" className="h-7 w-7" /><p>{section.note}</p></div>}
    {section.links && <div className="guide-actions">{section.links.map(([title, href]) => <Link prefetch={false} key={href} href={href}>{title}<span aria-hidden="true"> ↗</span></Link>)}</div>}
  </section>)}</>;
}
