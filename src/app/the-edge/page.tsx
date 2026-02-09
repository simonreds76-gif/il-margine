import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "The Edge",
  description: "Why Il Margine works: 25 years in the betting industry, former odds compiler, proprietary models, mathematical edge only.",
  alternates: {
    canonical: `${BASE_URL}/the-edge`,
  },
  robots: "index, follow",
};

export default function TheEdgePage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-4 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50 relative overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center opacity-[0.03] pointer-events-none">
          <Image src="/banner.png" alt="" width={1200} height={400} className="w-full max-w-6xl h-auto object-contain" />
        </div>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8">
            <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
            <span>← Home</span>
          </Link>
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">WHY IT WORKS</span>
              <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-2">The Edge</h1>
              <p className="text-lg text-slate-400 font-medium mb-6 sm:mb-8">Il Margine: Mind the margin.</p>
              <div className="space-y-6 text-slate-300 leading-relaxed text-base">
                <p>25 years in the betting industry. Former odds compiler. I&apos;ve worked on the other side, building the prices that bookmakers use. I know exactly where they cut corners and where value hides.</p>
                <p>Every pick is backed by proprietary models that strip out bookmaker margin to find true odds. We only bet when the numbers say yes. No hunches. No tips from a mate. Pure mathematics.</p>
                <p>The results speak for themselves. Over 1,200 tracked bets with consistent, verifiable profits across multiple markets.</p>
              </div>
              <div className="mt-8 bg-slate-900/50 rounded-lg border border-slate-800 p-6">
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
                  <div className="flex justify-between items-center py-3 bg-emerald-500/10 rounded px-3 -mx-3 mt-2">
                    <span className="text-emerald-400 font-semibold">Mathematical Edge</span>
                    <span className="text-emerald-400 font-bold text-lg">+11.1%</span>
                  </div>
                </div>
                <p className="text-xs text-slate-500 mt-4">We strip bookmaker margin to find true odds. When their price exceeds fair value, we bet.</p>
              </div>
            </div>
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6">
              <h2 className="text-2xl font-semibold mb-4 text-emerald-400">The Philosophy</h2>
              <div className="space-y-4 text-sm text-slate-400">
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">01</span>
                  <p><strong className="text-slate-200">Mathematical edge only.</strong> We calculate true odds. We only bet when our odds are better than the bookmaker&apos;s.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">02</span>
                  <p><strong className="text-slate-200">We don&apos;t bet because we think a team or player will win.</strong> We bet because we have an edge over the odds. Our true probability is higher than the price implies, so the bet is value. Whether the selection wins or loses is irrelevant to the decision; what matters is that the odds were wrong. That&apos;s the only reason we ever put a bet on.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">03</span>
                  <p><strong className="text-slate-200">Singles only.</strong> Accumulators compound the bookmaker&apos;s edge. A five-fold with 5% margin per leg = 22.6% against you. That&apos;s the graveyard of the bettor.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">04</span>
                  <p><strong className="text-slate-200">Exploit inefficiencies.</strong> Player props, niche markets, early lines. Where their models are weak, we attack.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">05</span>
                  <p><strong className="text-slate-200">No secrets given away.</strong> We share the picks, not the model. Rest assured we&apos;re not betting for fun.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
