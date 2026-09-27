import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import release from "@/data/manager-atlas-release.json";
import { MANAGER_ATLAS_FAQS } from "@/lib/manager-atlas-faq";
import { managerShell } from "./shell";
import ManagerClient from "./ManagerClient";
import "./manager.css";

export const dynamic = "force-static";
export const revalidate = false;
const url = "https://ilmargine.bet/manager-atlas";
const title = "Return Atlas Managers: Football H2H, ROI & Betting History";
const description = "Compare football managers’ head-to-head records and historical betting returns. Explore team, draw and opponent ROI by league, seasons, venue and odds range.";
export const metadata: Metadata = { title, description, alternates: { canonical: url }, robots: { index: true, follow: true }, openGraph: { title, description, url, type: "website", images: [{ url: "/manager-atlas/share-v1.png", width: 1200, height: 630, alt: "Return Atlas Managers — head-to-head, the odds and the returns" }] }, twitter: { card: "summary_large_image", title, description, images: ["/manager-atlas/share-v1.png"] } };

export default function ManagerAtlasPage() {
  const through = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(release.through + "T12:00:00Z"));
  const html = managerShell.replaceAll("__THROUGH__", through).replaceAll("__MATCHES__", release.matches.toLocaleString("en-GB")).replaceAll("__MANAGERS__", String(release.managers));
  const schema = [{ "@context": "https://schema.org", "@type": "WebApplication", name: "Return Atlas Managers", url, description, applicationCategory: "SportsApplication", operatingSystem: "Any", isAccessibleForFree: true }, { "@context": "https://schema.org", "@type": "FAQPage", mainEntity: MANAGER_ATLAS_FAQS.map(({ question, answer }) => ({ "@type": "Question", name: question, acceptedAnswer: { "@type": "Answer", text: answer } })) }];
  return <><main className="manager-atlas">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />
    <ManagerClient html={html} indexUrl={release.indexUrl} />
    <noscript><p>Enable JavaScript to filter the archive and compare managers. Coverage, explanations and FAQs remain available below.</p></noscript>
    <section className="manager-faq" id="manager-faq"><p className="eyebrow">UNDERSTAND THE RECORD</p><h2>Manager Return Atlas FAQs</h2>{MANAGER_ATLAS_FAQS.map(({ question, answer }) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <p><Link href="/football-atlas" prefetch={false}>Explore club returns →</Link> · <Link href="/tools" prefetch={false}>All betting tools →</Link> · <Link href="/track-record" prefetch={false}>Our published results →</Link></p>
  </main><Footer /></>;
}
