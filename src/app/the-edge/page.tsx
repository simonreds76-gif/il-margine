import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { BASE_URL, TELEGRAM_CHANNEL_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "The Edge",
  description: "Why Il Margine works: 25 years in the betting industry, former odds compiler, proprietary models, mathematical edge only.",
  alternates: {
    canonical: `${BASE_URL}/the-edge`,
  },
  robots: "index, follow",
};

const FAQ_ITEMS = [
  {
    q: "How often do you post picks?",
    a: "Irregularly. We only tip when we identify genuine value. Some weeks have 10+ selections. Some weeks have zero. We don't force picks to maintain a schedule.",
  },
  {
    q: "What's your typical ROI?",
    a: "We target positive ROI across market types. Player props historically higher ROI than tennis (wider margins = more exploitable). Exact figures vary by market and time period. See Track Record for current data.",
  },
  {
    q: "Do you bet on match odds or just props?",
    a: "Primarily player props and tennis handicaps. Occasionally match odds when clear mispricing exists. We bet wherever edge exists, but focus on less efficient markets where value is more frequent.",
  },
  {
    q: "Why don't you share your model?",
    a: "Same reason card counters don't publish their exact systems. If the methodology was public, bookmakers would adjust and the edge would disappear. Picks are shared, the proprietary modeling isn't.",
  },
  {
    q: "How do you strip bookmaker margin?",
    a: "We calculate fair odds for each outcome based on our probability assessment, then compare to bookmaker odds which include their margin. The gap between fair odds and offered odds reveals value opportunities. The exact modeling is proprietary.",
  },
  {
    q: "What if I don't get the same odds you post?",
    a: "Odds move. By the time we post, sharp money may have moved the line. Try to get close, but don't force bets at significantly worse odds. If you can't get within 5-10% of posted odds, skip that selection.",
  },
];

function FaqSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ_ITEMS.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export default function TheEdgePage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <FaqSchema />
      {/* Hero - keep as is */}
      <section className="pt-4 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50 relative overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center opacity-[0.03] pointer-events-none">
          <Image src="/banner.png" alt="" width={1200} height={400} className="w-full max-w-6xl h-auto object-contain" />
        </div>
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8">
            <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
            <span>← Home</span>
          </Link>
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">WHY IT WORKS</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-2">The Edge</h1>
          <p className="text-lg text-slate-400 font-medium mb-6 sm:mb-8">Il Margine: Mind the margin.</p>
          <div className="space-y-6 text-slate-300 leading-relaxed text-base">
            <p>25 years in the betting industry. Former odds compiler. I&apos;ve worked on the other side, building the prices that bookmakers use. I know exactly where they cut corners and where value hides.</p>
            <p>Every pick is backed by proprietary models that strip out bookmaker margin to find true odds. We only bet when the numbers say yes. No hunches. No tips from a mate. Pure mathematics.</p>
          </div>
          <div className="mt-8 bg-[#1a1d24] rounded-xl border border-slate-800 p-6 max-w-lg">
            <div className="flex items-center justify-between mb-6">
              <span className="font-mono text-sm text-slate-400">HOW WE FIND EDGE</span>
              <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-2 py-1 rounded">EXAMPLE</span>
            </div>
            <div className="space-y-3 font-mono text-sm">
              <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                <span className="text-slate-400">Bookmaker Odds</span>
                <span className="text-slate-100">2.10</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                <span className="text-slate-400">Implied Probability</span>
                <span className="text-slate-100">47.62%</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                <span className="text-slate-400">Our Fair Odds (margin stripped)</span>
                <span className="text-slate-100">1.89</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                <span className="text-slate-400">True Probability</span>
                <span className="text-slate-100">52.91%</span>
              </div>
              <div className="flex justify-between items-center py-3 bg-emerald-500/10 rounded px-3 -mx-3 mt-2 border border-emerald-500/20">
                <span className="text-emerald-400 font-semibold">Mathematical Edge</span>
                <span className="text-emerald-400 font-bold text-lg">+11.1%</span>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-4">We strip bookmaker margin to find true odds. When their price exceeds fair value, we bet.</p>
          </div>
        </div>
      </section>

      {/* New sections - dark cards */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16 space-y-10">
        {/* 1. Where We Find Value */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8">
          <h2 className="text-xl md:text-2xl font-semibold text-emerald-400 mb-4">Market Selection Philosophy</h2>
          <div className="space-y-4 text-slate-300 leading-relaxed text-base">
            <p>Not every market is worth betting. Most aren&apos;t.</p>
            <p>Bookmakers dedicate their resources unevenly. Premier League match odds get teams of traders, live monitoring, and sophisticated algorithms. Player props get template pricing and minimal oversight.</p>
            <p><strong className="text-slate-100">Our focus areas:</strong></p>
            <p><strong className="text-slate-200">Player Props</strong> — Individual player statistics: shots on target, fouls committed, tackles made, cards received. These markets receive a fraction of the analytical attention that match odds do. Bookmakers use historical averages with minimal matchup-specific adjustment. When opponent defensive stats, tactical setups, or referee tendencies create outliers, value emerges.</p>
            <p><strong className="text-slate-200">Tennis Handicaps</strong> — Game spreads and totals in ATP events, particularly 250s and Challengers. These tournaments get less market attention than Grand Slams. Surface-specific performance differentials are systematically underweighted.</p>
            <p><strong className="text-slate-200">Bet Builders</strong> <span className="text-slate-500">(Coming Soon)</span> — Same-game multiples where correlation is mispriced. When bookmakers price legs independently that are actually correlated, mathematical edges appear.</p>
            <p><strong className="text-slate-100">What we don&apos;t bet:</strong> High-profile match odds in major leagues unless clear mispricing exists. We&apos;re not competing with bookmaker traders on markets they prioritize. We operate where their models are weakest.</p>
          </div>
        </section>

        {/* 2. The Approach */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8">
          <h2 className="text-xl md:text-2xl font-semibold text-emerald-400 mb-4">How Value Betting Actually Works</h2>
          <div className="space-y-4 text-slate-300 leading-relaxed text-base">
            <p><strong className="text-slate-100">It&apos;s not about predicting winners.</strong></p>
            <p>Most people think betting is about being right. It&apos;s not. It&apos;s about finding situations where the bookmaker&apos;s price doesn&apos;t reflect true probability.</p>
            <p><strong className="text-slate-100">Example:</strong> Bookmaker offers 2.10 odds on a player prop (implied 47.6%). Our calculated probability: 53%. Edge: 5.4%. That&apos;s a value bet. Even if it loses (which it will 47% of the time), the mathematics are positive over 100+ repetitions.</p>
            <p><strong className="text-slate-100">The discipline:</strong> We calculate fair odds for selections we analyze. We only bet when bookmaker price exceeds fair value by a meaningful margin. We don&apos;t bet because we &quot;think&quot; something will happen; we bet because the odds are wrong.</p>
            <p><strong className="text-slate-100">Variance is real:</strong> Even with edge, you&apos;ll have losing streaks. 10-bet, 15-bet losing runs happen. This is normal variance, not system failure. Edge manifests over hundreds of bets, not dozens.</p>
            <p><strong className="text-slate-100">Singles only:</strong> Accumulators compound bookmaker margin. A five-fold with 5% margin per leg = 22.6% total margin against you. We don&apos;t give away 20%+ edge before the match even starts.</p>
          </div>
        </section>

        {/* 3. Former Compiler Advantage */}
        <section className="bg-[#1a1d24] rounded-xl border border-emerald-500/20 p-6 md:p-8">
          <h2 className="text-xl md:text-2xl font-semibold text-emerald-400 mb-4">Why The Other Side Knows Better</h2>
          <div className="space-y-4 text-slate-300 leading-relaxed text-base">
            <p>Most betting services are run by professional bettors who learned by betting. Valuable, but limited perspective. I learned by <em>building the prices</em> bookmakers use.</p>
            <p><strong className="text-slate-100">What you see from the compiler side:</strong></p>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong className="text-slate-200">Template pricing dominates.</strong> Player props aren&apos;t individually crafted for each match. They&apos;re generated from historical averages. Opponent-specific factors, tactical matchups—these often aren&apos;t in the template.</li>
              <li><strong className="text-slate-200">Margin allocation varies.</strong> Match odds: 3–5%. Player props: 10–15%. Less efficient markets get wider margins and less sophisticated pricing.</li>
              <li><strong className="text-slate-200">Copy-paste pricing.</strong> Smaller bookmakers copy larger ones. When the original price is wrong, everyone&apos;s price is wrong.</li>
              <li><strong className="text-slate-200">Risk management priorities.</strong> Bookmakers monitor winning accounts on match odds aggressively. Player props? Less so. That&apos;s your window.</li>
            </ul>
            <p>This isn&apos;t insider information. It&apos;s understanding how the machinery works.</p>
          </div>
        </section>

        {/* 4. What We Don't Do */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8">
          <h2 className="text-xl md:text-2xl font-semibold text-emerald-400 mb-4">Discipline Matters</h2>
          <div className="space-y-3 text-slate-300 leading-relaxed text-base">
            <p><strong className="text-slate-100">We don&apos;t bet on every match.</strong> Some days there are 5 selections. Some days zero. Value betting requires patience.</p>
            <p><strong className="text-slate-100">We don&apos;t promise win rates.</strong> 58% win rate at 1.90 average odds = profitable. 65% win rate at 1.50 average odds = long-term loss. Win rate without odds context is meaningless. We focus on ROI.</p>
            <p><strong className="text-slate-100">We don&apos;t hide losses.</strong> Losing bets happen. Anyone who only shows winners is either lying or hasn&apos;t bet long enough to hit variance.</p>
            <p><strong className="text-slate-100">We don&apos;t guarantee outcomes.</strong> Individual bets are coin flips with weighted probabilities. Anyone claiming guaranteed winners is either delusional or scamming.</p>
            <p><strong className="text-slate-100">We don&apos;t share the model.</strong> Picks are shared. The proprietary modeling isn&apos;t. Standard for any professional betting operation.</p>
          </div>
        </section>

        {/* 5. Realistic Expectations */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8">
          <h2 className="text-xl md:text-2xl font-semibold text-emerald-400 mb-4">What To Expect</h2>
          <div className="space-y-3 text-slate-300 leading-relaxed text-base">
            <p><strong className="text-slate-100">Irregular posting schedule.</strong> We post when we find value, not on a daily schedule.</p>
            <p><strong className="text-slate-100">Variance will test you.</strong> Prepare for losing runs. 10+ consecutive losing bets will happen even with positive edge.</p>
            <p><strong className="text-slate-100">Account restrictions.</strong> If you follow our picks and win, bookmakers will eventually limit your stakes. It&apos;s proof you&apos;re betting well. See our <Link href="/bookmakers" className="text-emerald-400 hover:text-emerald-300 underline">bookmakers page</Link> for context.</p>
            <p><strong className="text-slate-100">Long-term focus.</strong> Edge manifests over hundreds of bets. Judging performance after 20 bets is measuring noise, not signal.</p>
            <p><strong className="text-slate-100">No get-rich-quick.</strong> Professional betting is slow, steady edge exploitation.</p>
          </div>
        </section>

        {/* 6. Philosophy (keep 5 points) */}
        <section className="bg-[#1a1d24] rounded-xl border border-emerald-500/20 p-6 md:p-8">
          <h2 className="text-2xl font-semibold mb-6 text-emerald-400">The Philosophy</h2>
          <div className="space-y-4 text-sm text-slate-300 leading-relaxed">
            <div className="flex gap-3">
              <span className="text-emerald-400 font-mono shrink-0">01</span>
              <p><strong className="text-slate-100">Mathematical edge only.</strong> We calculate true odds. We only bet when our odds are better than the bookmaker&apos;s.</p>
            </div>
            <div className="flex gap-3">
              <span className="text-emerald-400 font-mono shrink-0">02</span>
              <p><strong className="text-slate-100">We bet value, not outcomes.</strong> We bet because we have an edge over the odds. Whether the selection wins or loses is irrelevant to the decision; what matters is that the odds were wrong.</p>
            </div>
            <div className="flex gap-3">
              <span className="text-emerald-400 font-mono shrink-0">03</span>
              <p><strong className="text-slate-100">Singles only.</strong> Accumulators compound the bookmaker&apos;s edge. A five-fold with 5% margin per leg = 22.6% against you.</p>
            </div>
            <div className="flex gap-3">
              <span className="text-emerald-400 font-mono shrink-0">04</span>
              <p><strong className="text-slate-100">Exploit inefficiencies.</strong> Player props, niche markets, early lines. Where their models are weak, we attack.</p>
            </div>
            <div className="flex gap-3">
              <span className="text-emerald-400 font-mono shrink-0">05</span>
              <p><strong className="text-slate-100">No secrets given away.</strong> We share the picks, not the model.</p>
            </div>
          </div>
        </section>

        {/* 7. FAQ Accordion */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden">
          <h2 className="text-xl md:text-2xl font-semibold text-emerald-400 p-6 md:p-8 pb-2">Frequently Asked Questions</h2>
          <div className="divide-y divide-slate-800">
            {FAQ_ITEMS.map((item, i) => (
              <details key={i} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                  <span>{item.q}</span>
                  <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                  </span>
                </summary>
                <div className="px-6 md:px-8 pb-4 pt-0">
                  <p className="text-slate-400 text-base leading-relaxed">
                    {item.a.includes("Track Record") ? (
                      <>We target positive ROI across market types. Player props historically higher ROI than tennis (wider margins = more exploitable). Exact figures vary by market and time period. See <Link href="/track-record" className="text-emerald-400 hover:text-emerald-300 underline">Track Record</Link> for current data.</>
                    ) : (
                      item.a
                    )}
                  </p>
                </div>
              </details>
            ))}
          </div>
        </section>

        {/* 8. CTA */}
        <section className="bg-emerald-500/10 rounded-xl border border-emerald-500/30 p-6 md:p-8 text-center">
          <h2 className="text-xl font-semibold text-emerald-400 mb-2">See The Edge In Practice</h2>
          <p className="text-slate-300 text-base mb-6 max-w-xl mx-auto leading-relaxed">
            Join our free Telegram channel to see the methodology in action. Every pick includes match details, market, selection, odds, bookmaker, and stake recommendation. When we identify value, you&apos;ll see it before the event starts.
          </p>
          <a
            href={TELEGRAM_CHANNEL_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 bg-[#10b981] hover:bg-emerald-400 text-slate-900 font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            → Join Free on Telegram
          </a>
        </section>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-8 text-center text-sm text-slate-500">
        <p>Betting involves risk. Only bet what you can afford to lose.</p>
        <p className="mt-1">18+ only. Gamble responsibly. <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="text-emerald-400/80 hover:text-emerald-400">BeGambleAware.org</a></p>
      </div>
      <Footer />
    </div>
  );
}
