export type BookmakerIdentity =
  | string
  | {
      short_name?: string | null;
      name?: string | null;
    }
  | null
  | undefined;

export interface ResolvedBookmakerLogo {
  key: string;
  displayName: string;
  paths: string[];
}

const LOGO_FILES: Record<string, string[]> = {
  "10bet": ["10bet.png", "10bet.svg"],
  "888sport": ["888sport.svg"],
  bet365: ["bet365.svg", "bet365.png"],
  betfair: ["betfair.png", "betfair.svg"],
  betfred: ["betfred.png", "betfred.svg"],
  betmgm: ["BetMGM UK_idPMHl2t9c_0.png", "betmgm.svg"],
  betvictor: ["betvictor.png", "betvictor.svg"],
  betway: ["betway.svg"],
  boylesports: ["boylesports.png"],
  bwin: ["bwin.png"],
  coral: ["coral.jpeg", "coral.svg"],
  ladbrokes: ["ladbrokes.png", "ladbrokes.svg"],
  midnite: ["midnite.png"],
  paddypower: ["paddypower.png", "paddypower.svg"],
  pinnacle: ["pinnacle.png", "pinnacle.svg"],
  sbk: ["sbk.svg"],
  skybet: ["skybet.png", "skybet.svg"],
  spreadex: ["spreadex.png", "spreadex.jpg", "spreadex.svg"],
  unibet: ["Unibet_idYHeiKVm__1.png", "unibet.png", "unibet.svg"],
  virginbet: ["virginbet.png"],
  williamhill: ["williamhill.png", "williamhill.svg"],
};

const DISPLAY_NAMES: Record<string, string> = {
  "10bet": "10bet",
  "888sport": "888sport",
  bet365: "Bet365",
  betfair: "Betfair",
  betfred: "Betfred",
  betmgm: "BetMGM",
  betvictor: "BetVictor",
  betway: "Betway",
  boylesports: "BoyleSports",
  bwin: "Bwin",
  coral: "Coral",
  ladbrokes: "Ladbrokes",
  midnite: "Midnite",
  paddypower: "Paddy Power",
  pinnacle: "Pinnacle",
  sbk: "SBK",
  skybet: "Sky Bet",
  spreadex: "Spreadex",
  unibet: "Unibet",
  virginbet: "Virgin Bet",
  williamhill: "William Hill",
};

const ALIASES: Record<string, string> = {
  "10": "10bet",
  "10bet": "10bet",
  tenbet: "10bet",
  "888": "888sport",
  "888sport": "888sport",
  bet365: "bet365",
  betfair: "betfair",
  betfred: "betfred",
  bf: "betfred",
  betmgm: "betmgm",
  betmgmuk: "betmgm",
  leovegas: "betmgm",
  betvictor: "betvictor",
  bv: "betvictor",
  betway: "betway",
  boyle: "boylesports",
  boylesport: "boylesports",
  boylesports: "boylesports",
  boy: "boylesports",
  bs: "boylesports",
  bwin: "bwin",
  bw: "bwin",
  coral: "coral",
  cr: "coral",
  lad: "ladbrokes",
  ladbrokes: "ladbrokes",
  lb: "ladbrokes",
  midnite: "midnite",
  midnight: "midnite",
  mn: "midnite",
  paddypower: "paddypower",
  paddy: "paddypower",
  pp: "paddypower",
  pinnacle: "pinnacle",
  pinnaclebet: "pinnacle",
  pn: "pinnacle",
  betsbk: "sbk",
  getsbk: "sbk",
  sbk: "sbk",
  skybet: "skybet",
  sb: "skybet",
  spreadex: "spreadex",
  spx: "spreadex",
  unibet: "unibet",
  ub: "unibet",
  virgin: "virginbet",
  virginbet: "virginbet",
  vb: "virginbet",
  williamhill: "williamhill",
  wh: "williamhill",
};

function normalizeBookmaker(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function publicLogoPath(fileName: string): string {
  return `/bookmakers/${encodeURIComponent(fileName)}`;
}

function resolveKey(value: string | null | undefined): string | null {
  if (!value) return null;
  const normalized = normalizeBookmaker(value);
  return ALIASES[normalized] ?? (LOGO_FILES[normalized] ? normalized : null);
}

export function resolveBookmakerLogo(bookmaker: BookmakerIdentity): ResolvedBookmakerLogo | null {
  if (!bookmaker) return null;

  const rawValues =
    typeof bookmaker === "string"
      ? [bookmaker]
      : [bookmaker.short_name, bookmaker.name];

  const key = rawValues.map(resolveKey).find(Boolean);
  if (!key) return null;

  return {
    key,
    displayName: DISPLAY_NAMES[key] ?? rawValues.find(Boolean) ?? key,
    paths: LOGO_FILES[key].map(publicLogoPath),
  };
}

export function getBookmakerLogoPath(bookmaker: string): string | null {
  return resolveBookmakerLogo(bookmaker)?.paths[0] ?? null;
}
