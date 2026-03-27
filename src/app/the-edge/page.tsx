import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";

const FAQ_ITEMS = [
  {
    question: "What's your typical ROI?",
    schemaAnswer:
      "Player props and tennis should not be judged by the same headline figure. Props are structurally softer, while tennis is generally sharper and more model-dependent. Exact figures vary by market and time period. See Track Record for current data.",
  },
  {
    question: "Why don't you share your model?",
    schemaAnswer:
      "Same reason card counters do not publish their exact systems. If the methodology was public, bookmakers would adjust and the edge would disappear. Picks are shared. The proprietary modelling is not.",
  },
  {
    question: "How do you strip bookmaker margin?",
    schemaAnswer:
      "We calculate fair odds from our own probability assessment, then compare them to bookmaker prices that already include margin. The gap between our fair odds and the offered odds is where value appears. The exact modelling is proprietary.",
  },
  {
    question: "What if I don't get the same odds you post?",
    schemaAnswer:
      "Odds move. If you cannot get reasonably close to the quoted price, skip the bet. Value betting depends on price discipline, not forcing action at a worse number.",
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

export default function TheEdgePage() {
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
        <div className="absolute inset-0 flex items-center justify-center opacity-[0.025] pointer-events-none">
          <Image
            src="/banner.png"
            alt=""
            width={1200}
            height={400}
            className="h-auto w-full max-w-6xl object-contain"
          />
        </div>

        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-8" />
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-emerald-400">
            Methodology
          </span>
          <h1 className="mt-3 text-3xl font-semibold text-slate-100 sm:text-4xl">The Edge</h1>
          <p className="mt-4 max-w-3xl text-lg leading-relaxed text-slate-400">
            25 years in the betting industry. Former odds compiler. I built the prices bookmakers use
            and now I use that knowledge against them.
          </p>
          <Link
            href="/track-record"
            className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-emerald-400 transition-colors hover:text-emerald-300"
          >
            See our verified track record <span aria-hidden="true">?</span>
          </Link>

          <div className="mt-10 max-w-lg rounded-2xl border border-slate-700/50 bg-slate-800/50 p-6 md:p-8">
            <div className="mb-6 flex items-center justify-between gap-3">
              <span className="text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-emerald-400">
                How We Find Edge
              </span>
              <span className="rounded-full border border-slate-700/50 bg-[#0c0f14] px-3 py-1 text-[10px] font-mono text-slate-500">
                Example
              </span>
            </div>
            <div className="space-y-3 font-mono text-sm">
              <div className="flex items-center justify-between border-b border-slate-700/40 py-2">
                <span className="text-slate-400">Bookmaker Odds</span>
                <span className="text-slate-100">2.10</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-700/40 py-2">
                <span className="text-slate-400">Implied Probability</span>
                <span className="text-slate-100">47.62%</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-700/40 py-2">
                <span className="text-slate-400">Our Fair Odds</span>
                <span className="text-slate-100">1.89</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-700/40 py-2">
                <span className="text-slate-400">True Probability</span>
                <span className="text-slate-100">52.91%</span>
              </div>
              <div className="-mx-3 mt-2 flex items-center justify-between rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-3">
                <span className="font-semibold text-emerald-400">Mathematical Edge</span>
                <span className="text-lg font-bold text-emerald-400">+11.1%</span>
              </div>
            </div>
            <p className="mt-4 text-xs leading-relaxed text-slate-500">
              We strip bookmaker margin to find true odds. When their price exceeds fair value,
              that is where we act.
            </p>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl space-y-10 px-4 py-12 sm:px-6 lg:px-8 md:py-16">
        <SectionCard highlighted>
          <SectionHeading>Why The Other Side Knows Better</SectionHeading>
          <div className="space-y-4 text-base leading-relaxed text-slate-300">
            <p>
              Most betting services are run by bettors who learned by betting. Valuable, but limited.
              I learned by building the prices bookmakers use.
            </p>
            <p className="font-medium text-slate-100">What you see from the compiler side:</p>
            <ul className="list-disc space-y-2 pl-6">
              <li>
                <strong className="text-slate-100">Template pricing dominates.</strong> Player props are
                rarely handcrafted for each match. Opponent-specific context and role changes often get
                underweighted or missed.
              </li>
              <li>
                <strong className="text-slate-100">Margin allocation varies.</strong> Match odds get more
                trader attention. Props and side markets carry wider margin and looser pricing.
              </li>
              <li>
                <strong className="text-slate-100">Copy-paste pricing exists.</strong> Smaller firms often
                inherit the same bad number when the original line is wrong.
              </li>
              <li>
                <strong className="text-slate-100">Risk management priorities are uneven.</strong> The
                highest-profile markets get monitored hardest. The weaker corners are where value lasts
                longest.
              </li>
            </ul>
            <p>This is not insider information. It is understanding how the machinery actually works.</p>
          </div>
        </SectionCard>

        <SectionCard>
          <SectionHeading>Market Selection Philosophy</SectionHeading>
          <div className="space-y-4 text-base leading-relaxed text-slate-300">
            <p>Not every market is worth betting. Most are not.</p>
            <p>
              <strong className="text-slate-100">Player Props.</strong> These are usually priced with less
              granular attention than headline markets. When role, matchup, referee profile, or tactical
              context shifts the true probability, value can appear quickly.
            </p>
            <p>
              For goalscorer-style markets the same logic applies to set-piece roles. That is why we keep a
              live <Link href="/penalty-takers" className="text-emerald-400 underline underline-offset-2 transition-colors hover:text-emerald-300">penalty takers board</Link> instead of trusting stale season-open assumptions.
            </p>
            <p>
              <strong className="text-slate-100">ATP Tennis.</strong> Tennis is not soft in the same way props
              are. We bet it because the pricing work is deeper there: surface-adjusted ratings, serve and
              return strength, event context, and long-term model validation.
            </p>
            <p>
              <strong className="text-slate-100">Bet Builders.</strong> <span className="text-slate-500">Coming soon.</span>
              Correlation gets mispriced more often than people think, especially when books price legs too independently.
            </p>
            <p>
              <strong className="text-slate-100">What we do not bet.</strong> We are not trying to out-trade
              bookmakers on the markets they prioritise most unless the mispricing is obvious.
            </p>
          </div>
        </SectionCard>

        <SectionCard>
          <SectionHeading>How Value Betting Actually Works</SectionHeading>
          <div className="space-y-4 text-base leading-relaxed text-slate-300">
            <p>
              <strong className="text-slate-100">It is not about predicting winners.</strong>
            </p>
            <p>
              Most people think betting is about being right. It is not. It is about finding spots where the
              bookmaker&apos;s price does not reflect the true probability.
            </p>
            <p>
              <strong className="text-slate-100">Example.</strong> A bookmaker offers 2.10 on a prop.
              That implies 47.6%. If our fair line makes it 53%, the bet is value even though it will still
              lose regularly. The decision is correct because the price is wrong.
            </p>
            <p>
              <strong className="text-slate-100">The discipline.</strong> We price the selection first, then
              compare that fair line with the market. We do not bet because we &quot;like&quot; something. We bet
              because the number is off.
            </p>
          </div>
        </SectionCard>

        <SectionCard highlighted>
          <SectionHeading>The Philosophy</SectionHeading>
          <div className="space-y-4 text-base leading-relaxed text-slate-300">
            {[
              ["01", "Mathematical edge only.", "We calculate true odds and only bet when our number is better than the bookmaker&apos;s price."],
              ["02", "We bet value, not outcomes.", "Whether the selection wins or loses is irrelevant to the quality of the decision. What matters is whether the odds were wrong."],
              ["03", "Singles only.", "Accumulators compound bookmaker margin. We do not give away edge before the event starts."],
              ["04", "Exploit inefficiencies.", "Player props, niche markets, and specific tennis spots are where our work matters most."],
              ["05", "No secrets given away.", "We share the picks. The proprietary model stays proprietary."],
            ].map(([label, title, body]) => (
              <div key={label} className="flex gap-3">
                <span className="shrink-0 font-mono text-sm font-bold text-emerald-400">{label}</span>
                <p>
                  <strong className="text-slate-100">{title}</strong> {body}
                </p>
              </div>
            ))}
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
                  {item.question === "What's your typical ROI?" ? (
                    <>
                      Player props and tennis should not be judged by the same headline figure. Props are
                      structurally softer, while tennis is generally sharper and more model-dependent. Exact
                      figures vary by market and time period. See{" "}
                      <Link href="/track-record" className="text-emerald-400 underline underline-offset-2 transition-colors hover:text-emerald-300">
                        Track Record
                      </Link>{" "}
                      for current data.
                    </>
                  ) : null}
                  {item.question === "Why don't you share your model?"
                    ? "Same reason card counters do not publish their exact systems. If the methodology was public, bookmakers would adjust and the edge would disappear. Picks are shared. The proprietary modelling is not."
                    : null}
                  {item.question === "How do you strip bookmaker margin?"
                    ? "We calculate fair odds from our own probability assessment, then compare them with bookmaker prices that already include margin. The gap between our fair odds and the offered odds is where value appears. The exact modelling is proprietary."
                    : null}
                  {item.question === "What if I don't get the same odds you post?"
                    ? "Odds move. If you cannot get reasonably close to the quoted price, skip the bet. Value betting depends on price discipline, not forcing action at a worse number."
                    : null}
                </div>
              </details>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-emerald-500/20 bg-emerald-500/8 p-6 text-center md:p-8">
          <h2 className="text-xl font-semibold text-emerald-400">See the edge in practice</h2>
          <p className="mx-auto mt-3 max-w-xl text-base leading-relaxed text-slate-300">
            Every pick includes the match, market, selection, odds, and stake. When we identify value,
            you see it before the line moves.
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

