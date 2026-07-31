"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import type { Bet } from "@/lib/supabase";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import PnL from "@/components/PnL";
import ResultBadge from "@/components/ResultBadge";
import { getDisplayBetCategory } from "@/lib/bet-category";
import { formatMatchDate, formatOdds, formatStake } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";
import teamLogoManifest from "../../data/goalscorer/team-logo-map.json";

type Mode = "pending" | "settled";

type TeamEntry = {
  team_key?: string;
  fotmob_name?: string;
  fotmob_short_name?: string;
  logo_path?: string;
};

type LeagueEntry = {
  teams?: Record<string, TeamEntry>;
};

type LogoRow = {
  category: string;
  leagueKey: string;
  logoPath: string;
  aliases: string[];
};

const CATEGORY_TO_LOGO_DIR: Record<string, string> = {
  worldcup: "world-cup",
  pl: "epl",
  seriea: "serie-a",
  laliga: "la-liga",
  bundesliga: "bundesliga",
  ligue1: "ligue-1",
};

const MANIFEST_LEAGUE_TO_CATEGORY: Record<string, string> = {
  epl: "pl",
  "serie-a": "seriea",
  "la-liga": "laliga",
  bundesliga: "bundesliga",
  "ligue-1": "ligue1",
};

const CATEGORY_TO_MANIFEST_LEAGUE = Object.fromEntries(
  Object.entries(MANIFEST_LEAGUE_TO_CATEGORY).map(([league, category]) => [category, league]),
) as Record<string, string>;

const TEAM_LOGO_ALIASES: Record<string, string> = {
  "cape-verde": "cabo-verde",
  "ivory-coast": "cote-d-ivoire",
  "iran": "ir-iran",
  "south-korea": "korea-republic",
  "republic-of-korea": "korea-republic",
  "dr-congo": "congo-dr",
  "democratic-republic-of-congo": "congo-dr",
  "turkey": "turkiye",
  "united-states": "usa",
  "united-states-of-america": "usa",
  "man-city": "manchester-city",
  "man-utd": "manchester-united",
  "man-united": "manchester-united",
  "newcastle": "newcastle-united",
  "nottingham": "nottingham-forest",
  "spurs": "tottenham",
  "tottenham-hotspur": "tottenham",
  "west-ham-united": "west-ham",
  "wolves": "wolves",
  "brighton-and-hove-albion": "brighton",
  "inter-milan": "inter",
  "ac-milan": "milan",
  "psg": "paris-saint-germain",
  "rb-leipzig": "rasenballsport-leipzig",
  "borussia-monchengladbach": "borussia-m-gladbach",
};

const WORLD_CUP_TEAM_KEYS = new Set([
  "algeria",
  "argentina",
  "australia",
  "austria",
  "belgium",
  "bosnia-and-herzegovina",
  "brazil",
  "cabo-verde",
  "canada",
  "colombia",
  "congo-dr",
  "cote-d-ivoire",
  "croatia",
  "curacao",
  "czechia",
  "ecuador",
  "egypt",
  "england",
  "france",
  "germany",
  "ghana",
  "haiti",
  "ir-iran",
  "iraq",
  "japan",
  "jordan",
  "korea-republic",
  "mexico",
  "morocco",
  "netherlands",
  "new-zealand",
  "norway",
  "panama",
  "paraguay",
  "portugal",
  "qatar",
  "saudi-arabia",
  "scotland",
  "senegal",
  "south-africa",
  "spain",
  "sweden",
  "switzerland",
  "tunisia",
  "turkiye",
  "uruguay",
  "usa",
  "uzbekistan",
]);

