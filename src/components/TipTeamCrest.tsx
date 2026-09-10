"use client";

import Image from "next/image";
import { useState } from "react";

export default function TipTeamCrest({ team, src }: { team: string; src: string | null }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const initials = team.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase();
  return (
    <span aria-hidden="true" className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl border border-white/20 bg-white/95 p-3 shadow-lg sm:h-24 sm:w-24">
      {src && src !== failedSrc ? (
        <Image src={src} alt="" width={72} height={72} unoptimized loading="eager" className="h-full w-full object-contain" onError={() => setFailedSrc(src)} />
      ) : (
        <span className="text-2xl font-black text-slate-700">{initials}</span>
      )}
    </span>
  );
}
