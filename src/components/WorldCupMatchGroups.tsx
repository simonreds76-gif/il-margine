"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import type { Bet } from "@/lib/supabase";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import PnL from "@/components/PnL";
import ResultBadge from "@/components/ResultBadge";
import { formatMatchDate, formatOdds, formatStake } from "@/lib/format";
import { slugifyTip } from "@/lib/slugify";

type Mode = "pending" | "settled";

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
};

function normalizeTeamKey(value: string): string {
  const key = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-");
  return TEAM_LOGO_ALIASES[key] ?? key;
}

function teamCrestImageUrl(team: string): string {
  return `/team-logos/world-cup/${normalizeTeamKey(team)}.png`;
}

function initials(team: string): string {
  const parts = team
    .replace(/[.'-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "WC";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

type MatchGroup = {
  key: string;
  event: string;
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
  const parts = event.split(/\s+(?:vs?\.?|v|@|-)\s+/i);
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

function buildGroups(bets: Bet[], mode: Mode): MatchGroup[] {
  const map = new Map<string, MatchGroup>();
  for (const bet of bets) {
    const event = (bet.event || "Unknown match").trim();
    const key = `${bet.match_date || "no-date"}::${event.toLowerCase()}`;
    let group = map.get(key);
    if (!group) {
      const fixture = parseFixture(event);
      group = {
        key,
        event,
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
    // Pending: soonest first. Settled: most recent first.
    return mode === "pending" ? aTime - bTime : bTime - aTime;
  });
  return groups;
}

function Crest({ team }: { team: string | null }) {
  const [errored, setErrored] = useState(false);
  const label = team ? initials(team) : "WC";
  const showImage = Boolean(team) && !errored;
  return (
    <span className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-slate-800 ring-2 ring-slate-950">
      {showImage ? (
        <Image
          src={teamCrestImageUrl(team as string)}
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

function PickRow({ bet, mode }: { bet: Bet; mode: Mode }) {
  const href = `/tips/${slugifyTip(bet.event, bet.id)}`;
  return (
    <Link href={href} className="block transition-colors hover:bg-slate-800/30 active:bg-slate-800/40">
      {/* Desktop ledger row */}
      <div className="hidden items-center gap-3 px-4 py-3 sm:flex">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center">
          <MarketBadge market={bet.market} category={bet.category} event={bet.event} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-slate-100">{bet.player || bet.selection}</div>
          {bet.player ? <div className="truncate text-xs text-slate-400">{bet.selection}</div> : null}
        </div>
        <div className="w-16 text-right font-mono text-sm text-slate-200">{formatOdds(bet.odds)}</div>
        <div className="w-16 text-right font-mono text-sm text-slate-300">{formatStake(bet.stake)}u</div>
        <div className="flex w-20 justify-center">
          <BookmakerLogo bookmaker={bet.bookmaker} size="sm" noLink stopPropagationOnClick />
        </div>
        <div className="flex w-32 justify-end">
          <StatusCell bet={bet} mode={mode} />
        </div>
      </div>

      {/* Mobile stacked row */}
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
        <div className="mt-2 flex items-center gap-4 pl-12 font-mono text-xs text-slate-400">
          <span>{formatOdds(bet.odds)}</span>
          <span>{formatStake(bet.stake)}u</span>
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

function MatchCard({ group, mode, open, onToggle }: { group: MatchGroup; mode: Mode; open: boolean; onToggle: () => void }) {
  const recordParts = [
    group.won > 0 ? `${group.won}W` : null,
    group.lost > 0 ? `${group.lost}L` : null,
    group.voided > 0 ? `${group.voided}V` : null,
  ].filter(Boolean);
  const netClass = group.netProfit > 0 ? "text-emerald-400" : group.netProfit < 0 ? "text-rose-400" : "text-slate-400";

  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/50">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-800/30"
      >
        <span className="flex shrink-0 -space-x-2">
          <Crest team={group.home} />
          <Crest team={group.away} />
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
              {recordParts.length > 0 ? (
                <span className="hidden rounded-full border border-slate-700 bg-slate-950/50 px-2.5 py-1 font-mono text-[11px] text-slate-400 sm:inline">
                  {recordParts.join(" / ")}
                </span>
              ) : null}
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

export default function WorldCupMatchGroups({ bets, mode }: { bets: Bet[]; mode: Mode }) {
  const groups = useMemo(() => buildGroups(bets, mode), [bets, mode]);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});

  const defaultOpen = (group: MatchGroup) => (mode === "pending" ? true : isTodayOrFuture(group.matchDate));
  const isOpen = (group: MatchGroup) => overrides[group.key] ?? defaultOpen(group);

  if (groups.length === 0) return null;

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        Grouped by match for readability. Each pick is still settled individually in the public ledger.
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

