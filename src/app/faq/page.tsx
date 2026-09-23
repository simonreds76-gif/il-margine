import type { Metadata } from "next";
import fs from "fs";
import path from "path";
import Link from "next/link";
import Footer from "@/components/Footer";
import FaqBrowser from "@/components/FaqBrowser";
import legacyAnchors from "@/data/faq-legacy-anchors.json";
import "./faq.css";
import { parseFaqMd, type FaqSection } from "@/lib/parse-faq";
import { BASE_URL } from "@/lib/config";
import PageHomeLink from "@/components/PageHomeLink";
import "@/components/editorial-surfaces.css";

export const metadata: Metadata = {
  title: "Betting FAQ: Tips, Odds and Bankroll",
  description:
    "Answers about betting tips, changed odds, penalty takers, Return Atlas, fair odds, staking calculators and the Il Margine results record.",
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
      <main className="public-hub-heading pt-5 pb-8 md:pb-10 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-8" />

          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">QUESTIONS</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-2">
            Your questions, answered.
          </h1>
          <p className="text-slate-400 text-base mb-8">
            Using the picks, checking a price, reading the record. Practical answers about Il Margine and its research tools.
          </p>

          <p className="text-xs text-slate-400">Reviewed <time dateTime="2026-09-23">23 September 2026</time> · Answers reflect the current public tools.</p>
          <FaqBrowser sections={sections} legacyAnchors={legacyAnchors} />

          <div className="mt-14 rounded-xl bg-slate-800/50 border border-slate-700/50 p-6 text-center shadow-sm">
            <p className="text-slate-400 text-sm mb-3">Still have questions?</p>
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 text-emerald-400 hover:text-emerald-300 font-medium text-sm"
            >
              Contact us
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