function normalizeText(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function normalizeTeamKey(value: string): string {
  const key = normalizeText(value).replace(/\s+/g, "-");
  return TEAM_LOGO_ALIASES[key] ?? key;
}

const MANIFEST_LOGOS: LogoRow[] = (() => {
  const leagues = (teamLogoManifest as { leagues?: Record<string, LeagueEntry> }).leagues ?? {};
  const rows: LogoRow[] = [];

  for (const [leagueKey, league] of Object.entries(leagues)) {
    const category = MANIFEST_LEAGUE_TO_CATEGORY[leagueKey];
    if (!category) continue;

    for (const [displayName, team] of Object.entries(league.teams ?? {})) {
      if (!team.logo_path) continue;
      const aliases = [displayName, team.team_key, team.fotmob_name, team.fotmob_short_name]
        .filter(Boolean)
        .map((value) => normalizeText(value as string))
        .filter((value, index, all) => value.length >= 2 && all.indexOf(value) === index);
      rows.push({ category, leagueKey, logoPath: team.logo_path, aliases });
    }
  }

  return rows.sort((a, b) => Math.max(...b.aliases.map((alias) => alias.length)) - Math.max(...a.aliases.map((alias) => alias.length)));
})();

function teamLogoPathFromCategory(team: string, category: string): string | null {
  const folder = CATEGORY_TO_LOGO_DIR[category];
  if (!folder) return null;
  return `/team-logos/${folder}/${normalizeTeamKey(team)}.png`;
}

function worldCupTeamLogoPath(team: string): string | null {
  const key = normalizeTeamKey(team);
  return WORLD_CUP_TEAM_KEYS.has(key) ? `/team-logos/world-cup/${key}.png` : null;
}

function resolveManifestLogoPath(team: string, category: string): string | null {
  const normalized = normalizeText(team);
  if (!normalized) return null;

  const preferredLeague = CATEGORY_TO_MANIFEST_LEAGUE[category];
  const isPreferred = (row: LogoRow) => !preferredLeague || row.leagueKey === preferredLeague || row.category === category;
  const exact = MANIFEST_LOGOS.find((row) => isPreferred(row) && row.aliases.includes(normalized));
  if (exact) return exact.logoPath;

  const loose = MANIFEST_LOGOS.find(
    (row) =>
      isPreferred(row) &&
      row.aliases.some((alias) => alias.length >= 5 && (normalized.includes(alias) || alias.includes(normalized))),
  );
  if (loose) return loose.logoPath;

  const anyExact = MANIFEST_LOGOS.find((row) => row.aliases.includes(normalized));
  if (anyExact) return anyExact.logoPath;

  const anyLoose = MANIFEST_LOGOS.find((row) =>
    row.aliases.some((alias) => alias.length >= 5 && (normalized.includes(alias) || alias.includes(normalized))),
  );
  return anyLoose?.logoPath ?? null;
}

function resolveTeamLogoPath(team: string | null, category: string): string | null {
  if (!team) return null;
  if (category === "worldcup") return worldCupTeamLogoPath(team) ?? teamLogoPathFromCategory(team, category);
  return (
    resolveManifestLogoPath(team, category) ??
    teamLogoPathFromCategory(team, category) ??
    worldCupTeamLogoPath(team) ??
    resolveManifestLogoPath(team, "all")
  );
}

function initials(team: string | null, category: string): string {
  if (!team) return category === "worldcup" ? "WC" : "FC";
  const parts = team
    .replace(/[.'-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return category === "worldcup" ? "WC" : "FC";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

type MatchGroup = {
  key: string;
  event: string;
  category: string;
  home: string | null;
  away: string | null;
  matchDate: string | null;
  bets: Bet[];
  totalStake: number;
  netProfit: number;
  won: number;
  lost: number;
  voided: number;
  settledCount: number;
};

function parseFixture(event: string): { home: string; away: string } | null {
  if (!event) return null;
  const parts = event.split(/\s+(?:vs?\.?|v|@|-|\u2013|\u2014)\s+/i);
  if (parts.length >= 2 && parts[0].trim() && parts[1].trim()) {
    return { home: parts[0].trim(), away: parts.slice(1).join(" ").trim() };
  }
  return null;
}

function formatNetUnits(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function startOfToday(): number {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return now.getTime();
}

function isTodayOrFuture(matchDate: string | null): boolean {
  if (!matchDate) return false;
  const date = new Date(`${matchDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return false;
  return date.getTime() >= startOfToday();
}

function categoryForBet(bet: Bet): string {
  return getDisplayBetCategory({ market: bet.market, category: bet.category, event: bet.event });
}

function buildGroups(bets: Bet[], mode: Mode): MatchGroup[] {
  const map = new Map<string, MatchGroup>();
  for (const bet of bets) {
    const event = (bet.event || "Unknown match").trim();
    const category = categoryForBet(bet);
    const key = `${category}::${bet.match_date || "no-date"}::${event.toLowerCase()}`;
    let group = map.get(key);
    if (!group) {
      const fixture = parseFixture(event);
      group = {
        key,
        event,
        category,
        home: fixture?.home ?? null,
        away: fixture?.away ?? null,
        matchDate: bet.match_date ?? null,
        bets: [],
        totalStake: 0,
        netProfit: 0,
        won: 0,
        lost: 0,
        voided: 0,
        settledCount: 0,
      };
      map.set(key, group);
    }
    group.bets.push(bet);
    group.totalStake += Number(bet.stake) || 0;
    if (!group.matchDate && bet.match_date) group.matchDate = bet.match_date;
    if (bet.status === "won") group.won += 1;
    else if (bet.status === "lost") group.lost += 1;
    else if (bet.status === "void") group.voided += 1;
    if (bet.status !== "pending") {
      group.settledCount += 1;
      group.netProfit += Number(bet.profit_loss) || 0;
    }
  }

  const groups = Array.from(map.values());
  groups.sort((a, b) => {
    const aTime = a.matchDate ? new Date(`${a.matchDate}T00:00:00`).getTime() : 0;
    const bTime = b.matchDate ? new Date(`${b.matchDate}T00:00:00`).getTime() : 0;
    return mode === "pending" ? aTime - bTime : bTime - aTime;
  });
  return groups;
}

function Crest({ team, category }: { team: string | null; category: string }) {
  const [errored, setErrored] = useState(false);
  const src = resolveTeamLogoPath(team, category);
  const label = initials(team, category);
  const showImage = Boolean(src) && !errored;
  return (
    <span data-testid="team-crest" className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-slate-800 ring-2 ring-slate-950">
      {showImage ? (
        <Image
          src={src as string}
          alt=""
          width={32}
          height={32}
          className="h-full w-full object-contain"
          onError={() => setErrored(true)}
        />
      ) : (
        <span className="font-mono text-[10px] font-bold text-slate-300">{label}</span>
      )}
    </span>
  );
}

function StatusCell({ bet, mode }: { bet: Bet; mode: Mode }) {
  if (mode === "pending") {
    return (
      <span className="rounded bg-amber-500/20 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wide text-amber-400">
        Pending
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <span className="font-mono text-xs font-semibold">
        <PnL value={bet.profit_loss} status={bet.status} />
      </span>
      <ResultBadge status={bet.status} size="sm" />
    </span>
  );
}

function PickMetric({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <span className={`rounded-lg border border-slate-800 bg-slate-950/45 px-2.5 py-1.5 text-right ${className}`}>
      <span className="block font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-slate-500">{label}</span>
      <span className="block font-mono text-sm font-semibold tabular-nums text-slate-100">{value}</span>
    </span>
  );
}

function PickRow({ bet, mode }: { bet: Bet; mode: Mode }) {
  const href = publicTipPath(bet);
  return (
    <Link href={href} className="block transition-colors hover:bg-slate-800/30 active:bg-slate-800/40">
      <div className="hidden items-center gap-3 px-4 py-3 sm:flex">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center">
          <MarketBadge market={bet.market} category={bet.category} event={bet.event} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-slate-100">{bet.player || bet.selection}</div>
          {bet.player ? <div className="truncate text-xs text-slate-400">{bet.selection}</div> : null}
        </div>
        <PickMetric label="Odds" value={formatOdds(bet.odds)} className="w-20" />
        <PickMetric label="Stake" value={`${formatStake(bet.stake)}u`} className="w-20" />
        <div className="flex w-20 justify-center">
          <BookmakerLogo bookmaker={bet.bookmaker} size="sm" noLink stopPropagationOnClick />
        </div>
        <div className="flex w-32 justify-end">
          <StatusCell bet={bet} mode={mode} />
        </div>
      </div>

      <div className="px-4 py-3 sm:hidden">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center">
            <MarketBadge market={bet.market} category={bet.category} event={bet.event} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-slate-100">{bet.player || bet.selection}</div>
            {bet.player ? <div className="truncate text-xs text-slate-400">{bet.selection}</div> : null}
          </div>
          <StatusCell bet={bet} mode={mode} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 pl-12">
          <PickMetric label="Odds" value={formatOdds(bet.odds)} />
          <PickMetric label="Stake" value={`${formatStake(bet.stake)}u`} />
          <BookmakerLogo bookmaker={bet.bookmaker} size="sm" noLink stopPropagationOnClick />
        </div>
      </div>
    </Link>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function RecordChip({ group }: { group: MatchGroup }) {
  const parts = [
    group.won > 0 ? { label: `${group.won}W`, className: "text-emerald-300" } : null,
    group.lost > 0 ? { label: `${group.lost}L`, className: "text-rose-300" } : null,
    group.voided > 0 ? { label: `${group.voided}V`, className: "text-slate-400" } : null,
  ].filter(Boolean) as Array<{ label: string; className: string }>;

  if (parts.length === 0) return null;

  return (
    <span className="hidden rounded-full border border-slate-700 bg-slate-950/50 px-2.5 py-1 font-mono text-[11px] sm:inline-flex">
      {parts.map((part, index) => (
        <span key={part.label} className={part.className}>
          {index > 0 ? <span className="px-1 text-slate-600">/</span> : null}
          {part.label}
        </span>
      ))}
    </span>
  );
}

function MatchCard({ group, mode, open, onToggle }: { group: MatchGroup; mode: Mode; open: boolean; onToggle: () => void }) {
  const netClass = group.netProfit > 0 ? "text-emerald-400" : group.netProfit < 0 ? "text-rose-400" : "text-slate-400";

  return (
    <div data-testid="player-props-match-group" className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/50">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-800/30"
      >
        <span className="flex shrink-0 -space-x-2">
          <Crest team={group.home} category={group.category} />
          <Crest team={group.away} category={group.category} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold leading-snug text-slate-100 sm:truncate sm:text-base">{group.event}</span>
          <span className="mt-0.5 block text-xs text-slate-500">{formatMatchDate(group.matchDate)}</span>
        </span>
        <span className="flex items-center gap-2 sm:gap-3">
          <span className="rounded-full border border-slate-700 bg-slate-950/50 px-2.5 py-1 font-mono text-[11px] text-slate-300">
            {group.bets.length} {group.bets.length === 1 ? "pick" : "picks"}
          </span>
          {mode === "pending" ? (
            <span className="hidden rounded-full border border-slate-700 bg-slate-950/50 px-2.5 py-1 font-mono text-[11px] text-slate-300 sm:inline">
              {formatStake(group.totalStake)}u stake
            </span>
          ) : (
            <>
              <RecordChip group={group} />
              <span className={`font-mono text-sm font-black tabular-nums ${netClass}`}>{formatNetUnits(group.netProfit)}</span>
            </>
          )}
          <Chevron open={open} />
        </span>
      </button>
      {open ? (
        <div className="divide-y divide-slate-800/70 border-t border-slate-800/70">
          {group.bets.map((bet) => (
            <PickRow key={bet.id} bet={bet} mode={mode} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function PlayerPropsMatchGroups({ bets, mode }: { bets: Bet[]; mode: Mode }) {
  const groups = useMemo(() => buildGroups(bets, mode), [bets, mode]);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});

  const defaultOpen = (group: MatchGroup) => (mode === "pending" ? true : isTodayOrFuture(group.matchDate));
  const isOpen = (group: MatchGroup) => overrides[group.key] ?? defaultOpen(group);

  if (groups.length === 0) return null;

  return (
    <div data-testid="player-props-match-groups" className="space-y-3">
      <p className="text-xs text-slate-500">
        Grouped by fixture for readability. Each pick is still settled individually in the public ledger.
      </p>
      {groups.map((group) => (
        <MatchCard
          key={group.key}
          group={group}
          mode={mode}
          open={isOpen(group)}
          onToggle={() => setOverrides((prev) => ({ ...prev, [group.key]: !isOpen(group) }))}
        />
      ))}
    </div>
  );
}
