"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";

export default function ATPTennis() {
  const [activeCategory, setActiveCategory] = useState("all");

  const categories = [
    { id: "all", name: "All Tennis", bets: 447, roi: "+8.6%", winRate: "54%", avgOdds: "2.05", color: "emerald" },
    { id: "atp", name: "ATP Tour", bets: 330, roi: "+10.5%", winRate: "55%", avgOdds: "2.06", color: "blue" },
    { id: "challenger", name: "Challenger", bets: 60, roi: "+5.9%", winRate: "53%", avgOdds: "1.95", color: "amber" },
    { id: "ausopen", name: "Australian Open", bets: 57, roi: "+0.5%", winRate: "51%", avgOdds: "2.10", color: "cyan" },
  ];

  const colorClasses: Record<string, { border: string; text: string; bg: string; bar: string }> = {
    emerald: { border: "border-emerald-500/50", text: "text-emerald-400", bg: "bg-emerald-500/10", bar: "from-emerald-500 to-emerald-400" },
    blue: { border: "border-blue-500/50", text: "text-blue-400", bg: "bg-blue-500/10", bar: "from-blue-500 to-blue-400" },
    amber: { border: "border-amber-500/50", text: "text-amber-400", bg: "bg-amber-500/10", bar: "from-amber-500 to-amber-400" },
    cyan: { border: "border-cyan-500/50", text: "text-cyan-400", bg: "bg-cyan-500/10", bar: "from-cyan-500 to-cyan-400" },
  };

  const activeColor = categories.find(c => c.id === activeCategory)?.color || "emerald";

  // Sample active picks - these would come from database
  const activePicks = [
    {
      id: 1,
      category: "atp",
      tournament: "ATP 500 Rotterdam",
      match: "Sinner vs Rune",
      selection: "Sinner -3.5 Games",
      odds: 1.95,
      bookmaker: "Pinnacle",
      stake: 1.5,
      posted: "2h ago",
      status: "pending"
    },
    {
      id: 2,
      category: "atp",
      tournament: "ATP 250 Montpellier",
      match: "Bublik vs Humbert",
      selection: "Over 22.5 Games",
      odds: 1.87,
      bookmaker: "bet365",
      stake: 1,
      posted: "4h ago",
      status: "pending"
    },
  ];

  // Recent results
  const recentResults = [
    { id: 1, category: "atp", match: "Alcaraz vs Djokovic", selection: "Alcaraz ML", odds: 2.10, stake: 2, result: "won", profit: "+2.2u" },
    { id: 2, category: "atp", match: "Medvedev vs Zverev", selection: "Over 38.5 Games", odds: 1.90, stake: 1, result: "won", profit: "+0.9u" },
    { id: 3, category: "challenger", match: "Stricker vs Coric", selection: "Stricker +1.5 Sets", odds: 1.75, stake: 1, result: "lost", profit: "-1u" },
    { id: 4, category: "atp", match: "Fritz vs Tiafoe", selection: "Fritz -2.5 Games", odds: 1.88, stake: 1.5, result: "won", profit: "+1.32u" },
    { id: 5, category: "atp", match: "Tsitsipas vs Rublev", selection: "Tsitsipas ML", odds: 2.05, stake: 1, result: "lost", profit: "-1u" },
    { id: 6, category: "ausopen", match: "De Minaur vs Paul", selection: "Over 36.5 Games", odds: 1.92, stake: 1, result: "won", profit: "+0.92u" },
  ];

  const filteredResults = activeCategory === "all" 
    ? recentResults 
    : recentResults.filter(r => r.category === activeCategory);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
      <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center">
              <Image src="/logo.png" alt="Il Margine" width={180} height={50} className="h-10 w-auto" style={{ background: 'transparent' }} />
            </Link>
            
            <div className="hidden md:flex items-center gap-6">
              <Link href="/" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Home</Link>
              <Link href="/player-props" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Player Props</Link>
              <Link href="/atp-tennis" className="text-sm text-emerald-400 font-medium">ATP Tennis</Link>
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
          <div className="flex items-center gap-2 mb-4">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">Home</Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400">ATP Tennis</span>
          </div>
          
          <h1 className="text-3xl md:text-4xl font-bold mb-4">ATP Tennis Betting</h1>
          <p className="text-slate-400 max-w-3xl mb-8">
            Data-driven tennis analysis focused on value in pre-match markets. We specialise in game handicaps, 
            totals, and set betting where bookmaker pricing is inefficient.
          </p>

          {/* Methodology */}
          <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6 mb-8">
            <h3 className="font-semibold mb-4 text-emerald-400">Our Approach</h3>
            <div className="grid md:grid-cols-3 gap-6 text-sm text-slate-400">
              <div>
                <span className="text-slate-200 font-medium block mb-2">Surface Analysis</span>
                We analyse player performance by surface type. Some players show significant statistical 
                edges on hard courts vs clay that bookmakers underweight.
              </div>
              <div>
                <span className="text-slate-200 font-medium block mb-2">Tournament Tier Focus</span>
                ATP 250/500 events and Challengers have thinner markets where pricing inefficiencies 
                persist longer than Grand Slams. Lower liquidity means better value.
              </div>
              <div>
                <span className="text-slate-200 font-medium block mb-2">Line Value, Not Outcomes</span>
                We don&apos;t predict winners. We identify when bookmakers have mispriced game handicaps 
                and totals based on historical data and matchup analysis.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Category Tabs */}
      <section className="py-8 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap gap-3 mb-8">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`px-4 py-3 rounded-lg border transition-all ${
                  activeCategory === cat.id
                    ? `bg-slate-900/80 ${colorClasses[cat.color].border} ${colorClasses[cat.color].text}`
                    : "bg-slate-900/30 border-slate-800 text-slate-400 hover:border-slate-700"
                }`}
              >
                <span className="font-medium">{cat.name}</span>
                <div className="flex gap-3 mt-1 text-xs">
                  <span>{cat.bets} bets</span>
                  <span className={`${colorClasses[cat.color].text} font-mono`}>{cat.roi}</span>
                </div>
              </button>
            ))}
          </div>

          {/* Stats for selected category */}
          {categories.filter(c => c.id === activeCategory).map(cat => (
            <div key={cat.id} className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Total Bets */}
              <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-white font-mono mb-2">{cat.bets}</div>
                <div className="text-xs text-slate-500 mb-3">Total Bets</div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className={`h-full bg-gradient-to-r ${colorClasses[cat.color].bar} rounded-full transition-all duration-500`}
                    style={{ width: `${Math.min((cat.bets / 500) * 100, 100)}%` }}
                  />
                </div>
              </div>
              
              {/* ROI */}
              <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className={`text-2xl font-bold ${colorClasses[cat.color].text} font-mono mb-2`}>{cat.roi}</div>
                <div className="text-xs text-slate-500 mb-3">ROI</div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className={`h-full bg-gradient-to-r ${colorClasses[cat.color].bar} rounded-full transition-all duration-500`}
                    style={{ width: `${Math.min(parseFloat(cat.roi) * 4, 100)}%` }}
                  />
                </div>
              </div>
              
              {/* Win Rate */}
              <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className={`text-2xl font-bold ${colorClasses[cat.color].text} font-mono mb-2`}>{cat.winRate}</div>
                <div className="text-xs text-slate-500 mb-3">Win Rate</div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className={`h-full bg-gradient-to-r ${colorClasses[cat.color].bar} rounded-full transition-all duration-500`}
                    style={{ width: `${parseInt(cat.winRate)}%` }}
                  />
                </div>
              </div>
              
              {/* Avg Odds */}
              <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className={`text-2xl font-bold ${colorClasses[cat.color].text} font-mono mb-2`}>{cat.avgOdds}</div>
                <div className="text-xs text-slate-500 mb-3">Avg Odds</div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className={`h-full bg-gradient-to-r ${colorClasses[cat.color].bar} rounded-full transition-all duration-500`}
                    style={{ width: `${(parseFloat(cat.avgOdds) / 3) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Active Picks */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-2 block">ACTIVE PICKS</span>
              <h2 className="text-2xl font-bold">Current Selections</h2>
            </div>
            <span className="text-xs text-slate-500">Updated daily on this page</span>
          </div>

          {activePicks.length > 0 ? (
            <div className="grid gap-4">
              {activePicks.map((pick) => (
                <div key={pick.id} className="bg-slate-900/50 rounded-lg border border-slate-800 p-5 relative overflow-hidden">
                  <div className="absolute top-0 right-0 bg-amber-500/20 text-amber-400 text-xs font-mono px-3 py-1 rounded-bl">
                    PENDING
                  </div>
                  
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-slate-500 font-mono uppercase">{pick.tournament}</span>
                        <span className="text-slate-700">•</span>
                        <span className="text-xs text-slate-500">{pick.posted}</span>
                      </div>
                      <h3 className="text-slate-400 mb-2">{pick.match}</h3>
                      <div className="bg-slate-800/50 rounded px-3 py-2 inline-block">
                        <span className="font-semibold text-lg text-white">{pick.selection}</span>
                      </div>
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-6">
                      <div className="text-center">
                        <div className="text-2xl font-bold font-mono text-emerald-400">{pick.odds}</div>
                        <div className="text-xs text-slate-500">{pick.bookmaker}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-xl font-bold font-mono">{pick.stake}u</div>
                        <div className="text-xs text-slate-500">Stake</div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">No active picks at the moment</p>
              <p className="text-xs text-slate-600 mt-2">Check back soon for new selections</p>
            </div>
          )}
          
          <div className="mt-6 p-4 bg-emerald-500/5 rounded-lg border border-emerald-500/20 text-center">
            <p className="text-sm text-slate-400">Tennis picks are posted directly on this page. Bookmark and check back regularly.</p>
          </div>
        </div>
      </section>

      {/* Recent Results */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-2 block">RESULTS</span>
              <h2 className="text-2xl font-bold">Recent Picks</h2>
            </div>
          </div>

          <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase">
                  <th className="px-4 py-3 text-left">Match</th>
                  <th className="px-4 py-3 text-left">Selection</th>
                  <th className="px-4 py-3 text-center">Odds</th>
                  <th className="px-4 py-3 text-center">Stake</th>
                  <th className="px-4 py-3 text-center">Result</th>
                  <th className="px-4 py-3 text-right">P/L</th>
                </tr>
              </thead>
              <tbody>
                {filteredResults.map((result) => (
                  <tr key={result.id} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                    <td className="px-4 py-4">
                      <span className="font-medium">{result.match}</span>
                    </td>
                    <td className="px-4 py-4 text-slate-400">{result.selection}</td>
                    <td className="px-4 py-4 text-center font-mono">{result.odds}</td>
                    <td className="px-4 py-4 text-center font-mono">{result.stake}u</td>
                    <td className="px-4 py-4 text-center">
                      <span className={`text-xs font-mono px-2 py-1 rounded ${
                        result.result === "won" 
                          ? "text-emerald-400 bg-emerald-500/10" 
                          : "text-red-400 bg-red-500/10"
                      }`}>
                        {result.result.toUpperCase()}
                      </span>
                    </td>
                    <td className={`px-4 py-4 text-right font-mono font-medium ${
                      result.result === "won" ? "text-emerald-400" : "text-red-400"
                    }`}>
                      {result.profit}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <p className="text-xs text-slate-600 mt-4 text-center">
            All picks timestamped and tracked transparently
          </p>
        </div>
      </section>

      {/* Staking */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <span className="text-xs font-mono text-emerald-400 mb-2 block">STAKING</span>
          <h2 className="text-2xl font-bold mb-6">Stake Sizing</h2>
          
          <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6">
            <p className="text-slate-400 mb-6">
              ATP Tennis picks use variable staking between <span className="text-slate-200 font-medium">0.5 to 2 units</span> based 
              on confidence level and perceived edge strength. Higher stakes indicate stronger conviction based on our analysis.
            </p>
            
            <div className="grid md:grid-cols-3 gap-4">
              <div className="p-4 bg-slate-800/30 rounded border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-slate-600 rounded-full"></div>
                  <span className="font-medium">0.5 - 1 Unit</span>
                </div>
                <p className="text-sm text-slate-500">Standard confidence. Edge identified but lower sample size or more variance expected.</p>
              </div>
              <div className="p-4 bg-slate-800/30 rounded border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-emerald-500/60 rounded-full"></div>
                  <span className="font-medium">1.5 Units</span>
                </div>
                <p className="text-sm text-slate-500">Strong confidence. Multiple factors align with our model. Historical edge proven.</p>
              </div>
              <div className="p-4 bg-slate-800/30 rounded border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-emerald-500 rounded-full"></div>
                  <span className="font-medium">2 Units</span>
                </div>
                <p className="text-sm text-slate-500">Maximum confidence. Clear pricing error. These are rare but high conviction plays.</p>
              </div>
            </div>

            <div className="mt-6 p-4 bg-emerald-500/5 rounded border border-emerald-500/20">
              <p className="text-sm text-slate-400">
                <span className="text-emerald-400 font-medium">Bankroll guidance:</span> We recommend 100 units minimum bankroll. 
                At average stake of ~1.2u per pick and ~10-15 picks per week, drawdown periods can reach 15-20 units. 
                Proper bankroll management is essential for long-term profitability.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8 mt-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Image src="/favicon.png" alt="Il Margine" width={32} height={32} className="rounded" />
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
