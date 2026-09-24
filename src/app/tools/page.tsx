import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import EditorialIcon from "@/components/EditorialIcon";
import { BASE_URL } from "@/lib/config";
import { BETTING_TOOL_GROUPS, BETTING_STEPS } from "@/lib/betting-tools";
import "./tools.css";

export const dynamic = "force-static";
const title = "Free Betting Tools: Fair Odds, Research & Staking";
const description = "Find the right betting tool: fair odds and value calculators, football and tennis Return Atlas, penalty takers, bookmaker margins and Kelly staking.";
export const metadata: Metadata = {
  title, description, alternates: { canonical: `${BASE_URL}/tools` }, robots: { index: true, follow: true },
  openGraph: { title, description, url: `${BASE_URL}/tools`, type: "website", images: ["/brand/20260913/social.png"] },
  twitter: { card: "summary_large_image", title, description, images: ["/brand/20260913/social.png"] },
};

export default function ToolsPage() {
  const schema = [
    { "@context": "https://schema.org", "@type": "CollectionPage", name: title, description, url: `${BASE_URL}/tools`, mainEntity: { "@type": "ItemList", itemListElement: BETTING_TOOL_GROUPS.flatMap(group => group.tools).map((tool, i) => ({ "@type": "ListItem", position: i + 1, name: tool.title, url: `${BASE_URL}${tool.href}` })) } },
    { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [{ "@type": "ListItem", position: 1, name: "Home", item: BASE_URL }, { "@type": "ListItem", position: 2, name: "Betting tools", item: `${BASE_URL}/tools` }] },
  ];
  return <div className="tools-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />
    <main className="site-container">
      <header className="page-heading tools-heading">
        <PageHomeLink />
        <p className="site-eyebrow">The Il Margine toolkit</p>
        <h1>Better questions.<br /><span>Sharper betting tools.</span></h1>
        <p className="tools-deck">Check a price. Research a player or club. Understand the stake. Free tools that put the numbers behind a bet within reach.</p>
        <nav className="tools-jumps" aria-label="Tool categories">{BETTING_TOOL_GROUPS.map(group => <a key={group.id} href={`#${group.id}`}>{({ price: "Prices", research: "Research", stake: "Staking" } as Record<string, string>)[group.id]} <span aria-hidden="true">↓</span></a>)}</nav>
      </header>
      <section className="tools-start" aria-labelledby="tools-start-title">
        <div className="tools-section-head"><div><p className="site-eyebrow">New to the numbers?</p><h2 id="tools-start-title">One bet, four useful questions.</h2></div><Link prefetch={false} href="/resources/odds-value-stakes" className="site-text-link">Follow the worked example →</Link></div>
        <ol className="tools-steps">{BETTING_STEPS.map((step, i) => <li key={step.title}><Link prefetch={false} href={step.href}><div className="tools-step-top"><EditorialIcon name={step.icon} className="h-8 w-8" /><span>0{i + 1}</span></div><h3>{step.title}</h3><p>{step.detail}</p></Link></li>)}</ol>
      </section>
      {BETTING_TOOL_GROUPS.map(group => <section key={group.id} id={group.id} className="tools-group" aria-labelledby={`${group.id}-title`}>
        <div className="tools-section-head"><div><p className="site-eyebrow">{group.question}</p><h2 id={`${group.id}-title`}>{group.title}</h2></div></div>
        <div className="tools-grid">{group.tools.map(tool => <Link prefetch={false} key={tool.href} href={tool.href} className="tools-card"><div className="tools-card-top"><EditorialIcon name={tool.icon} className="h-11 w-11" /><span>{tool.badge}</span></div><h3>{tool.title}</h3><p>{tool.description}</p><span className="tools-card-action">{tool.action}<span aria-hidden="true">↗</span></span></Link>)}</div>
      </section>)}
      <section className="tools-evidence"><EditorialIcon name="guide" className="h-11 w-11" /><div><h2>Keep research and results in view.</h2><p>Historical returns describe a sample. Model probabilities are estimates. Our published selections have their own record, including losing bets.</p><div className="tools-jumps"><Link prefetch={false} href="/track-record">Published track record →</Link><Link prefetch={false} href="/resources">Practical betting guides →</Link><Link prefetch={false} href="/the-edge">Our methodology →</Link></div></div></section>
    </main><Footer />
  </div>;
}
