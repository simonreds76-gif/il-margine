import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
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

export default function ManagerAtlasPage() {
  const through = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(release.through + "T12:00:00Z"));
  const html = managerShell.replaceAll("__THROUGH__", through).replaceAll("__MATCHES__", release.matches.toLocaleString("en-GB")).replaceAll("__MANAGERS__", String(release.managers));
  const schema = [{ "@context": "https://schema.org", "@type": "WebApplication", name: "Return Atlas Managers", url, description, applicationCategory: "SportsApplication", operatingSystem: "Any", isAccessibleForFree: true }, { "@context": "https://schema.org", "@type": "FAQPage", mainEntity: MANAGER_ATLAS_FAQS.map(({ question, answer }) => ({ "@type": "Question", name: question, acceptedAnswer: { "@type": "Answer", text: answer } })) }];
  return <><main className="manager-atlas">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />
    <Link className="manager-fixtures-entry" href="/football-atlas/fixtures" prefetch={false}><Image src="/football-atlas/matchday/mark-v1.svg" alt="" width={42} height={42} unoptimized className="shrink-0" /><span><strong>Return Atlas Matchday</strong><small>See upcoming fixtures with manager and club H2H returns</small></span><span aria-hidden="true" className="ml-auto">↗</span></Link>
    <ManagerClient html={html} indexUrl={release.indexUrl} />
    <noscript><p>Enable JavaScript to filter the archive and compare managers. Coverage, explanations and FAQs remain available below.</p></noscript>
    <section className="manager-faq" id="manager-faq"><p className="eyebrow">UNDERSTAND THE RECORD</p><h2>Manager Return Atlas FAQs</h2>{MANAGER_ATLAS_FAQS.map(({ question, answer }) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <p><Link href="/football-atlas" prefetch={false}>Explore club returns →</Link> · <Link href="/tools" prefetch={false}>All betting tools →</Link> · <Link href="/track-record" prefetch={false}>Our published results →</Link></p>
  </main><Footer /></>;
}
