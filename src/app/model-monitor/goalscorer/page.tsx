import Link from "next/link";
import { notFound } from "next/navigation";

import { readPenaltyReviewState } from "@/lib/goalscorer-penalty-review-state";
import { type GoalscorerMonitorSnapshot, readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";

import { PenaltyReviewActions } from "./PenaltyReviewActions";
import {
  EmptyState,
  HeroCard,
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  SectionCard,
  StatCard,
  StatusPill,
  actionTone,
  formatDateLabel,
  formatDateTimeLabel,
  formatOdds,
  formatPct,
  formatUnits,
  statusTone,
  toneClass,
} from "./shared";

export const dynamic = "force-dynamic";

type SnapshotPenaltyRow = GoalscorerMonitorSnapshot["penalty_watchlist"]["rows"][number] & {
  resolutionStatus?: "dismissed" | "done";
  resolutionUpdatedAt?: string;
};

function numericSum(values: Array<number | null | undefined>): number {
  return values.reduce<number>((total, value) => total + (value ?? 0), 0);
}

function renderSourceDetail(snapshot: GoalscorerMonitorSnapshot) {
  const source = snapshot.source_status;
  const parts = [
    source.hot_live_updated_at ? `Hot live ${formatDateTimeLabel(source.hot_live_updated_at)}` : null,
    source.expected_refresh_updated_at ? `Expected refresh ${formatDateTimeLabel(source.expected_refresh_updated_at)}` : null,
    source.settlement_updated_at ? `Settlement ${formatDateTimeLabel(source.settlement_updated_at)}` : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "Source timestamps unavailable";
}

function reviewTone(priority?: string) {
  const normalized = (priority || "").toLowerCase();
  if (normalized === "high") return "bg-rose-500/12 text-rose-200 border-rose-500/25";
  if (normalized === "medium") return "bg-amber-500/12 text-amber-200 border-amber-500/25";
  return "bg-slate-900/70 text-slate-300 border-slate-700/80";
}

function resolutionTone(status?: "dismissed" | "done") {
  if (status === "done") return "bg-emerald-500/12 text-emerald-200 border-emerald-500/25";
  if (status === "dismissed") return "bg-slate-900/70 text-slate-300 border-slate-700/80";
  return "bg-cyan-500/12 text-cyan-200 border-cyan-500/25";
}

function ValueText({ value, formatter, digits, className }: { value?: number | null; formatter: (value?: number | null, digits?: number) => string; digits?: number; className?: string }) {
  return <span className={className}>{formatter(value, digits)}</span>;
}

function PenaltyReviewCard({ row }: { row: SnapshotPenaltyRow }) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-950/35 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            {row.league || "League"} · {row.review_source || "Penalty review"}
          </div>
          <h3 className="mt-2 text-xl font-semibold text-white">{row.actual_taker || "Unknown taker"}</h3>
          <p className="mt-1 text-sm text-slate-300">
            {row.match || `${row.team || "Unknown team"} vs ${row.opponent || "Unknown opponent"}`} · {formatDateLabel(row.date)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {row.review_priority ? <StatusPill label={row.review_priority} tone={reviewTone(row.review_priority)} /> : null}
          {row.review_type ? <StatusPill label={row.review_type.replaceAll("_", " ")} tone="bg-cyan-500/12 text-cyan-200 border-cyan-500/25" /> : null}
          <StatusPill
            label={row.resolutionStatus ? row.resolutionStatus.replaceAll("_", " ") : "active"}
            tone={resolutionTone(row.resolutionStatus)}
          />
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Pre-match primary" value={row.primary_pre_match || "-"} />
        <StatCard label="Pre-match backup" value={row.secondary_pre_match || "-"} />
        <StatCard label="Active pre-match" value={row.active_taker_pre_match || "-"} detail={row.active_slot_pre_match || undefined} />
        <StatCard label="Penalty minute" value={row.minute || "-"} detail={row.event_result || row.event_type || undefined} />
        <StatCard label="Primary at penalty" value={row.primary_on_pitch_at_penalty || "-"} />
        <StatCard label="Active at penalty" value={row.active_on_pitch_at_penalty || "-"} />
        <StatCard label="Actual taker at penalty" value={row.actual_taker_on_pitch_at_penalty || "-"} />
        <StatCard label="Transfer path" value={row.inherited_from_pre_match || "-"} detail={row.transfer_level_pre_match || undefined} />
      </div>

      {row.editorial_note ? <p className="mt-4 text-sm text-slate-400">{row.editorial_note}</p> : null}
      {row.row_id ? <PenaltyReviewActions rowId={row.row_id} resolvedStatus={row.resolutionStatus} /> : null}
      {row.resolutionUpdatedAt ? <p className="mt-3 text-xs text-slate-500">Last updated {formatDateTimeLabel(row.resolutionUpdatedAt)}</p> : null}
    </article>
  );
}

function LiveBetsTable({ rows }: { rows: GoalscorerMonitorSnapshot["live_bets"] }) {
  if (rows.length === 0) {
    return <EmptyState message="No current goalscorer bets are live in the snapshot." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          <tr className="border-b border-slate-800">
            <th className="pb-3 pr-3 font-semibold">Player</th>
            <th className="pb-3 pr-3 font-semibold">Fixture</th>
            <th className="pb-3 pr-3 font-semibold">Lineup</th>
            <th className="pb-3 pr-3 font-semibold">Book</th>
            <th className="pb-3 pr-3 font-semibold">Odds</th>
            <th className="pb-3 pr-3 font-semibold">Fair</th>
            <th className="pb-3 pr-3 font-semibold">Edge</th>
            <th className="pb-3 pr-3 font-semibold">Stake</th>
            <th className="pb-3 font-semibold">Track</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-slate-900/80 align-top text-slate-200">
              <td className="py-3 pr-3">
                <div className="font-semibold text-white">{row.player}</div>
                <div className="text-xs text-slate-500">{row.team} · {row.league_label}</div>
              </td>
              <td className="py-3 pr-3">
                <div>{row.match}</div>
                <div className="text-xs text-slate-500">{formatDateTimeLabel(row.kickoff || row.match_date)}</div>
              </td>
              <td className="py-3 pr-3">
                <div className="font-medium">{row.lineup_short || "-"}</div>
                <div className="text-xs text-slate-500">{row.lineup_label}</div>
              </td>
              <td className="py-3 pr-3">{row.bookmaker || "-"}</td>
              <td className="py-3 pr-3">{formatOdds(row.odds)}</td>
              <td className="py-3 pr-3">{formatOdds(row.fair, 2)}</td>
              <td className={"py-3 pr-3 font-semibold " + toneClass(row.edge_pct)}>{formatPct(row.edge_pct)}</td>
              <td className="py-3 pr-3">{row.stake_label || "-"}</td>
              <td className="py-3">
                <StatusPill label={row.status === "PUBLIC" ? "public" : row.action_label || "shadow"} tone={actionTone(row.action)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecentSettlementsTable({ rows }: { rows: GoalscorerMonitorSnapshot["shadow_summary"]["recent_rows"] }) {
  if (rows.length === 0) {
    return <EmptyState message="No settled shadow rows are available in the snapshot yet." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          <tr className="border-b border-slate-800">
            <th className="pb-3 pr-3 font-semibold">Player</th>
            <th className="pb-3 pr-3 font-semibold">Fixture</th>
            <th className="pb-3 pr-3 font-semibold">Kickoff</th>
            <th className="pb-3 pr-3 font-semibold">Compared</th>
            <th className="pb-3 pr-3 font-semibold">Outcome</th>
            <th className="pb-3 pr-3 font-semibold">Odds</th>
            <th className="pb-3 pr-3 font-semibold">Fair</th>
            <th className="pb-3 pr-3 font-semibold">Edge</th>
            <th className="pb-3 font-semibold">Settled</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-slate-900/80 align-top text-slate-200">
              <td className="py-3 pr-3">
                <div className="font-semibold text-white">{row.player}</div>
                <div className="text-xs text-slate-500">{row.team} · {row.league_key}</div>
              </td>
              <td className="py-3 pr-3">{row.match}</td>
              <td className="py-3 pr-3">{formatDateTimeLabel(row.kickoff || row.date)}</td>
              <td className="py-3 pr-3">{formatDateTimeLabel(row.compared_at)}</td>
              <td className="py-3 pr-3">
                <StatusPill label={row.bet_outcome || "unknown"} tone={statusTone(row.bet_outcome)} />
              </td>
              <td className="py-3 pr-3">{formatOdds(row.best_bookmaker_odds)}</td>
              <td className="py-3 pr-3">{formatOdds(row.model_fair_odds)}</td>
              <td className={"py-3 pr-3 font-semibold " + toneClass(row.ev_pct)}>{formatPct(row.ev_pct)}</td>
              <td className="py-3">{formatDateTimeLabel(row.settled_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function GoalscorerMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [snapshot, penaltyState] = await Promise.all([
    readGoalscorerMonitorSnapshot(),
    readPenaltyReviewState(),
  ]);

  if (!snapshot) {
    return (
      <div className="min-h-screen bg-[#0a0f19] px-6 py-8 text-slate-200">
        <div className="mx-auto max-w-7xl">
          <MonitorNav current="goalscorer" />
          <HeroCard title="Goalscorer Monitor" eyebrow="Snapshot-first monitor">
            The goalscorer monitor snapshot is not available yet. Once the hosted goalscorer workflows publish
            <code className="mx-1 rounded bg-slate-950/60 px-1.5 py-0.5 text-xs">goalscorer-monitor-snapshot.json</code>
            the page will render from that single payload.
          </HeroCard>
        </div>
      </div>
    );
  }

  const publicNow = numericSum(snapshot.league_cards.map((card) => card.public_now));
  const shadowNow = numericSum(snapshot.league_cards.map((card) => card.shadow_now));
  const activePenaltyRows: SnapshotPenaltyRow[] = snapshot.penalty_watchlist.rows.filter((row) => !penaltyState[row.row_id]).map((row) => row);
  const resolvedPenaltyRows: SnapshotPenaltyRow[] = snapshot.penalty_watchlist.rows
    .filter((row) => penaltyState[row.row_id])
    .map((row) => ({
      ...row,
      resolutionStatus: penaltyState[row.row_id]?.status,
      resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
    }));

  const activePenaltyRowsWithState: SnapshotPenaltyRow[] = activePenaltyRows.map((row) => ({
    ...row,
    resolutionStatus: penaltyState[row.row_id]?.status,
    resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
  }));

  return (
    <div className="min-h-screen bg-[#0a0f19] px-6 py-8 text-slate-200">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <MonitorNav current="goalscorer" />

        <HeroCard title="Goalscorer Monitor" eyebrow="Snapshot-first architecture">
          <p>This page now renders from a single monitor snapshot instead of rebuilding joins at request time.</p>
          <p className="mt-2 text-slate-400">Generated {formatDateTimeLabel(snapshot.generated_at)} · {renderSourceDetail(snapshot)}</p>
        </HeroCard>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard label="Live bets" value={String(snapshot.live_bets.length)} />
          <StatCard label="Public now" value={String(publicNow)} detail="Rows surfaced to the public card" />
          <StatCard label="Shadow now" value={String(shadowNow)} detail="Shadow-track rows still open" />
          <StatCard label="Penalty reviews" value={String(activePenaltyRowsWithState.length)} detail={`${resolvedPenaltyRows.length} already resolved`} />
          <StatCard label="Flagged fixtures" value={String(snapshot.fixture_health.flagged_rows.length)} detail={`${snapshot.fixture_health.rows.length} fixtures in snapshot`} />
          <StatCard label="Avg EV" value={formatPct(snapshot.diagnostics.avg_ev_pct)} tone={toneClass(snapshot.diagnostics.avg_ev_pct)} />
        </section>

        <SectionCard title="League Scoreboard" subtitle="Page-ready league KPIs from the snapshot builder.">
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {snapshot.league_cards.map((card) => (
              <article key={card.key} className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{card.label}</h3>
                    <p className="mt-1 text-sm text-slate-400">Updated {formatDateTimeLabel(card.updated_at)}</p>
                  </div>
                  <StatusPill label={card.status_label} tone={statusTone(card.status_key)} />
                </div>
                {card.status_detail ? <p className="mt-3 text-sm text-slate-400">{card.status_detail}</p> : null}
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <StatCard label="Live rows" value={String(card.live_rows)} />
                  <StatCard label="Public / shadow" value={`${card.public_now} / ${card.shadow_now}`} />
                  <StatCard label="Fixture health" value={`${card.clean_fixtures} clean`} detail={`${card.degraded_fixtures} degraded · ${card.quarantined_fixtures} quarantined`} />
                  <StatCard label="Shadow open" value={String(card.shadow_record.open)} detail={`${card.shadow_record.settled} settled`} />
                  <StatCard label="Shadow ROI" value={formatPct(card.shadow_record.roi)} tone={toneClass(card.shadow_record.roi)} detail={formatUnits(card.shadow_record.pnl_units, 3)} />
                  <StatCard label="Public ROI" value={formatPct(card.public_record.roi)} tone={toneClass(card.public_record.roi)} detail={formatUnits(card.public_record.pnl_units, 3)} />
                </div>
              </article>
            ))}
          </div>
        </SectionCard>

        <SectionCard title={`Live Bets (${snapshot.live_bets.length})`} subtitle="Only snapshot-backed public and shadow rows are rendered here.">
          <LiveBetsTable rows={snapshot.live_bets} />
        </SectionCard>

        <SectionCard
          title={`Fixture Diagnostics (${snapshot.fixture_health.flagged_rows.length})`}
          subtitle={`${snapshot.fixture_health.clean_count} clean · ${snapshot.fixture_health.degraded_count} degraded · ${snapshot.fixture_health.quarantined_count} quarantined`}
        >
          {snapshot.fixture_health.flagged_rows.length === 0 ? (
            <EmptyState message="No degraded or quarantined fixtures are flagged in the current snapshot." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-left text-sm">
                <thead className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  <tr className="border-b border-slate-800">
                    <th className="pb-3 pr-3 font-semibold">Fixture</th>
                    <th className="pb-3 pr-3 font-semibold">League</th>
                    <th className="pb-3 pr-3 font-semibold">Lineup input</th>
                    <th className="pb-3 pr-3 font-semibold">Trust</th>
                    <th className="pb-3 pr-3 font-semibold">Flags</th>
                    <th className="pb-3 font-semibold">Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.fixture_health.flagged_rows.map((row) => (
                    <tr key={row.key} className="border-b border-slate-900/80 align-top text-slate-200">
                      <td className="py-3 pr-3">
                        <div className="font-semibold text-white">{row.home_team} vs {row.away_team}</div>
                        <div className="text-xs text-slate-500">{formatDateLabel(row.match_date)} · {row.bookmaker || "-"}</div>
                      </td>
                      <td className="py-3 pr-3">{row.league_label}</td>
                      <td className="py-3 pr-3">{row.lineup_input || "-"}</td>
                      <td className="py-3 pr-3"><StatusPill label={row.trust_tier || "unknown"} tone={statusTone(row.trust_tier)} /></td>
                      <td className="py-3 pr-3 text-xs text-slate-400">{row.corruption_flags?.length ? row.corruption_flags.join(", ") : "-"}</td>
                      <td className="py-3 text-sm text-slate-400">{row.summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard
          title={`Penalty Watchlist (${activePenaltyRowsWithState.length})`}
          subtitle="Penalty review rows are already enriched in the snapshot, including on-pitch-at-penalty answers."
        >
          <div className="flex flex-col gap-4">
            {activePenaltyRowsWithState.length === 0 ? (
              <EmptyState message="No active penalty review rows remain in the current snapshot." />
            ) : (
              activePenaltyRowsWithState.map((row) => <PenaltyReviewCard key={row.row_id} row={row} />)
            )}
          </div>
          <details className="mt-6 rounded-xl border border-slate-800 bg-slate-950/25 px-4 py-3">
            <summary className="cursor-pointer text-sm font-semibold text-slate-300">Resolved rows ({resolvedPenaltyRows.length})</summary>
            <div className="mt-4 flex flex-col gap-4">
              {resolvedPenaltyRows.length === 0 ? (
                <EmptyState message="No penalty review rows have been resolved yet." />
              ) : (
                resolvedPenaltyRows.map((row) => <PenaltyReviewCard key={row.row_id} row={row} />)
              )}
            </div>
          </details>
        </SectionCard>

        <SectionCard
          title={`Recent Shadow Settlements (${snapshot.shadow_summary.recent_rows.length})`}
          subtitle={`${snapshot.shadow_summary.settled_today.length} settled today · ${snapshot.shadow_summary.settled_yesterday.length} settled yesterday`}
        >
          <RecentSettlementsTable rows={snapshot.shadow_summary.recent_rows.slice(0, 25)} />
        </SectionCard>

        <SectionCard title="Related Tools" subtitle="The snapshot also feeds the dedicated lineups page and penalty API.">
          <div className="flex flex-wrap gap-3">
            <Link href="/model-monitor/goalscorer/lineups" className="inline-flex items-center rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1.5 text-sm text-cyan-100 transition-colors hover:border-cyan-400/40">
              Open lineups view
            </Link>
            <Link href="/api/model-monitor/goalscorer/penalty-watchlist" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-slate-500/80 hover:text-slate-100">
              Penalty watchlist API
            </Link>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

