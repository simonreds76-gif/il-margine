"use client";

import Link from "next/link";
import Image from "next/image";

/** Site-wide compliance bar: 18+, BeGambleAware, Gamble Responsibly. Below nav, above content. */
export default function ComplianceBar() {
  return (
    <div className="border-b border-slate-800/50 bg-slate-900/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 py-2.5">
          <div title="18+ only. Gambling is for adults.">
            <Image
              src="/compliance/18plus.svg"
              alt="18+"
              width={28}
              height={28}
              className="h-7 w-7 shrink-0"
            />
          </div>
          <a
            href="https://www.begambleaware.org"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 hover:opacity-90 transition-opacity"
            title="BeGambleAware - Advice, tools and support"
          >
            <Image
              src="/compliance/begambleaware.svg"
              alt="BeGambleAware - Advice, tools and support"
              width={120}
              height={28}
              className="h-6 w-auto min-w-[90px]"
            />
          </a>
          <span className="text-xs text-slate-500">Gamble responsibly</span>
        </div>
      </div>
    </div>
  );
}
