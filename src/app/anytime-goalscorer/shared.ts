export type LeagueKey = "serie-a" | "epl" | "la-liga" | "bundesliga" | "ligue-1";

export type PublicRow = {
  leagueKey: LeagueKey;
  leagueLabel: string;
  leagueShort: string;
  competition: string;
  date: string;
  kickoff: string;
  match: string;
  player: string;
  team: string;
  opponent: string;
  bestBookmaker: string;
  bestOdds: number;
  fairOdds: number;
  modelProb: number;
  ev: number;
  lineupState: string;
  comparedAt: string;
  settled: boolean;
  betOutcome: string;
  settledAt: string;
  pnlUnits: number;
  stakeUnits: number;
  stakeBand: string;
  stakeLabel: string;
  penaltyDependent: boolean;
  penaltyTransfer: boolean;
  positionUpgrade: boolean;
  penaltyDependencyShare: number;
  position: string;
  finishingLuck: number;
  fixtureSwing: number;
};

export type LeagueSource = {
  key: LeagueKey;
  label: string;
  short: string;
  file: string;
  logoPath: string;
  badgeClass: string;
};

export const LEAGUE_SOURCES: LeagueSource[] = [
  {
    key: "serie-a",
    label: "Serie A",
    short: "ITA",
    file: "data/goalscorer/goalscorer-public-signals.csv",
    logoPath: "/league-logos/serie-a.png",
    badgeClass: "border-emerald-500/30 bg-emerald-500/12 text-emerald-300",
  },
  {
    key: "epl",
    label: "Premier League",
    short: "ENG",
    file: "data/goalscorer/epl-public-signals.csv",
    logoPath: "/league-logos/epl.png",
    badgeClass: "border-indigo-500/30 bg-indigo-500/12 text-indigo-200",
  },
  {
    key: "la-liga",
    label: "La Liga",
    short: "ESP",
    file: "data/goalscorer/la-liga-public-signals.csv",
    logoPath: "/league-logos/la-liga.png",
    badgeClass: "border-amber-500/30 bg-amber-500/12 text-amber-200",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    short: "GER",
    file: "data/goalscorer/bundesliga-public-signals.csv",
    logoPath: "/league-logos/bundesliga.png",
    badgeClass: "border-rose-500/30 bg-rose-500/12 text-rose-200",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    short: "FRA",
    file: "data/goalscorer/ligue-1-public-signals.csv",
    logoPath: "/league-logos/ligue-1.png",
    badgeClass: "border-cyan-500/30 bg-cyan-500/12 text-cyan-200",
  },
];

export function formatPct(value: number, digits = 1, withSign = true): string {
  const sign = withSign && value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatUnits(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}u`;
}

export function formatOdds(value: number): string {
  return value > 0 ? value.toFixed(2) : "n/a";
}

export function formatResultDate(value: string): string {
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return value || "";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
  }).format(new Date(stamp));
}

export function formatDateTime(value: string | null): string {
  if (!value) return "n/a";
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return value;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(stamp));
}

export function formatTimeOnly(value: string): string {
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return value || "n/a";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(stamp));
}

export function formatPublishedLabel(value: string): string {
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return "";
  return `Published ${formatTimeOnly(value)}`;
}

export function slugifyAnchor(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

export function getPenaltyTakersHref(row: Pick<PublicRow, "leagueKey" | "team">): string {
  return `/penalty-takers#${row.leagueKey}-${slugifyAnchor(row.team)}`;
}

export function getPnlClass(value: number): string {
  return value >= 0 ? "text-emerald-300" : "text-rose-300";
}

export function getLeagueSource(leagueKey: LeagueKey): LeagueSource | undefined {
  return LEAGUE_SOURCES.find((league) => league.key === leagueKey);
}

export function getLeagueBadgeClass(leagueKey: LeagueKey): string {
  return (
    getLeagueSource(leagueKey)?.badgeClass ??
    "border-slate-700 bg-slate-900 text-slate-300"
  );
}

