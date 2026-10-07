import type { Metadata } from "next";
import fs from "fs";
import path from "path";
import Footer from "@/components/Footer";
import FaqBrowser from "@/components/FaqBrowser";
import legacyAnchors from "@/data/faq-legacy-anchors.json";
import "./faq.css";
import { parseFaqMd, type FaqSection } from "@/lib/parse-faq";
import { BASE_URL } from "@/lib/config";
import PageHeading from "@/components/PageHeading";
import RelatedLinks from "@/components/RelatedLinks";
import "@/components/editorial-surfaces.css";

export const metadata: Metadata = {
  title: "Betting FAQ: Return Atlas, Tips and Odds Explained",
  description:
    "Answers about betting tips, Return Atlas Matchday, manager and club history, Tennis Matchup Lab, fair odds, staking calculators and the Il Margine results record.",
  alternates: {
    canonical: `${BASE_URL}/faq`,
  },
  robots: "index, follow",
};

function stripForSchema(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\n\n+/g, "\n")
    .trim();
}

function buildFaqSchema(sections: FaqSection[]) {
  const mainEntity = sections.flatMap((s) =>
    s.items.map((item) => ({
      "@type": "Question" as const,
      name: item.q,
      acceptedAnswer: {
        "@type": "Answer" as const,
        text: stripForSchema(item.a),
      },
    }))
  );
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity,
  };
}

export default function FaqPage() {
  const mdPath = path.join(process.cwd(), "docs", "faq-content.md");
  const md = fs.readFileSync(mdPath, "utf8");
  const sections = parseFaqMd(md);
  const schema = buildFaqSchema(sections);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />
      <main className="pb-8 md:pb-10 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <PageHeading eyebrow="Questions" title="Your questions, answered." icon="guide"><p>Using the picks, checking a price, reading the record. Practical answers about Il Margine and its research tools.</p></PageHeading>

          <p className="text-xs text-slate-400">Updated <time dateTime="2026-10-01">1 October 2026</time> · Answers reflect the current public tools.</p>
          <FaqBrowser sections={sections} legacyAnchors={legacyAnchors} />

          <RelatedLinks title="Still have questions?" links={[{href:"/contact",title:"Contact Il Margine",description:"Ask a question, report an error or share evidence.",icon:"guide"},{href:"/resources",title:"Explore the guides",description:"Worked examples for odds, value and staking.",icon:"tools"}]} />
        </div>
      </main>
      <Footer />
    </div>
  );
}
