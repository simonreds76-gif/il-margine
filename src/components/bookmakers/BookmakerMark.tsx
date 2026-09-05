import Image from "next/image";

const CODES: Record<string, string> = {
  bet365: "b3", williamhill: "wh", unibet: "un", betfred: "fr",
  ladbrokes: "ld", betvictor: "vc", betmgm: "kn", betmgmuk: "kn",
  boylesports: "by", "10bet": "oe", starsports: "s6", pricedup: "pup",
  betgoodwin: "g5", quinnbet: "qn", betway: "wa", coral: "ce",
  betahoy: "bah", bettom: "btt", ivybet: "ivb", skybet: "sk",
  paddypower: "pp", akbets: "akb",
};

export default function BookmakerMark({ name }: { name: string }) {
  const key = name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const src = key === "virginbet" ? "/bookmakers/virginbet.png"
    : CODES[key] ? `/bookmakers/comparison/${CODES[key]}.svg` : null;
  const needsLightBackground = ["vc", "oe", "pup"].includes(CODES[key]);
  return <span className={`flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/10 ${needsLightBackground ? "bg-slate-100 p-1" : "bg-slate-800"}`} aria-hidden="true">
    {src ? <Image src={src} alt="" width={36} height={36} unoptimized className="h-9 w-9 object-contain" />
      : <span className="text-xs text-slate-300">{name.slice(0, 2)}</span>}
  </span>;
}
