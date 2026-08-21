import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";
import { fetchWorldCupRecordSummary } from "@/lib/public-record";

const PAGE_URL = `${BASE_URL}/world-cup-2026-free-picks`;
const OG_IMAGE = `${BASE_URL}/brand/world-cup-2026-free-picks.png`;

export const revalidate = 300;

export const metadata: Metadata = {
  title: "World Cup 2026 Free Picks: Final Record",
  description:
    "Every free World Cup 2026 pick published by Il Margine, retained on the public record with the full log, method and what continues next.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    type: "website",
    url: PAGE_URL,
    title: "World Cup 2026 Free Picks: Final Record | Il Margine",
    description:
      "The World Cup 2026 campaign is complete. Review the public record, penalty-taker research and the free picks feed that continues next.",
    images: [{ url: OG_IMAGE, width: 1024, height: 1024, alt: "Il Margine World Cup 2026 free picks archive", type: "image/png" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "World Cup 2026 Free Picks: Final Record | Il Margine",
    description: "Every World Cup 2026 pick remains on the public record. Review the campaign and follow what comes next.",
    images: [OG_IMAGE],
  },
};

const COVERAGE = [
  ["Goalscorer angles", "Player prices, penalty roles and matchup context were assessed throughout the campaign."],
  ["Player props", "Shots, tackles, fouls and cards formed the core of the published World Cup record."],
  ["Penalty-taker research", "The evidence file tracked first-choice and backup takers for all 48 nations."],
  ["Market value", "Every official selection, including losses, remains in the permanent public ledger."],
] as const;

const NEXT_LINKS = [
  ["ATP tennis", "Current match pricing and official tennis selections.", "/tennis-tips"],
  ["Football player props", "The permanent props record and 2026/27 selections.", "/player-props"],
  ["Track record", "The complete public record across every official market.", "/track-record"],
] as const;

const FAQ = [
  {
    question: "Are the World Cup 2026 picks still available?",
    answer: "Yes. The tournament is complete, but every official pick remains in the permanent Il Margine public record.",
  },
  {
    question: "Does the free Telegram channel continue after the World Cup?",
    answer: "Yes. The same channel continues with official ATP tennis and football player-prop selections.",
  },
  {
    question: "Where can I see the full World Cup record?",
    answer: "Use the World Cup filter on the Player Props page to review the published and settled selections.",
  },
] as const;

function TelegramIcon({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M21.6 4.1 18.2 20c-.2 1.1-.9 1.4-1.8.9l-5.1-3.8-2.5 2.4c-.3.3-.5.5-1 .5l.4-5.2 9.5-8.6c.4-.4-.1-.6-.6-.2L5.3 13.4.2 11.8c-1.1-.3-1.1-1.1.2-1.6L20.3 2.6c.9-.4 1.7.2 1.3 1.5Z" />
    </svg>
  );
}

function signed(value: number, suffix = ""): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
}

