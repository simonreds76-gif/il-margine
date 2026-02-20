"use client";

import Link from "next/link";
import Image from "next/image";

/** Entain/SG compliance: visible 18+ and BeGambleAware logos */
export default function ComplianceBadges({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-wrap items-center gap-4 ${className}`}>
      <div className="flex items-center gap-2" title="18+ only. Gambling is for adults.">
        <Image
          src="/compliance/18plus.svg"
          alt="18+"
          width={40}
          height={40}
          className="h-10 w-10 shrink-0"
        />
        <span className="text-xs text-slate-400">18+ only</span>
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
          width={160}
          height={38}
          className="h-9 w-auto min-w-[120px]"
        />
      </a>
    </div>
  );
}
