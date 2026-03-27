"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";

const FAQ_ITEMS = [
  {
    question: "How is performance calculated?",
    answer:
      "ROI is total profit divided by total stakes. Standard metrics: win rate, bet count, return on investment. Transparent accounting.",
  },
  {
    question: "How often do you post picks?",
    answer:
      "Irregularly. We only post when value exists. Some weeks have volume, some have none.",
  },
  {
    question: "How do you handle losing runs?",
    answer:
      "They stay visible. We don't hide drawdowns or pretend variance disappears when the sample turns against us.",
  },
  {
    question: "Can past picks be edited?",
    answer:
      "No. Once logged, records cannot be changed. That is the entire point of public tracking.",
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
        text: item.answer,
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
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setShow(true), delay);
    return () => window.clearTimeout(timer);
  }, [delay]);

  return (
    <div
      className={className}
      style={{
        opacity: show ? 1 : 0,
        transform: show ? "translateY(0)" : "translateY(18px)",
        transition: `opacity 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}ms, transform 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  accent = false,
  delay = 0,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: boolean;
  delay?: number;
}) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setShow(true), delay);
    return () => window.clearTimeout(timer);
  }, [delay]);

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border p-5 md:p-6 ${
        accent ? "border-emerald-500/20 bg-[#0a0d12]" : "border-slate-800/40 bg-[#0a0d12]"
      }`}
      style={{
        opacity: show ? 1 : 0,
        transform: show ? "translateY(0)" : "translateY(12px)",
        transition: "all 0.6s cubic-bezier(0.16,1,0.3,1)",
      }}
    >
      {accent ? (
        <div
          className="absolute top-0 left-[10%] right-[10%] h-px"
          style={{
            background: "linear-gradient(90deg, transparent, rgba(16,185,129,0.35), transparent)",
          }}
        />
      ) : null}
      <span
        className="pointer-events-none absolute -right-3 -bottom-4 select-none font-mono text-[80px] font-black leading-none"
        style={{
          color: accent ? "rgba(16,185,129,0.03)" : "rgba(255,255,255,0.015)",
        }}
      >
        {value.replace(/[^0-9.%+]/g, "")}
      </span>
      <div className="relative">
        <div className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-slate-600">
          {label}
        </div>
        <div
          className={`mt-3 font-mono text-[2.4rem] font-black leading-none tracking-tighter tabular-nums md:text-[2.8rem] ${
            accent ? "text-emerald-400" : "text-white"
          }`}
        >
          {value}
        </div>
        <div className="mt-3 font-mono text-[11px] leading-relaxed text-slate-500">{sub}</div>
      </div>
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

export default function TrackRecordPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <FaqSchema />

      <section className="relative overflow-hidden border-b border-slate-800/40 pt-6 pb-16 md:pb-20">
        <div
          className="pointer-events-none absolute inset-x-0 -top-20 h-[600px]"
          style={{
            background:
              "radial-gradient(ellipse 1100px 500px at 50% -100px, rgba(16,185,129,0.09), transparent)",
          }}
        />
        <div className="pointer-events-none absolute -left-40 top-20 h-[350px] w-[350px] rounded-full bg-emerald-600/[0.025] blur-[100px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <Reveal delay={0}>
            <PageHomeLink className="mb-12" />
          </Reveal>

          <Reveal delay={100}>
            <span className="text-[10px] font-mono font-bold uppercase tracking-[0.3em] text-emerald-400/90">
              Track Record
            </span>
          </Reveal>

          <Reveal delay={200}>
            <h1 className="mt-4 text-[3rem] font-extrabold leading-[0.95] tracking-[-0.03em] text-white sm:text-[4rem] lg:text-[4.5rem]">
              Track Record
            </h1>
          </Reveal>

          <Reveal delay={320}>
            <p className="mt-6 max-w-xl text-[17px] leading-[1.75] text-slate-400">
              Every bet posted before kick-off. Every result logged after settlement. No edits, no
              deletions.
            </p>
          </Reveal>

          <Reveal delay={420}>
            <Link
              href="/the-edge"
              className="mt-4 inline-flex items-center gap-1.5 text-[14px] text-slate-500 transition-colors hover:text-emerald-400"
            >
              See our methodology
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </Reveal>

          <div className="mt-12 grid gap-3 md:grid-cols-3">
            <StatCard
              label="Player Props"
              value="780+"
              sub="+25.0% ROI · 58% win rate"
              accent
              delay={550}
            />
            <StatCard
              label="ATP Tennis"
              value="447"
              sub="+8.6% ROI · 54% win rate · Tipstrr verified"
              delay={650}
            />
            <StatCard
              label="Combined ROI"
              value="+19%"
              sub="1,227+ bets · 18 months"
              accent
              delay={750}
            />
          </div>

          <Reveal delay={850}>
            <p className="mt-4 font-mono text-[10px] leading-relaxed text-slate-600">
              Validation-phase data from private tracking. Live public tracking is now ongoing.
            </p>
          </Reveal>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-emerald-400/80">
            How we prove it
          </span>
          <h2 className="mb-8 text-[1.6rem] font-extrabold tracking-tight text-white sm:text-[1.9rem]">
            Verification system
          </h2>

          <div className="grid gap-3 md:grid-cols-3">
            {[
              {
                icon: (
                  <svg
                    className="h-5 w-5 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                ),
                title: "Pre-match posting",
                body: "Every selection published on site before kick-off. Timestamps are immutable and verifiable.",
              },
              {
                icon: (
                  <svg
                    className="h-5 w-5 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                ),
                title: "Post-match settlement",
                body: "Once settled, the result is logged with outcome and P&L impact. No lag, no filtering.",
              },
              {
                icon: (
                  <svg
                    className="h-5 w-5 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
                    />
                  </svg>
                ),
                title: "No editing",
                body: "The public record cannot be changed after the fact. What is posted stays posted — wins and losses.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="group rounded-2xl border border-slate-800/40 bg-[#0a0d12] p-5 transition-all duration-300 hover:border-slate-700/50 md:p-6"
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/15 bg-emerald-500/[0.06]">
                  {item.icon}
                </div>
                <h3 className="mb-2 text-[15px] font-bold text-slate-200">{item.title}</h3>
                <p className="text-[13px] leading-[1.65] text-slate-500 transition-colors duration-300 group-hover:text-slate-400">
                  {item.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-emerald-400/80">
            Before you follow
          </span>
          <h2 className="mb-8 text-[1.6rem] font-extrabold tracking-tight text-white sm:text-[1.9rem]">
            Realistic expectations
          </h2>

          <div className="grid gap-x-12 gap-y-5 md:grid-cols-2">
            {[
              {
                t: "Variance is real",
                d: "Good process still comes with losing runs and ugly short-term swings.",
              },
              {
                t: "Sample size matters",
                d: "Twenty bets tells you almost nothing. Hundreds tell you much more.",
              },
              {
                t: "ROI varies by market",
                d: "Props and tennis are different types of edge with different return profiles.",
              },
              {
                t: "Posting is irregular",
                d: "We post when value exists, not because a schedule needs content.",
              },
              {
                t: "Stakes can get limited",
                d: "Win consistently and bookmakers may cut your size. That's a signal it works.",
              },
              {
                t: "Losses get logged",
                d: "Transparency matters more than a curated feed. Every loss stays visible.",
              },
            ].map((item) => (
              <div key={item.t} className="flex items-start gap-3.5">
                <div className="mt-[7px] h-[6px] w-[6px] shrink-0 rounded-full border border-emerald-500/40 bg-emerald-500/20" />
                <div>
                  <span className="text-[14px] font-bold text-slate-200">{item.t}.</span>{" "}
                  <span className="text-[14px] leading-[1.7] text-slate-500">{item.d}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 bg-[#0a0d12] p-6 md:p-8 lg:p-10">
            <div
              className="absolute top-0 left-0 right-0 h-px"
              style={{
                background:
                  "linear-gradient(90deg, transparent 5%, rgba(16,185,129,0.4) 50%, transparent 95%)",
              }}
            />
            <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-emerald-500/[0.04] blur-[60px]" />

            <div className="relative grid gap-10 lg:grid-cols-[1fr,0.6fr] lg:gap-14">
              <div>
                <span className="mb-3 block text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-emerald-400/80">
                  Why we're different
                </span>
                <h2 className="mb-5 text-[1.6rem] font-extrabold tracking-tight text-white sm:text-[1.9rem]">
                  The tipster problem
                </h2>
                <div className="space-y-4 text-[15px] leading-[1.75] text-slate-400">
                  <p>
                    Most tipster services are not businesses built on edge. They are marketing funnels built
                    on confidence.
                  </p>
                  <p>
                    The usual playbook: plays of the year with no timestamps, giant unit claims that vanish
                    when they lose, cherry-picked winner screenshots, records that get cleaner after the
                    fact.
                  </p>
                  <p>
                    That is not analysis. It is gambling repackaged as expertise — because confidence sells
                    better than honesty.
                  </p>
                </div>
              </div>

              <div className="flex items-center">
                <div className="w-full rounded-xl border border-slate-800/50 bg-[#080a0e] p-5">
                  <div className="mb-4 text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-emerald-400/70">
                    What real edge looks like
                  </div>
                  <div className="space-y-3">
                    {[
                      "Immutable timestamps",
                      "Visible losses",
                      "Transparent settlement",
                      "Bad runs kept alongside good",
                      "No edited history",
                    ].map((item) => (
                      <div key={item} className="flex items-center gap-3">
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-emerald-500/20 bg-emerald-500/[0.06]">
                          <svg
                            className="h-3 w-3 text-emerald-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                            strokeWidth="2.5"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                        <span className="text-[13px] text-slate-400">{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <h2 className="mb-6 text-[1.3rem] font-extrabold text-white">FAQ</h2>
          <div className="max-w-3xl space-y-2">
            <FAQ
              q="How is performance calculated?"
              a="ROI is total profit divided by total stakes. Standard metrics: win rate, bet count, return on investment. Transparent accounting."
            />
            <FAQ
              q="How often do you post picks?"
              a="Irregularly. We only post when value exists. Some weeks have volume, some have none."
            />
            <FAQ
              q="How do you handle losing runs?"
              a="They stay visible. We don't hide drawdowns or pretend variance disappears when the sample turns against us."
            />
            <FAQ
              q="Can past picks be edited?"
              a="No. Once logged, records cannot be changed. That is the entire point of public tracking."
            />
          </div>
        </section>

        <section className="py-16 md:py-20">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 p-10 text-center md:p-14">
            <div className="absolute inset-0 bg-[#0a0d12]" />
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
              <h2 className="text-[1.6rem] font-extrabold tracking-tight text-white sm:text-3xl">
                Follow the picks
              </h2>
              <p className="mx-auto mt-4 max-w-md text-[15px] leading-[1.7] text-slate-500">
                All selections posted on the website with full analysis.
              </p>
              <Link
                href="/player-props"
                className="mt-7 inline-flex items-center gap-2.5 rounded-lg bg-emerald-500 px-7 py-3 text-[14px] font-bold text-white transition-all hover:bg-emerald-400 hover:shadow-[0_0_40px_rgba(16,185,129,0.20)]"
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
