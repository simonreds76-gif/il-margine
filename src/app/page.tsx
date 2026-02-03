"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";

export default function Home() {
  const [activeMarket, setActiveMarket] = useState("props");
  const [tipsMenuOpen, setTipsMenuOpen] = useState(false);

  const markets = [
    { id: "props", name: "Player Props", description: "Football individual player markets", status: "active", bets: "780+", profit: "+25% ROI" },
    { id: "atp", name: "ATP Tennis", description: "Pre-match singles markets", status: "active", bets: "447", profit: "+8.6% ROI" },
    { id: "builders", name: "Bet Builders", description: "Same-game combinations", status: "coming" },
    { id: "atg", name: "ATG", description: "Anytime goalscorer markets", status: "coming" },
  ];

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
              {/* Tips Dropdown */}
              <div className="relative">
                <button 
                  onClick={() => setTipsMenuOpen(!tipsMenuOpen)}
                  onBlur={() => setTimeout(() => setTipsMenuOpen(false), 150)}
                  className="text-sm text-slate-400 hover:text-slate-100 transition-colors flex items-center gap-1"
                >
                  Tips
                  <svg className={`w-4 h-4 transition-transform ${tipsMenuOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                
                {tipsMenuOpen && (
                  <div className="absolute top-full left-0 mt-2 w-64 bg-slate-900/95 backdrop-blur-sm border border-slate-800 rounded-xl shadow-2xl overflow-hidden z-50">
                    <Link 
                      href="/player-props" 
                      className="group block px-4 py-4 hover:bg-emerald-500/10 transition-all duration-300 border-b border-slate-800/50"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-200 group-hover:text-emerald-400 transition-colors">Player Props</span>
                          <span className="block text-xs text-slate-500 mt-0.5">Football • Shots, Tackles, Fouls</span>
                        </div>
                        <div className="w-12 h-8 relative overflow-hidden">
                          <svg className="w-full h-full" viewBox="0 0 48 32">
                            <path 
                              d="M0 28 L12 20 L24 24 L36 12 L48 8" 
                              fill="none" 
                              stroke="currentColor" 
                              strokeWidth="2"
                              className="text-slate-700 group-hover:text-emerald-500/50 transition-colors duration-300"
                            />
                            <path 
                              d="M0 28 L12 20 L24 24 L36 12 L48 8" 
                              fill="none" 
                              stroke="currentColor" 
                              strokeWidth="2"
                              className="text-transparent group-hover:text-emerald-400 transition-all duration-500"
                              strokeDasharray="100"
                              strokeDashoffset="100"
                              style={{ animation: tipsMenuOpen ? 'none' : 'none' }}
                            />
                            <circle cx="48" cy="8" r="3" className="fill-slate-700 group-hover:fill-emerald-400 transition-colors duration-300" />
                          </svg>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-xs font-mono text-emerald-400/80">+25% ROI</span>
                        <span className="text-xs text-slate-600">780+ bets</span>
                      </div>
                    </Link>
                    
                    <Link 
                      href="/atp-tennis" 
                      className="group block px-4 py-4 hover:bg-emerald-500/10 transition-all duration-300 border-b border-slate-800/50"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-200 group-hover:text-emerald-400 transition-colors">ATP Tennis</span>
                          <span className="block text-xs text-slate-500 mt-0.5">Pre-match • Handicaps, Totals</span>
                        </div>
                        <div className="w-12 h-8 relative overflow-hidden">
                          <svg className="w-full h-full" viewBox="0 0 48 32">
                            <path 
                              d="M0 24 L16 22 L32 16 L48 10" 
                              fill="none" 
                              stroke="currentColor" 
                              strokeWidth="2"
                              className="text-slate-700 group-hover:text-emerald-500/50 transition-colors duration-300"
                            />
                            <circle cx="48" cy="10" r="3" className="fill-slate-700 group-hover:fill-emerald-400 transition-colors duration-300" />
                          </svg>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-xs font-mono text-emerald-400/80">+8.6% ROI</span>
                        <span className="text-xs text-slate-600">447 bets</span>
                      </div>
                    </Link>
                    
                    <div className="group px-4 py-4 border-b border-slate-800/50 opacity-50">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-500">Bet Builders</span>
                          <span className="block text-xs text-slate-600 mt-0.5">Same-game combos</span>
                        </div>
                        <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-2 py-0.5 rounded">SOON</span>
                      </div>
                    </div>
                    
                    <div className="group px-4 py-4 opacity-50">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-500">ATG</span>
                          <span className="block text-xs text-slate-600 mt-0.5">Anytime goalscorer</span>
                        </div>
                        <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-2 py-0.5 rounded">SOON</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              <a href="#the-edge" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">The Edge</a>
              <a href="#track-record" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Track Record</a>
              <button className="bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2 rounded transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="py-12 md:py-20 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Banner */}
          <div className="mb-12 flex justify-center">
            <Image 
              src="/banner.png" 
              alt="Il Margine" 
              width={900} 
              height={300} 
              className="max-w-3xl w-full h-auto object-contain"
              priority
            />
          </div>

          <div className="max-w-3xl mx-auto text-center">
            <div className="flex items-center justify-center gap-2 mb-6">
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded">FREE BETA</span>
            </div>
            
            <h1 className="text-4xl md:text-5xl font-bold mb-6 leading-tight">
              Betting with <span className="text-emerald-400">mathematical edge</span>.
            </h1>
            
            <p className="text-lg text-slate-400 mb-8 leading-relaxed">
              Professional betting methodology built on 25 years of odds compilation experience. We find value where bookmakers misprice. Singles only, data-driven picks, transparent results.
            </p>
            
            <div className="flex flex-wrap justify-center gap-4 mb-12">
              <button className="bg-emerald-500 hover:bg-emerald-400 text-black font-medium px-6 py-3 rounded flex items-center gap-2 transition-colors">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Telegram Channel
              </button>
              <a href="#the-edge" className="border border-slate-700 hover:border-slate-500 text-slate-300 font-medium px-6 py-3 rounded transition-colors">
                How It Works
              </a>
            </div>
            
            <div className="flex flex-wrap justify-center gap-6">
              <div className="p-4 bg-slate-900/50 rounded border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono mb-1">✓</div>
                <div className="text-xs text-slate-500">Verified Edge</div>
              </div>
              <div className="p-4 bg-slate-900/50 rounded border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono mb-1">100%</div>
                <div className="text-xs text-slate-500">Singles Only</div>
              </div>
              <div className="p-4 bg-slate-900/50 rounded border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono mb-1">25+</div>
                <div className="text-xs text-slate-500">Years Experience</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Markets */}
      <section id="markets" className="py-16 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-8">
            <span className="text-xs font-mono text-emerald-400">MARKETS</span>
          </div>
          
          <h2 className="text-3xl font-bold mb-4">Where we find edge</h2>
          <p className="text-slate-400 mb-10 max-w-2xl">
            We focus on markets where bookmaker pricing is inefficient. No mainstream match odds. No markets where the bookies have perfect data.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {markets.map((market) => {
              const href = market.id === "props" ? "/player-props" : market.id === "atp" ? "/atp-tennis" : "";
              const isActive = market.status === "active";
              
              const cardContent = (
                <>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold">{market.name}</h3>
                    {market.status === "coming" ? (
                      <span className="text-xs font-mono text-slate-600 bg-slate-800/50 px-2 py-0.5 rounded">SOON</span>
                    ) : (
                      <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">LIVE</span>
                    )}
                  </div>
                  <p className="text-sm text-slate-500 mb-4">{market.description}</p>
                  {market.status === "active" && (
                    <div className="flex gap-4 text-sm">
                      <span className="text-slate-400">{market.bets} bets</span>
                      <span className="text-emerald-400 font-mono">{market.profit}</span>
                    </div>
                  )}
                </>
              );
              
              const cardClass = `p-6 rounded-lg border transition-all cursor-pointer block ${
                market.status === "coming"
                  ? "bg-slate-900/30 border-slate-800/50 opacity-60"
                  : activeMarket === market.id
                  ? "bg-slate-900/80 border-emerald-500/50"
                  : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
              }`;
              
              return isActive ? (
                <Link
                  key={market.id}
                  href={href}
                  className={cardClass}
                  onClick={() => setActiveMarket(market.id)}
                >
                  {cardContent}
                </Link>
              ) : (
                <div
                  key={market.id}
                  className={cardClass}
                >
                  {cardContent}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Latest Results */}
      <section className="py-16 border-b border-slate-800/50 bg-slate-900/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-8">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-2 block">LATEST RESULTS</span>
              <h2 className="text-2xl font-bold">Recent Picks</h2>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-emerald-400 font-mono">Last 7 days: +4.87u</span>
            </div>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Result Card 1 - Won */}
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-4 hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500 font-mono">Feb 02</span>
                <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-medium">WON</span>
              </div>
              <div className="text-sm text-slate-400 mb-1">ATP Montpellier</div>
              <div className="font-medium mb-2">Fils ML</div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">@1.72 • 1u</span>
                <span className="text-emerald-400 font-mono font-medium">+0.72u</span>
              </div>
            </div>
            
            {/* Result Card 2 - Lost */}
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-4 hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500 font-mono">Feb 01</span>
                <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded font-medium">LOST</span>
              </div>
              <div className="text-sm text-slate-400 mb-1">Player Props</div>
              <div className="font-medium mb-2">Salah 2+ Shots OT</div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">@1.85 • 1.5u</span>
                <span className="text-red-400 font-mono font-medium">-1.50u</span>
              </div>
            </div>
            
            {/* Result Card 3 - Won */}
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-4 hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500 font-mono">Jan 31</span>
                <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-medium">WON</span>
              </div>
              <div className="text-sm text-slate-400 mb-1">ATP Montpellier</div>
              <div className="font-medium mb-2">Bublik +4.5 Games</div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">@1.85 • 2u</span>
                <span className="text-emerald-400 font-mono font-medium">+1.70u</span>
              </div>
            </div>
            
            {/* Result Card 4 - Won */}
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-4 hover:border-slate-700 transition-colors">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500 font-mono">Jan 30</span>
                <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-medium">WON</span>
              </div>
              <div className="text-sm text-slate-400 mb-1">Player Props</div>
              <div className="font-medium mb-2">Palmer 3+ Tackles</div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">@1.95 • 2u</span>
                <span className="text-emerald-400 font-mono font-medium">+1.90u</span>
              </div>
            </div>
          </div>
          
          <div className="mt-6 flex justify-center gap-4">
            <Link href="/atp-tennis" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
              View ATP Tennis Results →
            </Link>
            <Link href="/player-props" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
              View Player Props Results →
            </Link>
          </div>
        </div>
      </section>

      {/* The Edge Section */}
      <section id="the-edge" className="py-16 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-start">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-4 block">WHY IT WORKS</span>
              <h2 className="text-3xl font-bold mb-6">The Edge</h2>
              
              <div className="space-y-6 text-slate-400 leading-relaxed">
                <p>
                  25 years in the betting industry. Former odds compiler. I&apos;ve worked on the other side, building the prices that bookmakers use. I know exactly where they cut corners and where value hides.
                </p>
                <p>
                  Every pick is backed by proprietary models that strip out bookmaker margin to find true odds. We only bet when the numbers say yes. No hunches. No tips from a mate. Pure mathematics.
                </p>
                <p>
                  The results speak for themselves. Over 1,200 tracked bets with consistent, verifiable profits across multiple markets.
                </p>
              </div>
              
              {/* Edge Calculation Example */}
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
                    <span className="text-slate-400">Our Fair Odds <span className="text-slate-600">(margin stripped)</span></span>
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
                
                <p className="text-xs text-slate-500 mt-4">
                  We strip bookmaker margin to find true odds. When their price exceeds fair value, we bet.
                </p>
              </div>
            </div>
            
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6">
              <h3 className="font-semibold mb-4 text-emerald-400">The Philosophy</h3>
              <div className="space-y-4 text-sm text-slate-400">
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">01</span>
                  <p><strong className="text-slate-200">Mathematical edge only.</strong> We calculate true odds. We only bet when our odds are better than the bookmaker&apos;s.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">02</span>
                  <p><strong className="text-slate-200">Singles only.</strong> Accumulators compound the bookmaker&apos;s edge. A five-fold with 5% margin per leg = 22.6% against you. That&apos;s the graveyard of the bettor.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">03</span>
                  <p><strong className="text-slate-200">Exploit inefficiencies.</strong> Player props, niche markets, early lines. Where their models are weak, we attack.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">04</span>
                  <p><strong className="text-slate-200">No secrets given away.</strong> We share the picks, not the model. Rest assured we&apos;re not betting for fun.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Track Record */}
      <section id="track-record" className="py-16 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <span className="text-xs font-mono text-emerald-400 mb-4 block">TRACK RECORD</span>
          <h2 className="text-3xl font-bold mb-4">Proven Results</h2>
          <p className="text-slate-400 mb-10 max-w-2xl">
            Exposed results across all active markets. ATP Tennis verified on Tipstrr. Player Props self-tracked with timestamped records.
          </p>

          {/* Combined Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">1,200+</div>
              <div className="text-sm text-slate-500">Total Bets</div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">56%</div>
              <div className="text-sm text-slate-500">Win Rate</div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">+18%</div>
              <div className="text-sm text-slate-500">Combined ROI</div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-3xl font-bold text-emerald-400 font-mono mb-1">2</div>
              <div className="text-sm text-slate-500">Active Markets</div>
            </div>
          </div>

          {/* Individual Markets */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Player Props */}
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">Player Props</h3>
                <span className="text-xs font-mono text-slate-600">FOOTBALL 2025</span>
              </div>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">780+</div>
                  <div className="text-xs text-slate-500">Bets</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">+25%</div>
                  <div className="text-xs text-slate-500">ROI</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">58%</div>
                  <div className="text-xs text-slate-500">Win Rate</div>
                </div>
              </div>
              <p className="text-xs text-slate-500">Self-tracked with timestamped screenshots</p>
            </div>

            {/* ATP Tennis */}
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">ATP Tennis</h3>
                <span className="text-xs font-mono text-emerald-400">TIPSTRR VERIFIED</span>
              </div>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">447</div>
                  <div className="text-xs text-slate-500">Bets</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">+8.6%</div>
                  <div className="text-xs text-slate-500">ROI</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">54%</div>
                  <div className="text-xs text-slate-500">Win Rate</div>
                </div>
              </div>
              <p className="text-xs text-slate-500">Independently verified on Tipstrr.com</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to join?</h2>
          <p className="text-slate-400 mb-8 max-w-lg mx-auto">
            Free picks delivered to Telegram. Match, selection, odds, bookmaker. Everything you need.
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
