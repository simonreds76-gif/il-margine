import type { ReactNode } from "react";
import Link from "next/link";
import Footer from "./Footer";
import PageHomeLink from "./PageHomeLink";
import ResourceContentsNav from "./ResourceContentsNav";
import EditorialIcon, { type EditorialIconName } from "./EditorialIcon";
import { BASE_URL } from "@/lib/config";
import { RESOURCES } from "@/lib/resources";
import "./resource-guides.css";

type Props = { eyebrow: string; title: string; description: string; canonicalPath: string; datePublished?: string; dateModified?: string; toc: { id: string; label: string }[]; children: ReactNode; icon?: EditorialIconName; takeaway?: string };
export default function ResourceArticlePage({ eyebrow, title, description, canonicalPath, datePublished, dateModified, toc, children, icon = "guide", takeaway }: Props) {
  const current = RESOURCES.find(r => r.href === canonicalPath);
  const related = RESOURCES.filter(r => r.href !== canonicalPath && r.featured).slice(0, 3);
  const modified = dateModified ?? datePublished ?? "2026-09-23";
  const schemas = [{ "@context": "https://schema.org", "@type": "Article", headline: title, description, datePublished, dateModified: modified, author: { "@type": "Organization", name: "Il Margine" }, publisher: { "@type": "Organization", name: "Il Margine", logo: { "@type": "ImageObject", url: `${BASE_URL}/brand/20260913/logo.png` } }, image: `${BASE_URL}/brand/20260913/social.png`, mainEntityOfPage: `${BASE_URL}${canonicalPath}` }, { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [{ "@type": "ListItem", position: 1, name: "Home", item: BASE_URL }, { "@type": "ListItem", position: 2, name: "Resources", item: `${BASE_URL}/resources` }, { "@type": "ListItem", position: 3, name: title, item: `${BASE_URL}${canonicalPath}` }] }];
  return <div className="guide-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemas).replace(/</g, "\\u003c") }} />
    <header className="guide-hero"><div className="guide-container">
      <PageHomeLink />
      <nav aria-label="Breadcrumb" className="guide-breadcrumb"><Link href="/resources">Resources</Link><span aria-hidden="true">/</span><span aria-current="page">{title}</span></nav>
      <div className="guide-hero-title"><EditorialIcon name={icon} /><div><div className="guide-label">{eyebrow}</div><h1>{title}</h1><p className="guide-deck">{description}</p><div className="guide-meta"><span>By Il Margine</span><time dateTime={modified}>Updated {new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric" }).format(new Date(`${modified}T12:00:00Z`))}</time>{current && <span>{current.minRead} min read</span>}</div></div></div>
    </div></header>
    <main className="guide-container guide-layout"><ResourceContentsNav items={toc} /><article className="guide-copy">
      {takeaway && <aside className="guide-takeaway"><div className="guide-label">The useful bit, first</div><p>{takeaway}</p></aside>}
      {children}
      <section className="guide-related" aria-labelledby="related-guides"><div className="guide-label">Put it into practice</div><h2 id="related-guides">Keep learning</h2><div className="guide-related-grid"><Link href="/calculator"><EditorialIcon name="analysis" className="h-9 w-9" /><h3>Try the four betting calculators</h3></Link>{related.map(r => <Link key={r.href} href={r.href}><EditorialIcon name={r.href.includes("kelly") ? "bankroll" : r.href.includes("closing") ? "markets" : "guide"} className="h-9 w-9" /><h3>{r.title}</h3></Link>)}</div></section>
    </article></main><Footer />
  </div>;
}
