import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { TELEGRAM_CHANNEL_URL } from "@/lib/config";

const FAQ_ITEMS = [
  {
    q: "When will live results start appearing?",
    a: "March 2026. All picks from that point forward will be logged here with full transparency.",
  },
  {
    q: "Can I see detailed historical data?",
    a: "Summary statistics are available. Detailed bet-by-bet breakdown will be added after March launch when live tracking infrastructure is built.",
  },
  {
    q: "How do I verify bets are real?",
    a: "Every bet has Telegram timestamp (posted before event starts). You can verify by checking our Telegram channel history. After March, individual verification pages will provide direct proof.",
  },
  {
    q: "What if you have a losing month?",
    a: "It'll be visible here. Variance is part of betting. We're not hiding bad periods—they're inevitable even with positive edge.",
  },
  {
    q: "Why isn't there more data shown right now?",
    a: "Platform is in beta. Live tracking infrastructure launches March 2026. Historical data was tracked privately to validate methodology before public launch.",
  },
  {
    q: "Can you edit past results?",
    a: "No. Once a bet is logged, it's permanent. Telegram timestamps make retroactive editing impossible.",
  },
];

export default function TrackRecordPage() {
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ_ITEMS.map(({ q, a }) => ({
      "@type": "Question",
      name: q,
      acceptedAnswer: { "@type": "Answer", text: a },
    })),
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8">
          <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
          <span>← Home</span>
        </Link>

        {/* Hero */}
        <section className="mb-12 md:mb-16">
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">TRACK RECORD</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-3">Track Record</h1>
          <p className="text-lg text-slate-300 max-w-2xl mb-2">
            Transparent performance across our betting markets.
          </p>
          <p className="text-base text-slate-400 max-w-2xl leading-relaxed">
            All picks are timestamped and trackable. ATP Tennis verified on Tipstrr. Player Props self-tracked with Telegram timestamps. Results update as bets settle. No edits, no deletions, no hiding losses. See <Link href="/the-edge" className="text-emerald-400 hover:text-emerald-300 underline">The Edge</Link> for our methodology.
          </p>
        </section>

        {/* 1. Platform Status */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Platform Status</h2>
          <div className="text-slate-300 leading-relaxed space-y-3">
            <p><strong className="text-slate-100">Beta Phase</strong> — Building track record through March 2026.</p>
            <p><strong className="text-slate-100">Historical data:</strong> Available from prior private tracking.</p>
            <p><strong className="text-slate-100">Live picks:</strong> Launching March 2026 with full public logging.</p>
            <p>All future selections will be posted to Telegram with immutable timestamps before events start, then logged here after settlement.</p>
          </div>
        </section>

        {/* 2. How Tracking Works */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Verification System</h2>
          <ul className="space-y-3 text-slate-300 leading-relaxed list-none">
            <li><strong className="text-slate-100">Pre-Match Posting:</strong> Every selection posted to Telegram before event starts. Telegram timestamps are immutable.</li>
            <li><strong className="text-slate-100">Post-Match Settlement:</strong> After result, bet is logged here with outcome (win/loss/void), profit/loss in units, and link to original Telegram post.</li>
            <li><strong className="text-slate-100">Individual Verification:</strong> Each bet will have unique page: ilmargine.bet/bet/[id] — match details, selection, odds, bookmaker, stake, result, Telegram timestamp proof.</li>
            <li><strong className="text-slate-100">No Editing:</strong> Once logged, bets cannot be changed or deleted.</li>
          </ul>
        </section>

        {/* 3. Historical Performance - Option A */}
        <section className="bg-[#1a1d24] rounded-xl border border-emerald-500/20 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Pre-Launch Tracking</h2>
          <p className="text-slate-300 leading-relaxed mb-6">
            Prior to public launch, we tracked selections privately to validate methodology.
          </p>
          <div className="grid sm:grid-cols-3 gap-4 mb-4">
            <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-4">
              <div className="text-2xl font-bold text-emerald-400 font-mono">447</div>
              <div className="text-sm text-slate-400">ATP Tennis bets</div>
              <div className="text-xs text-slate-500 mt-1">Verified on Tipstrr</div>
            </div>
            <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-4">
              <div className="text-2xl font-bold text-emerald-400 font-mono">780+</div>
              <div className="text-sm text-slate-400">Player Props</div>
              <div className="text-xs text-slate-500 mt-1">Self-logged with timestamps</div>
            </div>
            <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-4">
              <div className="text-2xl font-bold text-emerald-400 font-mono">1,200+</div>
              <div className="text-sm text-slate-400">Combined</div>
              <div className="text-xs text-slate-500 mt-1">18 months tracked</div>
            </div>
          </div>
          <p className="text-sm text-slate-500">
            Full detailed breakdown available after March 2026 launch when live tracking begins.
          </p>
        </section>

        {/* 4. What To Expect */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Realistic Expectations</h2>
          <ul className="space-y-3 text-slate-300 leading-relaxed">
            <li><strong className="text-slate-100">Variance is real.</strong> Winning months and losing months happen. Even with positive long-term edge, short-term results fluctuate.</li>
            <li><strong className="text-slate-100">Sample size matters.</strong> Performance over 20 bets is mostly noise. Over 100+ bets, signal emerges. Judge long-term, not week-to-week.</li>
            <li><strong className="text-slate-100">ROI varies by market.</strong> Player props typically higher ROI than tennis. We adapt staking accordingly.</li>
            <li><strong className="text-slate-100">Account restrictions affect access.</strong> If you follow our picks successfully, bookmakers will limit your stakes eventually. See our <Link href="/bookmakers" className="text-emerald-400 hover:text-emerald-300 underline">bookmakers</Link> and <Link href="/faq" className="text-emerald-400 hover:text-emerald-300 underline">FAQ</Link> pages.</li>
            <li><strong className="text-slate-100">We don&apos;t hide losing bets.</strong> Every selection—winner or loser—will be logged here.</li>
          </ul>
        </section>

        {/* 5. Live Tracking Coming Soon - table mockup */}
        <section className="bg-[#1a1d24] rounded-xl border border-emerald-500/20 p-6 md:p-8 mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <h2 className="text-xl font-semibold text-emerald-400">Launching March 2026</h2>
            <span className="text-xs font-mono font-medium text-emerald-400 bg-emerald-500/20 border border-emerald-500/40 px-3 py-1.5 rounded">Coming Soon</span>
          </div>
          <p className="text-slate-300 leading-relaxed mb-6">
            Starting March, every pick will appear here: pre-match table, settled bets table, performance breakdown by market and league, and individual verification pages.
          </p>
          <div className="overflow-x-auto rounded-lg border border-slate-700">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-800/60 border-b border-slate-700">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Date</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Market</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Selection</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Odds</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Stake</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Result</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">P/L</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-800">
                  <td colSpan={7} className="py-8 px-4 text-center text-slate-500">
                    Live tracking launches March 2026. This table will populate automatically as bets settle.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-sm text-slate-500 mt-4">
            <a href={TELEGRAM_CHANNEL_URL} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 underline">Join Telegram</a> to be notified when live tracking goes live.
          </p>
        </section>

        {/* 6. Why Transparency Matters */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Industry Standard vs Our Standard</h2>
          <div className="grid md:grid-cols-2 gap-6 text-slate-300 leading-relaxed">
            <div>
              <p className="text-slate-500 text-sm font-medium mb-2">Most betting services:</p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>Hide losing bets</li>
                <li>Edit past selections when odds change</li>
                <li>Cherry-pick timeframes</li>
                <li>No independent verification</li>
              </ul>
            </div>
            <div>
              <p className="text-emerald-400/90 text-sm font-medium mb-2">Our approach:</p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>Every bet logged publicly</li>
                <li>Immutable Telegram timestamps</li>
                <li>No editing or deleting</li>
                <li>ATP tennis independently verified (Tipstrr)</li>
              </ul>
            </div>
          </div>
          <p className="mt-4 text-slate-300">
            Trust is earned through honesty, not marketing. If we have a bad month, you&apos;ll see it. This is our accountability.
          </p>
        </section>

        {/* 7. FAQ */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 p-6 md:p-8 pb-2">Frequently Asked Questions</h2>
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
                  <p className="text-slate-400 text-base leading-relaxed">{item.a}</p>
                </div>
              </details>
            ))}
          </div>
        </section>

        {/* 8. CTA */}
        <section className="bg-emerald-500/10 rounded-xl border border-emerald-500/30 p-6 md:p-8 text-center">
          <h2 className="text-xl font-semibold text-emerald-400 mb-2">Follow Live Results</h2>
          <p className="text-slate-300 text-base mb-6 max-w-xl mx-auto leading-relaxed">
            Join Telegram to see selections as they&apos;re posted (before events start) and verify timestamps yourself. When March launch happens, this page will update automatically with every settled bet.
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

        <div className="text-center text-sm text-slate-500 pt-4 pb-8">
          <p>Betting involves risk. Past performance doesn&apos;t guarantee future results.</p>
          <p className="mt-1">18+ only. Gamble responsibly. <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="text-emerald-400/80 hover:text-emerald-400">BeGambleAware.org</a></p>
        </div>
      </div>
      <Footer />
    </div>
  );
}
