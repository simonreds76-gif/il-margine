import Image from "next/image";

const CODES: Record<string, string> = {
  bet365: "b3", williamhill: "wh", unibet: "un", betfred: "fr",
  ladbrokes: "ld", betvictor: "vc", betmgm: "kn", betmgmuk: "kn",
  boylesports: "by", "10bet": "oe", starsports: "s6", pricedup: "pup",
  betgoodwin: "g5", quinnbet: "qn", betway: "wa", coral: "ce",
  betahoy: "bah", bettom: "btt", ivybet: "ivb", skybet: "sk",
  paddypower: "pp", akbets: "akb",
};

// These comparison marks have transparent backgrounds. Preserve their original
// artwork and restore the brand tile behind it, rather than tinting the logo.
const BRAND_TILES: Record<string, string> = {
  bet365: "#007b5b", paddypower: "#004833", ladbrokes: "#ed1c24",
  coral: "#0054a6", williamhill: "#00143c", skybet: "#003b7a",
  betmgm: "#111111", betmgmuk: "#111111", betfred: "#003b7a",
  unibet: "#111111", betway: "#111111", boylesports: "#003b7a",
  betvictor: "#ffffff", "10bet": "#ffffff", pricedup: "#ffffff",
  bwin: "#ffffff", akbets: "#101010", betahoy: "#004c84",
  betgoodwin: "#102444", quinnbet: "#006c43", starsports: "#123e6d",
};

export default function BookmakerMark({ name }: { name: string }) {
  const key = name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const src = key === "bwin" ? "/bookmakers/bwin.png" : key === "virginbet" ? "/bookmakers/virginbet.png"
    : CODES[key] ? `/bookmakers/comparison/${CODES[key]}.svg` : null;
  const needsLightBackground = ["vc", "oe", "pup"].includes(CODES[key]);
  return <span className={`bookmaker-brand-mark flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/15 shadow-[0_3px_10px_rgba(0,0,0,.18)] ${needsLightBackground ? "p-0.5" : ""}`} style={{backgroundColor: BRAND_TILES[key] ?? "#14212b"}} aria-hidden="true">
    {src ? <Image src={src} alt="" width={40} height={40} unoptimized className="h-10 w-10 object-contain" />
      : <span className="text-xs text-slate-300">{name.slice(0, 2)}</span>}
  </span>;
}
