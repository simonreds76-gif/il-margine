"use client";

import Image from "next/image";

/** Site-wide compliance bar: 18+, BeGambleAware, Gamble Responsibly. Below nav, above content. */
export default function ComplianceBar() {
  return (
    <div className="border-b border-slate-800/50 bg-slate-900/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-5 py-2.5 sm:py-3">
          <div title="18+ only. Gambling is for adults." className="shrink-0">
            <Image
              src="/compliance/18plus.svg"
              alt="18+"
              width={32}
              height={32}
              className="h-7 w-7 sm:h-8 sm:w-8 shrink-0"
            />
          </div>
          <a
            href="https://www.begambleaware.org"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center shrink-0 hover:opacity-90 transition-opacity"
            title="BeGambleAware - Advice, tools and support"
          >
            <Image
              src="/compliance/begambleaware.svg"
              alt="BeGambleAware - Advice, tools and support"
              width={167}
              height={40}
              className="h-7 sm:h-8 w-auto shrink-0"
            />
          </a>
          <span className="text-xs text-slate-500 shrink-0">Gamble responsibly</span>
        </div>
      </div>
    </div>
  );
}
