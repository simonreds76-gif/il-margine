import type { Metadata } from "next";
import Link from "next/link";

import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";
import { readWorldCupData, WORLD_CUP_PENALTIES_URL } from "@/lib/world-cup-penalties";

const PAGE_URL = `${BASE_URL}/player-props/world-cup-2026`;

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "World Cup 2026 Player Props | Il Margine",
  description:
    "World Cup 2026 player props hub for Il Margine, covering posted props, penalty-taker intelligence and the separate untracked goalscorer research lab.",
  alternates: {
    canonical: PAGE_URL,
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    type: "website",
    url: PAGE_URL,
    title: "World Cup 2026 Player Props | Il Margine",
    description:
      "World Cup player props hub: posted picks, penalty hierarchy and research-only goalscorer lab.",
    images: [{ url: `${BASE_URL}/og.png`, width: 1200, height: 630, alt: "Il Margine World Cup player props" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "World Cup 2026 Player Props | Il Margine",
    description: "World Cup player props hub: posted picks, penalty hierarchy and research-only goalscorer lab.",
    images: [`${BASE_URL}/og.png`],
  },
};

export default async function WorldCupPlayerPropsPage() {
  const worldCupData = await readWorldCupData().catch(() => null);
  const teamCount = worldCupData?.teams.length ?? 48;
  const lastVerified = worldCupData?.last_verified ?? "pending refresh";

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main>
        <section className="relative overflow-hidden border-b border-slate-800/60">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(87,209,150,0.18),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.96),rgba(3,7,18,0.98))]" />
          <div className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
            <div className="mb-6 flex flex-wrap items-center gap-3">
              <PageHomeLink />
              <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-mono uppercase tracking-[0.18em] text-emerald-300">
                World Cup 2026
              </span>
              <span className="rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1 text-xs font-mono uppercase tracking-[0.18em] text-slate-300">
                Player props hub
              </span>
            </div>

            <div className="grid gap-8 lg:grid-cols-[1.25fr_0.75fr] lg:items-end">
              <div>
                <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-white sm:text-6xl">
                  World Cup player props, without pretending the club model is already proven.
                </h1>
                <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300 sm:text-lg">
                  This is the tournament hub for World Cup 2026 props. Posted props can still enter the normal
                  Il Margine public record. Goalscorer model rows stay separate and untracked until the national-team
                  lane earns evidence.
                </p>
              </div>

              <div className="rounded-[1.5rem] border border-emerald-400/20 bg-slate-950/70 p-5">
                <p className="text-xs font-mono uppercase tracking-[0.2em] text-emerald-300">Readiness snapshot</p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
                    <div className="text-2xl font-semibold text-white">{teamCount}</div>
                    <div className="mt-1 text-xs text-slate-500">teams in file</div>
                  </div>
                  <div className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
                    <div className="text-sm font-semibold text-white">{lastVerified}</div>
                    <div className="mt-1 text-xs text-slate-500">penalty file verified</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-6xl gap-4 px-4 py-10 sm:px-6 lg:grid-cols-3 lg:px-8">
          {[
            {
              title: "Priority 1: shots on target",
              copy: "Most World Cup output should start here. SOT lines are less dependent on finishing variance and penalty-role noise.",
            },
            {
              title: "Priority 2: total shots",
              copy: "Useful when role and team attacking volume are clear, especially against weaker defensive tiers.",
            },
            {
              title: "Priority 3: ATGS research",
              copy: "Anytime goalscorer stays sparse: high-confidence penalty takers or clear number nines only.",
            },
          ].map((item) => (
            <article key={item.title} className="rounded-[1.5rem] border border-slate-800 bg-slate-950/70 p-6">
              <h2 className="text-xl font-semibold text-white">{item.title}</h2>
              <p className="mt-3 text-sm leading-6 text-slate-400">{item.copy}</p>
            </article>
          ))}
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-12 sm:px-6 lg:px-8">
          <div className="rounded-[1.75rem] border border-slate-800 bg-slate-950/70 p-6 sm:p-8">
            <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
              <div>
                <p className="text-xs font-mono uppercase tracking-[0.2em] text-emerald-300">What is tracked?</p>
                <h2 className="mt-3 text-2xl font-semibold text-white">Posted props stay in the official props record.</h2>
                <p className="mt-3 text-sm leading-6 text-slate-400">
                  If a World Cup shots, SOT, cards, tackles or fouls pick is posted as an Il Margine player prop, it
                  should use the existing public record path. The separate goalscorer research lab is not part of that
                  record.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Link
                  href="/player-props#picks"
                  className="rounded-2xl border border-emerald-400/30 bg-emerald-400/10 p-4 text-sm font-semibold text-emerald-100 transition hover:border-emerald-300"
                >
                  View current player props
                </Link>
                <Link
                  href={WORLD_CUP_PENALTIES_URL}
                  className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4 text-sm font-semibold text-slate-200 transition hover:border-emerald-400/50"
                >
                  World Cup penalty takers
                </Link>
                <Link
                  href="/fair-odds-lab/world-cup"
                  className="rounded-2xl border border-amber-300/30 bg-amber-300/10 p-4 text-sm font-semibold text-amber-100 transition hover:border-amber-200"
                >
                  Untracked goalscorer research lab
                </Link>
                <Link
                  href="/fair-odds-lab"
                  className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4 text-sm font-semibold text-slate-200 transition hover:border-emerald-400/50"
                >
                  Validated club Fair Odds Lab
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
