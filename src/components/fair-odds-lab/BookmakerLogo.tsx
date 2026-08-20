type BookmakerLogoProps = {
  name: string;
  size?: "xs" | "sm" | "md";
  className?: string;
};

const BOOKMAKER_LOGOS: Array<[RegExp, string]> = [
  [/10\s*bet/i, "/bookmakers/10bet.png"],
  [/ten\s*bet/i, "/bookmakers/10bet.png"],
  [/bet\s*365/i, "/bookmakers/bet365.svg"],
  [/pinnacle/i, "/bookmakers/pinnacle.png"],
  [/bet\s*sbk/i, "/bookmakers/sbk.svg"],
  [/\bsbk\b/i, "/bookmakers/sbk.svg"],
  [/betfair/i, "/bookmakers/betfair.png"],
  [/bet\s*mgm/i, "/bookmakers/BetMGM UK_idPMHl2t9c_0.png"],
  [/paddy\s*power/i, "/bookmakers/paddypower.png"],
  [/william\s*hill/i, "/bookmakers/williamhill.png"],
  [/sky\s*bet/i, "/bookmakers/skybet.png"],
  [/betway/i, "/bookmakers/betway.svg"],
  [/unibet/i, "/bookmakers/unibet.png"],
  [/betfred/i, "/bookmakers/betfred.png"],
  [/betvictor/i, "/bookmakers/betvictor.png"],
  [/ladbrokes/i, "/bookmakers/ladbrokes.png"],
  [/coral/i, "/bookmakers/coral.jpeg"],
  [/888/i, "/bookmakers/888sport.svg"],
  [/spreadex/i, "/bookmakers/spreadex.jpg"],
  [/virgin\s*bet/i, "/bookmakers/virginbet.png"],
  [/virginbet/i, "/bookmakers/virginbet.png"],
];

export function bookmakerLogoPath(name: string) {
  return BOOKMAKER_LOGOS.find(([pattern]) => pattern.test(name))?.[1] ?? "";
}

export function BookmakerLogo({ name, size = "sm", className = "" }: BookmakerLogoProps) {
  const src = bookmakerLogoPath(name);
  if (!src) return null;

  const isBet365 = /bet\s*365/i.test(name);
  const sizeClass =
    size === "md"
      ? "h-8 min-w-16 px-3"
      : size === "xs"
        ? "h-5 min-w-0 max-w-[74px] px-1.5"
        : "h-6 min-w-12 px-2.5";
  const shrinkClass = size === "xs" ? "shrink min-w-0" : "shrink-0";
  const imageClass = size === "xs" ? "max-h-[68%] max-w-[58px]" : "max-h-[70%] max-w-[72px]";
  const brandClass = isBet365
    ? "border-emerald-400/25 bg-[#071b12] shadow-[0_0_18px_rgba(16,185,129,0.12)]"
    : "border-slate-700/60 bg-slate-950/70";

  return (
    <span
      className={`inline-flex ${shrinkClass} items-center justify-center overflow-hidden rounded-md border ${brandClass} ${sizeClass} ${className}`}
      title={name}
    >
      <img
        src={src}
        alt={`${name} logo`}
        className={`${imageClass} object-contain`}
        loading="lazy"
      />
    </span>
  );
}
