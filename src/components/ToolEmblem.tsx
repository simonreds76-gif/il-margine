import Image from "next/image";
import { useId } from "react";
import "./tool-emblem.css";

export type ToolEmblemName = "price" | "football-price" | "margin" | "tennis" | "football" | "lab" | "penalty" | "kelly" | "returns" | "guide" | "record" | "closing" | "tools";

const artwork: Partial<Record<ToolEmblemName, string>> = {
  margin: "/brand/mind-the-margin-roundel-v1.webp",
  tennis: "/images/tools/tennis-v1.webp",
  football: "/images/tools/football-v1.webp",
  penalty: "/images/tools/penalty-v1.webp",
};

export function emblemForHref(href: string): ToolEmblemName {
  if (href.includes("penalty")) return "penalty";
  if (href.includes("football-atlas")) return "football";
  if (href.includes("return-atlas") || href.includes("clay-season")) return "tennis";
  if (href.includes("bookmakers")) return "margin";
  if (href.includes("calculator/football")) return "football-price";
  if (href.includes("kelly")) return "kelly";
  if (href.includes("closing")) return "closing";
  if (href.includes("track-record")) return "record";
  if (href.includes("fair-odds-lab")) return "lab";
  if (href.includes("tool=returns")) return "returns";
  if (href.includes("tool=margin")) return "price";
  if (href === "/calculator" || href === "/tools") return "tools";
  return "guide";
}

/** Decorative artwork: the adjacent live heading supplies the link's accessible name. */
export default function ToolEmblem({ name, className = "" }: { name: ToolEmblemName; className?: string }) {
  const id = `tool-${useId().replaceAll(":", "")}`;
  const mint = `url(#${id}-mint)`;
  const white = `url(#${id}-white)`;
  const ink = "#102b32";
  const src = artwork[name];
  return <span className={`tool-emblem tool-emblem--${name} ${className}`} aria-hidden="true">
    {src ? <Image src={src} width={320} height={320} alt="" unoptimized /> : <svg viewBox="0 0 120 120" fill="none" focusable="false">
      <defs><linearGradient id={`${id}-mint`} x1="22" y1="10" x2="96" y2="110" gradientUnits="userSpaceOnUse"><stop stopColor="#c3ffe7" /><stop offset=".5" stopColor="#63d8af" /><stop offset="1" stopColor="#218466" /></linearGradient><linearGradient id={`${id}-white`} x1="20" y1="12" x2="105" y2="108" gradientUnits="userSpaceOnUse"><stop stopColor="#fff" /><stop offset="1" stopColor="#a7c3ce" /></linearGradient></defs>
      <g strokeLinecap="round" strokeLinejoin="round">
        {name === "price" && <><rect x="14" y="17" width="88" height="87" rx="15" fill={white} /><rect x="23" y="27" width="70" height="24" rx="6" fill={ink} /><path d="M30 41h22m9-7h24m-24 8h16" stroke="#95ebcc" strokeWidth="4" /><rect x="24" y="62" width="68" height="30" rx="7" fill={mint} /><path d="m51 84 16-15" stroke={ink} strokeWidth="4" /><circle cx="48" cy="70" r="4" fill={ink} /><circle cx="70" cy="84" r="4" fill={ink} /></>}
        {name === "football-price" && <><rect x="10" y="23" width="100" height="75" rx="12" fill={mint} /><rect x="18" y="31" width="84" height="59" rx="6" fill={ink} /><path d="M46 31v59m28-59v59" stroke="#72bfae" strokeWidth="2" /><text x="32" y="69" textAnchor="middle" fontSize="25" fontWeight="700" fill="#f3fff9">1</text><text x="60" y="69" textAnchor="middle" fontSize="23" fontWeight="700" fill="#a4f3d6">X</text><text x="88" y="69" textAnchor="middle" fontSize="25" fontWeight="700" fill="#f3fff9">2</text><path d="M28 105h34m-10-6 10 6-10 6" stroke={white} strokeWidth="4" /></>}
        {name === "lab" && <><path d="M47 13h28m-22 0v34L24 91c-5 8 0 16 9 16h54c9 0 14-8 9-16L69 47V13" stroke={white} strokeWidth="7" /><path d="m43 72-13 22c-2 4 0 7 5 7h49c5 0 7-3 5-7L76 72c-13-8-20 9-33 0Z" fill={mint} /><circle cx="55" cy="89" r="5" fill={ink} /><circle cx="69" cy="81" r="3" fill={ink} /><circle cx="60" cy="60" r="4" fill={mint} /><circle cx="86" cy="33" r="5" fill={mint} /></>}
        {name === "kelly" && <><path d="M60 11 99 27v33c0 23-17 39-39 50C38 99 21 83 21 60V27Z" fill={white} /><path d="m60 22 29 12v26c0 16-11 29-29 39-18-10-29-23-29-39V34Z" fill={ink} /><path d="M43 65h34M43 45h34M43 84h34" stroke="#6b8f94" strokeWidth="4" /><rect x="48" y="37" width="8" height="16" rx="4" fill={mint} /><rect x="64" y="57" width="8" height="16" rx="4" fill={mint} /><rect x="51" y="76" width="8" height="16" rx="4" fill={mint} /></>}
        {name === "returns" && <><rect x="12" y="19" width="96" height="84" rx="12" fill={white} /><rect x="21" y="28" width="78" height="66" rx="6" fill={ink} /><path d="M29 77 42 51 55 59 69 35 81 54 91 41v44H29Z" fill={mint} opacity=".3" /><path d="m29 77 13-17 13 8 14-22 12 18 10-12" stroke={mint} strokeWidth="5" /><path d="M29 84h62" stroke="#76939f" strokeWidth="2" /></>}
        {(name === "guide" || name === "record") && <><path d="M18 17h61l20 20v65H18Z" fill={white} /><path d="M79 17v20h20" fill={mint} /><path d="M32 36h29M32 49h43M32 63h27" stroke={ink} strokeWidth="5" />{name === "record" ? <><circle cx="76" cy="81" r="24" fill={mint} stroke={ink} strokeWidth="3" /><path d="m64 81 8 8 16-18" stroke={ink} strokeWidth="5" /></> : <><path d="M31 91V76m14 15V70m14 21V80" stroke="#278f73" strokeWidth="7" /><circle cx="88" cy="80" r="17" fill={mint} stroke={ink} strokeWidth="3" /><path d="m100 94 9 12" stroke={white} strokeWidth="7" /></>}</>}
        {name === "closing" && <><circle cx="56" cy="60" r="43" fill={white} /><circle cx="56" cy="60" r="33" fill={ink} /><path d="M56 37v25l17 10" stroke={mint} strokeWidth="6" /><path d="m72 95 12-11 10 5 15-19m-15 0h15v15" stroke={mint} strokeWidth="6" /></>}
        {name === "tools" && <><rect x="16" y="12" width="88" height="96" rx="16" fill={white} /><rect x="27" y="24" width="66" height="25" rx="6" fill={ink} /><path d="M37 37h10m8 0h9m8 0h11" stroke="#a4f3d6" strokeWidth="4" /><rect x="27" y="59" width="27" height="33" rx="6" fill={mint} /><path d="M33 75h15m-7-8v16m25-17h20m-20 10h20m-20 10h20" stroke={ink} strokeWidth="4" /></>}
      </g>
    </svg>}
  </span>;
}
