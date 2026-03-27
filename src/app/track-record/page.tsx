import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";

const FAQ_ITEMS = [
  {
    question: "How is performance calculated?",
    answer:
      "ROI is total profit divided by total stakes across settled bets. We use standard metrics such as win rate, bet count, and return on investment. The point is transparent accounting, not marketing spin.",
  },
  {
    question: "How often do you post picks?",
    answer:
      "Irregularly. We only post when we identify value. Some weeks have volume. Some weeks have none. We do not force bets to maintain a schedule.",
  },
  {
    question: "How do you handle losing runs?",
    answer:
      "They stay visible. Losing streaks are part of value betting. We do not hide drawdowns, cherry-pick hot stretches, or pretend variance stops existing when the sample turns against us.",
  },
  {
    question: "Can past picks be edited?",
    answer:
      "No. Once a pick is logged on the site, the record is not retroactively changed or deleted. That is the whole point of public tracking.",
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

function SectionCard({
  children,
  highlighted = false,
}: {
  children: React.ReactNode;
  highlighted?: boolean;
}) {
  return (
    <section
      className={`rounded-2xl border p-6 md:p-8 ${
        highlighted
          ? "border-emerald-500/20 bg-slate-800/50"
          : "border-slate-700/50 bg-slate-800/50"
      }`}
    >
      {children}
    </section>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-4 text-xl font-semibold text-emerald-400 md:text-2xl">{children}</h2>;
}

function StatCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4">
      <div className="text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={`mt-2 font-mono text-xl font-bold tabular-nums md:text-2xl ${accent ? "text-emerald-400" : "text-slate-100"}`}>
        {value}
      </div>
      <div className="mt-2 font-mono text-[10px] text-slate-600">{sub}</div>
    </div>
  );
}

export default function TrackRecordPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <FaqSchema />

      <section className="relative overflow-hidden border-b border-slate-800/50 pt-6 pb-12 md:pb-16">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-80"
          style={{
            background:
              "radial-gradient(ellipse 860px 340px at 50% -40px, rgba(16,185,129,0.10), transparent)",
          }}
        />
        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-8" />
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-emerald-400">
            Track Record
          </span>
          <h1 className="mt-3 text-3xl font-semibold text-slate-100 sm:text-4xl">Track Record</h1>
          <p className="mt-4 max-w-3xl text-lg leading-relaxed text-slate-400">
            Every bet posted before kick-off. Every result logged after settlement. No edits, no deletions.
          </p>
          <Link
            href="/the-edge"
            className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-emerald-400 transition-colors hover:text-emerald-300"
          >
            See our methodology <span aria-hidden="true">?</span>
          </Link>
        </div>
      </section>

      <div className="mx-auto max-w-6xl space-y-10 px-4 py-12 sm:px-6 lg:px-8 md:py-16">
        <SectionCard>
          <SectionHeading>Performance Numbers</SectionHeading>
          <div className="grid gap-4 md:grid-cols-3">
            <StatCard
              label="Player Props"
              value="780+ bets"
              sub="+25.0% ROI · 58% win rate"
            />
            <StatCard
              label="ATP Tennis"
              value="447 bets"
              sub="+8.6% ROI · 54% win rate · Tipstrr verified"
              accent
            />
            <StatCard
              label="Combined"
              value="1,227+ bets"
              sub="+19.0% ROI · 18 months"
              accent
            />
          </div>
          <div className="mt-4 space-y-2 text-sm leading-relaxed text-slate-400">
            <p>Stakes: variable (0.05u to 5u based on edge confidence).</p>
            <p>Validation-phase data from private tracking. Live public tracking is now ongoing.</p>
          </div>
        </SectionCard>

        <SectionCard>
          <SectionHeading>Verification System</SectionHeading>
          <div className="space-y-4 text-base leading-relaxed text-slate-300">
            <p>
              <strong className="text-slate-100">Pre-match posting.</strong> Every selection is published on
              site before kick-off or before the match starts.
            </p>
            <p>
              <strong className="text-slate-100">Post-match settlement.</strong> Once the event settles, the
              result is logged with outcome and performance impact.
            </p>
            <p>
              <strong className="text-slate-100">No editing.</strong> The public record is not retroactively
              cleaned up. What is posted stays posted.
            </p>
          </div>
        </SectionCard>

        <SectionCard>
          <SectionHeading>Realistic Expectations</SectionHeading>
          <ul className="space-y-3 text-base leading-relaxed text-slate-300">
            <li>
              <strong className="text-slate-100">Variance is real.</strong> Good process still comes with
              losing runs and ugly short-term swings.
            </li>
            <li>
              <strong className="text-slate-100">Sample size matters.</strong> Twenty bets tells you almost
              nothing. Hundreds tell you much more.
            </li>
            <li>
              <strong className="text-slate-100">ROI varies by market.</strong> Props and tennis are not the
              same type of edge and should not be judged with the same expectations.
            </li>
            <li>
              <strong className="text-slate-100">Posting is irregular.</strong> We post when value exists, not
              because a content calendar needs feeding.
            </li>
            <li>
              <strong className="text-slate-100">Stakes can get limited.</strong> If you win consistently,
              bookmakers may cut your size. See our{" "}
              <Link href="/bookmakers" className="text-emerald-400 underline underline-offset-2 transition-colors hover:text-emerald-300">
                bookmakers guide
              </Link>{" "}
              and{" "}
              <Link href="/faq" className="text-emerald-400 underline underline-offset-2 transition-colors hover:text-emerald-300">
                FAQ
              </Link>{" "}
              for context.
            </li>
            <li>
              <strong className="text-slate-100">Losses get logged.</strong> Transparency matters more than a
              pretty feed.
            </li>
            <li>
              <strong className="text-slate-100">This is not a get-rich-quick pitch.</strong> The whole point
              is long-term discipline, not theatrical certainty.
            </li>
          </ul>
        </SectionCard>

        <SectionCard highlighted>
          <SectionHeading>The Tipster Problem</SectionHeading>
          <div className="space-y-4 text-base leading-relaxed text-slate-300">
            <p>
              Most tipster services are not businesses built on edge. They are marketing funnels built on
              confidence.
            </p>
            <p>
              Think of the usual playbook: plays of the year with no timestamps, giant unit claims that
              quietly vanish when they lose, cherry-picked winner screenshots, and a record that somehow gets
              cleaner after the fact.
            </p>
            <p>
              That is not analysis. It is gambling repackaged as expertise because confidence sells better than
              honesty. Real edge looks boring by comparison: immutable timestamps, visible losses, transparent
              settlement, and a public record that keeps the bad runs as well as the good ones.
            </p>
          </div>
        </SectionCard>

        <section>
          <SectionHeading>Frequently Asked Questions</SectionHeading>
          <div className="space-y-2">
            {FAQ_ITEMS.map((item) => (
              <details
                key={item.question}
                className="group overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/50"
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-5 py-4 text-left font-medium text-slate-200 transition-colors hover:bg-slate-700/20">
                  <span>{item.question}</span>
                  <span className="shrink-0 text-emerald-400/60 transition-transform group-open:rotate-180">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </span>
                </summary>
                <div className="border-t border-slate-700/30 px-5 py-4 text-sm leading-relaxed text-slate-400">
                  {item.answer}
                </div>
              </details>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-emerald-500/20 bg-emerald-500/8 p-6 text-center md:p-8">
          <h2 className="text-xl font-semibold text-emerald-400">Follow the picks</h2>
          <p className="mx-auto mt-3 max-w-xl text-base leading-relaxed text-slate-300">
            All selections posted on the website with full analysis.
          </p>
          <Link
            href="/player-props"
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-6 py-3 font-semibold text-white transition-colors hover:bg-emerald-400"
          >
            View Tips <span aria-hidden="true">?</span>
          </Link>
        </section>

        <div className="rounded-xl border border-amber-500/15 bg-amber-500/[0.04] px-5 py-4 text-[13px] leading-relaxed text-slate-400">
          <strong className="text-amber-400/90">Responsible gambling:</strong> Past performance does not
          guarantee future results. Only bet what you can afford to lose. <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 text-slate-300">BeGambleAware</a>{" "}
          · <a href="https://www.gamcare.org.uk" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 text-slate-300">GamCare</a>
        </div>
      </div>

      <Footer />
    </div>
  );
}

