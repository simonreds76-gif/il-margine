import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { TELEGRAM_CHANNEL_URL } from "@/lib/config";

const FAQ_ITEMS = [
  {
    q: "Where can I see the actual data?",
    a: "Data is being integrated into the site. Player props go to Telegram first (quick markets), tennis posts here. Check back as the database populates.",
  },
  {
    q: "How do I verify picks are real?",
    a: "Telegram timestamps for player props (posted before events start). Tennis picks posted on the website. You can check the archive to verify timing.",
  },
  {
    q: "What if results are poor?",
    a: "They stay logged. Losing bets are part of betting. Variance happens. What gets posted stays posted.",
  },
  {
    q: "Where's the detailed breakdown?",
    a: "Being built. Basic data is tracked, detailed tables and filtering coming as the site develops.",
  },
  {
    q: "Can past picks be edited?",
    a: "No. Telegram timestamps are immutable. Site data can't be retroactively changed once logged.",
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
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-8 md:pt-6 md:pb-12">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8">
          <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
          <span>← Home</span>
        </Link>

        {/* Hero */}
        <section className="mb-12 md:mb-16">
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">TRACK RECORD</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-3">Track Record</h1>
          <p className="text-lg text-slate-300 max-w-2xl mb-2">
            Performance data across betting markets.
          </p>
          <p className="text-base text-slate-400 max-w-2xl leading-relaxed">
            Player props posted to Telegram with timestamps. Tennis selections posted here. Results logged after settlement. No edits, no deletions. See <Link href="/the-edge" className="text-emerald-400 hover:text-emerald-300 underline">The Edge</Link> for our methodology.
          </p>
        </section>

        {/* 1. Current Data */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Performance Overview</h2>
          <div className="text-slate-300 leading-relaxed space-y-3">
            <p>Historical tracking across ATP tennis and player props markets. Data reflects actual bets placed and settled.</p>
            <p><strong className="text-slate-100">Player Props:</strong> Logged after posting to Telegram. Props odds move quickly so these are shared there first, then recorded here.</p>
            <p><strong className="text-slate-100">Tennis:</strong> Posted directly on site with full analysis. More stable markets allow detailed writeups.</p>
            <p>Performance data updates as bets settle. What&apos;s tracked stays tracked.</p>
          </div>
        </section>

        {/* 2. How Tracking Works */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Verification System</h2>
          <ul className="space-y-3 text-slate-300 leading-relaxed list-none">
            <li><strong className="text-slate-100">Pre-match posting:</strong> Every selection posted before event starts. Telegram timestamps for player props are immutable (can&apos;t be edited retroactively). Tennis picks posted directly on site.</li>
            <li><strong className="text-slate-100">Post-match settlement:</strong> After result, bet is logged here with outcome (win/loss/void), profit/loss in units, and link to original post where applicable.</li>
            <li><strong className="text-slate-100">No editing:</strong> Once logged, bets cannot be changed or deleted. What&apos;s posted is permanent.</li>
          </ul>
        </section>

        {/* 3. What To Expect */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Realistic Expectations</h2>
          <ul className="space-y-3 text-slate-300 leading-relaxed">
            <li><strong className="text-slate-100">Variance is real.</strong> Winning months and losing months happen. Even with positive long-term edge, short-term results fluctuate. This is normal.</li>
            <li><strong className="text-slate-100">Sample size matters.</strong> Performance over 20 bets is mostly noise. Over 100 bets, signal emerges. Over 200 bets, edge becomes clear. Judge long term, not week to week.</li>
            <li><strong className="text-slate-100">ROI varies by market.</strong> Player props typically higher ROI than tennis (wider margins, more exploitable). Match odds lower ROI (tighter margins). Staking adapts accordingly.</li>
            <li><strong className="text-slate-100">Stakes can get limited.</strong> If you follow picks successfully, bookmakers may reduce your stake sizes over time. See our <Link href="/bookmakers" className="text-emerald-400 hover:text-emerald-300 underline">bookmakers</Link> and <Link href="/faq" className="text-emerald-400 hover:text-emerald-300 underline">FAQ</Link> for context—it&apos;s a sign the approach works.</li>
            <li><strong className="text-slate-100">Losses get logged.</strong> Every selection gets recorded, winner or loser. Transparency over marketing.</li>
          </ul>
        </section>

        {/* 4. How It Works - Pick Distribution */}
        <section className="bg-[#1a1d24] rounded-xl border border-emerald-500/20 p-6 md:p-8 mb-8">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Pick Distribution</h2>
          <div className="text-slate-300 leading-relaxed space-y-3">
            <p><strong className="text-slate-100">Player Props:</strong> Posted to Telegram when value is identified. Props move quickly, so these are shared in real time on Telegram then logged here after settlement.</p>
            <p><strong className="text-slate-100">Tennis:</strong> Posted directly on the website. These markets are more stable, allowing time for proper analysis and posting.</p>
            <p>Results are tracked and logged transparently. What gets posted stays posted.</p>
          </div>
        </section>

        {/* 5. FAQ */}
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

        {/* 6. CTA */}
        <section className="bg-emerald-500/10 rounded-xl border border-emerald-500/30 p-6 md:p-8 text-center">
          <h2 className="text-xl font-semibold text-emerald-400 mb-2">Follow The Picks</h2>
          <p className="text-slate-300 text-base mb-6 max-w-xl mx-auto leading-relaxed">
            Player props posted to Telegram as value is identified. Tennis selections posted here with full analysis.
          </p>
          <a
            href={TELEGRAM_CHANNEL_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 bg-blue-500 hover:bg-blue-400 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            → Join Telegram for Player Props
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
