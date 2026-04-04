"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  LEAGUE_SOURCES,
  type LeagueKey,
  type LeagueSource,
  type PublicRow,
  bookmakerLogoPath,
  formatDateTime,
  formatOdds,
  formatPct,
  formatPublishedLabel,
  formatResultDate,
  formatUnits,
  getContextSignals,
  getLeagueBadgeClass,
  getLeagueSource,
  getPenaltyTakersHref,
  getPnlClass,
  getStakeCopy,
  getStakeTone,
  kickoffMeta,
  lineupBadgeMeta,
  marketProbability,
} from "./shared";

type FilterKey = "all" | LeagueKey;

function LeagueLogo({
  league,
  variant = "tab",
}: {
  league: LeagueSource;
  variant?: "tab" | "card" | "row";
}) {
  const wrapperClass =
    variant === "card"
      ? "flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-300/70 bg-gradient-to-b from-white to-slate-100"
      : variant === "row"
        ? "flex h-6 w-6 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-300/70 bg-gradient-to-b from-white to-slate-100"
        : "flex h-5 w-5 shrink-0 items-center justify-center overflow-hidden rounded-md border border-slate-300/70 bg-gradient-to-b from-white to-slate-100";

  const size = variant === "card" ? 24 : variant === "row" ? 16 : 14;

  return (
    <span className={wrapperClass}>
      <Image src={league.logoPath} alt={`${league.label} logo`} width={size} height={size} className="object-contain" loading="lazy" />
    </span>
  );
}

function BookmakerPill({ bookmaker }: { bookmaker: string }) {
  const logoPath = bookmakerLogoPath(bookmaker);
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-neutral-200">
      {logoPath ? (
        <Image src={logoPath} alt={bookmaker} width={16} height={16} className="h-4 w-4 rounded-sm object-contain" loading="lazy" />
      ) : (
        <span className="flex h-4 w-4 items-center justify-center rounded-sm bg-white/10 text-[10px] uppercase text-neutral-300">
          {(bookmaker || "m").slice(0, 1)}
        </span>
      )}
      <span>{bookmaker || "market"}</span>
    </span>
  );
}

function getLiveSignals(rows: PublicRow[]): PublicRow[] {
  return rows
    .filter((row) => {
      if (row.settled) return false;
      const kickoff = Date.parse(row.kickoff || row.date);
      if (!Number.isFinite(kickoff)) return true;
      const graceWindowMs = 15 * 60 * 1000;
      return kickoff > Date.now() - graceWindowMs;
    })
    .sort((left, right) => {
      const leftKickoff = Date.parse(left.kickoff || left.date);
      const rightKickoff = Date.parse(right.kickoff || right.date);
      if (Number.isFinite(leftKickoff) && Number.isFinite(rightKickoff) && leftKickoff !== rightKickoff) {
        return leftKickoff - rightKickoff;
      }
      return right.ev - left.ev;
    });
}

function getSettledPublished(rows: PublicRow[]): PublicRow[] {
  return rows
    .filter((row) => row.settled && row.betOutcome.toLowerCase() !== "void")
    .sort((left, right) => {
      const leftTime = Date.parse(left.settledAt || left.kickoff || left.date);
      const rightTime = Date.parse(right.settledAt || right.kickoff || right.date);
      return rightTime - leftTime;
    });
}

function getMetrics(rows: PublicRow[]) {
  const settledCount = rows.length;
  const wins = rows.filter((row) => row.betOutcome.toLowerCase() === "won").length;
  const losses = rows.filter((row) => row.betOutcome.toLowerCase() === "lost").length;
  const stakedUnits = rows.reduce((sum, row) => sum + (row.stakeUnits > 0 ? row.stakeUnits : 1), 0);
  const pnlUnits = rows.reduce((sum, row) => sum + row.pnlUnits, 0);
  return {
    settledCount,
    wins,
    losses,
    stakedUnits,
    pnlUnits,
    roi: stakedUnits > 0 ? (pnlUnits / stakedUnits) * 100 : 0,
  };
}