export function getTodayIsoLondon(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

export function addDaysIso(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const date = new Date(Date.UTC(year || 0, (month || 1) - 1, day || 1));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function kickoffMeta(value: string, todayIso: string, now = Date.now()) {
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) {
    return {
      sortValue: Number.POSITIVE_INFINITY,
      minutesUntil: null as number | null,
      label: value || "TBC",
      tone: "text-neutral-400",
      badge: "TBC",
      badgeClass: "border-white/10 bg-white/[0.04] text-neutral-400",
      dateKey: "",
    };
  }

  const dateKey = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/London",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(stamp));
  const tomorrowIso = addDaysIso(todayIso, 1);
  const timeLabel = formatTimeOnly(value);

  let label = timeLabel;
  if (dateKey === tomorrowIso) {
    label = `Tomorrow ${timeLabel}`;
  } else if (dateKey !== todayIso) {
    label = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/London",
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(new Date(stamp));
  }

  const minutesUntil = Math.round((stamp - now) / 60000);
  if (minutesUntil < 0 && minutesUntil >= -15) {
    return {
      sortValue: stamp,
      minutesUntil,
      label,
      tone: "text-rose-300",
      badge: "Live",
      badgeClass: "border-rose-500/35 bg-rose-500/12 text-rose-200",
      dateKey,
    };
  }
  if (minutesUntil <= 30) {
    return {
      sortValue: stamp,
      minutesUntil,
      label,
      tone: "text-rose-300",
      badge: "Soon",
      badgeClass: "border-rose-500/35 bg-rose-500/12 text-rose-200",
      dateKey,
    };
  }
  if (minutesUntil <= 60) {
    return {
      sortValue: stamp,
      minutesUntil,
      label,
      tone: "text-amber-300",
      badge: "<60m",
      badgeClass: "border-amber-500/35 bg-amber-500/12 text-amber-200",
      dateKey,
    };
  }
  return {
    sortValue: stamp,
    minutesUntil,
    label,
    tone: "text-neutral-200",
    badge: dateKey === todayIso ? "Today" : dateKey === tomorrowIso ? "Tomorrow" : "Upcoming",
    badgeClass: "border-white/10 bg-white/[0.04] text-neutral-300",
    dateKey,
  };
}

export function getStakeTone(row: Pick<PublicRow, "stakeBand">): string {
  if (row.stakeBand === "core") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (row.stakeBand === "standard") return "border-cyan-500/25 bg-cyan-500/10 text-cyan-200";
  return "border-amber-500/25 bg-amber-500/10 text-amber-200";
}

export function getStakeCopy(row: Pick<PublicRow, "stakeBand" | "stakeUnits" | "stakeLabel">): string {
  if (row.stakeBand === "core") return `Highest conviction · ${row.stakeUnits.toFixed(2)}u recommended`;
  if (row.stakeBand === "standard") return `Standard conviction · ${row.stakeUnits.toFixed(2)}u recommended`;
  return `Extended range · ${row.stakeUnits.toFixed(2)}u recommended`;
}

export function lineupBadgeMeta(stateValue: string): { label: string; className: string } {
  const state = stateValue.trim().toLowerCase();
  if (state === "starter" || state === "confirmed_starter") {
    return {
      label: "Confirmed starter",
      className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
    };
  }
  if (state === "expected_starter" || state === "expected") {
    return {
      label: "Expected starter",
      className: "border-amber-500/25 bg-amber-500/10 text-amber-200",
    };
  }
  if (state === "confirmed_not_starting") {
    return {
      label: "Not starting",
      className: "border-rose-500/25 bg-rose-500/10 text-rose-200",
    };
  }
  return {
    label: "Lineup watch",
    className: "border-white/10 bg-white/[0.04] text-neutral-300",
  };
}

export function marketProbability(odds: number): number | null {
  if (odds <= 0) return null;
  return 100 / odds;
}

export function bookmakerLogoPath(bookmaker: string): string | null {
  const normalized = bookmaker.trim().toLowerCase().replace(/\s+/g, "");
  const mapping: Record<string, string> = {
    bet365: "/bookmakers/bet365.png",
    betfair: "/bookmakers/betfair.png",
    paddypower: "/bookmakers/paddypower.png",
    williamhill: "/bookmakers/williamhill.png",
    skybet: "/bookmakers/skybet.png",
    betway: "/bookmakers/betway.svg",
    coral: "/bookmakers/coral.jpeg",
    ladbrokes: "/bookmakers/ladbrokes.png",
    betmgm: "/bookmakers/betmgm.svg",
    unibet: "/bookmakers/unibet.png",
    midnite: "/bookmakers/midnite.png",
    betvictor: "/bookmakers/betvictor.png",
    betfred: "/bookmakers/betfred.png",
    pinnacle: "/bookmakers/pinnacle.png",
    bwin: "/bookmakers/bwin.png",
    "888sport": "/bookmakers/888sport.png",
  };
  return mapping[normalized] ?? null;
}

export function getContextSignals(
  row: Pick<PublicRow, "finishingLuck" | "fixtureSwing">,
): Array<{ label: string; className: string }> {
  const signals: Array<{ label: string; className: string }> = [];
  if (row.finishingLuck <= -0.8) {
    signals.push({
      label: "Finishing running cold",
      className: "border-amber-500/25 bg-amber-500/10 text-amber-200",
    });
  } else if (row.finishingLuck >= 0.8) {
    signals.push({
      label: "Recent finishing above xG",
      className: "border-white/10 bg-white/[0.04] text-neutral-300",
    });
  }

  if (row.fixtureSwing >= 1.1) {
    signals.push({
      label: "Fixture swing in favour",
      className: "border-cyan-500/25 bg-cyan-500/10 text-cyan-200",
    });
  }
  return signals;
}
