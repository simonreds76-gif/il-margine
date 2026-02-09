import Link from "next/link";
import Image from "next/image";
import { LAUNCH_LABEL, SITE_MOTTO } from "@/lib/config";

interface FooterProps {
  className?: string;
}

export default function Footer({ className = "" }: FooterProps) {
  return (
    <footer className={`border-t border-slate-800 py-8 bg-[#0f1117] ${className}`.trim()}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-3">
            <Image src="/favicon.png" alt="Il Margine" width={40} height={40} className="h-8 w-8 object-contain" />
            <div className="flex flex-col gap-0.5">
              <span className="text-xs font-medium text-slate-400">Il Margine: {SITE_MOTTO}</span>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">FREE BETA</span>
                <span className="text-xs text-slate-500">{LAUNCH_LABEL}</span>
              </div>
            </div>
          </Link>
          <div className="flex flex-col items-center md:items-end gap-2">
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <Link href="/contact" className="hover:text-slate-300">Contact</Link>
              <Link href="/disclaimer" className="hover:text-slate-300">Disclaimer</Link>
              <Link href="/privacy-policy" className="hover:text-slate-300">Privacy Policy</Link>
              <Link href="/cookies-policy" className="hover:text-slate-300">Cookies Policy</Link>
              <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="hover:text-slate-300">
                Responsible Gambling
              </a>
            </div>
            <div className="text-xs text-slate-500">Gamble responsibly. 18+ only.</div>
          </div>
        </div>
      </div>
    </footer>
  );
}
