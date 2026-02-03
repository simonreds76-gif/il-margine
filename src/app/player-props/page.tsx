"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";

export default function PlayerProps() {
  const [activeLeague, setActiveLeague] = useState("all");

  const leagues = [
    { id: "all", name: "All Leagues", bets: 780, roi: "+25%", winRate: "58%", avgOdds: "2.35" },
    { id: "pl", name: "Premier League", bets: 285, roi: "+28%", winRate: "59%", avgOdds: "2.30" },
    { id: "seriea", name: "Serie A", bets: 245, roi: "+22%", winRate: "57%", avgOdds: "2.40" },
    { id: "ucl", name: "Champions League", bets: 180, roi: "+24%", winRate: "58%", avgOdds: "2.38" },
    { id: "other", name: "Other", bets: 70, roi: "+19%", winRate: "55%", avgOdds: "2.42" },
  ];

  // Sample active picks
  const activePicks = [
    {
      id: 1,
      league: "pl",
      match: "Arsenal vs Chelsea",
      player: "Saka",
      selection: "Over 2.5 Shots",
      odds: 1.85,
      bookmaker: "bet365",
      stake: 1.5,
      posted: "3h ago",
      status: "pending"
    },
    {
      id: 2,
      league: "seriea",
      match: "Inter vs Milan",
      player: "Lautaro Martinez",
      selection: "Over 1.5 Shots on Target",
      odds: 2.20,
      bookmaker: "Pinnacle",
      stake: 1,
      posted: "5h ago",
      status: "pending"
    },
  ];

  // Recent results
  const recentResults = [
    { id: 1, league: "pl", match: "Liverpool vs Man City", player: "Salah", selection: "2+ Shots on Target", odds: 1.95, stake: 2, result: "won", profit: "+1.9u" },
    { id: 2, league: "ucl", match: "Real Madrid vs Bayern", player: "Vinicius", selection: "1+ Foul Won", odds: 1.75, stake: 1, result: "won", profit: "+0.75u" },
    { id: 3, league: "seriea", match: "Napoli vs Juventus", player: "Osimhen", selection: "Over 2.5 Shots", odds: 1.90, stake: 1.5, result: "lost", profit: "-1.5u" },
    { id: 4, league: "pl", match: "Man Utd vs Tottenham", player: "Son", selection: "3+ Tackles", odds: 2.10, stake: 1, result: "won", profit: "+1.1u" },
    { id: 5, league: "pl", match: "Newcastle vs Aston Villa", player: "Isak", selection: "Over 1.5 SOT", odds: 2.25, stake: 1, result: "won", profit: "+1.25u" },
    { id: 6, league: "ucl", match: "PSG vs Dortmund", player: "Mbappe", selection: "1+ Foul Committed", odds: 1.80, stake: 1, result: "lost", profit: "-1u" },
  ];

  const filteredResults = activeLeague === "all" 
    ? recentResults 
    : recentResults.filter(r => r.league === activeLeague);

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
              <Link href="/player-props" className="text-sm text-emerald-400 font-medium">Player Props</Link>
              <Link href="/atp-tennis" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">ATP Tennis</Link>
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
            <span className="text-sm text-emerald-400">Player Props</span>
          </div>
          
          <h1 className="text-3xl md:text-4xl font-bold mb-4">Football Player Props</h1>
          <p className="text-slate-400 max-w-3xl mb-8">
            Individual player markets represent one of the most inefficient pricing areas in football betting. 
            While bookmakers dedicate significant resources to match odds, player props receive far less attention - 
            creating consistent value opportunities for those who specialise.
          </p>

          {/* Markets */}
          <div className="flex flex-wrap gap-2 mb-8">
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Shots</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Shots on Target</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Fouls Committed</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Fouls Won</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Tackles</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Cards</span>
          </div>

          {/* Methodology */}
          <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6 mb-8">
            <h3 className="font-semibold mb-4 text-emerald-400">Why Player Props?</h3>
            <div className="grid md:grid-cols-3 gap-6 text-sm text-slate-400">
              <div>
                <span className="text-slate-200 font-medium block mb-2">Market Inefficiency</span>
                Bookmakers apply wider margins to player props due to lower liquidity, but their pricing models 
                are far less sophisticated than match odds. Significant discrepancies exist between bookies - 
                often 10-15% on the same market. We exploit these gaps systematically.
              </div>
              <div>
                <span className="text-slate-200 font-medium block mb-2">Lower Limits, Higher Edge</span>
                Yes, stakes are capped lower than match betting. But edges are substantially larger. 
                A +25% ROI on capped stakes beats +2% ROI on unlimited stakes every time. 
                Smart money follows edge, not volume.
              </div>
              <div>
                <span className="text-slate-200 font-medium block mb-2">Data-Driven Selection</span>
                Every pick is backed by statistical analysis: historical player performance, 
                opponent defensive metrics, tactical matchups, and minute projections. 
                No gut feelings. No tips from mates. Pure numbers.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* League Tabs */}
      <section className="py-8 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap gap-3 mb-8">
            {leagues.map((league) => (
              <button
                key={league.id}
                onClick={() => setActiveLeague(league.id)}
                className={`px-4 py-3 rounded-lg border transition-all ${
                  activeLeague === league.id
                    ? "bg-slate-900/80 border-emerald-500/50 text-emerald-400"
                    : "bg-slate-900/30 border-slate-800 text-slate-400 hover:border-slate-700"
                }`}
              >
                <span className="font-medium">{league.name}</span>
                <div className="flex gap-3 mt-1 text-xs">
                  <span>{league.bets} bets</span>
                  <span className="text-emerald-400 font-mono">{league.roi}</span>
                </div>
              </button>
            ))}
          </div>

          {/* Stats for selected league */}
          {leagues.filter(l => l.id === activeLeague).map(league => (
            <div key={league.id} className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono">{league.bets}</div>
                <div className="text-xs text-slate-500">Total Bets</div>
              </div>
              <div className="p-4 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono">{league.roi}</div>
                <div className="text-xs text-slate-500">ROI</div>
              </div>
              <div className="p-4 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono">{league.winRate}</div>
                <div className="text-xs text-slate-500">Win Rate</div>
              </div>
              <div className="p-4 bg-slate-900/50 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono">{league.avgOdds}</div>
                <div className="text-xs text-slate-500">Avg Odds</div>
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
            <span className="text-xs text-slate-500">Updated in real-time via Telegram</span>
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
                        <span className="text-xs text-slate-500 font-mono uppercase">{pick.match}</span>
                        <span className="text-slate-700">•</span>
                        <span className="text-xs text-slate-500">{pick.posted}</span>
                      </div>
                      <h3 className="text-slate-400 mb-2">{pick.player}</h3>
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
              <p className="text-xs text-slate-600 mt-2">Join Telegram to get notified when new picks are posted</p>
            </div>
          )}
          
          <div className="mt-6 p-4 bg-slate-900/30 rounded-lg border border-slate-800 text-center">
            <p className="text-sm text-slate-400 mb-3">Get real-time alerts when new picks are posted</p>
            <button className="bg-emerald-500 hover:bg-emerald-400 text-black font-medium px-5 py-2 rounded inline-flex items-center gap-2 transition-colors text-sm">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
              Join Telegram Channel
            </button>
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
                      <span className="block text-xs text-slate-500">{result.player}</span>
                    </td>
                    <td className="px-4 py-4 text-slate-300">{result.selection}</td>
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
              Player Props picks use variable staking between <span className="text-slate-200 font-medium">0.5 to 2 units</span> based 
              on confidence level and perceived edge strength. Higher stakes indicate stronger conviction based on our analysis.
            </p>
            
            <div className="grid md:grid-cols-3 gap-4">
              <div className="p-4 bg-slate-800/30 rounded border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-slate-600 rounded-full"></div>
                  <span className="font-medium">0.5 - 1 Unit</span>
                </div>
                <p className="text-sm text-slate-500">Standard confidence. Edge identified but higher variance expected due to player form or minutes uncertainty.</p>
              </div>
              <div className="p-4 bg-slate-800/30 rounded border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-emerald-500/60 rounded-full"></div>
                  <span className="font-medium">1.5 Units</span>
                </div>
                <p className="text-sm text-slate-500">Strong confidence. Player confirmed starter, favourable matchup, historical data strongly supports selection.</p>
              </div>
              <div className="p-4 bg-slate-800/30 rounded border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-emerald-500 rounded-full"></div>
                  <span className="font-medium">2 Units</span>
                </div>
                <p className="text-sm text-slate-500">Maximum confidence. Clear pricing error across multiple bookmakers. These are rare but high conviction plays.</p>
              </div>
            </div>

            <div className="mt-6 p-4 bg-emerald-500/5 rounded border border-emerald-500/20">
              <p className="text-sm text-slate-400">
                <span className="text-emerald-400 font-medium">Bankroll guidance:</span> We recommend 100 units minimum bankroll. 
                Player props can be volatile short-term but edges are significant over large sample sizes.
                Trust the process and manage your stakes responsibly.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <span className="text-xs font-mono text-emerald-400 mb-4 block">FREE DURING BETA</span>
          <h2 className="text-3xl font-bold mb-4">Get Player Props picks on Telegram</h2>
          <p className="text-slate-400 mb-8 max-w-lg mx-auto">
            Match, player, selection, odds, bookmaker, stake. Everything you need. Posted in real-time before kickoff.
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
