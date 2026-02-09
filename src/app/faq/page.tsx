import type { Metadata } from "next";
import fs from "fs";
import path from "path";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import FaqAnswer from "@/components/FaqAnswer";
import FaqOpenByHash from "@/components/FaqOpenByHash";
import { parseFaqMd, questionSlug, type FaqSection } from "@/lib/parse-faq";
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

          {/* Section navigation - numbered list for clear structure */}
          <nav
            className="rounded-xl bg-slate-800/50 border border-slate-700/50 p-5 sm:p-6 mb-12 shadow-sm"
            aria-label="FAQ sections"
          >
            <h2 className="text-xs font-mono font-semibold text-emerald-400 tracking-wider mb-4">
              Jump to section
            </h2>
            <ol className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 list-none pl-0">
              {sections.map((sec, index) => (
                <li key={sec.id} className="flex items-baseline gap-2">
                  <span className="text-slate-500 font-mono text-sm shrink-0 w-6" aria-hidden>
                    {String(index + 1).padStart(2, " ")}.
                  </span>
                  <a
                    href={`#${sec.id}`}
                    className="text-sm text-slate-300 hover:text-emerald-400 transition-colors py-1.5 rounded hover:bg-slate-700/40 -mx-1 px-1"
                  >
                    {sec.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          {/* Accordion sections */}
          <div className="space-y-12">
            {sections.map((section, index) => (
              <section
                key={section.id}
                id={section.id}
                className="scroll-mt-24"
              >
                <h2 className="text-base font-semibold text-slate-100 mb-1 flex items-center gap-3">
                  <span className="text-emerald-400/80 font-mono text-sm shrink-0 w-6">{index + 1}.</span>
                  <span className="w-1 h-6 rounded-full bg-emerald-400/80 shrink-0" aria-hidden />
                  {section.title}
                </h2>
                <p className="text-slate-500 text-sm mb-5 pl-10">{section.items.length} question{section.items.length !== 1 ? "s" : ""}</p>
                <div className="space-y-3">
                  {section.items.map((item, idx) => (
                    <details
                      key={idx}
                      id={questionSlug(item.q)}
                      className="group rounded-xl bg-slate-800/50 border border-slate-700/50 overflow-hidden scroll-mt-24 shadow-sm hover:border-slate-600"
                    >
                      <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-4 text-left text-slate-200 hover:bg-slate-700/30 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 rounded-xl border-l-4 border-transparent group-open:border-emerald-500/80 group-open:bg-slate-700/20">
                        <span className="flex-1 font-medium text-[15px] leading-snug">{item.q}</span>
                        <span className="text-emerald-400 shrink-0 transition-transform duration-200 group-open:rotate-180" aria-hidden>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </span>
                      </summary>
                      <div className="border-t border-slate-700/50 px-5 py-4 bg-slate-800/30 min-h-[1px]">
                        <FaqAnswer text={item.a} />
                      </div>
                    </details>
                  ))}
                </div>
              </section>
            ))}
          </div>

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
      </section>
      <Footer />
    </div>
  );
}
