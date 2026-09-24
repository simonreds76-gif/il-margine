import { useId } from "react";

export type EditorialIconName = "guide" | "method" | "markets" | "compare" | "bankroll" | "analysis" | "about" | "responsible" | "football" | "tools";

/** Decorative section emblems. The adjacent text carries the accessible name. */
export default function EditorialIcon({ name, className = "h-7 w-7" }: { name: EditorialIconName; className?: string }) {
  const id = `editorial-${useId().replaceAll(":", "")}`;
  const body = `url(#${id}-body)`;
  const mint = `url(#${id}-mint)`;
  const ink = "#17252b";
  return <svg viewBox="0 0 72 72" fill="none" aria-hidden="true" focusable="false" className={`shrink-0 ${className}`}>
    <defs>
      <linearGradient id={`${id}-body`} x1="10" y1="5" x2="58" y2="65" gradientUnits="userSpaceOnUse"><stop stopColor="#fff" /><stop offset="1" stopColor="#c1d1d9" /></linearGradient>
      <linearGradient id={`${id}-mint`} x1="14" y1="12" x2="59" y2="64" gradientUnits="userSpaceOnUse"><stop stopColor="#a4f3d6" /><stop offset="1" stopColor="#5fcda9" /></linearGradient>
    </defs>
    <g strokeLinecap="round" strokeLinejoin="round">
      {name === "football" && <><rect x="6" y="12" width="60" height="48" rx="8" fill={mint} /><rect x="13" y="19" width="46" height="34" rx="2" stroke={ink} strokeWidth="3" /><path d="M36 19v34M13 29h9v14h-9m46-14h-9v14h9" stroke={ink} strokeWidth="3" /><circle cx="36" cy="36" r="7" fill={body} stroke={ink} strokeWidth="3" /></>}
      {name === "tools" && <><rect x="8" y="8" width="24" height="24" rx="5" fill={body} /><rect x="40" y="8" width="24" height="24" rx="5" fill={mint} /><rect x="8" y="40" width="24" height="24" rx="5" fill={mint} /><rect x="40" y="40" width="24" height="24" rx="5" fill={body} /><path d="M15 20h10m-5-5v10m21-5h12M15 48h10m-10 8h10m22-9 10 10m0-10-10 10" stroke={ink} strokeWidth="3" /></>}
      {name === "guide" && <><path d="M7 13c11-3 20 0 29 7 9-7 18-10 29-7v44c-11-3-20 0-29 7-9-7-18-10-29-7Z" fill={body} /><path d="M36 20v44" stroke={ink} strokeWidth="4" /><path d="M45 24h12v23l-6-5-6 5Z" fill={mint} /><path d="m15 26 12 4m-12 8 12 4m-12 8 12 4" stroke={ink} strokeWidth="3" /></>}
      {name === "method" && <><circle cx="36" cy="36" r="29" fill={body} /><circle cx="36" cy="36" r="21" fill={ink} /><path d="m48 22-7 20-17 8 7-20Z" fill={mint} /><path d="m31 30 10 12-17 8Z" fill={body} /><circle cx="36" cy="36" r="3" fill={ink} /></>}
      {name === "markets" && <><rect x="8" y="9" width="56" height="54" rx="9" fill={body} /><path d="M8 27h56M36 27v36" stroke={ink} strokeWidth="4" /><rect x="15" y="15" width="42" height="6" rx="3" fill={ink} /><rect x="15" y="35" width="14" height="20" rx="3" fill={mint} /><path d="M44 38h12m-12 12h12" stroke={ink} strokeWidth="4" /></>}
      {name === "compare" && <><rect x="8" y="12" width="56" height="48" rx="9" fill={body} /><path d="M18 24h36M18 36h36M18 48h36" stroke={ink} strokeWidth="5" /><rect x="35" y="17" width="10" height="14" rx="3" fill={mint} stroke={ink} strokeWidth="2" /><rect x="23" y="29" width="10" height="14" rx="3" fill={mint} stroke={ink} strokeWidth="2" /><rect x="43" y="41" width="10" height="14" rx="3" fill={mint} stroke={ink} strokeWidth="2" /></>}
      {name === "bankroll" && <><rect x="9" y="10" width="54" height="53" rx="9" fill={body} /><rect x="17" y="18" width="38" height="13" rx="3" fill={ink} /><rect x="17" y="39" width="14" height="16" rx="3" fill={mint} /><path d="M40 42h14m-14 10h14" stroke={ink} strokeWidth="4" /></>}
      {name === "analysis" && <><path d="M7 48a29 29 0 0 1 58 0v11H7Z" fill={body} /><path d="M16 47a20 20 0 0 1 40 0" stroke={ink} strokeWidth="6" /><path d="m36 47 13-21" stroke={mint} strokeWidth="7" /><circle cx="36" cy="47" r="6" fill={ink} /><path d="M24 59h24" stroke={ink} strokeWidth="4" /></>}
      {name === "about" && <><circle cx="36" cy="36" r="29" fill={body} /><circle cx="36" cy="23" r="5" fill={mint} stroke={ink} strokeWidth="2" /><path d="M31 34h7v18m-8 0h15" stroke={ink} strokeWidth="5" /></>}
      {name === "responsible" && <><path d="m36 6 25 10v20c0 14-11 23-25 30C22 59 11 50 11 36V16Z" fill={body} /><path d="m36 15 17 7v15c0 9-7 16-17 22-10-6-17-13-17-22V22Z" fill={mint} /><path d="M31 29v16m10-16v16" stroke={ink} strokeWidth="5" /></>}
    </g>
  </svg>;
}
