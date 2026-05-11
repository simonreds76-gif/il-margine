type BookmakerLogoProps = {
  name: string;
  size?: "sm" | "md";
  className?: string;
};

const BOOKMAKER_LOGOS: Array<[RegExp, string]> = [
  [/bet\s*365/i, "/bookmakers/bet365.png"],
  [/pinnacle/i, "/bookmakers/pinnacle.png"],
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
];

export function bookmakerLogoPath(name: string) {
  return BOOKMAKER_LOGOS.find(([pattern]) => pattern.test(name))?.[1] ?? "";
}

export function BookmakerLogo({ name, size = "sm", className = "" }: BookmakerLogoProps) {
  const src = bookmakerLogoPath(name);
  if (!src) return null;

  const sizeClass = size === "md" ? "h-8 min-w-14 px-2.5" : "h-6 min-w-11 px-2";

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-md border border-slate-700/60 bg-slate-950/70 ${sizeClass} ${className}`}
      title={name}
    >
      <img
        src={src}
        alt={`${name} logo`}
        className="max-h-[70%] max-w-[72px] object-contain"
        loading="lazy"
      />
    </span>
  );
}
