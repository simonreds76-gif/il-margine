"use client";

import { useState } from "react";

/** Same logo logic as BookmakerLogo. Maps bookmaker id to filename in public/bookmakers/. Omit if no logo file. */
const LOGO_MAP: Record<string, string> = {
  midnite: "midnite",
  betvictor: "betvictor",
  coral: "coral",
  ladbrokes: "ladbrokes",
  betmgm: "betmgm",
  "william-hill": "williamhill",
  betfred: "betfred",
  betway: "betway",
  boylesports: "boylesports",
  spreadex: "spreadex",
};

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
  betway: 1.14,
  boylesports: 0.92,
  spreadex: 0.95,
};

interface BookmakerThumbProps {
  id: string;
  name: string;
  size?: keyof typeof SIZE_CLASSES;
  className?: string;
}

export default function BookmakerThumb({ id, name, size = "md", className = "" }: BookmakerThumbProps) {
  const logoBase = LOGO_MAP[id];
  const [srcIndex, setSrcIndex] = useState(0);
  const [failed, setFailed] = useState(false);

  const logoPaths = logoBase ? [
    `/bookmakers/${logoBase}.svg`,
    `/bookmakers/${logoBase}.png`,
    `/bookmakers/${logoBase}.jpeg`,
    `/bookmakers/${logoBase}.jpg`,
  ] : [];

  const currentSrc = logoPaths[srcIndex] ?? null;
  const showImage = currentSrc && !failed;
  const scale = LOGO_SCALE[logoBase] ?? 1;

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
        <div className={`${FRAME_SIZE_CLASSES[size]} relative overflow-hidden rounded-lg flex items-center justify-center bg-slate-800/50`}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={currentSrc}
            alt={name}
            className={`${SIZE_CLASSES[size]} object-contain`}
            style={{ transform: `scale(${scale})` }}
            onError={handleError}
          />
        </div>
      ) : (
        <div className={`${SIZE_CLASSES[size]} rounded-lg bg-slate-700 flex items-center justify-center`}>
          <span className="text-sm font-semibold text-slate-400">{name.charAt(0)}</span>
        </div>
      )}
    </div>
  );
}
