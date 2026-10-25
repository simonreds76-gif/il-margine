"use client";

import { useMemo, useState } from "react";
import PropSelectionCard from "@/components/PropSelectionCard";
import { classifyProp } from "@/lib/prop-performance";
import Image from "next/image";
import { smallTeamLogo } from "@/lib/small-team-logo";
import Link from "next/link";
import type { Bet } from "@/lib/supabase";
import { getDisplayBetCategory } from "@/lib/bet-category";
import { formatMatchDate } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";
import { resolveTeamLogoPath } from "@/lib/team-logos";

type Mode = "pending" | "settled";

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
        netProfit: 0,
        won: 0,
        lost: 0,
        voided: 0,
        settledCount: 0,
      };
      map.set(key, group);
    }
    group.bets.push(bet);
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
    <span data-testid="team-crest" title={team ?? undefined} className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-slate-800 ring-2 ring-slate-950">
      {showImage ? (
        <Image
          src={smallTeamLogo(src, 64) as string}
          alt=""
          width={32}
          height={32}
          unoptimized
          className="h-full w-full object-contain"
          onError={() => setErrored(true)}
        />
      ) : (
        <span className="font-mono text-[10px] font-bold text-slate-300">{label}</span>
      )}
    </span>
  );
}

function PickRow({ bet }: { bet: Bet }) {
  return <PropSelectionCard grouped row={bet} market={classifyProp(bet)} href={publicTipPath(bet)} bookmaker={bet.bookmaker} />;
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
        className="flex min-h-14 w-full items-center gap-2 px-3 py-3 text-left transition-colors hover:bg-slate-800/30 focus-visible:outline-2 focus-visible:outline-emerald-300 sm:gap-3 sm:px-4"
      >
        <span className="flex shrink-0 -space-x-2">
          <Crest team={group.home} category={group.category} />
          <Crest team={group.away} category={group.category} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold leading-snug text-slate-100 break-words sm:text-base">{group.event}</span>
          <span className="mt-0.5 block text-xs text-slate-400">{formatMatchDate(group.matchDate)}{group.bets.length > 1 ? ` · ${group.bets.length} picks` : ""}</span>
        </span>
        <span className="flex items-center gap-2 sm:gap-3">
          {mode === "settled" && (
            <>
              <RecordChip group={group} />
              <span className={`font-mono text-sm font-black tabular-nums ${netClass}`}>{formatNetUnits(group.netProfit)}</span>
            </>
          )}
          <Chevron open={open} />
        </span>
      </button>
      <div className="border-t border-slate-800/50 px-4 py-2">
        <Link href={publicTipPath(group.bets[0])} aria-label={`Match tips and results for ${group.event}`} prefetch={false} className="text-xs font-medium text-emerald-300 hover:underline">
          Match tips &amp; results &#8594;
        </Link>
      </div>
      {open ? (
        <div className="grid gap-3 border-t border-slate-800/70 p-3 sm:p-4">
          {group.bets.map((bet) => (
            <PickRow key={bet.id} bet={bet} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

const RESULTS_PAGE_SIZE = 24;

export default function PlayerPropsMatchGroups({ bets, mode }: { bets: Bet[]; mode: Mode }) {
  const groups = useMemo(() => buildGroups(bets, mode), [bets, mode]);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [visibleCount, setVisibleCount] = useState(RESULTS_PAGE_SIZE);
  const visibleGroups = mode === "pending" ? groups : groups.slice(0, visibleCount);

  const defaultOpen = (group: MatchGroup) => (mode === "pending" ? true : group.key === groups[0]?.key || isTodayOrFuture(group.matchDate));
  const isOpen = (group: MatchGroup) => overrides[group.key] ?? defaultOpen(group);

  if (groups.length === 0) return null;

  return (
    <div data-testid="player-props-match-groups" className="space-y-3">
      <div className="grid items-start gap-3 lg:grid-cols-2">
      {visibleGroups.map((group) => (
        <MatchCard
          key={group.key}
          group={group}
          mode={mode}
          open={isOpen(group)}
          onToggle={() => setOverrides((prev) => ({ ...prev, [group.key]: !isOpen(group) }))}
        />
      ))}
      </div>
      {mode === "settled" && groups.length > RESULTS_PAGE_SIZE ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 py-3">
            <p className="text-sm text-slate-400" role="status">
              Showing {visibleGroups.length} of {groups.length} matches
            </p>
            {visibleGroups.length < groups.length ? (
              <button type="button" onClick={() => setVisibleCount((count) => count + RESULTS_PAGE_SIZE)}
                className="rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-5 py-3 text-sm font-semibold text-emerald-200 transition-colors hover:bg-emerald-400/20 focus-visible:outline-2 focus-visible:outline-emerald-300">
                Show {Math.min(RESULTS_PAGE_SIZE, groups.length - visibleGroups.length)} older matches
              </button>
            ) : null}
          </div>
          {/* Native details keeps older match links in the initial HTML, including without JavaScript. */}
          <details className="rounded-xl border border-slate-800 bg-slate-900/30 p-4" data-testid="older-match-links">
            <summary className="cursor-pointer text-sm font-semibold text-emerald-300">Browse older match pages</summary>
            <ul className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              {groups.slice(RESULTS_PAGE_SIZE).map((group) => (
                <li key={group.key}>
                  <Link href={publicTipPath(group.bets[0])} prefetch={false} className="text-slate-300 hover:text-emerald-300 hover:underline">
                    {group.event} <span className="text-xs text-slate-500">· {formatMatchDate(group.matchDate)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        </>
      ) : null}
    </div>
  );
}
