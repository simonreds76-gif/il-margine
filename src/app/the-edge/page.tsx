"use client";

import type { ElementType, ReactNode } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";

const FAQ_ITEMS = [
  {
    question: "What's your typical ROI?",
    schemaAnswer:
      "Player props and tennis should not be judged by the same figure. Props are structurally softer, while tennis is sharper. See Track Record for current data.",
  },
  {
    question: "Why don't you share your model?",
    schemaAnswer:
      "If the methodology was public, bookmakers would adjust. Picks are shared. The model is not.",
  },
  {
    question: "How do you strip bookmaker margin?",
    schemaAnswer:
      "We calculate fair odds from our own probability assessment, then compare them with prices that include margin. The gap is where value appears.",
  },
  {
    question: "What if I don't get the same odds?",
    schemaAnswer:
      "Odds move. If you cannot get close to the quoted price, skip the bet. Price discipline is non-negotiable.",
  },
] as const;

function FaqSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ_ITEMS.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.schemaAnswer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: ElementType;
}) {
  return (
    <Tag
      className={className}
      style={{
        animation: "page-reveal 0.7s cubic-bezier(0.16,1,0.3,1) both",
        animationDelay: `${delay}ms`,
      }}
    >
      {children}
    </Tag>
  );
}

function EdgeCard() {
  const rows = [
    ["Bookmaker Odds", "2.10"],
    ["Implied Probability", "47.62%"],
    ["Our Fair Odds", "1.89"],
    ["True Probability", "52.91%"],
  ] as const;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14] p-5 md:p-6">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />
      <div
        className="absolute top-0 left-[8%] right-[8%] h-px"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(16,185,129,0.35), transparent)",
        }}
      />

      <div className="relative">
        <div className="mb-5 flex items-center justify-between">
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-emerald-400/85">
            How we find edge
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="h-[5px] w-[5px] rounded-full bg-emerald-400"
              style={{ animation: "pulse 2s ease-in-out infinite" }}
            />
            <span className="text-[9px] font-mono uppercase tracking-[0.16em] text-slate-600">
              Live example
            </span>
          </span>
        </div>

        <div className="font-mono text-[13px]">
          {rows.map(([label, value], index) => (
            <div
              key={label}
              className="flex items-center justify-between border-b border-slate-800/50 py-[9px]"
              style={{
                animation: "edge-card-row-reveal 0.5s cubic-bezier(0.16,1,0.3,1) both",
                animationDelay: `${600 + index * 220}ms`,
              }}
            >
              <span className="text-slate-500">{label}</span>
              <span className="font-medium tabular-nums text-slate-200">{value}</span>
            </div>
          ))}

          <div
            className="-mx-1.5 mt-3 flex items-center justify-between rounded-xl border px-4 py-3.5"
            style={{
              borderColor: "rgba(16,185,129,0.35)",
              background: "rgba(16,185,129,0.08)",
              animation: "edge-card-result-reveal 0.6s cubic-bezier(0.16,1,0.3,1) both",
              animationDelay: `${600 + rows.length * 220}ms`,
            }}
          >
            <span className="text-[13px] font-semibold text-emerald-400">Mathematical Edge</span>
            <span className="text-[26px] font-black tracking-tighter tabular-nums text-emerald-400">
              +11.1%
            </span>
          </div>
        </div>

        <p className="mt-3 font-mono text-[10px] leading-relaxed text-slate-600">
          When their price exceeds fair value, we act.
        </p>
      </div>

      <style jsx global>{`
        @keyframes page-reveal {
          from {
            opacity: 0;
            transform: translateY(18px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes edge-card-row-reveal {
          from {
            opacity: 0.08;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes edge-card-result-reveal {
          from {
            opacity: 0.15;
            transform: scale(0.98);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }

        @keyframes pulse {
          0%,
          100% {
            opacity: 1;
          }
          50% {
            opacity: 0.3;
          }
        }
      `}</style>
    </div>
  );
}

