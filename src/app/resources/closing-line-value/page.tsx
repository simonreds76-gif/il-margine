import type { Metadata } from "next";
import ResourceArticlePage from "@/components/ResourceArticlePage";
import GuideBlocks from "@/components/GuideBlocks";
import { RESOURCE_GUIDES, GUIDE_REVIEW_DATE } from "@/lib/resource-guides";
import { BASE_URL } from "@/lib/config";

const PATH = "/resources/closing-line-value";
const guide = RESOURCE_GUIDES["closing-line-value"];
export const metadata: Metadata = {
  title: guide.title, description: guide.description,
  alternates: { canonical: `${BASE_URL}${PATH}` }, robots: { index: true, follow: true },
  openGraph: { title: guide.title, description: guide.description, url: `${BASE_URL}${PATH}`, type: "article", publishedTime: guide.published, modifiedTime: GUIDE_REVIEW_DATE, images: [`${BASE_URL}/brand/20260913/social.png`] },
  twitter: { card: "summary_large_image", title: guide.title, description: guide.description, images: [`${BASE_URL}/brand/20260913/social.png`] },
};
export default function GuidePage() {
  return <ResourceArticlePage eyebrow="Practical betting guide" title={guide.title} description={guide.description} canonicalPath={PATH} datePublished={guide.published} dateModified={GUIDE_REVIEW_DATE} icon={guide.icon} takeaway={guide.takeaway} toc={guide.sections.map(s => ({ id: s.id, label: s.title }))}>
    <GuideBlocks sections={guide.sections} />
  </ResourceArticlePage>;
}
