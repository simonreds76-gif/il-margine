"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import EditorialIcon, { type EditorialIconName } from "./EditorialIcon";
import FaqAnswer from "./FaqAnswer";
import { questionSlug, type FaqSection } from "@/lib/parse-faq";

const icons: EditorialIconName[] = ["guide", "method", "markets", "compare", "bankroll", "analysis", "about", "responsible", "analysis"];
const popular = [
  ["The odds have changed", "The advertised odds have gone. Is the tip still worth taking?"],
  ["Penalty-taker evidence", "How reliable is a club's penalty-taker order?"],
  ["Return Atlas explained", "What is Return Atlas, and is it the same as your track record?"],
];
const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

export default function FaqBrowser({ sections, legacyAnchors }: {
  sections: FaqSection[];
  legacyAnchors: Record<string, string[]>;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const words = normalize(query).trim().split(/\s+/).filter(Boolean);
  const matches = (q: string, a: string) => words.every(word => normalize(`${q} ${a}`).includes(word));
  const count = sections.reduce((total, section) => total + (category === "all" || category === section.id ? section.items.filter(item => matches(item.q, item.a)).length : 0), 0);

  useEffect(() => {
    let frame = 0;
    const openHash = () => {
      let id = "";
      try { id = decodeURIComponent(window.location.hash.slice(1)); } catch { return; }
      if (!id) return;
      setQuery(""); setCategory("all");
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const el = document.getElementById(id);
        if (el instanceof HTMLDetailsElement) el.open = true;
        el?.scrollIntoView({ block: "start" });
      });
    };
    openHash(); window.addEventListener("hashchange", openHash);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("hashchange", openHash); };
  }, []);

  return <>
    <div className="faq-finder editorial-surface">
      <label htmlFor="faq-search" className="faq-search-label">Find an answer</label>
      <div className="faq-search-row"><input id="faq-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Try odds, penalty takers, Return Atlas…" autoComplete="off" aria-controls="faq-answers" /><button type="button" onClick={() => { setQuery(""); setCategory("all"); }} disabled={!query && category === "all"}>Reset</button></div>
      <div className="faq-popular"><span>Quick answers</span>{popular.map(([label,q]) => <a key={q} href={`#${questionSlug(q)}`} onClick={() => { setQuery(""); setCategory("all"); }}>{label} ↗</a>)}</div>
      <div className="faq-topic-heading"><h2>Browse by topic</h2><button type="button" aria-pressed={category === "all"} onClick={() => setCategory("all")}>All topics</button></div>
      <div className="faq-topics" role="group" aria-label="FAQ topics">{sections.map((section,index) => <button key={section.id} type="button" aria-pressed={category === section.id} onClick={() => setCategory(category === section.id ? "all" : section.id)}><EditorialIcon name={icons[index] ?? "guide"} /><span>{section.title}<small>{section.items.length} answers</small></span></button>)}</div>
    </div>
    <p className="faq-result-count" role="status">{count} {count === 1 ? "answer" : "answers"}{query.trim() ? ` matching “${query.trim()}”` : " available"}</p>
    {count === 0 && <div className="faq-empty editorial-surface"><h2>No matching answers</h2><p>Try a shorter phrase or reset the topic filter.</p><button type="button" onClick={() => { setQuery(""); setCategory("all"); }}>Show all answers</button><Link href="/contact">Ask us a question →</Link></div>}
    <div id="faq-answers" className="faq-answers">{sections.map((section,index) => {
      const shown = (category === "all" || category === section.id) && section.items.some(item => matches(item.q,item.a));
      return <section key={section.id} id={section.id} hidden={!shown} className="faq-answer-section scroll-mt-24">
        {(legacyAnchors[section.id] ?? []).map(id => <span key={id} id={id} className="block scroll-mt-24" />)}
        <h2 className="faq-section-title"><EditorialIcon name={icons[index] ?? "guide"} className="h-10 w-10" />{section.title}</h2>
        <div className="space-y-3">{section.items.map(item => <details key={item.q} id={questionSlug(item.q)} hidden={!matches(item.q,item.a)} open={words.length > 0 ? true : undefined} className="editorial-disclosure faq-answer group scroll-mt-24">
          <summary><span>{item.q}</span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5 shrink-0 transition-transform group-open:rotate-180"><path d="m6 9 6 6 6-6" /></svg></summary>
          <div className="faq-answer-body"><FaqAnswer text={item.a} /></div>
        </details>)}</div>
      </section>;
    })}</div>
  </>;
}
