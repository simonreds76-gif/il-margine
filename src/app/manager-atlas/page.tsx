import AtlasPageHeader from "@/components/AtlasPageHeader";
import frame from "@/components/ResearchPage.module.css";
import type { Metadata } from "next";
import RelatedLinks from "@/components/RelatedLinks";
import Footer from "@/components/Footer";
import release from "@/data/manager-atlas-release.json";
import { MANAGER_ATLAS_FAQS } from "@/lib/manager-atlas-faq";
import { managerShell } from "./shell";
import ManagerClient from "./ManagerClient";
import "./manager.css";

export const dynamic = "force-static";
export const revalidate = false;
const url = "https://ilmargine.bet/manager-atlas";
const title = "Football Manager H2H & Betting Returns";
const shareTitle = `${title} | Return Atlas`;
const description = "Compare football managers head to head. Explore past results and see what backing their team, the draw or their opponent returned at the recorded odds.";
const shareImage = {
  url: "https://ilmargine.bet/manager-atlas/share-v2.png",
  width: 1200,
  height: 630,
  type: "image/png",
  alt: "Return Atlas Managers by Il Margine. Compare managers, results and historical betting returns.",
};
export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  robots: { index: true, follow: true, "max-image-preview": "large" },
  openGraph: {
    title: shareTitle, description, url, siteName: "Il Margine",
    locale: "en_GB", type: "website", images: [shareImage],
  },
  twitter: {
    card: "summary_large_image", title: shareTitle, description,
    images: [{ url: shareImage.url, alt: shareImage.alt }],
  },
};

// Adapt the generated research island without losing its runtime IDs or source evidence.
function prepareManagerShell(source: string) {
  const facts = source.match(/<div class="archive-facts">[\s\S]*?<\/div><\/div>\s*<\/div>/)?.[0]?.replace(/<\/div>\s*$/, "") ?? "";
  const coverage = source.slice(source.indexOf('<div class="coverage-strip">'), source.indexOf('</header>'));
  let html = source.replace(/<header>[\s\S]*?<\/header>/, `<details class="manager-coverage"><summary>How it works &amp; coverage</summary><p>Pick a manager to see their record. Add an opposing manager to compare their past meetings. These are historical returns at recorded prices, separate from our published picks.</p>${facts}${coverage}</details>`);
  html = html.replace('<label><span><i data-icon="club"></i> Opposing club', '<details class="manager-extra-filters"><summary>More filters <span id="active-filter-count"></span></summary><div class="manager-filter-grid"><label><span><i data-icon="club"></i> Opposing club');
  html = html.replace('<div class="filter-actions">', '</div></details><div class="filter-actions">');
  html = html.replace('<div class="unit-guide">', '<details class="manager-unit-help"><summary>Read ROI and units</summary><div class="unit-guide">').replace('<p id="status"', '</details><p id="status"');
  html = html.replace('<button id="swap">Swap managers ⇄</button>', '<button id="swap" aria-label="Swap managers" title="Swap managers">⇄</button>');
  return html;
}

export default function ManagerAtlasPage() {
  const through = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(release.through + "T12:00:00Z"));
  const html = prepareManagerShell(managerShell).replaceAll("__THROUGH__", through).replaceAll("__MATCHES__", release.matches.toLocaleString("en-GB")).replaceAll("__MANAGERS__", String(release.managers));
  const schema = [{ "@context": "https://schema.org", "@type": "WebApplication", name: "Return Atlas Managers", url, description, applicationCategory: "SportsApplication", operatingSystem: "Any", isAccessibleForFree: true }, { "@context": "https://schema.org", "@type": "FAQPage", mainEntity: MANAGER_ATLAS_FAQS.map(({ question, answer }) => ({ "@type": "Question", name: question, acceptedAnswer: { "@type": "Answer", text: answer } })) }];
  return <><main className={`manager-atlas ${frame.page}`}>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />
    <AtlasPageHeader edition="managers" description="Compare managers across clubs or head to head. Explore past results and returns for team wins, draws and opponents." />
    <ManagerClient html={html} indexUrl={release.indexUrl} />
    <noscript><p>Enable JavaScript to filter the archive and compare managers. Coverage, explanations and FAQs remain available below.</p></noscript>
    <section className="manager-faq" id="manager-faq"><p className="eyebrow">UNDERSTAND THE RECORD</p><h2>Manager Return Atlas FAQs</h2>{MANAGER_ATLAS_FAQS.map(({ question, answer }) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <RelatedLinks title="Follow the record into the next fixture." links={[
      { href: "/football-atlas/fixtures", title: "Matchday", description: "Upcoming fixtures with manager and club histories." },
      { href: "/football-atlas", title: "Football Return Atlas", description: "Explore club returns by season, venue and odds." },
      { href: "/tools", title: "All betting tools", description: "Find the right tool for your question." },
      { href: "/track-record", title: "Our published results", description: "Inspect the full record of our selections." },
    ]} />
  </main><Footer /></>;
}
