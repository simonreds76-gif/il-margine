"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { TELEGRAM_CHANNEL_URL } from "@/lib/config";

export default function BetBuilders() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [tipsMenuOpen, setTipsMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
      <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center">
              <Image src="/logo.png" alt="Il Margine" width={180} height={50} className="h-10 w-auto" style={{ background: 'transparent' }} />
            </Link>
            
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-slate-400 hover:text-slate-100 transition-colors"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
            
            <div className="hidden md:flex items-center gap-6">
              <Link href="/" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Home</Link>
              <div className="relative">
                <button 
                  onClick={() => setTipsMenuOpen(!tipsMenuOpen)}
                  onBlur={() => setTimeout(() => setTipsMenuOpen(false), 150)}
                  className="text-sm text-emerald-400 font-medium flex items-center gap-1"
                >
                  Tips
                  <svg className={`w-4 h-4 transition-transform ${tipsMenuOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {tipsMenuOpen && (
                  <div className="absolute top-full left-0 mt-2 w-48 bg-slate-900 border border-slate-800 rounded-lg shadow-xl z-50">
                    <Link href="/tennis-tips" className="block px-4 py-2 text-sm text-slate-300 hover:bg-slate-800">Tennis Tips</Link>
                    <Link href="/player-props" className="block px-4 py-2 text-sm text-slate-300 hover:bg-slate-800">Player Props</Link>
                    <Link href="/anytime-goalscorer" className="block px-4 py-2 text-sm text-slate-300 hover:bg-slate-800">Anytime Goalscorer</Link>
                    <Link href="/bet-builders" className="block px-4 py-2 text-sm text-emerald-400 hover:bg-slate-800">Bet Builders</Link>
                  </div>
                )}
              </div>
              <Link href="/bookmakers" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Bookmakers</Link>
              <Link href="/calculator" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Calculator</Link>
              <a
                href={TELEGRAM_CHANNEL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2 rounded transition-colors flex items-center gap-2"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </a>
            </div>
          </div>
          
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-slate-800/50 py-4 space-y-3">
              <Link href="/" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Home</Link>
              <Link href="/tennis-tips" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Tennis Tips</Link>
              <Link href="/player-props" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Player Props</Link>
              <Link href="/anytime-goalscorer" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Anytime Goalscorer</Link>
              <Link href="/bet-builders" className="block px-4 py-2 text-sm text-emerald-400 font-medium hover:bg-emerald-500/10 rounded transition-colors">Bet Builders</Link>
              <Link href="/bookmakers" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Bookmakers</Link>
              <Link href="/calculator" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Calculator</Link>
              <a 
                href={TELEGRAM_CHANNEL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full mt-4 bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2.5 rounded transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </a>
            </div>
          )}
        </div>
      </nav>

      {/* Hero */}
      <section className="py-12 md:py-20 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-4">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">Home</Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400">Bet Builders</span>
          </div>
          
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-4 sm:mb-6">Football Bet Builder Tips</h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed">
            Football bet builder tips and same game combo analysis, focusing on structure, correlation and risk control.
          </p>
        </div>
      </section>

      {/* Coming Soon */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-12 text-center">
            <p className="text-slate-400 text-lg">Coming soon. Check back for bet builder tips and same game combo analysis.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
