import type { Metadata } from "next";
import ResourceArticlePage from "@/components/ResourceArticlePage";
import GuideBlocks from "@/components/GuideBlocks";
import { ODDS_VALUE_GUIDE as guide } from "@/lib/odds-value-guide";
import { BASE_URL } from "@/lib/config";

export const dynamic = "force-static";
const path = "/resources/odds-value-stakes";
export const metadata: Metadata = {
  title: { absolute: `${guide.title} | Il Margine` }, description: guide.description,
  alternates: { canonical: `${BASE_URL}${path}` }, robots: { index: true, follow: true },
  openGraph: { title: guide.title, description: guide.description, url: `${BASE_URL}${path}`, type: "article", publishedTime: guide.published, modifiedTime: guide.published, images: ["/brand/20260913/social.png"] },
  twitter: { card: "summary_large_image", title: guide.title, description: guide.description, images: ["/brand/20260913/social.png"] },
};
export default function OddsValueGuidePage() {
  return <ResourceArticlePage eyebrow="From the question to the calculation" title={guide.title} description={guide.description} canonicalPath={path} datePublished={guide.published} dateModified={guide.published} icon={guide.icon} takeaway={guide.takeaway} toc={guide.sections.map(section => ({ id: section.id, label: section.title }))}><GuideBlocks sections={guide.sections} /></ResourceArticlePage>;
}
