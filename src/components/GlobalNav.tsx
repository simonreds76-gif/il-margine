"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";

export default function GlobalNav() {
  const [mobileMenuPath, setMobileMenuPath] = useState<string | null>(null);
  const [tipsMenuPath, setTipsMenuPath] = useState<string | null>(null);
  const [resourcesMenuPath, setResourcesMenuPath] = useState<string | null>(null);
  const pathname = usePathname();
  const showMonitorLink =
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
  const mobileMenuOpen = mobileMenuPath === pathname;
  const tipsMenuOpen = tipsMenuPath === pathname;
  const resourcesMenuOpen = resourcesMenuPath === pathname;

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.scrollTo(0, 0);
  }, [pathname]);

  const isTipsActive =
    pathname === "/tennis-tips" ||
    pathname === "/player-props";
  const isResourcesActive =
    pathname === "/bookmakers" ||
    pathname === "/calculator" ||
    pathname === "/resources" ||
    pathname.startsWith("/resources/");
  const linkClass = (active: boolean) =>
    `text-base font-medium transition-colors ${active ? "text-[var(--brand-green)]" : "text-slate-400 hover:text-slate-100"}`;

  return (
    <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between md:h-[88px]">
          <Link href="/" className="flex h-12 min-w-0 shrink items-center md:h-[68px]" onClick={() => { if (pathname === "/") window.scrollTo(0, 0); }}>
            <Image src="/logo.png" alt="Il Margine" width={240} height={64} className="h-12 max-w-[210px] w-auto object-contain md:h-[68px] md:max-w-none" priority />
          </Link>
          
          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuPath(mobileMenuOpen ? null : pathname)}
            className="md:hidden min-h-[44px] min-w-[44px] flex items-center justify-center p-2 text-slate-400 hover:text-slate-100 transition-colors"
            aria-label="Toggle menu"
            aria-expanded={mobileMenuOpen}
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
          <div className="hidden md:flex items-center gap-5 lg:gap-6">
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
                </div>
              )}
            </div>
            <Link href="/the-edge" className={linkClass(pathname === "/the-edge")}>The Edge</Link>
            <Link href="/penalty-takers" className={linkClass(pathname === "/penalty-takers")}>Penalty Takers</Link>
            <Link href="/fair-odds-lab" className={linkClass(pathname === "/fair-odds-lab")}>Fair Odds Lab</Link>
            <Link href="/track-record" className={linkClass(pathname === "/track-record")}>Track Record</Link>
            {showMonitorLink ? <Link href="/model-monitor" className={linkClass(pathname === "/model-monitor")}>Monitor</Link> : null}
            <div className="relative">
              <button
                onClick={() => setResourcesMenuPath(resourcesMenuOpen ? null : pathname)}
                onBlur={() => setTimeout(() => setResourcesMenuPath(null), 150)}
                className={`flex items-center gap-1 ${linkClass(isResourcesActive)}`}
              >
                Resources
                <svg className={`w-4 h-4 transition-transform ${resourcesMenuOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {resourcesMenuOpen && (
                <div className="absolute top-full right-0 mt-2 w-52 overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-2xl shadow-black/40 z-50">
                  <Link href="/resources" className="block px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-900">All resources</Link>
                  <Link href="/bookmakers" className="block px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-900">Bookmakers</Link>
                  <Link href="/calculator" className="block px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-900">Calculator</Link>
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="max-h-[calc(100dvh-4rem)] space-y-1 overflow-y-auto border-t border-slate-800/50 py-3 md:hidden">
            <div className="px-4">
              <button 
                onClick={() => setTipsMenuPath(tipsMenuOpen ? null : pathname)}
                className={`w-full min-h-[44px] flex items-center justify-between text-base font-medium rounded px-3 py-3 transition-colors ${isTipsActive ? 'text-[var(--brand-green)] font-medium bg-[rgba(87,209,150,0.10)]' : 'text-slate-300 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]'}`}
              >
                <span>Tips</span>
                <svg className={`w-4 h-4 transition-transform ${tipsMenuOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {tipsMenuOpen && (
                <div className="mt-1 ml-4 space-y-1">
                  <Link href="/tennis-tips" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-3 py-2 text-sm rounded transition-colors ${pathname === '/tennis-tips' ? 'text-[var(--brand-green)] font-medium bg-[rgba(87,209,150,0.10)]' : 'text-slate-400 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]'}`}>
                    Tennis Tips
                  </Link>
                  <Link href="/player-props" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-3 py-2 text-sm rounded transition-colors ${pathname === '/player-props' ? 'text-[var(--brand-green)] font-medium bg-[rgba(87,209,150,0.10)]' : 'text-slate-400 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]'}`}>
                    Player Props
                  </Link>
                </div>
              )}
            </div>
            <Link href="/the-edge" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/the-edge" ? "text-[var(--brand-green)] bg-[rgba(87,209,150,0.10)]" : "text-slate-300 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]"}`}>
              The Edge
            </Link>
            <Link href="/penalty-takers" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/penalty-takers" ? "text-[var(--brand-green)] bg-[rgba(87,209,150,0.10)]" : "text-slate-300 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]"}`}>
              Penalty Takers
            </Link>
            <Link href="/fair-odds-lab" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/fair-odds-lab" ? "text-[var(--brand-green)] bg-[rgba(87,209,150,0.10)]" : "text-slate-300 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]"}`}>
              Fair Odds Lab
            </Link>
            <Link href="/track-record" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/track-record" ? "text-[var(--brand-green)] bg-[rgba(87,209,150,0.10)]" : "text-slate-300 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]"}`}>
              Track Record
            </Link>
            {showMonitorLink ? (
              <Link href="/model-monitor" onClick={() => setMobileMenuPath(null)} className={`flex items-center min-h-[44px] px-4 py-3 text-base font-medium rounded transition-colors ${pathname === "/model-monitor" ? "text-[var(--brand-green)] bg-[rgba(87,209,150,0.10)]" : "text-slate-300 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]"}`}>
                Monitor
              </Link>
            ) : null}
            <div className="px-4">
              <button
                onClick={() => setResourcesMenuPath(resourcesMenuOpen ? null : pathname)}
                className={`w-full min-h-[44px] flex items-center justify-between rounded px-3 py-3 text-base font-medium transition-colors ${isResourcesActive ? 'text-[var(--brand-green)] bg-[rgba(87,209,150,0.10)]' : 'text-slate-300 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]'}`}
              >
                <span>Resources</span>
                <svg className={`w-4 h-4 transition-transform ${resourcesMenuOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {resourcesMenuOpen && (
                <div className="mt-1 ml-4 space-y-1">
                  <Link href="/resources" onClick={() => setMobileMenuPath(null)} className={`flex min-h-[44px] items-center rounded px-3 py-2 text-sm transition-colors ${pathname === '/resources' || pathname?.startsWith('/resources/') ? 'text-[var(--brand-green)] font-medium bg-[rgba(87,209,150,0.10)]' : 'text-slate-400 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]'}`}>
                    All resources
                  </Link>
                  <Link href="/bookmakers" onClick={() => setMobileMenuPath(null)} className={`flex min-h-[44px] items-center rounded px-3 py-2 text-sm transition-colors ${pathname === '/bookmakers' ? 'text-[var(--brand-green)] font-medium bg-[rgba(87,209,150,0.10)]' : 'text-slate-400 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]'}`}>
                    Bookmakers
                  </Link>
                  <Link href="/calculator" onClick={() => setMobileMenuPath(null)} className={`flex min-h-[44px] items-center rounded px-3 py-2 text-sm transition-colors ${pathname === '/calculator' ? 'text-[var(--brand-green)] font-medium bg-[rgba(87,209,150,0.10)]' : 'text-slate-400 hover:text-[var(--brand-green)] hover:bg-[rgba(87,209,150,0.10)]'}`}>
                    Calculator
                  </Link>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