function LivePickCard({ row, todayIso }: { row: PublicRow; todayIso: string }) {
  const kickoff = kickoffMeta(row.kickoff || row.date, todayIso);
  const lineupBadge = lineupBadgeMeta(row.lineupState);
  const league = getLeagueSource(row.leagueKey);
  const fairProb = row.modelProb > 0 ? row.modelProb * 100 : marketProbability(row.fairOdds);
  const marketProb = marketProbability(row.bestOdds);
  const contextSignals = getContextSignals(row);

  return (
    <article className="overflow-hidden rounded-[24px] border border-white/10 bg-[#121417] shadow-[0_12px_40px_rgba(0,0,0,0.22)]">
      <div className="border-b border-white/10 px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-sm text-neutral-300">
              {league ? <LeagueLogo league={league} variant="row" /> : null}
              <span>{row.leagueLabel}</span>
              <span className="text-neutral-600">·</span>
              <span className="truncate text-white">{row.match}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${kickoff.badgeClass}`}>
              {kickoff.badge === "Live" ? <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" /> : null}
              {kickoff.badge}
            </span>
            <span className={`text-sm font-semibold ${kickoff.tone}`}>{kickoff.label}</span>
          </div>
        </div>
      </div>

      <div className="px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="text-2xl font-semibold tracking-tight text-white">
                {row.player} <span className="text-lg font-normal text-neutral-400">to score anytime</span>
              </h3>
              <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${getStakeTone(row)}`}>
                {row.stakeLabel || `${row.stakeUnits.toFixed(2)}u`}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-neutral-400">
              <span>{row.team}</span>
              <span className="text-neutral-600">vs</span>
              <span>{row.opponent}</span>
              {row.position ? (
                <>
                  <span className="text-neutral-600">·</span>
                  <span>{row.position}</span>
                </>
              ) : null}
            </div>
            <div className="mt-2 text-sm text-neutral-500">{getStakeCopy(row)}</div>
          </div>

          <div className="text-right">
            <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-500">Value edge</div>
            <div className="mt-1 text-3xl font-semibold tracking-tight text-emerald-300">{formatPct(row.ev * 100, 1)}</div>
            <div className="mt-2 text-xs text-neutral-500">{formatPublishedLabel(row.comparedAt)}</div>
          </div>
        </div>

        <div className="mt-5 grid gap-3 rounded-2xl border border-white/10 bg-black/20 px-4 py-4 sm:grid-cols-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Model</div>
            <div className="mt-1 text-lg font-semibold text-white">{fairProb != null ? `${fairProb.toFixed(0)}%` : "n/a"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Market</div>
            <div className="mt-1 text-lg font-semibold text-white">{marketProb != null ? `${marketProb.toFixed(0)}%` : "n/a"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Fair / Book</div>
            <div className="mt-1 text-lg font-semibold text-white">{formatOdds(row.fairOdds)} / {formatOdds(row.bestOdds)}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Price</div>
            <div className="mt-1 flex items-center justify-start sm:justify-end">
              <BookmakerPill bookmaker={row.bestBookmaker} />
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${lineupBadge.className}`}>
            {lineupBadge.label}
          </span>
          {row.penaltyDependent ? (
            <span className="inline-flex rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-200">
              Set piece component{row.penaltyDependencyShare > 0 ? ` ${Math.round(row.penaltyDependencyShare * 100)}%` : ""}
            </span>
          ) : null}
          {row.penaltyTransfer ? (
            <span className="inline-flex rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
              Penalty reassigned
            </span>
          ) : null}
          {row.positionUpgrade ? (
            <span className="inline-flex rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
              Role upgrade
            </span>
          ) : null}
          {contextSignals.map((signal) => (
            <span key={signal} className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-300">
              {signal}
            </span>
          ))}
          {(row.penaltyDependent || row.penaltyTransfer) ? (
            <Link href={getPenaltyTakersHref(row)} className="text-xs text-emerald-300 transition-colors hover:text-emerald-200">
              Penalty order
            </Link>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function RecordTable({ rows }: { rows: PublicRow[] }) {
  return (
    <>
      <div className="hidden overflow-x-auto rounded-[24px] border border-white/10 bg-[#121417] md:block">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 bg-white/[0.03] text-[11px] uppercase tracking-[0.18em] text-neutral-500">
            <tr>
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">League</th>
              <th className="px-4 py-3 font-medium">Player</th>
              <th className="px-4 py-3 font-medium">Match</th>
              <th className="px-4 py-3 font-medium">Odds</th>
              <th className="px-4 py-3 font-medium">Edge</th>
              <th className="px-4 py-3 font-medium">Stake</th>
              <th className="px-4 py-3 font-medium">Result</th>
              <th className="px-4 py-3 font-medium">P/L</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}-row`} className="border-b border-white/5 last:border-b-0">
                <td className="px-4 py-3 text-neutral-300">{formatResultDate(row.date)}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {getLeagueSource(row.leagueKey) ? <LeagueLogo league={getLeagueSource(row.leagueKey)!} variant="row" /> : null}
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${getLeagueBadgeClass(row.leagueKey)}`}>
                      {row.leagueShort}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 font-medium text-white">{row.player}</td>
                <td className="px-4 py-3 text-neutral-300">{row.match}</td>
                <td className="px-4 py-3 text-white">{formatOdds(row.bestOdds)}</td>
                <td className="px-4 py-3 text-emerald-300">{formatPct(row.ev * 100, 1)}</td>
                <td className="px-4 py-3 text-neutral-300">{row.stakeLabel || `${row.stakeUnits.toFixed(2)}u`}</td>
                <td className={`px-4 py-3 font-semibold ${row.betOutcome.toLowerCase() === "won" ? "text-emerald-300" : "text-rose-300"}`}>
                  {row.betOutcome.toUpperCase()}
                </td>
                <td className={`px-4 py-3 font-semibold ${getPnlClass(row.pnlUnits)}`}>{formatUnits(row.pnlUnits)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-3 md:hidden">
        {rows.map((row) => (
          <article key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}-mobile`} className="rounded-2xl border border-white/10 bg-[#121417] px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="text-sm text-neutral-400">
                {formatResultDate(row.date)} · {row.leagueShort}
              </div>
              <div className={`text-sm font-semibold ${row.betOutcome.toLowerCase() === "won" ? "text-emerald-300" : "text-rose-300"}`}>
                {row.betOutcome.toUpperCase()} {formatUnits(row.pnlUnits)}
              </div>
            </div>
            <div className="mt-2 text-base font-semibold text-white">{row.player} to score</div>
            <div className="mt-1 text-sm text-neutral-400">{row.match}</div>
            <div className="mt-2 text-sm text-neutral-300">
              {formatOdds(row.bestOdds)} · {formatPct(row.ev * 100, 1)} · {row.stakeLabel || `${row.stakeUnits.toFixed(2)}u`}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

export default function PublicGoalscorerBoard({
  rows,
  snapshotGeneratedAt,
  todayIso,
}: {
  rows: PublicRow[];
  snapshotGeneratedAt: string | null;
  todayIso: string;
}) {
  const [selectedLeague, setSelectedLeague] = useState<FilterKey>("all");

  const liveSignals = useMemo(() => getLiveSignals(rows), [rows]);
  const settledSignals = useMemo(() => getSettledPublished(rows), [rows]);

  const leagueLiveCounts = useMemo(
    () =>
      LEAGUE_SOURCES.map((league) => ({
        ...league,
        live: liveSignals.filter((row) => row.leagueKey === league.key).length,
        settled: settledSignals.filter((row) => row.leagueKey === league.key).length,
      })),
    [liveSignals, settledSignals],
  );

  const filteredLiveSignals = useMemo(
    () => (selectedLeague === "all" ? liveSignals : liveSignals.filter((row) => row.leagueKey === selectedLeague)),
    [liveSignals, selectedLeague],
  );
  const filteredSettledSignals = useMemo(
    () => (selectedLeague === "all" ? settledSignals : settledSignals.filter((row) => row.leagueKey === selectedLeague)),
    [settledSignals, selectedLeague],
  );

  const upNextRows = filteredLiveSignals.filter((row) => {
    const meta = kickoffMeta(row.kickoff || row.date, todayIso);
    return meta.minutesUntil != null && meta.minutesUntil <= 60;
  });
  const remainingRows = filteredLiveSignals.filter((row) => !upNextRows.includes(row));
  const metrics = getMetrics(filteredSettledSignals);
  const selectedLeagueLabel =
    selectedLeague === "all" ? "All leagues" : LEAGUE_SOURCES.find((league) => league.key === selectedLeague)?.label ?? "Selected league";

  return (
    <>
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-neutral-400">
        <span className="text-neutral-200">{selectedLeagueLabel}</span>
        <span className="mx-2 text-neutral-600">·</span>
        <span>{filteredLiveSignals.length} live</span>
        <span className="mx-2 text-neutral-600">·</span>
        <span>{filteredSettledSignals.length} settled</span>
        <span className="mx-2 text-neutral-600">·</span>
        <span>Snapshot {formatDateTime(snapshotGeneratedAt)}</span>
      </div>

      <div className="mt-6 overflow-x-auto border-b border-white/10">
        <div className="flex min-w-max gap-2">
          <button
            type="button"
            onClick={() => setSelectedLeague("all")}
            className={`border-b-2 px-2 py-3 text-sm font-medium transition-colors ${selectedLeague === "all" ? "border-emerald-400 text-white" : "border-transparent text-neutral-400 hover:text-neutral-200"}`}
          >
            All
            <span className="ml-2 text-neutral-500">{liveSignals.length}</span>
          </button>
          {leagueLiveCounts.map((league) => (
            <button
              key={league.key}
              type="button"
              onClick={() => setSelectedLeague(league.key)}
              className={`inline-flex items-center gap-2 border-b-2 px-2 py-3 text-sm font-medium transition-colors ${selectedLeague === league.key ? "border-emerald-400 text-white" : "border-transparent text-neutral-400 hover:text-neutral-200"}`}
            >
              <LeagueLogo league={league} />
              <span>{league.label}</span>
              {league.live > 0 ? <span className="text-neutral-500">{league.live}</span> : null}
            </button>
          ))}
        </div>
      </div>

      <section className="mt-8 space-y-8">
        {upNextRows.length > 0 ? (
          <div>
            <div className="mb-4 flex items-center gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-200">Up next</h2>
              <span className="text-sm text-neutral-500">Kickoff inside 60 minutes or live inside the grace window.</span>
            </div>
            <div className="space-y-4">
              {upNextRows.map((row) => (
                <LivePickCard key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}-soon`} row={row} todayIso={todayIso} />
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-200">Live board</h2>
              <p className="mt-1 text-sm text-neutral-500">Filtered by league, sorted by kickoff, with the strongest context left visible.</p>
            </div>
          </div>

          {filteredLiveSignals.length === 0 ? (
            <div className="rounded-[24px] border border-white/10 bg-[#121417] px-5 py-6 text-sm leading-7 text-neutral-400">
              No live public picks in this view right now. Settled history stays available below.
            </div>
          ) : remainingRows.length === 0 ? (
            <div className="rounded-[24px] border border-white/10 bg-[#121417] px-5 py-6 text-sm leading-7 text-neutral-400">
              All current picks are already in the up-next block above.
            </div>
          ) : (
            <div className="space-y-4">
              {remainingRows.map((row) => (
                <LivePickCard key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}-live`} row={row} todayIso={todayIso} />
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="mt-12">
        <div className="mb-4">
          <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-200">Published record</h2>
          <p className="mt-2 text-sm text-neutral-400">
            W{metrics.wins} · L{metrics.losses} · {formatPct(metrics.roi, 1)} ROI · {formatUnits(metrics.pnlUnits)} on {metrics.stakedUnits.toFixed(2)}u staked
          </p>
        </div>

        {filteredSettledSignals.length === 0 ? (
          <div className="rounded-[24px] border border-white/10 bg-[#121417] px-5 py-6 text-sm leading-7 text-neutral-400">
            No settled public picks in this view yet.
          </div>
        ) : (
          <RecordTable rows={filteredSettledSignals.slice(0, 30)} />
        )}
      </section>
    </>
  );
}
