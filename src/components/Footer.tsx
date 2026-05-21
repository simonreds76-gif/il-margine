import Link from "next/link";
import Image from "next/image";
import { SITE_MOTTO } from "@/lib/config";

interface FooterProps {
  className?: string;
}

export default function Footer({ className = "" }: FooterProps) {
  return (
    <footer className={`border-t border-slate-800 py-8 bg-[#0f1117] ${className}`.trim()}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-3 rounded-2xl border border-[color:rgba(87,209,150,0.12)] bg-slate-950/45 px-3 py-2 transition hover:border-[color:rgba(87,209,150,0.28)]">
            <Image src="/logo.png" alt="Il Margine" width={210} height={64} className="h-9 w-auto object-contain" />
            <div className="hidden h-8 w-px bg-slate-800 sm:block" />
            <div className="hidden flex-col gap-0.5 sm:flex">
              <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--brand-green)]">
                {SITE_MOTTO}
              </span>
              <span className="text-[11px] text-slate-500">Data-led football and tennis edges.</span>
            </div>
          </Link>
          <div className="flex flex-col items-center md:items-end gap-3">
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <Link href="/faq" className="hover:text-slate-300">Frequently Asked Questions</Link>
              <Link href="/contact" className="hover:text-slate-300">Contact</Link>
              <Link href="/disclaimer" className="hover:text-slate-300">Disclaimer</Link>
              <Link href="/privacy-policy" className="hover:text-slate-300">Privacy Policy</Link>
              <Link href="/cookies-policy" className="hover:text-slate-300">Cookies Policy</Link>
            </div>
            <div className="text-xs text-slate-500">Gamble responsibly. 18+ only.</div>
          </div>
        </div>
      </div>
    </footer>
  );
}