function FAQ({ q, a }: { q: string; a: ReactNode }) {
  return (
    <details className="group overflow-hidden rounded-xl border border-slate-700/30 bg-[#0c0f14]">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-[14px] font-medium text-slate-300 transition-colors hover:text-white">
        {q}
        <svg
          className="h-4 w-4 shrink-0 text-emerald-500/40 transition-transform group-open:rotate-180"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </summary>
      <div className="border-t border-slate-800/40 px-5 py-4 text-[13px] leading-[1.7] text-slate-500">
        {a}
      </div>
    </details>
  );
}

export default function TheEdgePage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <FaqSchema />

      <section className="relative overflow-hidden border-b border-slate-800/40 pt-6 pb-20 md:pb-28">
        <div
          className="pointer-events-none absolute inset-x-0 -top-20 h-[600px]"
          style={{
            background:
              "radial-gradient(ellipse 1100px 500px at 50% -100px, rgba(16,185,129,0.09), transparent)",
          }}
        />
        <div className="pointer-events-none absolute -right-60 top-0 h-[400px] w-[400px] rounded-full bg-emerald-600/[0.025] blur-[100px]" />
        <div className="pointer-events-none absolute left-[15%] top-[350px] h-56 w-56 rounded-full bg-sky-500/[0.015] blur-[80px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <Reveal delay={0}>
            <PageHomeLink className="mb-12" />
          </Reveal>

          <div className="grid items-start gap-12 lg:grid-cols-[1.2fr,0.8fr] lg:gap-16">
            <div>
              <Reveal delay={100}>
                <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
                  Methodology
                </span>
              </Reveal>

              <Reveal delay={200}>
                <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-slate-100 sm:text-4xl md:text-5xl">
                  The Edge
                </h1>
              </Reveal>

              <Reveal delay={350}>
                <p className="mt-6 max-w-lg text-base leading-relaxed text-slate-300 sm:text-lg">
                  25 years in the betting industry. Former odds compiler. I built the prices bookmakers use
                  and now I use that knowledge against them.
                </p>
              </Reveal>

              <Reveal delay={480}>
                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <Link
                    href="/player-props"
                    className="group inline-flex items-center gap-2.5 rounded-lg bg-emerald-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-400"
                  >
                    View Tips
                    <span className="transition-transform group-hover:translate-x-0.5">→</span>
                  </Link>
                  <Link
                    href="/track-record"
                    className="group inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-emerald-400"
                  >
                    Track record
                    <svg
                      className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                    </svg>
                  </Link>
                </div>
              </Reveal>
            </div>

            <Reveal delay={400} className="lg:mt-8">
              <EdgeCard />
            </Reveal>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <div className="grid gap-10 lg:grid-cols-[0.35fr,1fr] lg:gap-16">
            <div className="lg:sticky lg:top-28 lg:self-start">
              <div className="mb-5 flex items-center gap-3">
                <div className="h-10 w-[3px] rounded-full bg-emerald-500" />
                <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
                  Insider knowledge
                </span>
              </div>
              <h2 className="text-2xl font-semibold leading-tight tracking-tight text-slate-100 sm:text-3xl">
                Why the other side
                <br />
                knows better
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-slate-500">
                Most services learn by betting.
                <br />
                I learned by building the prices.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {[
                {
                  n: "01",
                  t: "Template pricing",
                  d: "Props are rarely handcrafted per match. Opponent context, role changes, tactical matchups — often missing from the template entirely.",
                },
                {
                  n: "02",
                  t: "Margin allocation",
                  d: "Match odds: 3–5% margin, dedicated traders. Player props: 10–15% margin, minimal oversight. Less efficient means more opportunity.",
                },
                {
                  n: "03",
                  t: "Copy-paste pricing",
                  d: "Smaller firms inherit the same number. When the original line is wrong, the error propagates across every book in the market.",
                },
                {
                  n: "04",
                  t: "Risk management gaps",
                  d: "The highest-profile markets get monitored hardest. The weaker corners — that is where value survives longest.",
                },
              ].map((item) => (
                <div
                  key={item.n}
                  className="group relative overflow-hidden rounded-xl border border-slate-700/40 bg-[#0c0f14] p-5 transition-all duration-300 hover:border-slate-600/60"
                >
                  <span className="pointer-events-none absolute -right-2 -top-4 select-none font-mono text-[72px] font-black leading-none text-white/[0.02]">
                    {item.n}
                  </span>
                  <div className="relative">
                    <span className="font-mono text-[11px] font-bold text-emerald-500/40">{item.n}</span>
                    <h3 className="mt-1.5 text-base font-semibold text-slate-200">{item.t}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-slate-500 transition-colors duration-300 group-hover:text-slate-400">
                      {item.d}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
            Where we operate
          </span>
          <h2 className="mb-8 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
            Market selection
          </h2>

          <div className="grid gap-3 md:grid-cols-2">
            {[
              {
                name: "Player Props",
                tag: "Active",
                active: true,
                desc: "Shots, fouls, tackles, cards. Priced with less attention than headline markets. When role, matchup, or tactical context shifts probability, value appears fast.",
                extra: (
                  <Link
                    href="/penalty-takers"
                    className="mt-3 inline-flex text-[11px] font-medium text-emerald-400/60 transition-colors hover:text-emerald-400"
                  >
                    Penalty takers reference →
                  </Link>
                ),
              },
              {
                name: "ATP Tennis",
                tag: "Active",
                active: true,
                desc: "Not soft like props. We bet it because the model work is deeper — surface-adjusted ratings, serve/return splits, event context, and years of pricing experience.",
                extra: null,
              },
              {
                name: "What we avoid",
                tag: null,
                active: false,
                desc: "High-profile match odds in major leagues unless the mispricing is obvious. We do not compete where bookmakers are strongest.",
                extra: null,
              },
            ].map((market) => (
              <div
                key={market.name}
                className={`group relative overflow-hidden rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-[2px] md:p-6 ${
                  market.active
                    ? "border-emerald-500/20 bg-[#0c0f14] hover:border-emerald-500/30"
                    : "border-slate-700/40 bg-[#0c0f14] hover:border-slate-600/60"
                }`}
              >
                {market.active ? (
                  <div
                    className="absolute top-0 left-[10%] right-[10%] h-px"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent, rgba(16,185,129,0.25), transparent)",
                    }}
                  />
                ) : null}
                <div className="relative">
                  <div className="mb-3 flex items-center gap-2.5">
                    <h3 className="text-base font-semibold text-slate-200">{market.name}</h3>
                    {market.tag ? (
                      <span
                        className={`rounded-full border px-2.5 py-[3px] text-[8px] font-mono font-bold uppercase tracking-[0.15em] ${
                          market.active
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400/80"
                            : "border-slate-700/40 bg-slate-800/60 text-slate-600"
                        }`}
                      >
                        {market.tag}
                      </span>
                    ) : null}
                  </div>
                  <p className="text-sm leading-relaxed text-slate-500 transition-colors duration-300 group-hover:text-slate-400">
                    {market.desc}
                  </p>
                  {market.extra}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <div className="grid items-start gap-10 lg:grid-cols-[1fr,0.55fr] lg:gap-14">
            <div>
              <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
                Core concept
              </span>
              <h2 className="mb-6 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
                How value betting works
              </h2>
              <div className="space-y-5 text-base leading-relaxed text-slate-400">
                <p>
                  <strong className="font-semibold text-slate-200">It is not about predicting winners.</strong>{" "}
                  It is about finding spots where the price does not reflect the true probability.
                </p>
                <p>
                  <strong className="font-semibold text-slate-200">Example.</strong> A bookmaker offers 2.10
                  on a prop — implied 47.6%. If our fair line makes it 53%, the bet is value even though it
                  still loses regularly.
                </p>
                <p>
                  <strong className="font-semibold text-slate-200">The discipline.</strong> We price first,
                  then compare. We do not bet because we like something. We bet because the number is off.
                </p>
              </div>
            </div>

            <div className="lg:mt-14">
              <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 bg-[#0c0f14] p-6">
                <div
                  className="absolute top-0 left-[10%] right-[10%] h-px"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent, rgba(16,185,129,0.3), transparent)",
                  }}
                />
                <div className="pointer-events-none absolute -right-16 -bottom-16 h-40 w-40 rounded-full bg-emerald-500/[0.04] blur-[50px]" />
                <div className="relative">
                  <div className="mb-5 text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-emerald-400/80">
                    Key insight
                  </div>
                  <p className="text-xl font-semibold leading-relaxed tracking-tight text-slate-100">
                    A winning bet and a <span className="text-emerald-400">correct</span> bet are not the
                    same thing.
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-slate-500">
                    A bet is correct when the odds were wrong in your favour — regardless of the outcome.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
            Principles
          </span>
          <h2 className="mb-8 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
            The philosophy
          </h2>

          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
            {[
              { n: "01", t: "Edge only", d: "We bet when our number is better. Nothing else triggers action." },
              {
                n: "02",
                t: "Value > outcomes",
                d: "Decision quality is independent of the result.",
              },
              {
                n: "03",
                t: "Singles only",
                d: "Accumulators compound the bookmaker's margin against you.",
              },
              {
                n: "04",
                t: "Attack weakness",
                d: "Props, niche markets, specific tennis spots.",
              },
              {
                n: "05",
                t: "Model is private",
                d: "Picks shared. The engine stays proprietary.",
              },
            ].map((item) => (
              <div
                key={item.n}
                className="group relative flex flex-col overflow-hidden rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 transition-colors duration-300 hover:border-slate-600/60"
              >
                <span className="pointer-events-none absolute -right-1 -top-3 select-none font-mono text-[56px] font-black leading-none text-white/[0.015]">
                  {item.n}
                </span>
                <div className="relative">
                  <span className="font-mono text-[10px] font-bold text-emerald-500/35">{item.n}</span>
                  <h3 className="mt-1 text-sm font-semibold leading-snug text-slate-200">{item.t}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-600 transition-colors duration-300 group-hover:text-slate-500">
                    {item.d}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
            Common questions
          </span>
          <h2 className="mb-6 text-xl font-semibold text-slate-100">FAQ</h2>
          <div className="max-w-3xl space-y-2">
            <FAQ
              q="What's your typical ROI?"
              a={
                <>
                  Props and tennis should not be judged by the same figure. Props are structurally softer;
                  tennis is sharper. See{" "}
                  <Link
                    href="/track-record"
                    className="text-emerald-400 underline underline-offset-2 hover:text-emerald-300"
                  >
                    Track Record
                  </Link>{" "}
                  for current data.
                </>
              }
            />
            <FAQ
              q="Why don't you share your model?"
              a="If the methodology was public, bookmakers would adjust. Picks are shared. The model is not."
            />
            <FAQ
              q="How do you strip bookmaker margin?"
              a="We calculate fair odds from our own probability assessment, then compare with prices that include margin. The gap is where value appears."
            />
            <FAQ
              q="What if I don't get the same odds?"
              a="Odds move. If you can't get close to the quoted price, skip the bet. Price discipline is non-negotiable."
            />
          </div>
        </section>

        <section className="py-16 md:py-20">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 p-10 text-center md:p-14">
            <div className="absolute inset-0 bg-[#0c0f14]" />
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                background:
                  "radial-gradient(circle at 50% 130%, rgba(16,185,129,0.10), transparent 55%)",
              }}
            />
            <div
              className="absolute top-0 left-[15%] right-[15%] h-px"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(16,185,129,0.3), transparent)",
              }}
            />

            <div className="relative">
              <h2 className="text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
                See the edge in practice
              </h2>
              <p className="mx-auto mt-4 max-w-md text-base leading-relaxed text-slate-400">
                Every pick: match, market, selection, odds, stake. When we find value, you see it before the
                line moves.
              </p>
              <Link
                href="/player-props"
                className="mt-7 inline-flex items-center gap-2.5 rounded-lg bg-emerald-500 px-8 py-3.5 text-base font-semibold text-white transition-colors hover:bg-emerald-400"
              >
                View Tips →
              </Link>
            </div>
          </div>
        </section>

        <div className="pb-14">
          <div className="rounded-xl border border-amber-500/10 bg-amber-500/[0.03] px-5 py-4 text-[12px] leading-relaxed text-slate-500">
            <strong className="text-amber-400/80">Responsible gambling:</strong> Past performance does not
            guarantee future results. Only bet what you can afford to lose.{" "}
            <a
              href="https://www.begambleaware.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 underline underline-offset-2"
            >
              BeGambleAware
            </a>{" "}
            ·{" "}
            <a
              href="https://www.gamcare.org.uk"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 underline underline-offset-2"
            >
              GamCare
            </a>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}
