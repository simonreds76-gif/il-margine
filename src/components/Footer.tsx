import Link from "next/link";
import Image from "next/image";
import { SITE_MOTTO } from "@/lib/config";

interface FooterProps {
  className?: string;
}

export default function Footer({ className = "" }: FooterProps) {
  return (
    <footer className={`border-t border-slate-800/70 bg-[#0b0e13] py-10 ${className}`.trim()}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-5">
          <Link
            href="/"
            aria-label={`Il Margine: ${SITE_MOTTO}`}
            className="group -ml-2 flex items-center transition hover:brightness-110"
          >
            <Image
              src="/brand/il-margine-tube-footer-compact.png"
              alt="Il Margine - Mind the Margin"
              width={360}
              height={90}
              className="h-14 w-auto max-w-[min(86vw,25rem)] object-contain opacity-95 drop-shadow-[0_0_22px_rgba(87,209,150,0.12)] sm:h-16"
            />
          </Link>
          <div className="flex flex-col items-center md:items-end gap-3">
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-slate-400">
              <Link href="/faq" className="hover:text-white">Frequently Asked Questions</Link>
              <Link href="/contact" className="hover:text-white">Contact</Link>
              <Link href="/disclaimer" className="hover:text-white">Disclaimer</Link>
              <Link href="/privacy-policy" className="hover:text-white">Privacy Policy</Link>
              <Link href="/cookies-policy" className="hover:text-white">Cookies Policy</Link>
            </div>
            <div className="text-xs text-slate-400">Gamble responsibly. 18+ only.</div>
          </div>
        </div>
      </div>
    </footer>
  );
}
