import Link from "next/link";
import Image from "next/image";
import { BRAND } from "@/lib/brand";
import ComplianceBar from "@/components/ComplianceBar";

interface FooterProps {
  className?: string;
}

export default function Footer({ className = "" }: FooterProps) {
  return (
    <footer className={`border-t border-slate-800/70 bg-[#0b0e13] py-12 ${className}`.trim()}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-8 lg:gap-12">
          <Link
            prefetch={false}
            href="/"
            aria-label="Il Margine home"
            className="group flex w-full max-w-[400px] shrink-0 items-center rounded-xl transition hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-300 lg:w-[400px]"
          >
            <Image
              src={BRAND.full}
              alt="Il Margine — Independent betting analysis"
              width={900}
              height={386}
              unoptimized
              className="h-auto w-full rounded-lg object-contain"
            />
          </Link>
          <div className="flex flex-col items-center lg:items-end gap-4">
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-slate-400">
              <Link prefetch={false} href="/faq" className="hover:text-white">Frequently Asked Questions</Link>
              <Link prefetch={false} href="/contact" className="hover:text-white">Contact</Link>
              <Link prefetch={false} href="/disclaimer" className="hover:text-white">Disclaimer</Link>
              <Link prefetch={false} href="/privacy-policy" className="hover:text-white">Privacy Policy</Link>
              <Link prefetch={false} href="/cookies-policy" className="hover:text-white">Cookies Policy</Link>
            </div>
            <div className="flex flex-wrap justify-center gap-4 text-xs text-slate-300"><Link prefetch={false} href="/the-edge">Our methodology</Link><Link prefetch={false} href="/track-record">Track record</Link><Link prefetch={false} href="/resources">Resources</Link></div>
            <ComplianceBar />
          </div>
        </div>
      </div>
    </footer>
  );
}
