import type { Metadata } from "next";
import fs from "fs";
import path from "path";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import FaqAnswer from "@/components/FaqAnswer";
import FaqOpenByHash from "@/components/FaqOpenByHash";
import { parseFaqMd, type FaqSection } from "@/lib/parse-faq";

function questionSlug(q: string): string {
  return q
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "FAQ",
  description:
    "Frequently asked questions about Il Margine: betting tips, Telegram, player props, tennis, ROI, bookmakers, bankroll management, and more.",
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
      <FaqOpenByHash />
      <section className="pt-4 pb-8 md:pt-6 md:pb-10 border-b border-slate-800/50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8"
          >
            <Image
              src="/favicon.png"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 object-contain shrink-0"
            />
            <span>← Home</span>
          </Link>

          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-2">
            Frequently Asked Questions
          </h1>
          <p className="text-slate-400 text-base mb-8">
            Betting with mathematical edge, Telegram tips, player props, tennis, ROI, bookmakers, and more.
          </p>

          {/* Section navigation */}
          <nav
            className="rounded-xl bg-slate-800/40 border border-slate-700/50 p-4 sm:p-5 mb-10"
            aria-label="FAQ sections"
          >
            <h2 className="text-xs font-mono font-semibold text-emerald-400 tracking-wider mb-3">
              Jump to section
            </h2>
            <ul className="flex flex-wrap gap-2">
              {sections.map((sec) => (
                <li key={sec.id}>
                  <a
                    href={`#${sec.id}`}
                    className="text-sm text-slate-300 hover:text-emerald-400 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-700/50"
                  >
                    {sec.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          {/* Accordion sections */}
          <div className="space-y-10">
            {sections.map((section) => (
              <section
                key={section.id}
                id={section.id}
                className="scroll-mt-24"
              >
                <h2 className="text-lg font-semibold text-emerald-400 mb-4 font-mono tracking-wide">
                  {section.title}
                </h2>
                <div className="space-y-2">
                  {section.items.map((item, idx) => (
                    <details
                      key={idx}
                      id={questionSlug(item.q)}
                      className="group rounded-xl bg-slate-800/40 border border-slate-700/50 overflow-hidden scroll-mt-24"
                    >
                      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3.5 text-left text-slate-200 hover:bg-slate-700/30 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500">
                        <span className="flex-1 font-medium">{item.q}</span>
                        <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180" aria-hidden>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </span>
                      </summary>
                      <div className="border-t border-slate-700/50 px-4 py-3 bg-slate-800/20">
                        <FaqAnswer text={item.a} />
                      </div>
                    </details>
                  ))}
                </div>
              </section>
            ))}
          </div>

          <div className="mt-12 rounded-xl bg-slate-800/40 border border-slate-700/50 p-5 text-center">
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
      </section>
      <Footer />
    </div>
  );
}