export default async function WorldCupFreePicksPage() {
  const summary = await fetchWorldCupRecordSummary().catch((error) => {
    console.error("[world-cup-archive] failed to load record summary", error);
    return null;
  });
  const isFinal = summary?.isFinal === true;

  const faqData = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqData) }} />
      <main className="mx-auto max-w-6xl px-4 pb-20 sm:px-6 lg:px-8">
        <section className="pt-6 pb-10 md:pb-14">
          <PageHomeLink className="mb-8" />

          <div className="relative overflow-hidden rounded-[34px] border border-slate-800/80 bg-[radial-gradient(circle_at_18%_18%,rgba(16,185,129,0.16),transparent_28%),linear-gradient(155deg,rgba(4,10,18,0.98),rgba(6,22,20,0.96))] p-5 shadow-[0_22px_70px_rgba(0,0,0,0.3)] sm:p-8 lg:p-10">
            <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-emerald-400/12 blur-3xl" />
            <div className="relative grid gap-8 lg:grid-cols-[1.08fr,0.92fr] lg:items-center">
              <div>
                <div className="inline-flex rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-emerald-200">
                  World Cup 2026 archive
                </div>
                <h1 className="mt-5 text-[2.45rem] font-semibold leading-[0.95] tracking-tight text-slate-100 sm:text-6xl sm:leading-[0.98]">
                  Free World Cup 2026 picks.
                  <span className="block text-emerald-400">{isFinal ? "Settled. On the record." : "Published. On the record."}</span>
                </h1>
                <p className="mt-5 max-w-3xl text-[15px] leading-7 text-slate-300 sm:text-lg sm:leading-8">
                  The tournament ended on 19 July 2026. Every official selection remains in the permanent public ledger; nothing is removed because it lost.
                </p>

                <div className={`mt-6 rounded-2xl border p-4 ${isFinal ? "border-emerald-400/25 bg-emerald-400/8" : "border-amber-400/25 bg-amber-400/8"}`}>
                  <div className={`text-[10px] font-semibold uppercase tracking-[0.22em] ${isFinal ? "text-emerald-300" : "text-amber-200"}`}>
                    {isFinal ? "Final record" : "Settlement in progress"}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-200">
                    {isFinal
                      ? "Tournament complete. The World Cup record is final and frozen."
                      : summary
                        ? `Tournament complete. ${summary.pending} pick${summary.pending === 1 ? "" : "s"} await official settlement. Final figures publish when the last bet grades.`
                        : "Tournament complete. The record is being reconciled before final figures are published."}
                  </p>
                </div>

                <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                  <Link href="/player-props?comp=worldcup#competition-record" className="inline-flex items-center justify-center rounded-full bg-emerald-400 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300">
                    Review the World Cup record
                  </Link>
                  <Link href="/go/telegram?source=wc_archive" prefetch={false} className="inline-flex items-center justify-center gap-2 rounded-full border border-[#2AABEE]/50 px-6 py-3 text-sm font-semibold text-sky-100 transition hover:bg-[#2AABEE]/10">
                    <TelegramIcon className="h-4 w-4" />
                    Follow future free picks
                  </Link>
                </div>
              </div>

              <div className="mx-auto w-full max-w-[390px] lg:ml-auto">
                <div className="rounded-[32px] border border-emerald-400/18 bg-slate-950/70 p-3 shadow-[0_24px_90px_rgba(0,0,0,0.38)]">
                  <Image src="/brand/world-cup-2026-free-picks.png" alt="Il Margine World Cup 2026 free picks archive" width={1024} height={1024} priority className="h-auto w-full rounded-[26px]" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {isFinal && summary ? (
          <section aria-labelledby="final-record-heading" className="rounded-3xl border border-emerald-400/20 bg-slate-900/70 p-5 sm:p-7">
            <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Final record at a glance</div>
            <h2 id="final-record-heading" className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">The complete campaign, frozen after settlement</h2>
            <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                ["Settled bets", String(summary.totalBets)],
                ["Record", `${summary.wins}-${summary.losses}`],
                ["P/L", signed(summary.totalProfit, "u")],
                ["ROI", signed(summary.roi, "%")],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="font-mono text-2xl font-semibold tabular-nums text-slate-100">{value}</div>
                  <div className="mt-1 text-xs text-slate-500">{label}</div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs leading-6 text-slate-500">ROI uses the recorded unit stakes from the public ledger. It is not reconstructed from a synthetic flat-stake history.</p>
          </section>
        ) : null}

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {COVERAGE.map(([title, body]) => (
            <article key={title} className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5">
              <h2 className="text-lg font-semibold tracking-tight text-slate-100">{title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-400">{body}</p>
            </article>
          ))}
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-2">
          <article className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6">
            <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">What remains public</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">The record is the evidence</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>The World Cup tab contains the official selections exactly as published, with prices, stakes and settlement attached.</p>
              <p>The penalty-taker file remains available as a dated research archive rather than being rewritten after the results.</p>
              <p>{isFinal ? "The final campaign figures above now match the permanent record source." : "A full market-level review will publish only after the final outstanding selections are graded."}</p>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link href="/player-props?comp=worldcup#competition-record" className="rounded-full border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-200 hover:bg-emerald-400/10">Open full log</Link>
              <Link href="/penalty-takers/world-cup-2026" className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-slate-500">Penalty-taker archive</Link>
            </div>
          </article>

          <article className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6">
            <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Method</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Price first, then preserve the audit trail</h2>
            <p className="mt-4 text-sm leading-7 text-slate-300">
              The campaign combined player-role research, price comparison and recorded staking. Results are never used to erase the original call, and the public ledger remains the source of truth.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link href="/penalty-takers/methodology" className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-slate-500">Penalty methodology</Link>
              <Link href="/resources/closing-line-value" className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-slate-500">How we use CLV</Link>
            </div>
          </article>
        </section>

        <section className="mt-6 rounded-3xl border border-emerald-400/18 bg-[linear-gradient(140deg,rgba(6,26,20,0.94),rgba(10,15,24,0.96))] p-6 sm:p-7">
          <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">The edge continues</div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Same record. Current markets.</h2>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {NEXT_LINKS.map(([title, body, href]) => (
              <Link key={href} href={href} className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4 transition hover:border-emerald-400/30">
                <div className="font-semibold text-slate-100">{title}</div>
                <div className="mt-2 text-sm leading-6 text-slate-400">{body}</div>
              </Link>
            ))}
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6">
          <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Common questions</div>
          <div className="mt-5 grid gap-3 lg:grid-cols-3">
            {FAQ.map((item) => (
              <article key={item.question} className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
                <h2 className="font-semibold text-slate-100">{item.question}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-400">{item.answer}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
