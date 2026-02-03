"use client";

import Link from "next/link";
import Image from "next/image";

export default function ATPTennis() {
  const samplePicks = [
    { event: "Sinner vs Alcaraz", tournament: "ATP Finals", selection: "Sinner ML", odds: 2.10, bookmaker: "Pinnacle", status: "won" },
    { event: "Djokovic vs Medvedev", tournament: "Australian Open", selection: "Over 38.5 Games", odds: 1.95, bookmaker: "bet365", status: "lost" },
    { event: "Rune vs Tsitsipas", tournament: "ATP Miami", selection: "Rune +1.5 Sets", odds: 1.80, bookmaker: "Betfair", status: "pending" },
  ];

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
      <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href="/" className="flex items-center">
                <Image src="/logo.png" alt="Il Margine" width={150} height={40} className="h-8 w-auto" />
              </Link>
              <span className="text-slate-700">/</span>
              <span className="text-slate-400 text-sm">ATP Tennis</span>
            </div>
            
            <div className="hidden md:flex items-center gap-8">
              <Link href="/" className="text-sm text-slate-400 hover:text-slate-100 transition-colors flex items-center gap-1">
                ← Back
              </Link>
              <button className="bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2 rounded transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-emerald-500/20 rounded-lg flex items-center justify-center">
              <span className="text-2xl">🎾</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold">ATP Tennis</h1>
              <p className="text-slate-500 text-sm">Pre-match singles markets</p>
            </div>
          </div>
          
          <div className="flex flex-wrap gap-2 mt-4">
            <span className="px-3 py-1 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">ATP Tour</span>
            <span className="px-3 py-1 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">ATP Challenger</span>
            <span className="px-3 py-1 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Grand Slams</span>
          </div>
        </div>
      </section>

      {/* Track Record */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-emerald-400">2025 TRACK RECORD</span>
            </div>
            <a href="https://www.tipstrr.com" target="_blank" rel="noopener noreferrer" className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1">
              Verified on Tipstrr ↗
            </a>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">447</div>
              <div className="text-sm text-slate-500">Total Bets</div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">54%</div>
              <div className="text-sm text-slate-500">Win Rate</div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">8.6%</div>
              <div className="text-sm text-slate-500">ROI</div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">2.05</div>
              <div className="text-sm text-slate-500">Avg Odds</div>
            </div>
          </div>

          {/* Breakdown by competition */}
          <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden mb-10">
            <div className="px-5 py-4 border-b border-slate-800">
              <h3 className="font-semibold">By Competition</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-slate-500 font-mono border-b border-slate-800/50">
                    <th className="px-5 py-3">COMPETITION</th>
                    <th className="px-5 py-3">BETS</th>
                    <th className="px-5 py-3">WIN %</th>
                    <th className="px-5 py-3">ROI</th>
                    <th className="px-5 py-3 text-right">AVG ODDS</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  <tr className="border-b border-slate-800/30">
                    <td className="px-5 py-4 font-medium">ATP Tour</td>
                    <td className="px-5 py-4 text-slate-400 font-mono">330</td>
                    <td className="px-5 py-4 text-emerald-400 font-mono">55%</td>
                    <td className="px-5 py-4 text-emerald-400 font-mono">+10.5%</td>
                    <td className="px-5 py-4 text-right text-slate-400 font-mono">2.06</td>
                  </tr>
                  <tr className="border-b border-slate-800/30">
                    <td className="px-5 py-4 font-medium">ATP Challenger</td>
                    <td className="px-5 py-4 text-slate-400 font-mono">60</td>
                    <td className="px-5 py-4 text-emerald-400 font-mono">53%</td>
                    <td className="px-5 py-4 text-emerald-400 font-mono">+5.9%</td>
                    <td className="px-5 py-4 text-right text-slate-400 font-mono">2.05</td>
                  </tr>
                  <tr>
                    <td className="px-5 py-4 font-medium">Australian Open</td>
                    <td className="px-5 py-4 text-slate-400 font-mono">57</td>
                    <td className="px-5 py-4 text-slate-400 font-mono">51%</td>
                    <td className="px-5 py-4 text-slate-400 font-mono">+0.5%</td>
                    <td className="px-5 py-4 text-right text-slate-400 font-mono">2.02</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* Staking */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h3 className="font-semibold mb-4">Staking</h3>
          <p className="text-slate-400 text-sm mb-6">
            Variable staking between 0.5 and 2 units based on confidence level. Average stake is 1 unit.
          </p>
          <div className="flex flex-wrap gap-3">
            <span className="px-4 py-2 bg-slate-800/50 rounded text-sm font-mono text-slate-400 border border-slate-700/50">0.5u = Low confidence</span>
            <span className="px-4 py-2 bg-slate-800/50 rounded text-sm font-mono text-slate-400 border border-slate-700/50">1u = Standard</span>
            <span className="px-4 py-2 bg-slate-800/50 rounded text-sm font-mono text-emerald-400 border border-emerald-500/30">2u = High confidence</span>
          </div>
        </div>
      </section>

      {/* Recent Picks */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h3 className="font-semibold mb-6">Recent Picks</h3>
          <div className="space-y-3">
            {samplePicks.map((pick, i) => (
              <div key={i} className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className="flex items-center gap-4">
                  <div className={`w-2 h-2 rounded-full ${
                    pick.status === "won" ? "bg-emerald-400" : 
                    pick.status === "lost" ? "bg-red-400" : "bg-yellow-400"
                  }`} />
                  <div>
                    <p className="font-medium text-sm">{pick.event}</p>
                    <p className="text-xs text-slate-500">{pick.tournament}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-emerald-400">{pick.selection}</p>
                  <p className="text-xs text-slate-500 font-mono">@{pick.odds} • {pick.bookmaker}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl font-bold mb-4">Get ATP Tennis picks</h2>
          <p className="text-slate-400 mb-6 max-w-lg mx-auto">
            Match, selection, odds, bookmaker. Everything you need.
          </p>
          <button className="bg-emerald-500 hover:bg-emerald-400 text-black font-medium px-6 py-3 rounded inline-flex items-center gap-2 transition-colors">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
            Join Telegram Channel
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Image src="/favicon.png" alt="Il Margine" width={24} height={24} className="rounded" />
              <span className="font-semibold text-sm">Il Margine</span>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">FREE BETA</span>
            </div>
            
            <div className="text-xs text-slate-600">
              Gamble responsibly. 18+ only.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
