import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";
import { CLUB_LEAGUES, CLUB_PENALTY_SEASON } from "@/lib/club-penalty-takers";

const PAGE_URL = `${BASE_URL}/penalty-takers/methodology`;
const PAGE_TITLE = "How Il Margine Verifies Club Penalty Takers";
const PAGE_DESCRIPTION = "The evidence, absence, shootout and correction rules behind Il Margine's club penalty-taker hierarchies.";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: PAGE_URL },
  openGraph: { type: "article", url: PAGE_URL, title: `${PAGE_TITLE} | Il Margine`, description: PAGE_DESCRIPTION, siteName: "Il Margine" },
  robots: { index: true, follow: true },
};

const RULES = [
  {
    title: "Competitive in-match penalties lead",
    body: "A regular-time or extra-time penalty in a competitive match is the strongest direct evidence. We record the taker, outcome, players available and whether the listed first choice was on the pitch.",
  },
  {
    title: "Absence is not a promotion",
    body: "A backup taking while the primary is injured, suspended, substituted or benched does not automatically change the order. It confirms the fallback only unless later evidence shows a genuine handover.",
  },
  {
    title: "Shootouts are supporting evidence",
    body: "Shootout order can reveal trust under pressure, but it is labelled separately and cannot by itself overrule a stronger trail of in-match penalties.",
  },
  {
    title: "Misses need context",
    body: "One miss does not automatically remove a taker. A repeated handover, a manager statement or another player taking with the former primary available is stronger evidence of change.",
  },
  {
    title: "No evidence means no confident claim",
    body: "Promoted clubs and unclear squads remain marked not verified. We would rather publish an honest gap than fill a search page with a speculative name.",
  },
  {
    title: "Every public change is reviewed",
    body: "Detection can be automated, but hierarchy changes are not. A human reviews the match context and source trail before the public file, page and sitemap date can change.",
  },
];

export default function ClubPenaltyMethodologyPage() {
  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: "Penalty Takers", item: `${BASE_URL}/penalty-takers` },
      { "@type": "ListItem", position: 3, name: "Methodology", item: PAGE_URL },
    ],
  };
  const articleData = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
    url: PAGE_URL,
    datePublished: "2026-07-10",
    dateModified: "2026-07-10",
    author: { "@type": "Organization", name: "Il Margine", url: BASE_URL },
    publisher: { "@type": "Organization", name: "Il Margine", url: BASE_URL },
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleData) }} />
      <main className="mx-auto max-w-5xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pt-6 pb-10">
          <PageHomeLink className="mb-8" />
          <div className="mb-5 flex items-center gap-2 text-sm text-slate-400">
            <Link href="/penalty-takers" className="hover:text-slate-100">Penalty Takers</Link><span>/</span><span className="text-slate-200">Methodology</span>
          </div>
          <div className="rounded-[32px] border border-emerald-400/18 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.17),transparent_38%),linear-gradient(150deg,#07100f,#0e1620_62%,#11131b)] p-6 sm:p-9 lg:p-11">
            <div className="font-mono text-xs uppercase tracking-[0.26em] text-emerald-400">Evidence policy</div>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-100 sm:text-5xl">How we verify club penalty takers</h1>
            <p className="mt-5 max-w-3xl text-base leading-8 text-slate-300">
              The {CLUB_PENALTY_SEASON} boards separate direct evidence from inference. These rules determine what can change a hierarchy, what remains provisional and what we refuse to publish automatically.
            </p>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          {RULES.map((rule, index) => (
            <article key={rule.title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
              <div className="font-mono text-xs text-emerald-400">0{index + 1}</div>
              <h2 className="mt-2 text-xl font-semibold text-slate-100">{rule.title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-400">{rule.body}</p>
            </article>
          ))}
        </section>

        <section className="mt-8 rounded-3xl border border-slate-800 bg-slate-900/50 p-5 sm:p-7">
          <h2 className="text-2xl font-semibold text-slate-100">Freshness and corrections</h2>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-400">
            <p><strong className="text-slate-200">Last verified</strong> is the date of the strongest reviewed evidence. <strong className="text-slate-200">Public file updated</strong> changes only when the page content or hierarchy changes.</p>
            <p>During preseason, final {CLUB_PENALTY_SEASON === "2026/27" ? "2025/26" : "prior-season"} orders can appear as labelled carryovers. They are not presented as newly confirmed evidence.</p>
            <p>Corrections are applied to the public record with an explicit reason. Detection tools can produce review candidates, but they cannot publish a new first-choice taker.</p>
          </div>
        </section>

        <nav aria-label="Penalty taker league boards" className="mt-8 flex flex-wrap gap-2">
          {CLUB_LEAGUES.map((league) => <Link key={league.key} href={`/penalty-takers/${league.key}`} className="rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300 hover:border-emerald-400/30 hover:text-emerald-200">{league.label}</Link>)}
        </nav>
      </main>
      <Footer />
    </div>
  );
}
