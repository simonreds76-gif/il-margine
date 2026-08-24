"use client";

import { useState } from "react";
import { resolveBookmakerLogo } from "@/lib/bookmaker-logos";

const SIZE_CLASSES = {
  xs: "w-7 h-7",
  sm: "w-8 h-8",
  md: "w-10 h-10",
  lg: "w-12 h-12",
} as const;

const FRAME_SIZE_CLASSES = {
  xs: "w-12 h-7",
  sm: "w-16 h-8",
  md: "w-20 h-10",
  lg: "w-24 h-12",
} as const;

const LOGO_SCALE: Record<string, number> = {
  "10bet": 1,
  ballybet: 1.08,
  betway: 1.14,
  boylesports: 0.92,
  spreadex: 0.95,
  sbk: 1,
  virginbet: 1.75,
};

const FRAME_CLASSES: Record<string, string> = {
  ballybet: "border border-red-300/70 bg-[#c8102e] px-1.5 py-1",
  sbk: "border border-slate-200/90 bg-white px-2 py-1",
};

interface BookmakerThumbProps {
  id: string;
  name: string;
  size?: keyof typeof SIZE_CLASSES;
  className?: string;
}

export default function BookmakerThumb({ id, name, size = "md", className = "" }: BookmakerThumbProps) {
  const resolvedLogo = resolveBookmakerLogo({ short_name: id, name });
  const [srcIndex, setSrcIndex] = useState(0);
  const [failed, setFailed] = useState(false);

  const logoPaths = resolvedLogo?.paths ?? [];
  const currentSrc = logoPaths[srcIndex] ?? null;
  const showImage = currentSrc && !failed;
  const scale = LOGO_SCALE[resolvedLogo?.key ?? ""] ?? 1;
  const frameClass = FRAME_CLASSES[resolvedLogo?.key ?? ""] ?? "bg-slate-800/50";
  const displayName = resolvedLogo?.displayName ?? name;

  const handleError = () => {
    if (srcIndex < logoPaths.length - 1) {
      setSrcIndex((i) => i + 1);
    } else {
      setFailed(true);
    }
  };

  return (
    <div className={`flex items-center justify-center flex-shrink-0 ${className}`}>
      {showImage ? (
        <div className={`${FRAME_SIZE_CLASSES[size]} relative overflow-hidden rounded-lg flex items-center justify-center ${frameClass}`}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={currentSrc}
            alt={displayName}
            className={`${SIZE_CLASSES[size]} object-contain`}
            style={{ transform: `scale(${scale})` }}
            onError={handleError}
          />
        </div>
      ) : (
        <div className={`${SIZE_CLASSES[size]} rounded-lg bg-slate-700 flex items-center justify-center`}>
          <span className="text-sm font-semibold text-slate-400">{displayName.charAt(0)}</span>
        </div>
      )}
    </div>
  );
}
