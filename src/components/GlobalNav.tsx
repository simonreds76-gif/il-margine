"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";

export default function GlobalNav() {
  const [mobileMenuPath, setMobileMenuPath] = useState<string | null>(null);
  const [tipsMenuPath, setTipsMenuPath] = useState<string | null>(null);
  const pathname = usePathname();
  const showMonitorLink =
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
  const mobileMenuOpen = mobileMenuPath === pathname;
  const tipsMenuOpen = tipsMenuPath === pathname;

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.scrollTo(0, 0);
  }, [pathname]);

  const isTipsActive = ["/tennis-tips", "/player-props", "/bet-builders"].includes(pathname);
  const linkClass = (active: boolean) =>
    `text-base font-medium transition-colors ${active ? "text-emerald-400" : "text-slate-400 hover:text-slate-100"}`;

  return (
    <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          <Link href="/" className="flex items-center h-14 md:h-16 shrink-0" onClick={() => { if (pathname === "/") window.scrollTo(0, 0); }}>
            <Image src="/logo.png" alt="Il Margine" width={240} height={64} className="h-14 md:h-16 w-auto object-contain" priority />
          </Link>
          
          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuPath(mobileMenuOpen ? null : pathname)}
            className="md:hidden min-h-[44px] min-w-[44px] flex items-center justify-center p-2 text-slate-400 hover:text-slate-100 transition-colors"
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
          
          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-6">
            {/* Tips Dropdown */}
            <div className="relative">
              <button 
                onClick={() => setTipsMenuPath(tipsMenuOpen ? null : pathname)}
                onBlur={() => setTimeout(() => setTipsMenuPath(null), 150)}
                className={`flex items-center gap-1 ${linkClass(isTipsActive)}`}
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
                  <Link href="/bet-builders" className="block px-4 py-2 text-sm text-slate-300 hover:bg-slate-800">Bet Builders</Link>
                </div>
              )}
            </div>
            <Link href="/the-edge" className={linkClass(pathname === "/the-edge")}>The Edge</Link>
            <Link href="/anytime-goalscorer" className={linkClass(pathname === "/anytime-goalscorer")}>Goalscorer Model</Link>
            <Link href="/track-record" className={linkClass(pathname === "/track-record")}>Track Record</Link>
            {showMonitorLink ? <Link href="/model-monitor" className={linkClass(pathname === "/model-monitor")}>Monitor</Link> : null}
            <Link href="/bookmakers" className={linkClass(pathname === '/bookmakers')}>Bookmakers</Link>
            <Link href="/calculator" className={linkClass(pathname === '/calculator')}>Calculator</Link>
            <Link href="/resources" className={linkClass(pathname === '/resources' || pathname.startsWith('/resources/'))}>Resources</Link>
          </div>
        </div>
        
        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-slate-800/50 py-4 space-y-1">
            <div className="px-4">
              <button 
                onClick={() => setTipsMenuPath(tipsMenuOpen ? null : pathname)}
                className={`w-full min-h-[44px] flex items-center justify-between text-base font-medium rounded px-3 py-3 transition-colors ${isTipsActive ? 'text-emerald-400 font-medium bg-emerald-500/10' : 'text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10'}`}
              >
                <span>Tips</span>
                <svg className={`w-4 h-4 transition-transform ${tipsMenuOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {tipsMenuOpen && (
                <div className="mt-1 ml-4 space-y-1">
                  <Link href="/tennis-tips" className={`flex items-center min-h-[44px] px-3 py-2 text-sm rounded transition-colors ${pathname === '/tennis-tips' ? 'text-emerald-400 font-medium bg-emerald-500/10' : 'text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10'}`}>
                    Tennis Tips
                  </Link>
                  <Link href="/player-props" className={`flex items-center min-h-[44px] px-3 py-2 text-sm rounded transition-colors ${pathname === '/player-props' ? 'text-emerald-400 font-medium bg-emerald-500/10' : 'text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10'}`}>
                    Player Props
                  </Link>
                  <Link href="/bet-builders" className={`flex items-center min-h-[44px] px-3 py-2 text-sm rounded transition-colors ${pathname === '/bet-builders' ? 'text-emerald-400 font-medium bg-emerald-500/10' : 'text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10'}`}>
                    Bet Builders
                  </Link>
                </div>
              )}
            </div>
            <Link href="/the-edge" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/the-edge" ? "text-emerald-400 bg-emerald-500/10" : "text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10"}`}>
              The Edge
            </Link>
            <Link href="/anytime-goalscorer" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/anytime-goalscorer" ? "text-emerald-400 bg-emerald-500/10" : "text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10"}`}>
              Goalscorer Model
            </Link>
            <Link href="/track-record" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/track-record" ? "text-emerald-400 bg-emerald-500/10" : "text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10"}`}>
              Track Record
            </Link>
            {showMonitorLink ? (
              <Link href="/model-monitor" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/model-monitor" ? "text-emerald-400 bg-emerald-500/10" : "text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10"}`}>
                Monitor
              </Link>
            ) : null}
            <Link href="/bookmakers" className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === '/bookmakers' ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10'}`}>
              Bookmakers
            </Link>
            <Link href="/calculator" className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === '/calculator' ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10'}`}>
              Calculator
            </Link>
            <Link href="/resources" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === '/resources' || pathname?.startsWith('/resources/') ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10'}`}>
              Resources
            </Link>
          </div>
        )}
      </div>
    </nav>
  );
}
