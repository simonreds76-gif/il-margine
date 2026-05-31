import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";

const PAGE_URL = `${BASE_URL}/world-cup-2026-free-picks`;
const OG_IMAGE = `${BASE_URL}/brand/world-cup-2026-free-picks.png`;

export const metadata: Metadata = {
  title: "Free World Cup 2026 Picks",
  description:
    "Join the free Il Margine World Cup 2026 Telegram channel for goalscorer angles, player props, penalty-taker updates and big-market value spots.",
  alternates: {
    canonical: PAGE_URL,
  },
  openGraph: {
    type: "website",
    url: PAGE_URL,
    title: "Free World Cup 2026 Picks | Il Margine",
    description:
      "Goalscorer angles, player props, penalty-taker swings and big-market value spots posted free on Telegram during the World Cup.",
    images: [
      {
        url: OG_IMAGE,
        width: 1024,
        height: 1024,
        alt: "Il Margine World Cup 2026 Free Picks",
        type: "image/png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Free World Cup 2026 Picks | Il Margine",
    description:
      "Join the free Il Margine Telegram channel for World Cup 2026 picks, props and penalty-taker updates.",
    images: [OG_IMAGE],
  },
};

const INSIDE = [
  {
    title: "Goalscorer angles",
    body: "Player prices, role changes, penalty status and matchup context when the market leaves a gap.",
  },
  {
    title: "Player props",
    body: "Shots, assists, cards and tournament-specific player markets where the number looks wrong.",
  },
  {
    title: "Penalty-taker updates",
    body: "The hierarchy swings from our World Cup penalty file, with the evidence behind the call.",
  },
  {
    title: "Big-market value spots",
    body: "Match lines, totals and broader market notes when the price is interesting enough to flag.",
  },
] as const;

export default function WorldCupFreePicksPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pt-6 pb-12 md:pb-16">
          <PageHomeLink className="mb-8" />

          <div className="relative overflow-hidden rounded-[34px] border border-slate-800/80 bg-[radial-gradient(circle_at_18%_18%,rgba(16,185,129,0.16),transparent_28%),linear-gradient(155deg,rgba(4,10,18,0.98),rgba(6,22,20,0.96))] p-5 shadow-[0_22px_70px_rgba(0,0,0,0.3)] sm:p-8 lg:p-10">
            <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-emerald-400/12 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-24 left-20 h-64 w-64 rounded-full bg-amber-400/10 blur-3xl" />

            <div className="relative grid gap-8 lg:grid-cols-[1.05fr,0.95fr] lg:items-center">
              <div>
                <div className="inline-flex rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-emerald-200">
                  Telegram channel
                </div>
                <h1 className="mt-5 text-[2.45rem] font-semibold leading-[0.95] tracking-tight text-slate-100 sm:text-6xl sm:leading-[0.98]">
                  Free World Cup 2026 picks.
                  <span className="block text-emerald-400">Straight from the model.</span>
                </h1>
                <p className="mt-5 max-w-3xl text-[15px] leading-7 text-slate-300 sm:text-lg sm:leading-8">
                  Goalscorer angles, player props, penalty-taker swings and big-market value spots posted free on Telegram during the tournament.
                </p>
                <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                  <a
                    href="/go/world-cup-telegram?source=landing_hero"
                    className="inline-flex items-center justify-center rounded-full bg-emerald-400 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
                  >
                    Join Free on Telegram
                  </a>
                  <Link
                    href="/penalty-takers/world-cup-2026"
                    className="inline-flex items-center justify-center rounded-full border border-slate-700 px-6 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
                  >
                    See penalty taker file
                  </Link>
                </div>
                <p className="mt-4 text-xs leading-5 text-slate-500">Free through the World Cup. No lottery acca spam.</p>
              </div>

              <div className="mx-auto w-full max-w-[420px] lg:ml-auto">
                <div className="rounded-[32px] border border-emerald-400/18 bg-slate-950/70 p-3 shadow-[0_24px_90px_rgba(0,0,0,0.38)]">
                  <Image
                    src="/brand/world-cup-2026-free-picks.png"
                    alt="Il Margine World Cup 2026 Free Picks Telegram channel"
                    width={1024}
                    height={1024}
                    priority
                    className="h-auto w-full rounded-[26px]"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {INSIDE.map((item) => (
            <article key={item.title} className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)]">
              <h2 className="text-xl font-semibold tracking-tight text-slate-100">{item.title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-400">{item.body}</p>
            </article>
          ))}
        </section>

        <section className="mt-10 grid gap-4 lg:grid-cols-[0.95fr,1.05fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_12px_32px_rgba(0,0,0,0.16)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Why join</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Not another noisy tips channel.</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>Il Margine is built around pricing, data and evidence by someone who used to work on the bookmaker side building prices.</p>
              <p>The point is not to post every match. The point is to flag where the market may be wrong and explain the reasoning quickly.</p>
              <p>During the World Cup, the Telegram channel is the fast feed. The site remains the slower evidence file.</p>
            </div>
          </div>

          <div className="rounded-3xl border border-emerald-400/18 bg-[linear-gradient(140deg,rgba(6,26,20,0.94),rgba(10,15,24,0.96))] p-6 shadow-[0_12px_32px_rgba(0,0,0,0.16)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Start here</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Get the World Cup feed.</h2>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              Join once, turn notifications on, and the live picks, late team-news swings and price notes land in Telegram.
            </p>
            <div className="mt-5 flex flex-col gap-3 sm:flex-row">
              <a
                href="/go/world-cup-telegram?source=landing_bottom"
                className="inline-flex items-center justify-center rounded-full bg-emerald-400 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
              >
                Join Free on Telegram
              </a>
              <Link
                href="/track-record"
                className="inline-flex items-center justify-center rounded-full border border-slate-700 px-6 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
              >
                View track record
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
