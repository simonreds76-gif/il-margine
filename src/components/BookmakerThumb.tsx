"use client";

import { useState } from "react";
import Image from "next/image";

/** Same logo logic as BookmakerLogo. Maps bookmaker id to filename in public/bookmakers/. Omit if no logo file. */
const LOGO_MAP: Record<string, string> = {
  betvictor: "betvictor",
  coral: "coral",
  ladbrokes: "ladbrokes",
  betmgm: "betmgm",
  "william-hill": "williamhill",
  betfred: "betfred",
};

const LOGO_SCALE: Record<string, number> = {
  ladbrokes: 0.85,
};

const SIZE_CLASSES = {
  xs: "w-7 h-7",
  sm: "w-8 h-8",
  md: "w-10 h-10",
  lg: "w-12 h-12",
} as const;

interface BookmakerThumbProps {
  id: string;
  name: string;
  size?: keyof typeof SIZE_CLASSES;
  className?: string;
}

export default function BookmakerThumb({ id, name, size = "md", className = "" }: BookmakerThumbProps) {
  const logoBase = LOGO_MAP[id];
  const [failed, setFailed] = useState(false);

  const logoPaths = logoBase ? [
    `/bookmakers/${logoBase}.svg`,
    `/bookmakers/${logoBase}.png`,
    `/bookmakers/${logoBase}.jpg`,
  ] : [];

  const scale = LOGO_SCALE[logoBase ?? ""] ?? 1;
  const showImage = logoPaths.length > 0 && !failed;

  return (
    <div className={`flex items-center justify-center flex-shrink-0 ${className}`}>
      {showImage ? (
        <div className={`${SIZE_CLASSES[size]} min-w-[1.5rem] min-h-[1.5rem] relative overflow-hidden rounded-lg`}>
          <div className="absolute inset-0" style={{ transform: `scale(${scale})` }}>
            <Image
              src={logoPaths[0]}
              alt={name}
              fill
              sizes="48px"
              className="object-contain"
              unoptimized
              onError={() => setFailed(true)}
            />
          </div>
        </div>
      ) : (
        <div className={`${SIZE_CLASSES[size]} rounded-lg bg-slate-700 flex items-center justify-center`}>
          <span className="text-sm font-semibold text-slate-400">{name.charAt(0)}</span>
        </div>
      )}
    </div>
  );
}
